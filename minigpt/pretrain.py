"""Pré-entraînement du mini-GPT (bloc 1) sur un flux de tokens français `train.bin` (uint16).

C'est le même modèle écrit à la main (`minigpt/model.py`), mais en configuration plus grande
(celle de la compétition : 6 couches, 5 têtes, d_model 320, contexte 512, vocab 8 192) pour la
démo de chat. Il tourne sur GPU (Kaggle T4) en fp16. Ce n'est PAS la soumission officielle :
celle-ci passe par `ftb.train` du kit.

    python -m minigpt.pretrain --data train.bin --tokenizer tokenizer.json --out runs/pretrain
"""

import argparse
import json
import math
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from minigpt.model import CausalSelfAttention, GPT, GPTConfig, LayerNorm

# Configuration de la compétition : environ 12,6 M paramètres avec notre tête de sortie non liée.
COMPETITION_CONFIG = GPTConfig(vocab_size=8192, block_size=512, n_layer=6, n_head=5, d_model=320)


def enable_fused_kernels(model):
    """Active les noyaux optimisés sans changer les poids ni la configuration."""
    for module in model.modules():
        if isinstance(module, (CausalSelfAttention, LayerNorm)):
            module.fused = True


def learning_rate(step: int, steps: int, warmup: int, lr: float, min_lr: float) -> float:
    """Montée linéaire pendant `warmup` pas, puis décroissance cosinus de `lr` vers `min_lr`."""
    if step < warmup:
        return lr * (step + 1) / warmup
    fraction = (step - warmup) / max(steps - warmup - 1, 1)
    return min_lr + 0.5 * (lr - min_lr) * (1 + math.cos(math.pi * fraction))


def batches(bin_path, batch_size: int, seq_len: int, seed: int, steps: int, *, ordered=False):
    """Produit `steps` lots (x, y) de forme (batch_size, seq_len).

    Le flux est coupé en séquences bout à bout. Par défaut l'ordre est mélangé avant le
    premier passage. En mode ordonné, un flux prémélangé est lu une seule fois, par préfixe.
    y est x décalé d'un token."""
    data = np.memmap(bin_path, dtype="<u2", mode="r")
    n_seq = (len(data) - 1) // seq_len  # nombre de séquences complètes (+1 token pour la cible)
    if n_seq < batch_size:
        raise ValueError("train.bin trop court pour un lot")
    if ordered and steps * batch_size > n_seq:
        raise ValueError("Budget supérieur au flux disponible sans répétition.")
    order = range(n_seq) if ordered else np.random.default_rng(seed).permutation(n_seq)
    for step in range(steps):
        rows = [order[(step * batch_size + b) % n_seq] for b in range(batch_size)]
        chunk = np.stack([data[r * seq_len: r * seq_len + seq_len + 1] for r in rows]).astype(np.int64)
        t = torch.from_numpy(chunk)
        yield t[:, :-1], t[:, 1:]


def pretrain(bin_path, cfg: GPTConfig, *, steps: int, batch_size: int, micro_batch: int, lr: float,
             min_lr: float, warmup: int, seed: int, device: str, log_every: int = 60,
             weight_decay: float = 0.1, ordered: bool = False, fused: bool = False) -> dict:
    """Entraîne un GPT neuf et renvoie {'model', 'losses'}.

    Le lot logique `batch_size` est découpé en micro-lots (accumulation de gradient) pour tenir
    en mémoire GPU, sans changer le calcul."""
    if batch_size % micro_batch:
        raise ValueError("batch_size doit être un multiple de micro_batch")
    accum = batch_size // micro_batch
    torch.manual_seed(seed)
    model = GPT(cfg).to(device)
    if fused:
        enable_fused_kernels(model)
    # Le weight decay ne s'applique qu'aux matrices (pas aux biais ni aux LayerNorm).
    decay = [p for p in model.parameters() if p.dim() >= 2]
    no_decay = [p for p in model.parameters() if p.dim() < 2]
    opt = torch.optim.AdamW([{"params": decay, "weight_decay": weight_decay},
                             {"params": no_decay, "weight_decay": 0.0}], lr=lr, betas=(0.9, 0.95))
    use_amp = device.startswith("cuda")  # fp16 + GradScaler sur GPU, float32 sur CPU
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    losses, started = [], time.monotonic()
    model.train()
    for step, (x, y) in enumerate(batches(bin_path, batch_size, cfg.block_size, seed, steps, ordered=ordered)):
        for group in opt.param_groups:
            group["lr"] = learning_rate(step, steps, warmup, lr, min_lr)
        opt.zero_grad(set_to_none=True)
        total = 0.0
        for i in range(accum):
            xs = x[i * micro_batch:(i + 1) * micro_batch].to(device)
            ys = y[i * micro_batch:(i + 1) * micro_batch].to(device)
            with torch.autocast(device_type=device.split(":")[0], dtype=torch.float16, enabled=use_amp):
                _, loss = model(xs, ys)
            scaler.scale(loss / accum).backward()  # moyenne des micro-lots = loss du lot logique
            total += loss.item() / accum
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        losses.append(total)
        if log_every and (step + 1) % log_every == 0:
            print(f"pas {step + 1}/{steps} | loss {total:.4f} | {time.monotonic() - started:.0f}s", flush=True)
    return {"model": model, "losses": losses}


