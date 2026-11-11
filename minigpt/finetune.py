"""Compare deux continuations CPU depuis les mêmes poids Molière."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import torch

from minigpt.bigram import CORPUS, load_utf8
from minigpt.bpe import BPETokenizer
from minigpt.model import GPT, GPTConfig, evaluate_bpb
from minigpt.train import sample_batch, train_step


def learning_rate(step: int, steps: int, schedule: str) -> float:
    """Renvoie le taux constant ou la décroissance cosinus de 1e-4 à 1e-5."""
    if schedule == "constant":
        return 1e-4
    fraction = step / max(steps - 1, 1)
    return 1e-5 + 0.5 * (1e-4 - 1e-5) * (1 + math.cos(math.pi * fraction))


def restore_model(checkpoint: dict) -> GPT:
    """Reconstruit un modèle indépendant et recharge strictement tous ses poids."""
    model = GPT(GPTConfig(**checkpoint["config"])).cpu()
    model.load_state_dict(checkpoint["model"], strict=True)
    return model


def write_json(path: Path, value: dict | list) -> None:
    """Enregistre les mesures lisibles après chaque évaluation."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def save_samples(model: GPT, tokenizer: BPETokenizer, path: Path) -> None:
    """Reproduit les cinq amorces et la température de la référence."""
    generator = torch.Generator().manual_seed(42)
    samples = []
    for prompt in ["ACTE I\n", "SCÈNE PREMIÈRE\n", "HARPAGON.\n", "SGANARELLE.\n", "MONSIEUR JOURDAIN.\n"]:
        ids = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long)
        result = model.generate(ids, 128, temperature=0.8, generator=generator)
        samples.append(tokenizer.decode(result[0].tolist()))
    path.write_text("\n\n".join(samples), encoding="utf-8")


def main() -> None:
    """Mesure la référence puis compare deux reprises avec un nouvel AdamW."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--eval-every", type=int, default=200)
    args = parser.parse_args()
    if min(args.steps, args.eval_every) < 1:
        parser.error("Les nombres de pas doivent être positifs.")
    # Refuser tout dossier existant empêche d'écraser un essai ou la référence.
    args.out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    tokenizer = BPETokenizer.load(args.tokenizer)
    train_bytes = load_utf8(CORPUS / "moliere_train.txt")
    val_bytes = load_utf8(CORPUS / "moliere_val.txt")
    # Les empreintes lient la continuation aux corpus exacts du premier run.
    for name, raw in [("train", train_bytes), ("val", val_bytes)]:
        if hashlib.sha256(raw).hexdigest() != checkpoint[f"{name}_sha256"]:
            raise ValueError(f"Le corpus {name} diffère de la référence.")
    if len(tokenizer.vocab) != checkpoint["config"]["vocab_size"]:
        raise ValueError("Le vocabulaire ne correspond pas aux poids.")
    train_ids = torch.tensor(tokenizer.encode(train_bytes.decode("utf-8")), dtype=torch.long)
    val_text = val_bytes.decode("utf-8")
    val_ids = tokenizer.encode(val_text)
    reference = restore_model(checkpoint)
    baseline = evaluate_bpb(reference, val_ids, val_text)
    # Une permutation de vocabulaire de même taille serait détectée par ce contrôle.
    if abs(baseline - checkpoint["val_bpb"]) > 1e-4:
        raise ValueError("Le BPB de référence n'est pas reproduit : vérifier le tokenizer.")
    metadata = {
        "baseline_bpb": baseline, "steps": args.steps, "batch_size": 32,
        "seed": 142, "threads": 4, "optimizer_reset": True,
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "tokenizer_sha256": hashlib.sha256(args.tokenizer.read_bytes()).hexdigest(),
        "train_sha256": checkpoint["train_sha256"], "val_sha256": checkpoint["val_sha256"],
    }
    write_json(args.out / "manifest.json", metadata)
    print(f"Référence reproduite : {baseline:.6f} BPB", flush=True)
    save_samples(reference, tokenizer, args.out / "baseline_samples.txt")
    # Un échantillon d'entraînement fixe permet d'observer l'écart train/validation.
    probe = sample_batch(train_ids, 32, reference.cfg.block_size, torch.Generator().manual_seed(314))
    summaries = []
    for schedule in ["cosine", "constant"]:
        torch.manual_seed(142)
        generator = torch.Generator().manual_seed(142)
        model = restore_model(checkpoint)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
        run_dir = args.out / schedule
        run_dir.mkdir()
        best_bpb, best_step = baseline, 0
        # Le candidat initial reste gagnant si tous les pas supplémentaires dégradent le BPB.
        torch.save(checkpoint, run_dir / "best.pt")
        history = []
        started = time.perf_counter()
        for step in range(args.steps + 1):
            if step:
                lr = learning_rate(step - 1, args.steps, schedule)
                for group in optimizer.param_groups:
                    group["lr"] = lr
                model.train()
                loss = train_step(model, optimizer, *sample_batch(train_ids, 32, model.cfg.block_size, generator))
                if step % 100 == 0:
                    print(f"{schedule} {step}/{args.steps} loss={loss:.4f}", flush=True)
            if step % args.eval_every == 0 or step == args.steps:
                bpb = evaluate_bpb(model, val_ids, val_text)
                model.eval()
                with torch.no_grad():
                    _, train_loss = model(*probe)
                history.append({"step": step, "val_bpb": bpb, "train_probe_loss": train_loss.item(),
                                "lr": optimizer.param_groups[0]["lr"], "seconds": time.perf_counter() - started})
                write_json(run_dir / "history.json", history)
                if bpb < best_bpb:
                    best_bpb, best_step = bpb, step
                    # Conserver aussi l'optimiseur et les générateurs pour une future reprise fidèle.
                    torch.save({**checkpoint, "model": model.state_dict(), "val_bpb": bpb,
                                "optimizer": optimizer.state_dict(), "rng_state": torch.get_rng_state(),
                                "batch_rng_state": generator.get_state(),
                                "continuation": {**metadata, "schedule": schedule, "step": step}}, run_dir / "best.pt")
                print(f"{schedule} étape={step} BPB={bpb:.6f} meilleur={best_bpb:.6f}", flush=True)
        best = restore_model(torch.load(run_dir / "best.pt", map_location="cpu", weights_only=True))
        save_samples(best, tokenizer, run_dir / "samples.txt")
        summaries.append({"schedule": schedule, "best_bpb": best_bpb, "best_step": best_step,
                          "final_bpb": bpb, "seconds": time.perf_counter() - started})
        write_json(args.out / "summary.json", summaries)
    print(json.dumps(summaries, indent=2), flush=True)


if __name__ == "__main__":
    main()
