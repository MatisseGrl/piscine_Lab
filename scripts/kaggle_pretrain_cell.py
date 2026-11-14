# Cellule à coller dans un notebook Kaggle (GPU T4, Internet activé).
# Pré-entraîne le mini-GPT du bloc 1 (config compétition) sur le flux « dédupliqué + qualité 80/12/8 ».
# Entrée : le dataset Kaggle qui contient `ablation/quality/train.bin` et `ablation/tokenizer.json`
# (l'archive ablation-extra-kaggle.zip importée en Upload). Sortie : /kaggle/working/runs/pretrain/.
import subprocess
import sys
from pathlib import Path

# Retrouve le dossier d'entrée qui contient le flux « qualité ».
train_bin = next(Path("/kaggle/input").rglob("quality/train.bin"))
# Le tokenizer est dans le dossier parent de `quality/`, quel que soit le préfixe ajouté par Kaggle.
tokenizer = train_bin.parent.parent / "tokenizer.json"
print("train.bin :", train_bin, "| tokenizer :", tokenizer)

# Code du dépôt (public), branche du chat.
repo = Path("/kaggle/working/piscine_Lab")
if not repo.exists():
    subprocess.run(["git", "clone", "--branch", "feat/chat-pretrain",
                    "https://github.com/MatisseGrl/piscine_Lab.git", str(repo)], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3"], check=True)

# Validation publique du kit, pour mesurer un BPB indicatif.
kit = Path("/kaggle/working/piscine-kit")
if not kit.exists():
    subprocess.run(["git", "clone", "https://github.com/Meuleur/Piscine.git", str(kit)], check=True)
    subprocess.run(["git", "checkout", "--detach", "3709c85ddaabfcd688d6eea80a5c5ed90605b549"], cwd=kit, check=True)

# 3 052 pas x 64 x 512 tokens = 100 M tokens, comme la compétition (~15 à 40 min sur T4).
subprocess.run([sys.executable, "-m", "minigpt.pretrain",
                "--data", str(train_bin), "--tokenizer", str(tokenizer),
                "--val", str(kit / "data/validation.jsonl"),
                "--out", "/kaggle/working/runs/pretrain",
                "--micro-batch", "16"], cwd=repo, check=True,
               env={**__import__("os").environ, "PYTHONPATH": str(repo)})
