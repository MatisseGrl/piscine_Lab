"""Lance une étape de la comparaison sur un notebook Kaggle privé."""
import argparse
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


ACCOUNT = "matissegarlot"
BUDGET_DATASET = f"{ACCOUNT}/piscine-chat-budget-fr"
CHAT_DATASET = f"{ACCOUNT}/piscine-chat-ft"
REPO = "https://github.com/MatisseGrl/piscine_Lab.git"
STEPS = {"100m": 3052, "300m": 9155}


def main():
    """Prépare le notebook et envoie uniquement du code et des références privées."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["pretrain", "adapt"])
    parser.add_argument("budget", choices=STEPS)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--accelerator", default="NvidiaTeslaT4")
    args = parser.parse_args()
    batch = f"piscine-chat-budget-{args.budget}-s{args.seed}"
    kernel = f"{ACCOUNT}/{batch}-{args.stage}"
    pretrain_job = f"{ACCOUNT}/{batch}-pretrain"
    pretrain = args.stage == "pretrain"
    metadata = {
        "id": kernel, "title": kernel.split("/")[1], "code_file": "script.py",
        "language": "python", "kernel_type": "script", "is_private": True,
        "enable_gpu": True, "enable_internet": True,
        "dataset_sources": [CHAT_DATASET, BUDGET_DATASET] if pretrain else [CHAT_DATASET],
        "kernel_sources": [] if pretrain else [pretrain_job],
        "competition_sources": [], "model_sources": [],
    }
    # Kaggle monte les entrées privées. Le clone public ne transporte que le code.
    source = '''"""Point d'entrée Kaggle pour la démo Molière."""
import subprocess
import sys
from pathlib import Path

inputs = Path("/kaggle/input")
out = Path("/kaggle/working")
repo = Path("/tmp/piscine-chat-budget")
repo.mkdir()

def run(*args):
    """Arrête l'exécution dès la première erreur de commande."""
    subprocess.run(list(map(str, args)), cwd=repo, check=True)

'''
    source += f'run("git", "init", "-q")\nrun("git", "fetch", "--depth", "1", {REPO!r}, {args.commit!r})\n'
    source += '''run("git", "checkout", "--detach", "FETCH_HEAD")
run(sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3")
data = next(inputs.rglob("chat_v5_train.json")).parent
'''
    stage_args = (
        f'"--archive", next(inputs.rglob("train.bin.gz")), "--steps", {STEPS[args.budget]}'
        if pretrain else '"--checkpoint", next(inputs.rglob("pretrain/pretrained.pt"))'
    )
    source += (
        f'run(sys.executable, "-m", "scripts.run_chat_budget", {args.stage!r}, '
        f'"--data", data, "--out", out, "--seed", {args.seed}, {stage_args})\n'
    )
    with TemporaryDirectory(prefix="piscine-chat-kernel-") as scratch:
        path = Path(scratch)
        (path / "script.py").write_text(source, encoding="utf-8")
        (path / "kernel-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        result = subprocess.run(
            ["kaggle", "kernels", "push", "-p", str(path), "--accelerator", args.accelerator],
            check=True, capture_output=True, text=True,
        )
        print(result.stdout, end="")
        if "successfully pushed" not in result.stdout:
            raise RuntimeError(result.stderr or "L'envoi Kaggle n'a pas été confirmé.")


if __name__ == "__main__":
    main()
