"""Exécute une étape GPU de la comparaison des budgets de la démo."""
import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import torch


ROOT = Path(__file__).resolve().parents[1]


def run(module, *args):
    """Réutilise les points d'entrée de la démo avec le même interpréteur."""
    subprocess.run([sys.executable, "-m", module, *map(str, args)], cwd=ROOT, check=True)


def text_digest(path):
    """Calcule le SHA-256 UTF-8 après conversion des fins de ligne en LF."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def extract_verified(path, target, manifest, steps):
    """Vérifie le préfixe, y compris lorsque Kaggle a déjà décompressé l'archive."""
    if path.suffix == ".gz":
        with path.open("rb") as stream:
            archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if archive_hash != manifest["archive_sha256"]:
            raise ValueError("Archive d'entraînement différente du manifeste.")
        source = gzip.open(path, "rb")
    else:
        if path.stat().st_size != 2 * manifest["total_input_tokens"]:
            raise ValueError("Taille du flux décompressé différente du manifeste.")
        source = path.open("rb")
    short = steps * 64 * 512 == manifest["short_targets"]
    expected = manifest["short_bin_sha256"] if short else manifest["train_bin_sha256"]
    remaining = (steps * 64 * 512 + 1) * 2
    digest = hashlib.sha256()
    with source, target.open("xb") as destination:
        while remaining:
            chunk = source.read(min(remaining, 8 << 20))
            if not chunk:
                raise ValueError("Flux de tokens tronqué.")
            destination.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
    if digest.hexdigest() != expected:
        raise ValueError("Flux de tokens différent du manifeste.")


def main():
    """Entraîne un poids français ou l'adapte successivement à Molière et au chat."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["pretrain", "adapt"])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("GPU requis pour ces essais.")
    print(torch.__version__, torch.cuda.get_device_name(), flush=True)
    data, out = args.data.resolve(), args.out.resolve()
    tokenizer = data / "tokenizer.json"
    validation = data / "moliere_val.txt"
    chat = data / "chat_v5_train.json"
    common = ["--tokenizer", tokenizer, "--corpus", data]
    measure = ["--tokenizer", tokenizer, "--validation", validation, "--device", "cuda"]
    checks = {
        "tokenizer_sha256": hashlib.sha256(tokenizer.read_bytes()).hexdigest(),
        "chat_train_sha256": hashlib.sha256(chat.read_bytes()).hexdigest(),
        "moliere_train_sha256": text_digest(data / "moliere_train.txt"),
        "moliere_validation_sha256": text_digest(validation),
    }
    if args.stage == "pretrain":
        if args.archive is None:
            parser.error("--archive est requis au pré-entraînement.")
        manifest = json.loads(args.archive.with_name("manifest.json").read_text(encoding="utf-8"))
        if args.steps is None or args.steps * 64 * 512 not in (manifest["short_targets"], manifest["total_targets"]):
            parser.error("Le budget doit correspondre à l'un des préfixes du manifeste.")
        if any(manifest[key] != value for key, value in checks.items() if key in manifest):
            raise ValueError("Tokenizer, validation ou données de chat différents du manifeste.")
        with TemporaryDirectory(prefix="piscine-chat-") as scratch:
            train = Path(scratch) / "train.bin"
            extract_verified(args.archive, train, manifest, args.steps)
            run("minigpt.pretrain", "--data", train, "--tokenizer", tokenizer, "--out", out / "pretrain",
                "--steps", args.steps, "--seed", args.seed, "--ordered", "--fused")
        run("minigpt.evaluate_chat", "--checkpoints", out / "pretrain/pretrained.pt", *measure,
            "--bpb-only", "--out", out / "pretrain-bpb")
        # Transmet à la phase suivante les empreintes des entrées et du modèle.
        record = json.loads((out / "pretrain-bpb/0-pretrained.json").read_text(encoding="utf-8"))
        provenance = {**checks, "checkpoint_sha256": record["checkpoint_sha256"],
                      "steps": args.steps, "seed": args.seed}
        (out / "pretrain/provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
        return

    if args.checkpoint is None:
        parser.error("--checkpoint est requis à l'adaptation.")
    checkpoint = args.checkpoint.resolve()
    provenance = json.loads(checkpoint.with_name("provenance.json").read_text(encoding="utf-8"))
    checks["checkpoint_sha256"] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    checks["seed"] = args.seed
    if any(provenance[key] != value for key, value in checks.items()):
        raise ValueError("Entrées différentes du pré-entraînement.")
    run("minigpt.continue_pretrained", "--checkpoint", checkpoint, *common,
        "--steps", 1500, "--every", 200, "--out", out / "moliere")
    best = out / "moliere/best.pt"
    run("minigpt.evaluate_chat", "--checkpoints", best, *measure, "--out", out / "moliere-dev")
    run("minigpt.chat_sft", "--checkpoint", best, *common, "--data", chat,
        "--steps", 1500, "--every", 500, "--lr", "0.0001", "--replay", "0.3", "--out", out / "chat")


if __name__ == "__main__":
    main()
