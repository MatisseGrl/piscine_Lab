"""Prépare les flux des nouveaux mélanges de sources (M1 à M5) sans lancer d'entraînement.

Même protocole que `pipeline.ablation` et `pipeline.ablation_extra` : tokenizer 8 192 de la
série de base (même SHA-256), mélange compté en tokens, même proportion dans chaque fenêtre
de mélange, graine 42, flux de 100 007 937 tokens au format du kit (uint16 + data_meta.json).
Seule nouveauté : une source trop petite pour son quota est RÉPÉTÉE (nouvelle passe mélangée
avec une autre graine), au plus `MAX_PASSES` fois, et le nombre de répétitions est noté.
"""

import argparse
import gzip
import json
import os
import random
import shutil
import subprocess
import sys
from contextlib import ExitStack
from itertools import islice
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile

from pipeline.ablation import KIT_REV, ROOT, SEED, read_json, sha256, write_json

# Nombre maximal de passes sur une même source (règle du plan : au plus ~3 répétitions).
MAX_PASSES = 3

# Mélanges à construire, en pourcentage de tokens vus. Ordre W, C, A, G, N.
# M1 et M2 sont des lectures de notes orales du mentor : ce sont des hypothèses.
MIXES = {
    "M3": {"wikipedia_fr": 50, "common_crawl": 15, "assemblee_nationale": 10, "gutenberg_fr": 25},
    "M1": {"wikipedia_fr": 35, "common_crawl": 15, "assemblee_nationale": 20, "gutenberg_fr": 30},
    "M2": {"wikipedia_fr": 25, "common_crawl": 25, "assemblee_nationale": 25, "gutenberg_fr": 25},
    "M4": {"wikipedia_fr": 40, "common_crawl": 15, "assemblee_nationale": 15, "gutenberg_fr": 25,
           "wikinews_fr": 5},
    "M5": {"wikipedia_fr": 60, "common_crawl": 12, "assemblee_nationale": 8, "gutenberg_fr": 20},
}


def quotas(size, shares):
    """Répartit `size` positions selon `shares` (en %), avec compensation des arrondis."""
    if sum(shares.values()) != 100:
        raise ValueError(f"Les parts doivent faire 100 % : {shares}")
    limits = [0]
    for percent in shares.values():
        limits.append(limits[-1] + percent)
    # Bornes cumulées : la somme des quotas vaut exactement `size`.
    return {
        source: size * end // 100 - size * start // 100
        for source, start, end in zip(shares, limits, limits[1:])
    }


def shuffled_texts(path, rate, seed, scratch):
    """Tire des documents (taux `rate`) sur toute l'archive puis les mélange avec `seed`."""
    rng = random.Random(seed)
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


def encode_repeating(entry, target, tokenizer, stream, scratch, max_passes=MAX_PASSES):
    """Écrit `target` tokens d'une source ; refait une passe mélangée si le stock ne suffit pas.

    Renvoie le nombre de passes (1,0 = aucune répétition ; 1,8 = 80 % du stock vu deux fois).
    """
    import numpy as np

    path, size, _ = entry
    remaining = target
    stock = None
    for number in range(max_passes):
        # Première passe : suréchantillonnage en octets comme dans pipeline.ablation.
        # Si le quota dépasse le stock, ce taux vaut 1 : la passe lit alors tout le stock.
        # Passes suivantes : tout le stock, dans un autre ordre (graine différente).
        rate = min(1, 10 * target / size) if number == 0 else 1
        written = 0
        texts = shuffled_texts(path, rate, SEED + number, scratch)
        while batch := list(islice(texts, 128)):
            for ids in tokenizer.encode_batch(batch):
                ids.append(tokenizer.eot_id)
                tokens = ids[:remaining]
                stream.write(np.asarray(tokens, dtype="<u2").tobytes())
                remaining -= len(tokens)
                written += len(tokens)
                if not remaining:
                    # Aucune répétition : 1,0. Sinon passes complètes + fraction de la dernière.
                    return 1.0 if stock is None else number + written / stock
        if rate < 1:
            raise ValueError(f"{path} : tirage trop petit, relancer avec un taux plus élevé")
        # Une passe complète a lu tout le stock : sa taille sert à compter les répétitions.
        stock = written
    raise ValueError(f"{path} : {remaining} tokens manquants après {max_passes} passes")


def prepare_mix(folder, sources, shares, tokenizer, config, scratch):
    """Assemble un flux au format du kit, avec le même mélange dans chaque fenêtre."""
    import numpy as np
    import tokenizers

    train = config["train"]
    seen = train["max_steps"] * train["tokens_per_step"]
    window = train["shuffle_window_steps"] * train["tokens_per_step"]
    counts = quotas(seen, shares)
    folder.mkdir()
    passes = {}
    with ExitStack() as stack:
        inputs = {}
        for source, count in counts.items():
            print(f"{folder.name}/{source} : {count:,} tokens", flush=True)
            stream = stack.enter_context(TemporaryFile(dir=scratch))
            passes[source] = encode_repeating(sources[source], count, tokenizer, stream, scratch)
            stream.seek(0)
            inputs[source] = stream
        rng = random.Random(SEED)
        with (folder / "train.bin").open("wb") as output:
            # Le premier token sert de contexte. Le kit note les positions 1 à seen.
            output.write(np.asarray([tokenizer.eot_id], dtype="<u2").tobytes())
            for start in range(0, seen, window):
                # Quotas cumulés : pas de dérive des arrondis entre fenêtres.
                before, after = quotas(start, shares), quotas(min(start + window, seen), shares)
                order = list(shares)
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
        "n_tokens": seen + 1, "budget_tokens": train["budget_tokens"],
        # Clé lue par ftb.train : passes sur le FICHIER, calculée comme le kit (ftb/data.py).
        # Les répétitions internes d'une source sont dans passes_started_by_source.
        "passes_over_data": round(train["budget_tokens"] / max(seen + 1, 1), 3),
        "source_percent": shares, "tokens_seen_by_source": counts,
        "passes_started_by_source": passes,
        "input_sha256_by_source": {source: sources[source][2] for source in shares},
    }
    write_json(folder / "data_meta.json", metadata)
    return metadata


