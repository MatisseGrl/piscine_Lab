"""Prépare les flux de l’ablation sans lancer d’entraînement du modèle."""

import argparse
from contextlib import ExitStack
import gzip
from hashlib import file_digest, sha256 as digest_bytes
from itertools import islice
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory, TemporaryFile

SEED = 42
SHARES = {"wikipedia_fr": 80, "common_crawl": 12, "assemblee_nationale": 8}
VARIANTS = {"raw": "clean/raw", "clean": "clean", "dedup": "dedup/final"}
KIT_REV = "3709c85ddaabfcd688d6eea80a5c5ed90605b549"
ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    """Lit un fichier JSON en UTF-8."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    """Écrit les métadonnées en UTF-8."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    """Calcule le SHA-256 du fichier réellement utilisé."""
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def kit_command(kit, module, *args):
    """Appelle le module officiel depuis le kit, dans le même environnement Python."""
    subprocess.run([sys.executable, "-m", module, *map(str, args)], cwd=kit, check=True)


def quotas(size):
    """Répartit les positions selon le mélange, avec compensation des arrondis."""
    limits = [0]
    for percent in SHARES.values():
        limits.append(limits[-1] + percent)
    return {
        source: size * end // 100 - size * start // 100
        for source, start, end in zip(SHARES, limits, limits[1:])
    }


def audited_sources(interim, validation):
    """Vérifie que les neuf archives sont celles des audits à zéro recouvrement."""
    clean = read_json(interim / "clean/stats.json")
    dedup = read_json(interim / "dedup/final/stats.json")
    audit = dedup["audit"]
    if (audit["validation_docs"], audit["matching_training_docs"], audit["mean_overlap"]) != (230, 0, 0):
        raise ValueError("Audit MinHash invalide")
    # Le mode texte élimine les différences CRLF/LF d'un checkout du kit.
    val_hash = digest_bytes(validation.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    if clean["validation_sha256"] != audit["validation_sha256"] or clean["validation_sha256"] not in {
        val_hash, sha256(validation)
    }:
        raise ValueError("Validation publique différente de celle des audits")
    result = {}
    for variant, folder in VARIANTS.items():
        if variant != "dedup":
            report = read_json(interim / f"clean/audit-{variant}.json")
            if report["n_documents_evalues"] != 230 or any(r["recouvrement"] for r in report["detail"]):
                raise ValueError(f"Audit invalide pour {variant}")
        result[variant] = {}
        for source in SHARES:
            path = interim / folder / f"{source}.jsonl.gz"
            row = clean["sources"][source]
            if variant == "dedup":
                expected = dedup["minhash"][source]["sha256"]
                size = dedup["minhash"][source]["bytes"]
            else:
                expected = row[f"{variant}_sha256"]
                size = row["bytes_after" if variant == "clean" else "bytes_before"]
            if sha256(path) != expected:
                raise ValueError(f"Archive différente de celle de l’audit : {path}")
            result[variant][source] = (path, size, expected)
            print(f"Audit vérifié : {variant}/{source}", flush=True)
    return result, val_hash


def shuffled_texts(path, rate, scratch):
    """Tire des documents sur toute l’archive, puis mélange leurs positions sur disque."""
    rng = random.Random(SEED)
    with TemporaryFile(dir=scratch) as spool:
        offsets = []
        with gzip.open(path, "rb") as stream:
            for line in stream:
                if rng.random() < rate:
                    offsets.append(spool.tell())
                    spool.write(line)
        rng.shuffle(offsets)
        for offset in offsets:
            spool.seek(offset)
            yield json.loads(spool.readline())["text"]


def train_tokenizer(kit, sources, scratch):
    """Entraîne le tokenizer commun sur 10 Mo de textes nettoyés, dosés en octets UTF-8."""
    sample = scratch / "tokenizer-sample.jsonl"
    used = {}
    with sample.open("w", encoding="utf-8", newline="\n") as stream:
        for source, limit in quotas(10_000_000).items():
            path, size, _ = sources[source]
            remaining = limit
            # Le tirage initial contient en moyenne deux fois le volume nécessaire.
            for text in shuffled_texts(path, min(1, 2 * limit / size), scratch):
                data = text.encode("utf-8")
                # Termine à une frontière UTF-8 même si le quota coupe un document.
                fits = len(data) < remaining
                chunk = data[:remaining].decode("utf-8", errors="ignore")
                if chunk:
                    stream.write(json.dumps({"text": chunk}, ensure_ascii=False) + "\n")
                remaining -= len(chunk.encode("utf-8"))
                if not fits:
                    break
            if remaining > 3:
                raise ValueError(f"Échantillon trop petit : {source}")
            used[source] = limit - remaining
    tokenizer = scratch / "tokenizer.json"
    kit_command(kit, "ftb.tokenizer", "train", "--inputs", sample, "--out", tokenizer)
    return tokenizer, {"bytes_by_source": used, "sample_sha256": sha256(sample)}


def encode_source(entry, target, tokenizer, stream, scratch):
    """Écrit les tokens d’une source, avec séparateur de document et sans remise."""
    import numpy as np

    path, size, _ = entry
    # Suréchantillonne en octets pour couvrir le quota malgré la compression du BPE.
    texts = shuffled_texts(path, min(1, 10 * target / size), scratch)
    remaining = target
    while batch := list(islice(texts, 128)):
        for ids in tokenizer.encode_batch(batch):
            ids.append(tokenizer.eot_id)
            tokens = ids[:remaining]
            stream.write(np.asarray(tokens, dtype="<u2").tobytes())
            remaining -= len(tokens)
            if not remaining:
                return
    raise ValueError(f"Quota insuffisant dans {path} : {remaining} tokens manquants")


def prepare_variant(folder, sources, tokenizer, config, scratch):
    """Assemble un flux au format du kit avec le même mélange dans chaque fenêtre."""
    import numpy as np
    import tokenizers

    train = config["train"]
    seen = train["max_steps"] * train["tokens_per_step"]
    window = train["shuffle_window_steps"] * train["tokens_per_step"]
    counts = quotas(seen)
    folder.mkdir()
    with ExitStack() as stack:
        inputs = {}
        for source, count in counts.items():
            print(f"{folder.name}/{source} : {count:,} tokens", flush=True)
            stream = stack.enter_context(TemporaryFile(dir=scratch))
            encode_source(sources[source], count, tokenizer, stream, scratch)
            stream.seek(0)
            inputs[source] = stream
        rng = random.Random(SEED)
        with (folder / "train.bin").open("wb") as output:
            # Le premier token sert de contexte. Le kit note les positions 1 à seen.
            output.write(np.asarray([tokenizer.eot_id], dtype="<u2").tobytes())
            for start in range(0, seen, window):
                # Les quotas cumulés évitent de propager les arrondis entre fenêtres.
                before, after = quotas(start), quotas(min(start + window, seen))
                order = list(SHARES)
                rng.shuffle(order)
                for source in order:
                    length = 2 * (after[source] - before[source])
                    chunk = inputs[source].read(length)
                    if len(chunk) != length:
                        raise ValueError(f"Flux incomplet : {source}")
                    output.write(chunk)
    metadata = {
        "kit_version": config["kit_version"], "tokenizers_version": tokenizers.__version__,
        "dataset_sha256": sha256(folder / "train.bin"), "tokenizer_sha256": tokenizer.sha256,
        "n_tokens": seen + 1, "budget_tokens": train["budget_tokens"], "passes_over_data": 1.0,
        "tokens_seen_by_source": counts, "input_sha256_by_source": {
            source: entry[2] for source, entry in sources.items()
        },
    }
    write_json(folder / "data_meta.json", metadata)
    return metadata


def prepare(kit, interim, output):
    """Construit et publie ensemble le tokenizer, les trois flux et leur manifeste."""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    sys.path.insert(0, str(kit))
    from ftb import VALIDATION_PATH, load_config
    from ftb.tokenizer import load_tokenizer

    if output.exists():
        raise FileExistsError(f"Choisis un dossier de sortie neuf : {output}")
    config = load_config()
    sources, validation_hash = audited_sources(interim, VALIDATION_PATH)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as name:
        scratch = Path(name)
        staged = scratch / "ablation"
        staged.mkdir()
        tokenizer, sample = train_tokenizer(kit, sources["clean"], scratch)
        shutil.copyfile(tokenizer, staged / "tokenizer.json")
        tok = load_tokenizer(tokenizer)
        manifest = {
            "seed": SEED, "source_percent": SHARES, "kit_revision": KIT_REV,
            "validation_sha256": validation_hash, "validation_documents": 230,
            "validation_bytes": sum(
                len(json.loads(line)["text"].encode("utf-8"))
                for line in VALIDATION_PATH.read_text(encoding="utf-8").split("\n") if line.strip()
            ),
            "config": config, "tokenizer_sha256": tok.sha256, "tokenizer_sample": sample,
            "variants": {},
        }
        for variant in VARIANTS:
            manifest["variants"][variant] = prepare_variant(
                staged / variant, sources[variant], tok, config, scratch
            )
            print(variant, manifest["variants"][variant]["dataset_sha256"], flush=True)
        write_json(staged / "manifest.json", manifest)
        staged.rename(output)


def main():
    """Résout les chemins locaux, y compris depuis un autre checkout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=ROOT / "kit/Piscine-official")
    parser.add_argument("--interim", type=Path, default=ROOT / "data/interim")
    parser.add_argument("--out", type=Path, default=ROOT / "data/processed/ablation")
    args = parser.parse_args()
    kit = args.kit.resolve()
    if subprocess.check_output(["git", "-C", str(kit), "rev-parse", "HEAD"], text=True).strip() != KIT_REV:
        raise ValueError(f"Clone du kit attendu à la révision {KIT_REV}")
    if subprocess.check_output(["git", "-C", str(kit), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("Le clone du kit contient des modifications")
    prepare(kit, args.interim.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
