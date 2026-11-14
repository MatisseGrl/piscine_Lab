"""Lancé sur une VM Colab par `colab exec` : recolle le flux, vérifie son SHA-256, puis démarre
l'entraînement officiel du kit en arrière-plan (même protocole que kaggle/mix-template/script.py).

Le flux (train.bin) arrive en morceaux de 20 Mo (`part.NN`), car l'API de fichiers de Colab
refuse les gros envois. Le mélange est lu dans `/content/data/MIX`, écrit par `colab_mix.sh`.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

# Nom du mélange, écrit dans un petit fichier par le lanceur local.
MIX = Path("/content/data/MIX").read_text().strip()
data = Path(f"/content/data/{MIX}")

# Recolle les morceaux dans l'ordre, puis les supprime.
parts = sorted(data.glob("part.*"))
if parts:
    with (data / "train.bin").open("wb") as out:
        for part in parts:
            out.write(part.read_bytes())
    for part in parts:
        part.unlink()

# Le flux doit être exactement celui construit en local (sinon le run ne vaut rien).
expected = json.loads((data / "data_meta.json").read_text())["dataset_sha256"]
digest = hashlib.sha256((data / "train.bin").read_bytes()).hexdigest()
if digest != expected:
    raise SystemExit(f"SHA-256 différent : {digest} au lieu de {expected}")
print("flux vérifié :", digest)

# Même version du kit que pour toutes les mesures de l'ablation.
kit = Path("/content/piscine-kit")
if not kit.exists():
    subprocess.run(["git", "clone", "-q", "https://github.com/Meuleur/Piscine.git", str(kit)], check=True)
    subprocess.run(["git", "checkout", "-q", "--detach", "3709c85ddaabfcd688d6eea80a5c5ed90605b549"], cwd=kit, check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3"], check=True)

# Graine optionnelle (fichier /content/data/SEED) : relance de bruit, non soumissible.
# Seule la graine de la config du kit change ; absent = config officielle (1337).
seed_file = Path("/content/data/SEED")
if seed_file.exists():
    seed = int(seed_file.read_text().strip())
    cfg_path = kit / "config" / "official.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["train"]["seed"] in (1337, seed)
    cfg["train"]["seed"] = seed
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print("graine d'entraînement :", seed)

# Entraînement puis évaluation, détachés : `colab exec` rend la main tout de suite.
out = f"/content/run-{MIX}"
tokenizer = "/content/data/tokenizer.json"
command = (
    f"{sys.executable} -m ftb.train --data {data} --tokenizer {tokenizer} --out {out} "
    f"--device cuda:0 --micro-batch 8 && "
    f"{sys.executable} -m ftb.evaluate --ckpt {out}/ckpt.pt --tokenizer {tokenizer} "
    f"--data data/validation.jsonl --device cuda:0 --out {out}/evaluation.json"
)
subprocess.Popen(["bash", "-c", f"({command}) > /content/train-{MIX}.log 2>&1"], cwd=kit,
                 start_new_session=True)
print("entraînement lancé, journal : /content/train-" + MIX + ".log")
