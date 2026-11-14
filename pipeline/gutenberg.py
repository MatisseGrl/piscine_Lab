"""Collecte et nettoyage de Project Gutenberg en français (livres du domaine public).

Étapes : catalogue officiel (langue `fr`) -> exclusions (corpus Molière du kit, tout Molière,
pièces de la validation) -> téléchargement + manifeste -> retrait des en-têtes, pieds de page,
notes de transcription et tables des matières -> mêmes étapes que les autres sources
(ftfy, fastText >= 0,80, contamination 13 mots, dédup exacte normalisée, MinHash 0,97,
filtre qualité). Un document = un livre. Sorties dans `data/interim/gutenberg/`.

    uv run python -m pipeline.gutenberg
"""

import argparse
import csv
import gzip
import io
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

import numpy as np

from pipeline.clean import (
    INTERIM, MODEL, MODEL_HASH, MODEL_URL, ValidationGuard, default_kit, digest,
    process_source,
)
from pipeline.collect import RAW, download
from pipeline.dedup import (
    BANDS, ExactDeduper, build_links, select_matches, shingles, signature,
)
from pipeline.quality import evaluate

SOURCE = "gutenberg_fr"
CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
BOOK_URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
USER_AGENT = "piscine-lab-ece-research/1.0 (projet etudiant, collecte polie)"
RAW_DIR = RAW / "gutenberg"
OUT_DIR = INTERIM / "gutenberg"
THRESHOLD = 0.97
SEED = 42

# eBooks du corpus Molière du kit : leur texte est dans la validation Molière.
KIT_MOLIERE_IDS = frozenset({40086, 43535, 50173, 57270})
# Pièces présentes dans la validation du kit (Le Misanthrope, L'Avare, Le Sicilien).
VALIDATION_TITLES = re.compile(r"misanthrope|l['’]avare|sicilien", re.IGNORECASE)
MOLIERE_AUTHOR = re.compile(r"moli[eè]re", re.IGNORECASE)

START = re.compile(r"\*\*\*\s*START OF [^\n]*", re.IGNORECASE)
END = re.compile(r"\*\*\*\s*END OF [^\n]*", re.IGNORECASE)
NOTE = re.compile(
    r"^\[?\s*(?:notes?)\s+(?:du|de la|de l['’]|des)\s*(?:transcript|transcription|éditeur)",
    re.IGNORECASE,
)
ILLUSTRATION = re.compile(r"^\[\s*(?:illustration|image)[^\]]*\]$", re.IGNORECASE)
TOC_TITLE = re.compile(
    r"^(?:table(?: générale| analytique)?(?: des (?:matières|chapitres))?|sommaire|contents?|matières)\s*\.?$",
    re.IGNORECASE,
)
TOC_ENTRY_MAX = 150  # un bloc plus long qu'une entrée de table marque la fin de la table
TOC_BLOCKS_MAX = 400


def parse_catalog(csv_text):
    """Lit le catalogue officiel et ne garde que les textes dont la langue est exactement `fr`."""
    rows = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        if row["Type"] != "Text" or row["Language"].strip() != "fr":
            continue
        rows.append({
            "id": int(row["Text#"]), "title": row["Title"].replace("\n", " "),
            "authors": row["Authors"].replace("\n", " "), "issued": row["Issued"],
        })
    return rows


def exclusion_reason(row):
    """Motif d'exclusion obligatoire d'un livre (kit Molière, auteur Molière, pièce de validation)."""
    if row["id"] in KIT_MOLIERE_IDS:
        return "kit_moliere_id"
    if MOLIERE_AUTHOR.search(row["authors"]) or MOLIERE_AUTHOR.search(row["title"]):
        return "moliere_author"
    if VALIDATION_TITLES.search(row["title"]):
        return "validation_title"
    return None


