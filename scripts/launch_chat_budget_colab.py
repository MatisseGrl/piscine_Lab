"""Envoie le préfixe vérifié et lance l'essai court sur une session Colab T4 privée."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = "/content/piscine-chat-budget-100m"
CHUNK = 16 << 20
DATA_FILES = ("tokenizer.json", "moliere_train.txt", "moliere_val.txt", "chat_v5_train.json")


def colab(session, *args):
    """Transmet uniquement les fichiers énumérés à la session renseignée."""
    result = subprocess.run(
        ["colab", args[0], "--session", session, *map(str, args[1:])],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    # Certaines erreurs réseau du CLI incluent le jeton éphémère dans une URL.
    cleaned = re.sub(r"colab-runtime-proxy-token=[\w.-]+", "colab-runtime-proxy-token=[masqué]",
                     result.stdout + result.stderr)
    if result.returncode or "Upload failed" in cleaned:
        raise RuntimeError(cleaned.strip())
    print(cleaned, end="", flush=True)
    return result.stdout


def upload_file(session, path):
    """Retente un transfert interrompu vers le même nom de fichier."""
    for attempt in range(3):
        try:
            colab(session, "upload", path, f"{ROOT}/data/{path.name}")
            return
        except RuntimeError:
            if attempt == 2:
                raise
            print(f"Nouvel envoi de {path.name}", flush=True)
            time.sleep(3)


def split_prefix(source, folder, manifest):
    """Découpe le court préfixe en morceaux acceptés par l'API Colab."""
    remaining = 2 * (manifest["short_targets"] + 1)
    digest = hashlib.sha256()
    parts = []
    with gzip.open(source, "rb") as stream:
        while remaining:
            chunk = stream.read(min(remaining, CHUNK))
            if not chunk:
                raise ValueError("Le préfixe est tronqué.")
            target = folder / f"part.{len(parts):03}"
            target.write_bytes(chunk)
            parts.append(target)
            digest.update(chunk)
            remaining -= len(chunk)
    if digest.hexdigest() != manifest["short_bin_sha256"]:
        raise ValueError("Le préfixe diffère du manifeste.")
    return parts


def remote_code(commit):
    """Écrit un processus distant dont le journal reste lisible pendant l'entraînement."""
    return f'''from pathlib import Path
import subprocess
import sys

root = Path({ROOT!r})
worker = r"""import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path({ROOT!r})
result = root / "result"
repo = root / "repo"
data = root / "data"
parts = sorted(data.glob("part.*"))
with (data / "train.bin").open("xb") as output:
    for part in parts:
        with part.open("rb") as stream:
            shutil.copyfileobj(stream, output)

repo.mkdir()
def run(*args):
    # Chaque étape vérifie son statut avant la suivante.
    subprocess.run(list(map(str, args)), cwd=repo, check=True)

try:
    run("git", "init", "-q")
    run("git", "fetch", "--depth", "1", "https://github.com/MatisseGrl/piscine_Lab.git", {commit!r})
    run("git", "checkout", "--detach", "FETCH_HEAD")
    run(sys.executable, "-m", "pip", "install", "-q", "tokenizers==0.23.3")
    common = [sys.executable, "-m", "scripts.run_chat_budget"]
    run(*common, "pretrain", "--data", data, "--out", result, "--archive", data / "train.bin", "--steps", 3052)
    run(*common, "adapt", "--data", data, "--out", result, "--checkpoint", result / "pretrain/pretrained.pt")
except Exception:
    (root / "status.json").write_text(json.dumps({{"status": "error"}}))
    raise
else:
    (root / "status.json").write_text(json.dumps({{"status": "complete"}}))
"""
(root / "worker.py").write_text(worker, encoding="utf-8")
with (root / "run.log").open("xb") as log:
    child = subprocess.Popen([sys.executable, "-u", str(root / "worker.py")], stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=True)
print("Étapes GPU lancées, PID :", child.pid)
'''


def main():
    """Prépare les entrées locales, les envoie puis démarre les étapes GPU."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--session", default="piscine-chat-budget-100m")
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    manifest_path = args.archive.with_name("manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["short_targets"] != 3052 * 64 * 512:
        parser.error("Le manifeste n'indique pas le budget court de 100 M.")
    with TemporaryDirectory(prefix="piscine-chat-colab-") as directory:
        folder = Path(directory)
        parts = split_prefix(args.archive, folder, manifest)
        setup = folder / "setup.py"
        setup.write_text(
            f"from pathlib import Path\nPath({ROOT + '/data'!r}).mkdir(parents=True, exist_ok=True)\n",
            encoding="utf-8",
        )
        colab(args.session, "exec", "--file", setup)
        present = set(colab(args.session, "ls", ROOT + "/data").splitlines())
        inputs = [manifest_path, *(args.data / name for name in DATA_FILES), *parts]
        with ThreadPoolExecutor(max_workers=2) as pool:
            uploads = [pool.submit(upload_file, args.session, path)
                       for path in inputs if path.name not in present]
            for upload in uploads:
                upload.result()
        start = folder / "start.py"
        start.write_text(remote_code(args.commit), encoding="utf-8")
        colab(args.session, "exec", "--file", start)


if __name__ == "__main__":
    main()
