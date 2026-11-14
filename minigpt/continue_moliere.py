"""Poursuit la langue de Molière avec un taux réglable et des paliers conservés."""
import argparse
import hashlib
import math
import time
from pathlib import Path

import torch

from minigpt.bigram import load_utf8
from minigpt.bpe import BPETokenizer
from minigpt.finetune import restore_model, write_json
from minigpt.model import evaluate_bpb
from minigpt.train import sample_batch, train_step
from scripts.audit_chat_data import shingles


def main():
    """Entraîne sur le seul train officiel et mesure le BPB avec le protocole historique."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint', 'tokenizer', 'corpus', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--steps', type=int, default=6000)
    parser.add_argument('--every', type=int, default=500)
    parser.add_argument('--lr', type=float, default=0.00025)
    parser.add_argument('--extra', type=Path)
    parser.add_argument('--extra-rate', type=float, default=0.25)
    parser.add_argument('--dropout', type=float)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if min(args.steps, args.every, args.threads) < 1 or args.lr <= 0 or (args.dropout is not None and not 0 <= args.dropout < 1):
        parser.error('Les pas, la fréquence, le nombre de threads et le taux doivent être positifs.')
    torch.set_num_threads(args.threads)
    torch.manual_seed(813)
    generator = torch.Generator().manual_seed(813)
    saved = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    # Le dropout ne modifie aucun poids ni la fonction d'évaluation.
    if args.dropout is not None:
        saved['config'] = {**saved['config'], 'dropout': args.dropout}
    model = restore_model(saved)
    tokenizer = BPETokenizer.load(args.tokenizer)
    texts = {}
    # La validation ne participe jamais aux gradients ; les empreintes vérifient les deux entrées.
    for split in ('train', 'val'):
        raw = load_utf8(args.corpus / f'moliere_{split}.txt')
        if hashlib.sha256(raw).hexdigest() != saved[f'{split}_sha256']:
            raise ValueError(f'Corpus différent de la référence : {split}')
        texts[split] = raw.decode('utf-8')
    ids = torch.tensor(tokenizer.encode(texts['train']), dtype=torch.long)
    extra_ids, extra_count, extra_sha = None, 0, None
    if args.extra:
        extra_count = round(32 * args.extra_rate)
        if not 1 <= extra_count < 32:
            parser.error('Le rappel supplémentaire doit occuper entre 1 et 31 fenêtres par batch.')
        extra_raw = load_utf8(args.extra)
        extra_text = extra_raw.decode('utf-8')
        if shingles(extra_text) & shingles(texts['val']):
            raise ValueError('Recouvrement des pièces supplémentaires avec la validation.')
        extra_ids = torch.tensor(tokenizer.encode(extra_text), dtype=torch.long)
        extra_sha = hashlib.sha256(extra_raw).hexdigest()
    val_ids = tokenizer.encode(texts['val'])
    baseline = evaluate_bpb(model, val_ids, texts['val'])
    if abs(baseline - saved['val_bpb']) > 1e-4:
        raise ValueError('Le BPB de départ ne correspond pas au checkpoint.')
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    manifest.update(seed=813, batch_size=32, train_sha256=saved['train_sha256'], baseline_bpb=baseline,
                    parent_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                    tokenizer_sha256=hashlib.sha256(args.tokenizer.read_bytes()).hexdigest())
    manifest.update(extra_sha256=extra_sha, extra_windows_per_batch=extra_count)
    write_json(args.out / 'manifest.json', manifest)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    history, losses = [], []
    best = baseline
    start = time.monotonic()
    for step in range(1, args.steps + 1):
        # Échauffement court puis décroissance cosinus jusqu'à 10 % du taux initial.
        progress = max(0, step - 100) / max(1, args.steps - 100)
        lr = args.lr * min(1, step / 100) * (0.55 + 0.45 * math.cos(math.pi * progress))
        optimizer.param_groups[0]['lr'] = lr
        model.train()
        x, y = sample_batch(ids, 32 - extra_count, model.cfg.block_size, generator)
        if extra_ids is not None:
            # Chaque tirage supplémentaire reste indépendant du train du kit.
            extra_x, extra_y = sample_batch(extra_ids, extra_count, model.cfg.block_size, generator)
            x, y = torch.cat((x, extra_x)), torch.cat((y, extra_y))
        losses.append(train_step(model, optimizer, x, y))
        if step % 100 == 0:
            print(f'Pas {step} ; loss train {sum(losses[-100:]) / len(losses[-100:]):.4f}', flush=True)
        if step % args.every == 0 or step == args.steps:
            score = evaluate_bpb(model, val_ids, texts['val'])
            record = dict(step=step, bpb=score, lr=lr, train_loss=sum(losses[-100:])/len(losses[-100:]),
                          seconds=time.monotonic()-start)
            history.append(record)
            # Les paliers conservent les poids et l'état d'optimisation dans le dossier propre au run.
            state = {**saved, 'model': model.state_dict(), 'val_bpb': score,
                     'optimizer': optimizer.state_dict(), 'deep_continuation': {**manifest, **record},
                     'rng_state': torch.get_rng_state(), 'batch_rng_state': generator.get_state()}
            torch.save(state, args.out / f'step-{step}.pt')
            if score < best:
                best = score
                torch.save(state, args.out / 'best.pt')
            write_json(args.out / 'measures.json', history)
            print(f'Pas {step} ; {score:.6f} BPB ; meilleur {best:.6f}', flush=True)


if __name__ == '__main__':
    main()