def check_audit(audit, reference, name):
    """Refuse une source dont l'audit de contamination n'est pas à zéro sur la même validation."""
    if audit.get("validation_sha256") != reference:
        raise ValueError(f"{name} : audit fait sur une autre validation")
    if audit.get("overlap", 1) != 0:
        raise ValueError(f"{name} : recouvrement avec la validation")


def load_sources(interim):
    """Renvoie {source: (chemin, octets UTF-8, sha256)} après vérification des audits."""
    quality = read_json(interim / "quality/final/stats.json")
    audit = quality["audit"]
    reference = audit["validation_sha256"]
    if (audit["validation_docs"], audit["matching_training_docs"], audit["mean_overlap"]) != (230, 0, 0):
        raise ValueError("Audit de la sortie qualité invalide")
    result = {}
    # W, C, A : sortie dédup + qualité déjà utilisée pour le meilleur run (1,3304).
    for source, entry in quality["sources"].items():
        path = interim / "quality/final" / f"{source}.jsonl.gz"
        result[source] = (path, entry["bytes"], entry["sha256"])
    # N : Wikinews FR (PR #31), mêmes étapes, audit 13-grammes à zéro.
    news = read_json(interim / "wikinews/stats.json")
    check_audit({"validation_sha256": news["validation_sha256"],
                 "overlap": news["final"]["overlap_with_validation_docs"]}, reference, "wikinews_fr")
    result["wikinews_fr"] = (interim / "wikinews/wikinews_fr.jsonl.gz",
                             news["final"]["bytes"], news["final"]["sha256"])
    # G : Gutenberg FR, branche feat/sources-gutenberg (format de stats à confirmer à l'arrivée).
    book_stats = interim / "gutenberg/stats.json"
    if book_stats.exists():
        books = read_json(book_stats)
        final = books["final"]
        check_audit({"validation_sha256": books["validation_sha256"],
                     "overlap": final["overlap_with_validation_docs"]}, reference, "gutenberg_fr")
        result["gutenberg_fr"] = (interim / "gutenberg/gutenberg_fr.jsonl.gz", final["bytes"],
                                  final["sha256"])
    # Le fichier lu doit être exactement celui de l'audit.
    for source, (path, _, expected) in result.items():
        if sha256(path) != expected:
            raise ValueError(f"SHA-256 différent de celui de l'audit : {path}")
        print(f"Audit vérifié : {source}", flush=True)
    return result


def prepare(kit, interim, base, out, names):
    """Construit les mélanges demandés dans `out/<nom>/`, avec un manifeste commun."""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    sys.path.insert(0, str(kit))
    from ftb import load_config
    from ftb.tokenizer import load_tokenizer

    if out.exists():
        raise FileExistsError(f"Choisis un dossier de sortie neuf : {out}")
    manifest = read_json(base / "manifest.json")
    tokenizer_path = base / "tokenizer.json"
    # Même tokenizer et même config que toute l'ablation, sinon la comparaison ne vaut rien.
    if sha256(tokenizer_path) != manifest["tokenizer_sha256"]:
        raise ValueError("Le tokenizer de la série de base diffère de son manifeste")
    config = load_config()
    if config != manifest["config"] or manifest["kit_revision"] != KIT_REV:
        raise ValueError("Le kit ne correspond pas au protocole de la série de base")
    tokenizer = load_tokenizer(tokenizer_path)
    sources = load_sources(interim)
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as name:
        scratch = Path(name)
        staged = scratch / "mixes"
        staged.mkdir()
        shutil.copyfile(tokenizer_path, staged / "tokenizer.json")
        metas = {}
        for mix in names:
            missing = set(MIXES[mix]) - set(sources)
            if missing:
                raise ValueError(f"{mix} : sources absentes {sorted(missing)}")
            metas[mix] = prepare_mix(staged / mix, sources, MIXES[mix], tokenizer, config, scratch)
            print(mix, metas[mix]["dataset_sha256"], flush=True)
        write_json(staged / "manifest.json", dict(
            manifest, variants=metas, parent_manifest_sha256=sha256(base / "manifest.json"),
            source_bytes={source: entry[1] for source, entry in sources.items()},
        ))
        staged.rename(out)


def main():
    """Résout les chemins, vérifie le clone intact du kit, puis prépare les mélanges."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=ROOT / "kit/Piscine-official")
    parser.add_argument("--interim", type=Path, default=ROOT / "data/interim")
    parser.add_argument("--base", type=Path, default=ROOT / "data/processed/ablation")
    parser.add_argument("--out", type=Path, default=ROOT / "data/processed/mixes")
    parser.add_argument("--mixes", nargs="+", default=list(MIXES), choices=list(MIXES))
    args = parser.parse_args()
    kit = args.kit.resolve()
    if subprocess.check_output(["git", "-C", str(kit), "rev-parse", "HEAD"], text=True).strip() != KIT_REV:
        raise ValueError(f"Clone du kit attendu à la révision {KIT_REV}")
    if subprocess.check_output(["git", "-C", str(kit), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("Le clone du kit contient des modifications")
    prepare(kit, args.interim.resolve(), args.base.resolve(), args.out.resolve(), args.mixes)


if __name__ == "__main__":
    main()
