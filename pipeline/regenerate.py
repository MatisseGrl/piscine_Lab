"""Commande unique qui regénère le dataset final, du web brut au flux `train.bin`.

    uv run python -m pipeline.regenerate --mix M4

Elle enchaîne, dans l'ordre, les étapes déjà écrites (collect, clean, dedup, quality, tokenizer
et flux de base, Wikinews, Gutenberg, mélange) puis compare le SHA-256 du flux obtenu à celui
du run Kaggle/Colab consigné dans `Kaggle submissions/LOG.md`. Même SHA = reproductible.

Une étape déjà faite (son fichier témoin existe) est sautée : on peut relancer après une
interruption. Chaque étape refuse d'écraser une sortie existante, donc rien n'est perdu.
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Révision du kit officiel (même valeur que pipeline.ablation.KIT_REV).
KIT_REV = "3709c85ddaabfcd688d6eea80a5c5ed90605b549"
KIT_URL = "https://github.com/Meuleur/Piscine.git"
KIT_DIR = Path("kit/Piscine-official")

# SHA-256 de `train.bin` obtenus lors des runs consignés dans le LOG (flux de 100 007 937 tokens).
# M5 n'est pas encore figé : pas de contrôle tant que son SHA n'est pas noté ici.
EXPECTED_SHA256 = {
    "M1": "7fafbea6078795809be9e46d98a4b8ed4c67f12c8ab86559f8bc66306dc5a6fa",
    "M2": "6d2a5128de9a6d28e923eabf65d36ecf88c0ff64ecbbbcdc803e5bece41a37ba",
    "M3": "b771c8aa44f9ebf478fa7c5c4395c071aee410d445505fddf993b5cd217ccb39",
    "M4": "c6c628a6b44640db55654c68878a35d02748a860f7aad1ab4c9b9597349738a9",
}

PY = sys.executable
# Plafond d'octets compressés des archives WET retenues (10 archives), voir pipeline/README.md.
CC_MAX_BYTES = "1050000000"


@dataclass(frozen=True)
class Step:
    """Une étape : un nom, la commande à lancer et le fichier qui prouve qu'elle est faite."""

    name: str
    argv: list
    done: Path


def build_steps(mix, kit=KIT_DIR):
    """Liste ordonnée des étapes pour produire le flux du mélange `mix` (chemins relatifs à ROOT)."""
    kit = str(kit)
    return [
        Step("kit", ["git", "clone", KIT_URL, kit], Path(kit) / "data/validation.jsonl"),
        Step("kit-rev", ["git", "-C", kit, "checkout", "--detach", KIT_REV],
             Path(kit) / "corpus/moliere_val.txt"),
        # Le dernier fichier téléchargé par la collecte sert de témoin.
        Step("collect", [PY, "-m", "pipeline.collect"],
             Path("data/raw/assemblee_nationale/16/syseron.xml.zip")),
        Step("clean", [PY, "-m", "pipeline.clean", "--kit", kit, "--include-raw",
                       "--cc-max-bytes", CC_MAX_BYTES], Path("data/interim/clean/stats.json")),
        Step("dedup", [PY, "-m", "pipeline.dedup", "all", "--kit", kit, "--threshold", "0.97"],
             Path("data/interim/dedup/final/stats.json")),
        Step("quality", [PY, "-m", "pipeline.quality", "--kit", kit],
             Path("data/interim/quality/final/stats.json")),
        # Tokenizer 8 192 commun (appris sur le nettoyé) + flux de base : requis par Wikinews et le mélange.
        Step("tokenizer", [PY, "-m", "pipeline.ablation", "--kit", kit],
             Path("data/processed/ablation/manifest.json")),
        Step("wikinews-dump", [PY, "-m", "pipeline.wikinews", "--download"],
             Path("data/raw/wikinews_fr/frwikinews-20261101-pages-articles.xml.bz2")),
        Step("wikinews", [PY, "-m", "pipeline.wikinews", "--kit", kit],
             Path("data/interim/wikinews/stats.json")),
        Step("gutenberg", [PY, "-m", "pipeline.gutenberg", "--kit", kit],
             Path("data/interim/gutenberg/stats.json")),
        Step(f"mix-{mix}", [PY, "-m", "pipeline.mixes", "--kit", kit, "--mixes", mix,
                            "--out", str(final_dir(mix))],
             final_dir(mix) / mix / "data_meta.json"),
    ]


def final_dir(mix):
    """Dossier de sortie du mélange final (neuf : `pipeline.mixes` refuse d'écraser)."""
    return Path("data/processed/final") / mix


def verify_final(mix, root=ROOT):
    """Compare le SHA-256 du flux regénéré à celui du run de référence ; renvoie (ok, message)."""
    meta_path = root / final_dir(mix) / mix / "data_meta.json"
    if not meta_path.is_file():
        return False, f"Introuvable : {meta_path}"
    obtained = json.loads(meta_path.read_text(encoding="utf-8"))["dataset_sha256"]
    expected = EXPECTED_SHA256.get(mix)
    if expected is None:
        return True, f"{mix} : SHA-256 {obtained} (pas de référence enregistrée, à noter dans le LOG)"
    if obtained != expected:
        return False, f"{mix} : SHA-256 DIFFÉRENT\n  obtenu   {obtained}\n  attendu  {expected}"
    return True, f"{mix} : SHA-256 identique au run de référence ({obtained[:12]}…)"


def run(mix, dry_run=False, only=None, start=None, root=ROOT):
    """Lance les étapes dans l'ordre ; saute celles dont le témoin existe. Renvoie 0 si tout va bien."""
    steps = build_steps(mix)
    names = [step.name for step in steps]
    for label, value in (("--only", only), ("--from", start)):
        if value and value not in names:
            raise SystemExit(f"{label} {value} inconnu. Étapes : {', '.join(names)}")
    started = start is None
    for step in steps:
        started = started or step.name == start
        if not started or (only and step.name != only):
            continue
        if (root / step.done).exists():
            print(f"[déjà fait] {step.name}  ({step.done})", flush=True)
            continue
        print(f"[à lancer ] {step.name} : {' '.join(map(str, step.argv))}", flush=True)
        if dry_run:
            continue
        # Une étape qui échoue arrête tout : mieux vaut s'arrêter que mélanger des sorties incohérentes.
        if subprocess.run(step.argv, cwd=root).returncode != 0:
            print(f"ÉCHEC à l'étape {step.name}", file=sys.stderr)
            return 1
    if dry_run:
        return 0
    ok, message = verify_final(mix, root)
    print(message, flush=True)
    return 0 if ok else 1


def main():
    """Lit les options et lance la régénération."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mix", default="M4", choices=["M1", "M2", "M3", "M4", "M5"],
                        help="Mélange final à produire (défaut : M4).")
    parser.add_argument("--dry-run", action="store_true", help="Affiche les étapes sans rien lancer.")
    parser.add_argument("--only", help="Ne lance que cette étape.")
    parser.add_argument("--from", dest="start", help="Reprend à partir de cette étape.")
    args = parser.parse_args()
    # Console Windows : forcer l'UTF-8 pour que les accents des messages s'affichent bien.
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(run(args.mix, args.dry_run, args.only, args.start))


if __name__ == "__main__":
    main()
