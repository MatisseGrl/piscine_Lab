"""Prépare les flux qualité/PII de l'ablation avec le tokenizer et le protocole déjà figés.

Aucun tokenizer n'est entraîné ici : le fichier `tokenizer.json` de la première série est
réutilisé tel quel (même SHA-256), avec le même mélange 80/12/8 en tokens, la même graine et
la même taille de flux. Aucun entraînement n'est lancé.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.ablation import KIT_REV, ROOT, SHARES, prepare_variant, read_json, sha256, write_json

# Variante -> dossier de sortie sous data/interim/.
EXTRA = {"quality": "quality/final", "pii": "pii/dedup", "quality_pii": "pii/quality"}
REFERENCE = "dedup/final"


def extra_sources(interim):
    """Vérifie audit et SHA-256 des archives, et renvoie {variante: {source: (chemin, octets, sha)}}."""
    reference = read_json(interim / REFERENCE / "stats.json")["audit"]
    result = {}
    for variant, folder in EXTRA.items():
        stats = read_json(interim / folder / "stats.json")
        audit = stats["audit"]
        # Audit à zéro recouvrement, mené sur la même validation publique que la référence.
        if (audit["validation_docs"], audit["matching_training_docs"], audit["mean_overlap"]) != (230, 0, 0) \
                or audit["validation_sha256"] != reference["validation_sha256"]:
            raise ValueError(f"Audit invalide ou autre validation : {variant}")
        result[variant] = {}
        for source in SHARES:
            path = interim / folder / f"{source}.jsonl.gz"
            entry = stats["sources"][source]
            if sha256(path) != entry["sha256"]:
                raise ValueError(f"SHA-256 différent de celui de l'audit : {path}")
            result[variant][source] = (path, entry["bytes"], entry["sha256"])
            print(f"Audit vérifié : {variant}/{source}", flush=True)
    return result


def build_variants(output, sources, tokenizer, config, scratch):
    """Construit un flux par variante dans `output/<variante>/` avec le protocole de la base."""
    metas = {}
    # prepare_variant crée seulement le dossier de la variante, pas ses parents.
    Path(output).mkdir(parents=True, exist_ok=True)
    for variant, entries in sources.items():
        metas[variant] = prepare_variant(Path(output) / variant, entries, tokenizer, config, scratch)
        print(variant, metas[variant]["dataset_sha256"], flush=True)
    return metas


def prepare(kit, interim, base, out):
    """Publie les trois flux et un manifeste qui hérite de celui de la série de base."""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    sys.path.insert(0, str(kit))
    from ftb import load_config
    from ftb.tokenizer import load_tokenizer

    if out.exists():
        raise FileExistsError(f"Choisis un dossier de sortie neuf : {out}")
    manifest = read_json(base / "manifest.json")
    tokenizer_path = base / "tokenizer.json"
    if sha256(tokenizer_path) != manifest["tokenizer_sha256"]:
        raise ValueError("Le tokenizer de la série de base diffère de son manifeste")
    config = load_config()
    if config != manifest["config"] or manifest["kit_revision"] != KIT_REV:
        raise ValueError("Le kit ne correspond pas au protocole de la série de base")
    tokenizer = load_tokenizer(tokenizer_path)
    sources = extra_sources(interim)
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as name:
        scratch = Path(name)
        staged = scratch / "ablation-extra"
        staged.mkdir()
        shutil.copyfile(tokenizer_path, staged / "tokenizer.json")
        metas = build_variants(staged, sources, tokenizer, config, scratch)
        # Même protocole que la base ; seules les variantes et la filiation changent.
        write_json(staged / "manifest.json", dict(
            manifest, variants=metas, parent_manifest_sha256=sha256(base / "manifest.json"),
        ))
        staged.rename(out)


def main():
    """Résout les chemins et vérifie le clone intact du kit avant de préparer les flux."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=ROOT / "kit/Piscine-official")
    parser.add_argument("--interim", type=Path, default=ROOT / "data/interim")
    parser.add_argument("--base", type=Path, default=ROOT / "data/processed/ablation")
    parser.add_argument("--out", type=Path, default=ROOT / "data/processed/ablation-extra")
    args = parser.parse_args()
    kit = args.kit.resolve()
    if subprocess.check_output(["git", "-C", str(kit), "rev-parse", "HEAD"], text=True).strip() != KIT_REV:
        raise ValueError(f"Clone du kit attendu à la révision {KIT_REV}")
    if subprocess.check_output(["git", "-C", str(kit), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("Le clone du kit contient des modifications")
    prepare(kit, args.interim.resolve(), args.base.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