@torch.no_grad()
def validation_bpb(model: GPT, tokenizer, jsonl_path, device: str) -> float:
    """BPB indicatif sur les documents de validation du kit (fenêtres disjointes de block_size).

    Les bits sont divisés par les octets UTF-8 des textes. Un peu plus pessimiste que
    `ftb.evaluate` (qui chevauche les fenêtres), mais comparable d'un modèle à l'autre."""
    model.eval()
    T = model.cfg.block_size
    nats, n_bytes = 0.0, 0
    for line in open(jsonl_path, encoding="utf-8"):
        text = json.loads(line)["text"]
        ids = torch.tensor(tokenizer.encode(text), dtype=torch.long)
        n_bytes += len(text.encode("utf-8"))
        for s in range(0, len(ids) - 1, T):
            chunk = ids[s:s + T + 1].to(device)
            logits, _ = model(chunk[:-1].unsqueeze(0))
            nats += torch.nn.functional.cross_entropy(logits[0], chunk[1:], reduction="sum").item()
    model.train()
    return nats / math.log(2) / n_bytes


def main() -> None:
    """Entraîne, mesure le BPB de validation du kit et sauvegarde le checkpoint."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, required=True, help="train.bin (uint16)")
    p.add_argument("--tokenizer", type=Path, required=True, help="tokenizer.json (8 192 entrées)")
    p.add_argument("--val", type=Path, default=None, help="validation.jsonl du kit (optionnel)")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--steps", type=int, default=3052)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--micro-batch", type=int, default=16)
    p.add_argument("--lr", type=float, default=2e-3)
    p.add_argument("--min-lr", type=float, default=2e-4)
    p.add_argument("--warmup", type=int, default=150)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--ordered", action="store_true", help="Lire un flux prémélangé sans répétition.")
    p.add_argument("--fused", action="store_true", help="Activer les noyaux accélérés de la démo.")
    p.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = COMPETITION_CONFIG
    # Message de départ : confirme le périphérique avant le premier affichage de perte.
    print(f"démarrage | périphérique : {args.device} | pas : {args.steps}", flush=True)
    result = pretrain(args.data, cfg, steps=args.steps, batch_size=args.batch_size,
                      micro_batch=args.micro_batch, lr=args.lr, min_lr=args.min_lr,
                      warmup=args.warmup, seed=args.seed, device=args.device, ordered=args.ordered,
                      fused=args.fused)
    model = result["model"]
    from minigpt.hf_tokenizer import HFTokenizer  # import tardif : `tokenizers` seulement ici
    tok = HFTokenizer(args.tokenizer)
    meta = {"steps": args.steps, "batch_size": args.batch_size, "seed": args.seed,
            "ordered": args.ordered, "fused": args.fused,
            "target_tokens": args.steps * args.batch_size * cfg.block_size,
            "lr": args.lr, "min_lr": args.min_lr, "warmup": args.warmup,
            "tokenizer_sha256": tok.sha256, "params": model.num_params(),
            "final_loss": result["losses"][-1]}
    if args.val:
        meta["val_bpb"] = validation_bpb(model, tok, args.val, args.device)
        print(f"BPB validation (indicatif) : {meta['val_bpb']:.4f}", flush=True)
    torch.save({"model": model.state_dict(), "config": asdict(cfg), "pretrain": meta}, args.out / "pretrained.pt")
    (args.out / "pretrain.json").write_text(json.dumps({**meta, "losses": result["losses"]}, indent=2))
    print(json.dumps(meta, indent=2), flush=True)


if __name__ == "__main__":
    main()
