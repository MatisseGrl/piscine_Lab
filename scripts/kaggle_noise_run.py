"""Prépare et pousse un kernel Kaggle de mesure du bruit d'entraînement.

Relance exactement le flux « dédup + qualité 80/12/8 » (dataset Kaggle
matissegarlot/piscine-ablation-extra) avec une autre graine d'entraînement.
Seule la graine de config/official.json change ; tout le reste est identique
au kernel de soumission `piscine-submission-quality`.

Usage : uv run python scripts/kaggle_noise_run.py 1338
Le token Kaggle vient de ~/.kaggle ou de l'environnement, jamais du dépôt.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Code exécuté sur Kaggle : modèle de script, la graine est substituée avant l'envoi.
SCRIPT = '''# Mesure du bruit : « dédup + qualité 80/12/8 » avec la graine d'entraînement __SEED__.
import json, subprocess, sys
from pathlib import Path

data = next(Path("/kaggle/input").rglob("quality/train.bin")).parent
tokenizer = data.parent / "tokenizer.json"
kit = Path("/kaggle/working/piscine-kit")
subprocess.run(["git", "clone", "https://github.com/Meuleur/Piscine.git", str(kit)], check=True)
subprocess.run(["git", "checkout", "--detach", "3709c85ddaabfcd688d6eea80a5c5ed90605b549"], cwd=kit, check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3"], check=True)

# Seule modification : la graine d'entraînement dans la config (1337 -> __SEED__).
cfg_path = kit / "config" / "official.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
assert cfg["train"]["seed"] == 1337
cfg["train"]["seed"] = __SEED__
cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

out = Path("/kaggle/working/run-noise")
subprocess.run([sys.executable, "-m", "ftb.train", "--data", str(data), "--tokenizer", str(tokenizer),
                "--out", str(out), "--device", "cuda:0", "--micro-batch", "8"], cwd=kit, check=True)
subprocess.run([sys.executable, "-m", "ftb.evaluate", "--ckpt", str(out / "ckpt.pt"),
                "--tokenizer", str(tokenizer), "--data", "data/validation.jsonl",
                "--device", "cuda:0", "--out", str(out / "evaluation.json")], cwd=kit, check=True)
print((out / "evaluation.json").read_text(encoding="utf-8"))
# On supprime le checkpoint lourd : seuls les JSON et le journal sont utiles.
(out / "ckpt.pt").unlink(missing_ok=True)
'''


def main(seed: int) -> None:
    slug = f"piscine-noise-s{seed}"
    d = Path(tempfile.mkdtemp(prefix=slug))
    (d / f"{slug}.py").write_text(SCRIPT.replace("__SEED__", str(seed)), encoding="utf-8")
    meta = {"id": f"matissegarlot/{slug}", "title": slug, "code_file": f"{slug}.py",
            "language": "python", "kernel_type": "script", "is_private": True,
            "enable_gpu": True, "enable_tpu": False, "enable_internet": True,
            "dataset_sources": ["matissegarlot/piscine-ablation-extra"],
            "kernel_sources": [], "competition_sources": [], "model_sources": [],
            "machine_shape": "NvidiaTeslaT4"}
    (d / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    subprocess.run(["kaggle", "kernels", "push", "-p", str(d)], check=True)


if __name__ == "__main__":
    main(int(sys.argv[1]))
