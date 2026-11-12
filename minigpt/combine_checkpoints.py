"""Mesure une moyenne de distributions et, en option, une moyenne de poids."""
import argparse
import hashlib
import math
from collections import Counter
from pathlib import Path

import torch
import torch.nn.functional as F

from minigpt.bigram import load_utf8
from minigpt.bpe import BPETokenizer
from minigpt.finetune import restore_model, write_json
from minigpt.model import bits_per_byte, evaluate_bpb
from scripts.audit_chat_data import shingles


@torch.inference_mode()
def target_log_probs(model, ids):
    """Calcule les probabilités des mêmes cibles que l'évaluation de référence."""
    model.eval()
    size = model.cfg.block_size
    usable = (ids.numel() - 1) // size * size
    inputs = ids[:usable].view(-1, size)
    targets = ids[1:usable + 1].view(-1, size)
    chunks = []
    # Grouper les fenêtres change le débit, pas la longueur du contexte.
    for x, y in zip(inputs.split(32), targets.split(32), strict=True):
        if x.numel():
            logits, _ = model(x)
            chunks.append(F.log_softmax(logits, -1).gather(-1, y.unsqueeze(-1)).flatten())
    if usable + 1 < ids.numel():
        logits, _ = model(ids[usable:-1].unsqueeze(0))
        y = ids[usable + 1:].view(1, -1, 1)
        chunks.append(F.log_softmax(logits, -1).gather(-1, y).flatten())
    return torch.cat(chunks).double()


def ngram_probabilities(train, validation, size, vocab_size, prior=12, strength=10):
    """Calcule un appoint normalisé de fréquences sur le seul train officiel."""
    orders = range(1, 6)
    occurrences = {order: Counter() for order in orders}
    totals = {order: Counter() for order in orders}
    for order in orders:
        # Un préfixe sans token suivant ne contribue pas au dénominateur.
        for i in range(order, len(train)):
            context = tuple(train[i - order:i])
            occurrences[order][context + (train[i],)] += 1
            totals[order][context] += 1
    unigrams = Counter(train)
    denominator = len(train) + vocab_size
    probabilities, confidences = [], []
    for i in range(1, len(validation)):
        target = validation[i]
        probability = (unigrams[target] + 1) / denominator
        support = 0
        # La partie statistique reçoit exactement le contexte causal du mini-GPT.
        for order in range(1, min(5, (i - 1) % size + 1) + 1):
            context = tuple(validation[i - order:i])
            count = totals[order][context]
            if count:
                observed = occurrences[order][context + (target,)]
                probability = (observed + prior * probability) / (count + prior)
                if order >= 2:
                    support = count
        probabilities.append(probability)
        confidences.append(support / (support + strength))
    return torch.tensor(probabilities, dtype=torch.float64), torch.tensor(confidences, dtype=torch.float64)


def main():
    """Archive les scores, la provenance des poids et le checkpoint moyen demandé."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoints', nargs='+', type=Path, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True)
    parser.add_argument('--validation', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--save-average', action='store_true')
    parser.add_argument('--ngram-train', type=Path)
    parser.add_argument('--ngram-extra', type=Path)
    parser.add_argument('--ngram-fraction', type=float, default=0.5)
    parser.add_argument('--ngram-prior', type=float, default=12)
    parser.add_argument('--ngram-strength', type=float, default=10)
    args = parser.parse_args()
    if not 0 <= args.ngram_fraction <= 1 or min(args.ngram_prior, args.ngram_strength) <= 0:
        parser.error('Fraction entre 0 et 1 ; lissage et seuil de confiance positifs.')
    if args.ngram_extra and not args.ngram_train:
        parser.error('Le supplément de fréquences requiert le train officiel.')
    torch.set_num_threads(2)
    validation = load_utf8(args.validation)
    digest = hashlib.sha256(validation).hexdigest()
    tokenizer = BPETokenizer.load(args.tokenizer)
    text = validation.decode('utf8')
    ids = torch.tensor(tokenizer.encode(text))
    if ids.numel() < 2:
        parser.error('La validation doit contenir au moins deux tokens.')
    states = [torch.load(p, map_location='cpu', weights_only=True) for p in args.checkpoints]
    ref = states[0]
    shape = {k: v for k, v in ref['config'].items() if k != 'dropout'}
    for state in states:
        config = {k: v for k, v in state['config'].items() if k != 'dropout'}
        if state['val_sha256'] != digest or config != shape or config['vocab_size'] != len(tokenizer.vocab):
            parser.error('Les checkpoints doivent partager la validation, le vocabulaire et l’architecture.')
    args.out.mkdir(parents=True, exist_ok=False)
    predictions = [target_log_probs(restore_model(state), ids) for state in states]
    # Le mélange est uniforme dans l'espace des probabilités, pas des logits.
    logp = torch.logsumexp(torch.stack(predictions), dim=0) - math.log(len(states))
    result = dict(bpb_ensemble=bits_per_byte(-logp.sum().item(), text),
                  validation_sha256=digest,
                  tokenizer_sha256=hashlib.sha256(args.tokenizer.read_bytes()).hexdigest(),
                  checkpoints=[dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                    bpb=bits_per_byte(-pred.sum().item(), text))
                               for path, pred in zip(args.checkpoints, predictions, strict=True)])
    if args.ngram_train:
        raw = load_utf8(args.ngram_train)
        train_digest = hashlib.sha256(raw).hexdigest()
        if train_digest == digest or any(state['train_sha256'] != train_digest for state in states):
            parser.error('L’appoint doit apprendre uniquement sur le train officiel des checkpoints.')
        train_text = raw.decode('utf8')
        extra_digest = None
        if args.ngram_extra:
            # Le supplément est contrôlé avant de construire les tables de fréquences.
            extra = load_utf8(args.ngram_extra)
            extra_text = extra.decode('utf8')
            if shingles(extra_text) & shingles(text):
                parser.error('Le supplément et la validation partagent une séquence de 13 mots.')
            extra_digest = hashlib.sha256(extra).hexdigest()
            train_text += '\n\n' + extra_text
        train = tokenizer.encode(train_text)
        ngram, confidence = ngram_probabilities(train, ids.tolist(), shape['block_size'], shape['vocab_size'],
                                                 args.ngram_prior, args.ngram_strength)
        alpha = args.ngram_fraction * confidence
        result['ngram'] = dict(fraction=args.ngram_fraction, prior=args.ngram_prior, strength=args.ngram_strength,
                               train_sha256=train_digest, extra_sha256=extra_digest,
                               bpb=bits_per_byte(-(logp.exp() * (1 - alpha) + ngram * alpha).log().sum().item(), text))
    if args.save_average:
        # Les poids partagent la même initialisation dans les essais Molière.
        weights = {name: torch.stack([state['model'][name] for state in states]).mean(0)
                   for name in ref['model']}
        saved = {name: ref[name] for name in ('config', 'train_sha256', 'val_sha256')}
        saved.update(model=weights, average=result['checkpoints'])
        saved['val_bpb'] = evaluate_bpb(restore_model(saved), ids.tolist(), text)
        result['bpb_average'] = saved['val_bpb']
        torch.save(saved, args.out / 'average.pt')
    write_json(args.out / 'measures.json', result)
    print(result, flush=True)


if __name__ == '__main__':
    main()
