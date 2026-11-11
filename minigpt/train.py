"""Entraîne le mini-GPT sur Molière avec le BPE du bloc 1."""

import argparse
import hashlib
import math
import time
from dataclasses import asdict
from pathlib import Path

import torch

from minigpt.bigram import CORPUS, load_utf8
from minigpt.bpe import BPETokenizer
from minigpt.model import GPT, GPTConfig, evaluate_bpb

TOKENIZER = Path("data/processed/bpe_moliere_1024.json")
EXPERIMENTS = Path("Kaggle submissions")
CHECKPOINT = Path("checkpoints/moliere_gpt.pt")
BIGRAM_BPB = 3.3544
SEED = 42


def sample_batch(
    ids: torch.Tensor, batch_size: int, block_size: int, generator: torch.Generator
) -> tuple[torch.Tensor, torch.Tensor]:
    """Tire des fenêtres de longueur block_size et leurs cibles décalées."""
    if len(ids) <= block_size:
        raise ValueError("Le corpus doit contenir plus de tokens que la fenêtre.")
    # Le dernier départ valide laisse un token de plus pour la dernière cible.
    starts = torch.randint(len(ids) - block_size, (batch_size,), generator=generator)
    positions = starts[:, None] + torch.arange(block_size)
    return ids[positions], ids[positions + 1]


def train_step(
    model: GPT, optimizer: torch.optim.Optimizer, x: torch.Tensor, y: torch.Tensor
) -> float:
    """Calcule la loss, rétropropage et applique un pas d'optimisation."""
    optimizer.zero_grad(set_to_none=True)
    _, loss = model(x, y)
    loss.backward()
    optimizer.step()
    return loss.item()


def save_loss_plot(losses: list[float]) -> None:
    """Enregistre la loss par pas dans un PNG, sans ouvrir de fenêtre."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    ax.plot(range(1, len(losses) + 1), losses, linewidth=0.8)
    ax.set(title="Mini-GPT sur Molière", xlabel="Pas d’entraînement", ylabel="Loss train (nats/token)")
    ax.grid(alpha=0.25)
    fig.savefig(EXPERIMENTS / "moliere_loss.png", dpi=160)
    plt.close(fig)


def save_samples(model: GPT, tokenizer: BPETokenizer) -> None:
    """Génère cinq continuations avec une graine indépendante des batchs."""
    prompts = ["ACTE I\n", "SCÈNE PREMIÈRE\n", "HARPAGON.\n", "SGANARELLE.\n", "MONSIEUR JOURDAIN.\n"]
    generator = torch.Generator().manual_seed(SEED)
    samples = []
    for index, prompt in enumerate(prompts, start=1):
        start = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long)
        result = model.generate(start, max_new_tokens=128, temperature=0.8, generator=generator)
        samples.append(f"=== Échantillon {index} ===\n{tokenizer.decode(result[0].tolist())}")
    (EXPERIMENTS / "moliere_samples.txt").write_text("\n\n".join(samples) + "\n", encoding="utf-8")


def main() -> None:
    """Lance l'entraînement CPU, évalue le BPB et sauvegarde les résultats."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=2700, help="nombre de pas AdamW")
    parser.add_argument("--batch-size", type=int, default=32, help="fenêtres par batch")
    parser.add_argument("--lr", type=float, default=3e-4, help="taux d'apprentissage")
    parser.add_argument("--eval-every", type=int, default=500, help="intervalle entre deux BPB de validation")
    parser.add_argument("--log-every", type=int, default=100, help="intervalle entre deux logs de loss")
    args = parser.parse_args()
    if min(args.steps, args.batch_size, args.eval_every, args.log_every) < 1:
        parser.error("les nombres de pas et de fenêtres doivent être positifs")
    if not math.isfinite(args.lr) or args.lr <= 0:
        parser.error("--lr doit être fini et strictement positif")
    if not TOKENIZER.is_file():
        parser.error(f"{TOKENIZER} absent : lance uv run python -m minigpt.bpe")

    torch.manual_seed(SEED)
    batch_generator = torch.Generator().manual_seed(SEED)
    cfg = GPTConfig()
    tokenizer = BPETokenizer.load(TOKENIZER)
    if len(tokenizer.vocab) != cfg.vocab_size:
        parser.error(f"le tokenizer doit avoir {cfg.vocab_size} entrées")

    # load_utf8 normalise les fins de ligne du kit avant le BPE et le calcul du BPB.
    train_bytes = load_utf8(CORPUS / "moliere_train.txt")
    val_bytes = load_utf8(CORPUS / "moliere_val.txt")
    val_text = val_bytes.decode("utf-8")
    train_ids = torch.tensor(tokenizer.encode(train_bytes.decode("utf-8")), dtype=torch.long)
    val_ids = tokenizer.encode(val_text)
    train_hash = hashlib.sha256(train_bytes).hexdigest()
    val_hash = hashlib.sha256(val_bytes).hexdigest()
    print(f"SHA-256 train : {train_hash}\nSHA-256 val   : {val_hash}", flush=True)

    model = GPT(cfg).cpu()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    model.train()
    losses = []
    logged_at = 0
    started_at = time.perf_counter()
    for step in range(1, args.steps + 1):
        x, y = sample_batch(train_ids, args.batch_size, cfg.block_size, batch_generator)
        losses.append(train_step(model, optimizer, x, y))
        if step == 1 or step % args.log_every == 0 or step == args.steps:
            mean_loss = sum(losses[logged_at:]) / (step - logged_at)
            logged_at = step
            elapsed = time.perf_counter() - started_at
            print(f"Pas {step}/{args.steps} | loss train {mean_loss:.4f} | {elapsed:.1f} s", flush=True)
        if step % args.eval_every == 0 or step == args.steps:
            # evaluate_bpb passe en mode évaluation puis restaure le mode entraînement.
            val_bpb = evaluate_bpb(model, val_ids, val_text)
            print(f"Pas {step}/{args.steps} | BPB val {val_bpb:.4f}", flush=True)

    tokens_seen = args.steps * args.batch_size * cfg.block_size
    print(f"BPB final {val_bpb:.4f} | bigramme {BIGRAM_BPB:.4f} | écart {val_bpb - BIGRAM_BPB:+.4f}")
    print(f"Tokens vus : {tokens_seen:,}", flush=True)
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model": model.state_dict(),
            "config": asdict(cfg),
            "training": vars(args),
            "seed": SEED,
            "val_bpb": val_bpb,
            "train_sha256": train_hash,
            "val_sha256": val_hash,
        },
        CHECKPOINT,
    )
    EXPERIMENTS.mkdir(parents=True, exist_ok=True)
    save_loss_plot(losses)
    save_samples(model, tokenizer)
    print(f"Résultats dans {EXPERIMENTS} et {CHECKPOINT}", flush=True)


if __name__ == "__main__":
    main()
