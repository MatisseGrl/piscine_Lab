"""Pousse sur Kaggle un run d'ablation pour un mélange (M1 à M5) à partir du modèle kaggle/mix-template.

Usage : uv run python scripts/kaggle_mix_run.py M3
Crée kaggle/mix-<id>/ (script + metadata, versionnés) puis lance `kaggle kernels push`.
Le jeton Kaggle reste dans le profil utilisateur, jamais dans le dépôt.
"""

import json
import subprocess
import sys
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


def main():
    """Usage : `kaggle_mix_run.py M3 [dossier_du_flux]`. Avec un dossier, crée d'abord le dataset."""
    mix = sys.argv[1]
    if len(sys.argv) > 2:
        upload_dataset(mix, sys.argv[2])
    folder = ROOT / "kaggle" / f"mix-{mix.lower()}"
    folder.mkdir(exist_ok=True)
    template = (ROOT / "kaggle/mix-template/script.py").read_text(encoding="utf-8")
    (folder / "script.py").write_text(template.replace("__MIX__", mix), encoding="utf-8")
    # Le kernel ne doit PAS avoir le même slug que son dataset : Kaggle répond alors « 409 Conflict ».
    slug = f"piscine-run-{mix.lower()}"
    metadata = {
        "id": f"matissegarlot/{slug}", "title": slug, "code_file": "script.py",
        "language": "python", "kernel_type": "script", "is_private": True,
        # Un dataset privé par mélange (piscine-mix-<id>), créé par upload_dataset().
        "enable_gpu": True, "enable_internet": True, "dataset_sources": [f"matissegarlot/piscine-mix-{mix.lower()}"],
        "competition_sources": [], "kernel_sources": [], "model_sources": [],
    }
    (folder / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    # Même CLI que le reste du projet (règle 9 d'AGENTS.md).
    subprocess.run(["uvx", "--with", "six", "kaggle", "kernels", "push", "-p", str(folder)], check=True)


if __name__ == "__main__":
    main()