def strip_gutenberg(text):
    """Retire en-tête, pied de page, notes de transcription, illustrations et tables des matières.

    Renvoie (texte, None) ou (None, motif de rejet).
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    start, end = START.search(text), END.search(text)
    if not start or not end or end.start() < start.end():
        return None, "no_markers"
    body = text[start.end():end.start()]
    blocks = re.split(r"\n\s*\n", body.strip())
    kept = []
    index = 0
    while index < len(blocks):
        block = blocks[index].strip()
        if NOTE.match(block) or ILLUSTRATION.match(block):
            index += 1
        elif TOC_TITLE.match(block):
            # Saute le titre puis les blocs courts qui suivent (entrées de la table).
            index += 1
            skipped = 0
            while index < len(blocks) and skipped < TOC_BLOCKS_MAX and len(blocks[index].strip()) <= TOC_ENTRY_MAX:
                index += 1
                skipped += 1
        else:
            kept.append(block)
            index += 1
    return "\n\n".join(kept).strip(), None


def fetch(url):
    """Télécharge une URL avec un agent identifiable et quelques essais (None si 404)."""
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Échec de téléchargement : {url}")


def collect(rows, workers=4, delay=0.3):
    """Télécharge les livres dans `data/raw/gutenberg/` (reprise possible) et renvoie le manifeste."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    def one(row):
        """Télécharge un livre sauf s'il est déjà en cache, puis calcule son empreinte."""
        path = RAW_DIR / f"{row['id']}.txt"
        if not path.exists():
            data = fetch(BOOK_URL.format(id=row["id"]))
            time.sleep(delay)
            if data is None:
                return {**row, "status": "not_found"}
            path.write_bytes(data)
        data = path.read_bytes()
        return {**row, "status": "ok", "bytes": len(data), "sha256": sha256(data).hexdigest(),
                "url": BOOK_URL.format(id=row["id"])}

    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, rows))


def process_books(rows, predict, guard):
    """Nettoie les livres (ftfy, langue, contamination 13 mots) puis applique le filtre qualité.

    `rows` : dicts {id, text}. Renvoie (livres gardés, statistiques avec rejets par motif).
    """
    jsonl = io.StringIO()
    stats = process_source(((row["id"], row["text"]) for row in rows), SOURCE, jsonl, None, predict, guard)
    rejected = Counter(stats["rejected_docs_by_reason"])
    rejected_bytes = Counter(stats["rejected_input_bytes_by_reason"])
    originals = {row["id"]: row["text"] for row in rows}
    kept = []
    for line in jsonl.getvalue().splitlines():
        row = json.loads(line)
        reason, _ = evaluate(row["text"], SOURCE)
        if reason:
            rejected[reason] += 1
            rejected_bytes[reason] += len(originals[row["id"]].encode("utf-8"))
            stats["docs_after"] -= 1
            stats["bytes_after"] -= len(row["text"].encode("utf-8"))
            continue
        kept.append(row)
    stats["rejected_docs_by_reason"] = dict(rejected)
    stats["rejected_input_bytes_by_reason"] = dict(rejected_bytes)
    return kept, stats


def dedup_books(rows, threshold=THRESHOLD):
    """Dédup exacte sur texte normalisé, puis MinHash (mêmes fonctions que `pipeline.dedup`)."""
    deduper = ExactDeduper()
    survivors = []
    exact_rejected = 0
    for row in rows:
        if deduper.add(SOURCE, row["text"]) == "kept":
            survivors.append(row)
        else:
            exact_rejected += 1
    # On ne garde que taille et signature de chaque livre : les ensembles de shingles
    # sont recalculés à la demande (sinon des centaines de millions de chaînes en mémoire).
    sizes = np.empty(len(survivors), dtype=np.uint32)
    keys = np.empty((len(survivors), BANDS), dtype=np.uint64)
    for position, row in enumerate(survivors):
        items = shingles(row["text"])
        sizes[position] = len(items)
        keys[position] = signature(items)
    links = build_links(keys) if len(survivors) else np.empty((0, BANDS), dtype=np.int32)
    kept_mask, _ = select_matches(
        links, sizes, lru_cache(maxsize=8)(lambda i: shingles(survivors[i]["text"])),
        threshold, inspect=False,
    )
    kept = [row for row, keep in zip(survivors, kept_mask) if keep]
    return kept, {"exact_rejected": exact_rejected, "minhash_rejected": len(survivors) - len(kept)}


def load_guard(kit):
    """Garde-fou 13 mots : 230 documents publics du kit + validation Molière."""
    validation = kit / "data" / "validation.jsonl"
    moliere = kit / "corpus" / "moliere_val.txt"
    with validation.open(encoding="utf-8") as stream:
        texts = [json.loads(line)["text"] for line in stream if line.strip()]
    if len(texts) != 230:
        raise ValueError("Les 230 documents de validation publique du kit sont requis")
    guard = ValidationGuard([*texts, *moliere.read_text(encoding="utf-8").split("=====")])
    return guard, validation, moliere


