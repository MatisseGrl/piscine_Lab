"""Reprend le mini-GPT pré-entraîné (vocab 8 192, contexte 512) sur les 25 pièces du train Molière.

Le nombre de pas se choisit sur un held-out tiré de la FIN du train officiel (jamais sur la
validation). Le BPB de validation est seulement mesuré et noté à chaque palier."""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from minigpt.bigram import load_utf8
from minigpt.finetune import restore_model, write_json
from minigpt.hf_tokenizer import HFTokenizer
from minigpt.model import evaluate_bpb
from minigpt.train import sample_batch


def split_holdout(ids, fraction):
    """Coupe la fin du train en held-out : contigu, donc sans recouvrement de fenêtres."""
    cut = len(ids) - int(len(ids) * fraction)
    return ids[:cut], ids[cut:]


def cosine_lr(step, steps, lr, min_lr):
    """Décroissance cosinus de lr (pas 0) à min_lr (dernier pas)."""
    return min_lr + 0.5 * (lr - min_lr) * (1 + math.cos(math.pi * min(step, steps) / steps))


@torch.no_grad()
def mean_loss(model, ids):
    """Loss moyenne (nats/token) sur des fenêtres consécutives : critère d'arrêt sans validation."""
    model.eval()
    ids = ids.to(next(model.parameters()).device)  # même appareil que le modèle
    T, total, count = model.cfg.block_size, 0.0, 0
    for s in range(0, len(ids) - 1, T):
        chunk = ids[s:s + T + 1]
        logits, _ = model(chunk[:-1].unsqueeze(0))
        total += F.cross_entropy(logits[0], chunk[1:], reduction='sum').item()
        count += len(chunk) - 1
    model.train()
    return total / count


def continue_training(model, train_ids, holdout_ids, *, steps, every, batch_size, lr, min_lr, seed,
                      on_measure=None):
    """Boucle AdamW + cosinus ; mesure la loss held-out au départ et tous les `every` pas.
    `on_measure(step, model, entry)` permet d'ajouter le BPB de validation et de sauvegarder."""
    torch.manual_seed(seed)
    generator = torch.Generator().manual_seed(seed)  # graine des fenêtres tirées
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    history = []

    def measure(step):
        """Note la loss held-out, puis laisse l'appelant compléter l'entrée."""
        entry = {'step': step, 'holdout_loss': mean_loss(model, holdout_ids)}
        if on_measure:
            on_measure(step, model, entry)
        history.append(entry)
        print(json.dumps(entry), flush=True)

    measure(0)
    model.train()
    for step in range(1, steps + 1):
        optimizer.param_groups[0]['lr'] = cosine_lr(step - 1, steps, lr, min_lr)
        x, y = sample_batch(train_ids, batch_size, model.cfg.block_size, generator)
        device = next(model.parameters()).device
        x, y = x.to(device), y.to(device)  # tirage sur CPU (graine stable), calcul sur GPU
        _, loss = model(x, y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step % every == 0 or step == steps:
            measure(step)
    return history


def main():
    """Charge le checkpoint, vérifie le tokenizer, entraîne et sauvegarde chaque palier."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint', 'tokenizer', 'corpus', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--steps', type=int, default=1000)
    parser.add_argument('--every', type=int, default=200)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--min-lr', type=float, default=1e-5)
    parser.add_argument('--holdout', type=float, default=0.05)
    parser.add_argument('--threads', type=int, default=8)
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    saved = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    model = restore_model(saved).to('cuda' if torch.cuda.is_available() else 'cpu')  # GPU sur Kaggle
    tokenizer = HFTokenizer.load(args.tokenizer)
    if len(tokenizer.vocab) != model.cfg.vocab_size:
        raise ValueError('Tokenizer incompatible avec le checkpoint.')
    # Mode texte : CRLF -> LF, octets identiques au kit.
    train_text = load_utf8(args.corpus / 'moliere_train.txt').decode('utf-8')
    val_text = load_utf8(args.corpus / 'moliere_val.txt').decode('utf-8')
    train_ids, holdout_ids = split_holdout(torch.tensor(tokenizer.encode(train_text)), args.holdout)
    val_ids = tokenizer.encode(val_text)
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    manifest.update(seed=1337, tokenizer_sha256=tokenizer.sha256,
                    train_sha256=hashlib.sha256(train_text.encode()).hexdigest(),
                    val_sha256=hashlib.sha256(val_text.encode()).hexdigest(),
                    train_tokens=len(train_ids), holdout_tokens=len(holdout_ids))
    write_json(args.out / 'manifest.json', manifest)
    started = time.monotonic()

    def on_measure(step, model, entry):
        """BPB de validation (mesuré, pas utilisé pour choisir) et sauvegarde du palier."""
        entry['val_bpb'] = evaluate_bpb(model, val_ids, val_text)
        entry['seconds'] = round(time.monotonic() - started, 1)
        if step:
            torch.save({'model': model.state_dict(), 'config': saved['config'], 'step': step,
                        'val_bpb': entry['val_bpb'], 'holdout_loss': entry['holdout_loss'],
                        'tokenizer_sha256': tokenizer.sha256}, args.out / f'step-{step}.pt')

    history = continue_training(model, train_ids, holdout_ids, steps=args.steps, every=args.every,
                                batch_size=args.batch_size, lr=args.lr, min_lr=args.min_lr, seed=1337,
                                on_measure=on_measure)
    # Sélection sur le held-out uniquement.
    best = min(history[1:], key=lambda h: h['holdout_loss'])
    write_json(args.out / 'history.json', {'history': history, 'selected_on_holdout': best})
    # Copie du palier retenu sous un nom fixe, point de départ du SFT du chat.
    (args.out / 'best.pt').write_bytes((args.out / f"step-{best['step']}.pt").read_bytes())
    print('Retenu (held-out) :', json.dumps(best), flush=True)


if __name__ == '__main__':
    main()
