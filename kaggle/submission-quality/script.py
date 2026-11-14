# Run officiel « dédupliqué + qualité 80/12/8 » avec le script d'entraînement du kit (ftb.train).
# Sert à produire le checkpoint de la soumission. Les sorties de /kaggle/working sont conservées
# par Kaggle quand le script est poussé par `kaggle kernels push` (contrairement à un brouillon).
import subprocess
import sys
from pathlib import Path

# Flux « qualité » (train.bin + data_meta.json) et tokenizer 8 192 du dataset ajouté.
data = next(Path("/kaggle/input").rglob("quality/train.bin")).parent
tokenizer = data.parent / "tokenizer.json"
print("données :", data, "| tokenizer :", tokenizer, flush=True)

# Même version du kit que pour toutes les mesures de l'ablation.
kit = Path("/kaggle/working/piscine-kit")
subprocess.run(["git", "clone", "https://github.com/Meuleur/Piscine.git", str(kit)], check=True)
subprocess.run(["git", "checkout", "--detach", "3709c85ddaabfcd688d6eea80a5c5ed90605b549"], cwd=kit, check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3"], check=True)

out = Path("/kaggle/working/run-quality")
# Entraînement officiel : config et hyperparamètres figés par le kit.
subprocess.run([sys.executable, "-m", "ftb.train", "--data", str(data), "--tokenizer", str(tokenizer),
                "--out", str(out), "--device", "cuda:0", "--micro-batch", "8"], cwd=kit, check=True)
# BPB sur les 230 documents publics.
subprocess.run([sys.executable, "-m", "ftb.evaluate", "--ckpt", str(out / "ckpt.pt"),
                "--tokenizer", str(tokenizer), "--data", "data/validation.jsonl",
                "--device", "cuda:0", "--out", str(out / "evaluation.json")], cwd=kit, check=True)
print((out / "evaluation.json").read_text(encoding="utf-8"))