def run(out, kit, limit):
    """Chaîne complète : catalogue, exclusions, collecte, nettoyage, dédup, sorties et stats."""
    import fasttext

    if out.exists():
        raise FileExistsError(f"Choisis un dossier de sortie neuf : {out}")
    guard, validation, moliere = load_guard(kit)
    download(MODEL_URL, MODEL, size=131_266_198, checksum=("sha256", MODEL_HASH))
    model = fasttext.load_model(str(MODEL))

    def predict(text):
        """Renvoie la meilleure langue et le score du modèle figé."""
        labels, scores = model.predict(text, k=1)
        return labels[0].removeprefix("__label__"), float(scores[0])

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    catalog_path = RAW_DIR / "pg_catalog.csv"
    if not catalog_path.exists():
        catalog_path.write_bytes(fetch(CATALOG_URL))
    catalog = parse_catalog(catalog_path.read_text(encoding="utf-8"))
    excluded = Counter()
    wanted = []
    for row in sorted(catalog, key=lambda r: r["id"]):
        reason = exclusion_reason(row)
        if reason:
            excluded[reason] += 1
        else:
            wanted.append(row)
    if limit:
        wanted = wanted[:limit]
    print(f"{len(catalog)} livres fr au catalogue, {len(wanted)} à collecter", flush=True)
    manifest = collect(wanted)
    (RAW_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    # Retrait des en-têtes, pieds de page, notes et tables.
    stripped, strip_rejected, raw_bytes = [], Counter(), 0
    for entry in manifest:
        if entry["status"] != "ok":
            strip_rejected[entry["status"]] += 1
            continue
        raw = (RAW_DIR / f"{entry['id']}.txt").read_bytes()
        raw_bytes += len(raw)
        text, reason = strip_gutenberg(raw.decode("utf-8", errors="replace"))
        if reason or not text:
            strip_rejected[reason or "empty"] += 1
            continue
        stripped.append({"id": entry["id"], "text": text})
    stripped_bytes = sum(len(r["text"].encode("utf-8")) for r in stripped)
    print(f"{len(stripped)} livres après retrait des en-têtes", flush=True)

    cleaned, clean_stats = process_books(stripped, predict, guard)
    kept, dedup_stats = dedup_books(cleaned, THRESHOLD)
    out.mkdir(parents=True)
    path = out / f"{SOURCE}.jsonl.gz"
    meta = {entry["id"]: entry for entry in manifest}
    with path.open("wb") as raw_file, gzip.GzipFile(filename="", fileobj=raw_file, mode="wb", mtime=0) as gz:
        for row in kept:
            row["source"] = SOURCE
            row["title"], row["authors"] = meta[row["id"]]["title"], meta[row["id"]]["authors"]
            gz.write((json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
    # Dernier contrôle : aucun livre gardé ne partage 13 mots avec la validation.
    assert not any(guard.matches(row["text"]) for row in kept)
    stats = {
        "source": SOURCE, "seed": SEED, "language_threshold": 0.80, "minhash_threshold": THRESHOLD,
        "collected_date": time.strftime("%Y-%m-%d"), "catalog_url": CATALOG_URL,
        "catalog_sha256": digest(catalog_path), "validation_sha256": digest(validation),
        "moliere_validation_sha256": digest(moliere), "fasttext_model_sha256": MODEL_HASH,
        "catalog_french_books": len(catalog), "excluded_before_download": dict(excluded),
        "kit_moliere_ids": sorted(KIT_MOLIERE_IDS), "downloaded": len(manifest),
        "download_or_strip_rejects": dict(strip_rejected),
        "raw_bytes_utf8": raw_bytes, "after_strip": {"docs": len(stripped), "bytes_utf8": stripped_bytes},
        "clean": clean_stats, "dedup": dedup_stats,
        "final": {"docs": len(kept), "bytes_utf8": sum(len(r["text"].encode("utf-8")) for r in kept),
                  "bytes": sum(len(r["text"].encode("utf-8")) for r in kept),
                  "sha256": digest(path), "max_overlap_13_words": 0,
                  "overlap_with_validation_docs": 0},
        "manifest_sha256": digest(RAW_DIR / "manifest.json"),
    }
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8", newline="\n")
    print(json.dumps(stats["final"]), flush=True)


def main():
    """Commande unique : `python -m pipeline.gutenberg`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--kit", type=Path, default=default_kit())
    parser.add_argument("--limit", type=int, help="Nombre maximal de livres (test borné).")
    args = parser.parse_args()
    if args.limit and args.out == OUT_DIR:
        parser.error("Indique --out pour séparer le test borné de la sortie complète")
    run(args.out, args.kit, args.limit)


if __name__ == "__main__":
    main()
