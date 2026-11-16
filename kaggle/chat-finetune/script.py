# Démo chat du bloc 1 sur GPU : (1) continuation du mini-GPT pré-entraîné sur le train Molière,
# palier choisi sur un held-out du train ; (2) SFT du chat (dialogues v4) avec rappel Molière.
# Script poussé par `kaggle kernels push` : les sorties de /kaggle/working sont conservées.
import subprocess
import sys
from pathlib import Path

# Dataset privé : pretrained.pt, tokenizer.json, moliere_train/val.txt, chat_v4_train.json.
data = next(Path("/kaggle/input").rglob("pretrained.pt")).parent
print("données :", data, flush=True)
corpus = Path("/kaggle/working/corpus")
corpus.mkdir(exist_ok=True)
for name in ("moliere_train.txt", "moliere_val.txt"):
    # chat_sft attend un dossier contenant les deux fichiers Molière.
    (corpus / name).write_bytes((data / name).read_bytes())

# Code du dépôt public, branche de cette expérience.
repo = Path("/kaggle/working/piscine_Lab")
subprocess.run(["git", "clone", "--depth", "1", "--branch", "feat/chat-finetune",
                "https://github.com/MatisseGrl/piscine_Lab.git", str(repo)], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3"], check=True)
tok = str(data / "tokenizer.json")
cont = Path("/kaggle/working/moliere-cont")
sft = Path("/kaggle/working/chat-sft")

# (1) Continuation Molière : 1 500 pas, cosinus 1e-4 -> 1e-5, mesure tous les 200 pas.
subprocess.run([sys.executable, "-m", "minigpt.continue_pretrained", "--checkpoint", str(data / "pretrained.pt"),
                "--tokenizer", tok, "--corpus", str(corpus), "--out", str(cont),
                "--steps", "1500", "--every", "200", "--batch-size", "16"], cwd=repo, check=True)

# (2) SFT du chat depuis le palier retenu ; loss = 0,7 chat + 0,3 Molière.
subprocess.run([sys.executable, "-m", "minigpt.chat_sft", "--checkpoint", str(cont / "best.pt"),
                "--tokenizer", tok, "--data", str(data / "chat_v4_train.json"), "--corpus", str(corpus),
                "--out", str(sft), "--steps", "2000", "--every", "250", "--lr", "0.0001",
                "--replay", "0.3", "--batch-size", "32", "--replay-batch", "8"], cwd=repo, check=True)

# Les paliers intermédiaires de la continuation sont lourds : on ne garde que best.pt.
for path in cont.glob("step-*.pt"):
    path.unlink()
print("terminé", flush=True)
