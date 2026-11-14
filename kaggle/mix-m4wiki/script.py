# Run d'ablation sur un mélange de sources avec le script d'entraînement du kit.
# MIX et KEEP_CHECKPOINT sont renseignés par scripts/kaggle_mix_run.py.
import json
import shutil
import subprocess
import sys
from pathlib import Path

MIX = "M4WIKI"
KEEP_CHECKPOINT = "1" == "1"
SEED = 1337

# Charge le flux et son tokenizer dédié s'il existe, sinon le tokenizer partagé du dataset.
data = next(Path("/kaggle/input").rglob(f"{MIX}/train.bin")).parent
tokenizer = data / "tokenizer.json"
if not tokenizer.is_file():
    tokenizer = next(parent / "tokenizer.json" for parent in data.parents
                     if (parent / "tokenizer.json").is_file())
print("données :", data, "| tokenizer :", tokenizer, flush=True)

# Même version du kit que pour toutes les mesures de l'ablation.
kit = Path("/kaggle/working/piscine-kit")
subprocess.run(["git", "clone", "https://github.com/Meuleur/Piscine.git", str(kit)], check=True)
subprocess.run(["git", "checkout", "--detach", "3709c85ddaabfcd688d6eea80a5c5ed90605b549"], cwd=kit, check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3"], check=True)

# Une autre graine sert uniquement à mesurer la stabilité du score.
suffix = ""
if SEED != 1337:
    path = kit / "config" / "official.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    assert config["train"]["seed"] == 1337
    config["train"]["seed"] = SEED
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    suffix = f"-s{SEED}"

out = Path(f"/kaggle/working/run-{MIX}{suffix}")
# Les runs de la graine officielle passent par la configuration du kit intacte.
subprocess.run([sys.executable, "-m", "ftb.train", "--data", str(data), "--tokenizer", str(tokenizer),
                "--out", str(out), "--device", "cuda:0", "--micro-batch", "8"], cwd=kit, check=True)
# BPB sur les 230 documents publics, global et par genre.
subprocess.run([sys.executable, "-m", "ftb.evaluate", "--ckpt", str(out / "ckpt.pt"),
                "--tokenizer", str(tokenizer), "--data", "data/validation.jsonl",
                "--device", "cuda:0", "--out", str(out / "evaluation.json")], cwd=kit, check=True)
# Archive les métadonnées et conserve les poids des candidats à la soumission.
shutil.copyfile(data / "data_meta.json", out / "data_meta.json")
(out / "protocol.json").write_text(json.dumps({"seed": SEED}, indent=2), encoding="utf-8")
if not KEEP_CHECKPOINT:
    (out / "ckpt.pt").unlink()
print((out / "evaluation.json").read_text(encoding="utf-8"))
