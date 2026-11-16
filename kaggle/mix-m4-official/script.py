# Run d'ablation sur un mélange de sources (M1 à M5) avec le script d'entraînement du kit.
# MIX est remplacé par scripts/kaggle_mix_run.py au moment du push. Config figée du kit,
# même tokenizer, même micro-batch que l'ablation : seules les données changent.
import shutil
import subprocess
import sys
from pathlib import Path

MIX = "M4"

# Flux du mélange (train.bin + data_meta.json) et tokenizer 8 192 commun du dataset Kaggle.
data = next(Path("/kaggle/input").rglob(f"{MIX}/train.bin")).parent
# Recherche dans tout le dataset : Kaggle peut ajouter un niveau de dossier en décompressant.
tokenizer = next(Path("/kaggle/input").rglob("tokenizer.json"))
print("données :", data, "| tokenizer :", tokenizer, flush=True)

# Même version du kit que pour toutes les mesures de l'ablation.
kit = Path("/kaggle/working/piscine-kit")
subprocess.run(["git", "clone", "https://github.com/Meuleur/Piscine.git", str(kit)], check=True)
subprocess.run(["git", "checkout", "--detach", "3709c85ddaabfcd688d6eea80a5c5ed90605b549"], cwd=kit, check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3"], check=True)

out = Path(f"/kaggle/working/run-{MIX}")
# Entraînement officiel : config et hyperparamètres figés par le kit (graine 1337).
subprocess.run([sys.executable, "-m", "ftb.train", "--data", str(data), "--tokenizer", str(tokenizer),
                "--out", str(out), "--device", "cuda:0", "--micro-batch", "8"], cwd=kit, check=True)
# BPB sur les 230 documents publics, global et par genre.
subprocess.run([sys.executable, "-m", "ftb.evaluate", "--ckpt", str(out / "ckpt.pt"),
                "--tokenizer", str(tokenizer), "--data", "data/validation.jsonl",
                "--device", "cuda:0", "--out", str(out / "evaluation.json")], cwd=kit, check=True)
# Archive les métadonnées du flux et conserve les poids pour préparer la soumission.
shutil.copyfile(data / "data_meta.json", out / "data_meta.json")
print((out / "evaluation.json").read_text(encoding="utf-8"))
