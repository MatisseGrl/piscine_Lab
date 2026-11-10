"""Étape commune de transformation : lecture, filtre ou masquage, relecture et audit.

Utilisée par `pipeline.quality` et `pipeline.pii`. Une étape lit un dossier de JSONL gzip
(sortie MinHash, qualité ou PII), applique une transformation document par document, écrit
un dossier neuf (jamais d'écrasement), relit la sortie, compte documents et octets UTF-8
avant/après, calcule les SHA-256 et vérifie zéro recouvrement de 13 mots avec la
validation publique avant publication.
"""

import json
import random
from collections import Counter
from contextlib import ExitStack
from itertools import islice
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from pipeline.clean import ValidationGuard, digest, open_output, write_document
from pipeline.dedup import SEED, SOURCES, prepare_full_run, read_rows, source_path, write_json

VALIDATION_DOCS = 230
EXAMPLES = 3


def project_seconds(elapsed, done_bytes, total_bytes):
    """Projette la durée sur tout le volume, proportionnellement aux octets traités."""
    return elapsed * total_bytes / done_bytes


def snippet_source(text, masker, size=100):
    """Début du texte (coupé à un mot entier), passé par le masquage, limité à `size`."""
    head = " ".join(text[:400].split())
    # Retire le dernier mot, peut-être coupé, pour ne pas laisser un fragment de donnée.
    head = head.rsplit(" ", 1)[0] if len(text) > 400 and " " in head else head
    return masker(head)[0][:size]


def expected_inputs(src):
    """Lit les volumes et SHA-256 attendus dans les statistiques du dossier d'entrée."""
    stats = json.loads((src / "stats.json").read_text(encoding="utf-8"))
    table = stats["minhash"] if "minhash" in stats else stats["sources"]
    return {source: table[source] for source in SOURCES}


def load_validation(kit):
    """Charge les 230 documents de validation publique et leur empreinte."""
    path = kit / "data" / "validation.jsonl"
    with path.open(encoding="utf-8") as stream:
        texts = [json.loads(line)["text"] for line in stream if line.strip()]
    if len(texts) != VALIDATION_DOCS:
        raise ValueError("Les 230 documents de validation publique sont requis")
    return ValidationGuard(texts), digest(path)


def verify_output(stage, guard, counts):
    """Relit chaque sortie : volumes, recouvrement avec la validation, puis SHA-256."""
    for source in SOURCES:
        path = source_path(stage, source)
        docs = byte_count = 0
        for row in read_rows(path):
            docs += 1
            byte_count += len(row["text"].encode("utf-8"))
            if guard.matches(row["text"]):
                raise ValueError(f"Recouvrement avec la validation dans {source}, id={row['id']}")
        if (docs, byte_count) != (counts[source]["docs"], counts[source]["bytes"]):
            raise ValueError(f"Compteurs de sortie incorrects : {path}")
        counts[source]["sha256"] = digest(path)


def run_stage(src, out, transform, kit, *, name, limit=None, check_power=True):
    """Applique `transform` à chaque source et publie le dossier de sortie après audit.

    `transform.apply(row)` renvoie (ligne ou None, compte par motif) ; `transform.view`
    fabrique un extrait sans donnée personnelle ; `transform.summary()` ajoute des mesures.
    """
    src, out, kit = Path(src), Path(out), Path(kit)
    pilot = limit is not None
    if out.exists():
        raise FileExistsError(f"La sortie existe déjà : {out}")
    if not pilot and check_power:
        prepare_full_run()
    expected = expected_inputs(src)
    guard, validation_sha = load_validation(kit)
    rng = random.Random(SEED)
    started = perf_counter()
    out.parent.mkdir(parents=True, exist_ok=True)
    counts = {}
    with TemporaryDirectory(dir=out.parent) as tmp:
        stage = Path(tmp) / out.name
        stage.mkdir()
        for source in SOURCES:
            path = source_path(src, source)
            if digest(path) != expected[source]["sha256"]:
                raise ValueError(f"SHA-256 de l'entrée incorrect : {path}")
            entry = dict(docs_before=0, bytes_before=0, docs=0, bytes=0, rejected=Counter(),
                         tags=Counter(), docs_with=Counter(), examples={})
            seen = Counter()
            rows = read_rows(path)
            with ExitStack() as stack:
                writer = open_output(stack, stage, source)
                for row in islice(rows, limit):
                    size = len(row["text"].encode("utf-8"))
                    entry["docs_before"] += 1
                    entry["bytes_before"] += size
                    new_row, tags = transform.apply(row)
                    for tag, number in tags.items():
                        entry["tags"][tag] += number
                        entry["docs_with"][tag] += 1
                        if new_row is None:
                            entry["rejected"][tag] += 1
                    if new_row is not None:
                        entry["docs"] += 1
                        entry["bytes"] += len(new_row["text"].encode("utf-8"))
                        write_document(writer, new_row)
                    # Échantillon aléatoire à graine fixe de quelques documents par motif.
                    for tag in tags or ("kept",):
                        seen[tag] += 1
                        pool = entry["examples"].setdefault(tag, [])
                        slot = len(pool) if len(pool) < EXAMPLES else rng.randrange(seen[tag])
                        if slot < EXAMPLES:
                            item = {"id": row["id"], "snippet": transform.view(row, new_row, tag)}
                            if slot == len(pool):
                                pool.append(item)
                            else:
                                pool[slot] = item
            if not pilot and (entry["docs_before"], entry["bytes_before"]) != (
                expected[source]["docs"], expected[source]["bytes"],
            ):
                raise ValueError(f"Compteurs d'entrée incorrects : {path}")
            for key in ("rejected", "tags", "docs_with"):
                entry[key] = dict(entry[key])
            counts[source] = entry
            print(f"{name} {source} : {entry['docs_before']:,} -> {entry['docs']:,} documents", flush=True)
        verify_output(stage, guard, counts)
        elapsed = perf_counter() - started
        total_before = sum(counts[source]["bytes_before"] for source in SOURCES)
        stats = {
            "name": name, "params": transform.params, "pilot": pilot, "limit": limit, "seed": SEED,
            "input_stats_sha256": digest(src / "stats.json"), "sources": counts,
            "summary": transform.summary(),
            "totals": {
                "docs_before": sum(c["docs_before"] for c in counts.values()),
                "docs": sum(c["docs"] for c in counts.values()),
                "bytes_before": total_before, "bytes": sum(c["bytes"] for c in counts.values()),
            },
            "audit": {"validation_docs": VALIDATION_DOCS, "matching_training_docs": 0,
                      "mean_overlap": 0.0, "flagged_validation_docs": 0,
                      "validation_sha256": validation_sha},
            "seconds": elapsed,
        }
        if pilot:
            full_bytes = sum(expected[source]["bytes"] for source in SOURCES)
            stats["projection_seconds"] = project_seconds(elapsed, total_before, full_bytes)
        write_json(stage / "stats.json", stats)
        stage.rename(out)
    return stats

