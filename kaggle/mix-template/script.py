# Run d'ablation sur un mélange de sources (M1 à M5) avec le script d'entraînement du kit.
# MIX est remplacé par scripts/kaggle_mix_run.py au moment du push. Config figée du kit,
# même tokenizer, même micro-batch que l'ablation : seules les données changent.
import json
import shutil
import subprocess
import sys
from pathlib import Path

MIX = "__MIX__"
# Graine d'entraînement : 1337 = config officielle ; autre valeur = run de bruit, non soumissible.
SEED = __SEED__

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

# Hors config officielle, seule la graine change (mesure du bruit sur ce mélange).
if SEED != 1337:
    cfg_path = kit / "config" / "official.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["train"]["seed"] == 1337
    cfg["train"]["seed"] = SEED
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

out = Path(f"/kaggle/working/run-{MIX}")
# Entraînement officiel : config et hyperparamètres figés par le kit (graine 1337).
subprocess.run([sys.executable, "-m", "ftb.train", "--data", str(data), "--tokenizer", str(tokenizer),
                "--out", str(out), "--device", "cuda:0", "--micro-batch", "8"], cwd=kit, check=True)
# BPB sur les 230 documents publics, global et par genre.
subprocess.run([sys.executable, "-m", "ftb.evaluate", "--ckpt", str(out / "ckpt.pt"),
                "--tokenizer", str(tokenizer), "--data", "data/validation.jsonl",
                "--device", "cuda:0", "--out", str(out / "evaluation.json")], cwd=kit, check=True)
# Copie des métadonnées du flux pour l'archive, puis suppression du checkpoint (inutile ici).
shutil.copyfile(data / "data_meta.json", out / "data_meta.json")
(out / "ckpt.pt").unlink()
print((out / "evaluation.json").read_text(encoding="utf-8"))
