"""Pousse un mélange sur Kaggle à partir du modèle kaggle/mix-template.

Usage : uv run python scripts/kaggle_mix_run.py M3
Crée kaggle/mix-<id>/ (script + metadata, versionnés) puis lance `kaggle kernels push`.
Le jeton Kaggle reste dans le profil utilisateur, jamais dans le dépôt.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def upload_dataset(mix, source):
    """Crée le dataset Kaggle privé `piscine-mix-<id>` à partir du dossier local du flux.

    `source` est le dossier de sortie de pipeline.mixes (tokenizer.json + <ID>/train.bin).
    """
    slug = f"piscine-mix-{mix.lower()}"
    meta = {"title": slug, "id": f"matissegarlot/{slug}", "licenses": [{"name": "other"}]}
    (Path(source) / "dataset-metadata.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    # --dir-mode zip : le sous-dossier du mélange est envoyé compressé et décompressé par Kaggle.
    # Lancé depuis le dossier lui-même : sous Windows, la CLI casse les chemins absolus (« C_/... »).
    subprocess.run(["uvx", "--with", "six", "kaggle", "datasets", "create", "-p", ".",
                    "--dir-mode", "zip"], check=True, cwd=source)
    # Kaggle accepte le dépôt avant de rendre sa première version accessible aux kernels.
    status_command = ["uvx", "--with", "six", "kaggle", "datasets", "status", meta["id"]]
    for _ in range(24):
        result = subprocess.run(status_command, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip().lower() == "ready":
            return
        time.sleep(5)
    raise RuntimeError(f"Dataset Kaggle indisponible après deux minutes : {meta['id']}")


def main():
    """Crée éventuellement le dataset privé puis pousse le script d'entraînement."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mix")
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("--keep-checkpoint", action="store_true")
    parser.add_argument("--accelerator")
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()
    mix = args.mix
    if args.seed != 1337 and args.keep_checkpoint:
        parser.error("--keep-checkpoint est réservé à la graine officielle 1337")
    if args.source:
        upload_dataset(mix, args.source)
    suffix = f"-s{args.seed}" if args.seed != 1337 else ""
    folder = ROOT / "kaggle" / f"mix-{mix.lower()}{suffix}"
    folder.mkdir(exist_ok=True)
    template = (ROOT / "kaggle/mix-template/script.py").read_text(encoding="utf-8")
    script = (template.replace("__MIX__", mix)
              .replace("__KEEP_CHECKPOINT__", str(int(args.keep_checkpoint)))
              .replace("__TRAIN_SEED__", str(args.seed)))
    (folder / "script.py").write_text(script, encoding="utf-8")
    # Le kernel ne doit PAS avoir le même slug que son dataset : Kaggle répond alors « 409 Conflict ».
    slug = f"piscine-run-{mix.lower()}{suffix}"
    metadata = {
        "id": f"matissegarlot/{slug}", "title": slug, "code_file": "script.py",
        "language": "python", "kernel_type": "script", "is_private": True,
        # Un dataset privé par mélange (piscine-mix-<id>), créé par upload_dataset().
        "enable_gpu": True, "enable_internet": True, "dataset_sources": [f"matissegarlot/piscine-mix-{mix.lower()}"],
        "competition_sources": [], "kernel_sources": [], "model_sources": [],
    }
    (folder / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    # Même CLI que le reste du projet (règle 9 d'AGENTS.md).
    command = ["uvx", "--with", "six", "kaggle", "kernels", "push", "-p", str(folder)]
    if args.accelerator:
        command.extend(["--accelerator", args.accelerator])
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
