# Second run de la démo chat : même SFT que piscine-chat-finetune, mais sur les dialogues v5
# (v4 + 8 000 paires de théâtre Claire/TheatreGratuit, CC-BY-NC-SA 4.0, rien de publié).
# Part du checkpoint Molière retenu par le premier run (sortie de noyau en entrée).
import subprocess
import sys
from pathlib import Path

data = next(Path("/kaggle/input").rglob("chat_v5_train.json")).parent
best = next(Path("/kaggle/input").rglob("moliere-cont/best.pt"))  # palier choisi sur le held-out
print("données :", data, "| départ :", best, flush=True)
corpus = Path("/kaggle/working/corpus")
corpus.mkdir(exist_ok=True)
for name in ("moliere_train.txt", "moliere_val.txt"):
    # chat_sft attend un dossier avec les deux fichiers Molière (rappel et BPB).
    (corpus / name).write_bytes((data / name).read_bytes())
repo = Path("/kaggle/working/piscine_Lab")
subprocess.run(["git", "clone", "--depth", "1", "--branch", "feat/chat-finetune",
                "https://github.com/MatisseGrl/piscine_Lab.git", str(repo)], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3"], check=True)
# Mêmes réglages que le run v4 : seule la donnée change (comparaison propre).
subprocess.run([sys.executable, "-m", "minigpt.chat_sft", "--checkpoint", str(best),
                "--tokenizer", str(data / "tokenizer.json"), "--data", str(data / "chat_v5_train.json"),
                "--corpus", str(corpus), "--out", "/kaggle/working/chat-sft-v5", "--steps", "2000",
                "--every", "250", "--lr", "0.0001", "--replay", "0.3", "--batch-size", "32",
                "--replay-batch", "8"], cwd=repo, check=True)
print("terminé", flush=True)
