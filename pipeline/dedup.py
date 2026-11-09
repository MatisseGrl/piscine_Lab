"""Déduplique les sorties nettoyées, avec un point de reprise après le hash exact."""

import argparse
import gzip
import json
import random
import unicodedata
from collections import Counter
from contextlib import ExitStack
from functools import lru_cache
from hashlib import blake2b, sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np

from pipeline.clean import WORD, ValidationGuard, default_kit, digest, open_output, write_document

SOURCES = ("assemblee_nationale", "wikipedia_fr", "common_crawl")
SEED = 42
WIKI_SIZE = 300_000
BANDS = 16
ROWS = 6
ID_BITS = 22
ID_MASK = (1 << ID_BITS) - 1

# Les permutations affines modulo 2⁶⁴ sont tirées séparément.
_rng = np.random.Generator(np.random.PCG64(SEED))
MULTIPLIERS = _rng.bit_generator.random_raw(BANDS * ROWS) | np.uint64(1)
OFFSETS = _rng.bit_generator.random_raw(BANDS * ROWS)


def normalize(text):
    """Met en minuscules, compose les accents et uniformise les espaces."""
    return " ".join(unicodedata.normalize("NFC", text.lower()).split())


class ExactDeduper:
    """Conserve la première occurrence dans l'ordre de priorité du flux."""

    def __init__(self):
        """Associe chaque empreinte à la source du représentant."""
        self.sources = {}

    def add(self, source, text):
        """Classe un texte par rapport à son représentant exact."""
        key = sha256(normalize(text).encode("utf-8")).digest()
        first = self.sources.get(key)
        if first is not None:
            return "within" if first == source else "cross"
        self.sources[key] = source
        return "kept"


def shingles(text):
    """Forme un ensemble de suites de cinq mots, ou la suite courte entière."""
    words = WORD.findall(normalize(text))
    if 0 < len(words) < 5:
        return {" ".join(words)}
    return {" ".join(words[i:i + 5]) for i in range(len(words) - 4)}


def signature(words):
    """Calcule 96 minima puis compacte les six minima de chaque bande."""
    if not words:
        return np.zeros(BANDS, dtype=np.uint64)
    hashes = np.fromiter(
        (int.from_bytes(blake2b(word.encode(), digest_size=8).digest(), "little")
         for word in words),
        dtype=np.uint64, count=len(words),
    )
    minima = np.full(BANDS * ROWS, np.iinfo(np.uint64).max, dtype=np.uint64)
    # Borne la matrice temporaire, même pour un document très long.
    for start in range(0, len(hashes), 1024):
        values = hashes[start:start + 1024, None] * MULTIPLIERS + OFFSETS
        np.minimum(minima, values.min(axis=0), out=minima)
    return np.bitwise_xor.reduce(minima.reshape(BANDS, ROWS), axis=1)


def build_links(keys):
    """Trie chaque bande et relie chaque document au précédent de son seau."""
    count = len(keys)
    if count > ID_MASK + 1:
        raise ValueError("Trop de documents pour les identifiants compacts de l'index")
    links = np.full((count, BANDS), -1, dtype=np.int32)
    ids = np.arange(count, dtype=np.uint64)
    for band in range(BANDS):
        # Les bits bas contiennent l'identifiant et départagent les clés égales.
        packed = (keys[:, band] << ID_BITS) | ids
        packed.sort()
        same = (packed[1:] >> ID_BITS) == (packed[:-1] >> ID_BITS)
        links[packed[1:][same] & ID_MASK, band] = packed[:-1][same] & ID_MASK
    return links


def select_matches(links, sizes, get_shingles, threshold, *, inspect=True, groups=None):
    """Retire un document si un représentant déjà gardé atteint le seuil."""
    kept = np.ones(len(links), dtype=bool)
    examples = {}
    example_counts = Counter()
    for index, bands in enumerate(links):
        if not sizes[index]:
            continue
        seen = set()
        for band, previous in enumerate(bands):
            # Tous les maillons précédents ont déjà été évalués.
            while previous >= 0 and not kept[previous]:
                previous = links[previous, band]
            links[index, band] = previous
            while previous >= 0:
                if previous not in seen:
                    seen.add(previous)
                    low = min(sizes[index], sizes[previous])
                    high = max(sizes[index], sizes[previous])
                    # Le rapport des tailles borne Jaccard avant toute lecture disque.
                    if low and low / high >= (min(0.2, threshold) if inspect else threshold):
                        left, right = get_shingles(index), get_shingles(int(previous))
                        shared = len(left & right)
                        score = shared / (len(left) + len(right) - shared)
                        if inspect:
                            interval = next(
                                label for bound, label in (
                                    (0.6, "0.2–0.6"), (0.75, "0.6–0.75"),
                                    (0.8, "0.75–0.8"), (0.85, "0.8–0.85"),
                                    (0.9, "0.85–0.9"), (0.96, "0.9–0.96"),
                                    (0.97, "0.96–0.97"), (1.0, "0.97–1"), (1.01, "1"),
                                ) if score < bound
                            )
                            if score >= 0.2:
                                key = interval, groups[index] if groups is not None else None
                                if example_counts[key] < 8:
                                    examples.setdefault(interval, []).append((int(previous), index, score))
                                    example_counts[key] += 1
                        if score >= threshold:
                            kept[index] = False
                            break
                previous = links[previous, band]
                while previous >= 0 and not kept[previous]:
                    previous = links[previous, band]
            if not kept[index]:
                break
    return kept, examples


def source_path(folder, source):
    """Retrouve le fichier gzip associé à une source."""
    return folder / f"{source}.jsonl.gz"


def read_rows(path, positions=None):
    """Décode les lignes retenues en conservant l'ordre du fichier."""
    with gzip.open(path, "rb") as stream:
        for index, line in enumerate(stream):
            if positions is None or index in positions:
                yield json.loads(line)


def sample(count, size):
    """Tire des positions sans remise avec une graine fixe."""
    return set(random.Random(SEED).sample(range(count), min(size, count)))


def write_json(path, value):
    """Écrit un rapport lisible et stable."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def exact(clean, output, pilot):
    """Vérifie le nettoyage et publie la dédup exacte dans un dossier neuf."""
    stats = json.loads((clean / "stats.json").read_text(encoding="utf-8"))
    selection = stats["common_crawl_selection"]
    if (stats["limit_per_source"] is not None or selection["max_bytes"] != 1_050_000_000
            or selection["archive_bytes"] != 1_019_886_136 or len(selection["archives"]) != 10):
        raise ValueError("Les fichiers doivent provenir du nettoyage plafonné à 1,05 Go")
    deduper = ExactDeduper()
    report = {"pilot": pilot, "clean_stats_sha256": digest(clean / "stats.json"),
              "validation_sha256": stats["validation_sha256"], "sources": {}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as tmp:
        stage = Path(tmp) / "exact"
        stage.mkdir()
        for source in SOURCES:
            start = perf_counter()
            expected = stats["sources"][source]
            path = source_path(clean, source)
            if digest(path) != expected["clean_sha256"]:
                raise ValueError(f"SHA-256 du nettoyage incorrect : {path}")
            positions = None
            if pilot:
                positions = sample(expected["docs_after"], 50_000 if source == "wikipedia_fr" else 6000)
            counts = dict(input_docs=0, input_bytes=0, docs=0, bytes=0, within=0, cross=0)
            with ExitStack() as stack:
                writer = open_output(stack, stage, source)
                for row in read_rows(path, positions):
                    if row["source"] != source:
                        raise ValueError(f"Source inattendue dans {path}")
                    size = len(row["text"].encode("utf-8"))
                    counts["input_docs"] += 1
                    counts["input_bytes"] += size
                    decision = deduper.add(source, row["text"])
                    if decision == "kept":
                        counts["docs"] += 1
                        counts["bytes"] += size
                        write_document(writer, row)
                    else:
                        counts[decision] += 1
                    if not pilot and counts["input_docs"] % 250_000 == 0:
                        print(f"Exact {source} : {counts['input_docs']:,} documents lus", flush=True)
            if not pilot and (counts["input_docs"], counts["input_bytes"]) != (
                expected["docs_after"], expected["bytes_after"],
            ):
                raise ValueError(f"Compteurs du nettoyage incorrects : {path}")
            counts["sha256"] = digest(source_path(stage, source))
            counts["seconds"] = perf_counter() - start
            report["sources"][source] = counts
            print(f"Exact {source} : {counts}", flush=True)
        write_json(stage / "stats.json", report)
        stage.rename(output)
    return report


def build_index(exact_folder, report, spool):
    """Signe les textes retenus et conserve leurs lignes originales sur disque."""
    total = sum(
        min(WIKI_SIZE, counts["docs"]) if source == "wikipedia_fr" else counts["docs"]
        for source, counts in report["sources"].items()
    )
    keys = np.empty((total, BANDS), dtype=np.uint64)
    sizes = np.empty(total, dtype=np.uint32)
    offsets = np.empty(total, dtype=np.uint64)
    intervals = {}
    index = 0
    for source in SOURCES:
        start = perf_counter()
        counts = report["sources"][source]
        path = source_path(exact_folder, source)
        if digest(path) != counts["sha256"]:
            raise ValueError(f"SHA-256 de la dédup exacte incorrect : {path}")
        positions = None
        if source == "wikipedia_fr" and counts["docs"] > WIKI_SIZE:
            positions = sample(counts["docs"], WIKI_SIZE)
        first = index
        byte_count = 0
        for row in read_rows(path, positions):
            words = shingles(row["text"])
            keys[index] = signature(words)
            sizes[index] = len(words)
            offsets[index] = spool.tell()
            spool.write(json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\n")
            byte_count += len(row["text"].encode("utf-8"))
            index += 1
            if (index - first) % 25_000 == 0:
                print(f"Signatures {source} : {index - first:,}", flush=True)
        if index - first != (len(positions) if positions is not None else counts["docs"]):
            raise ValueError(f"Nombre de documents inattendu : {path}")
        intervals[source] = {
            "start": first, "stop": index, "docs": index - first, "bytes": byte_count,
            "seconds": perf_counter() - start,
        }
        print(f"Signatures {source} : {intervals[source]}", flush=True)
    # Les clés ne sont nécessaires que le temps de construire les maillons.
    links = build_links(keys)
    memory = {
        "keys": keys.nbytes, "links": links.nbytes, "offsets": offsets.nbytes,
        "sizes": sizes.nbytes,
    }
    return links, sizes, offsets, intervals, memory


def verify(stage, kit, counts, validation_sha):
    """Relit chaque document, contrôle les volumes et recherche les suites du kit."""
    validation = kit / "data" / "validation.jsonl"
    if digest(validation) != validation_sha:
        raise ValueError("Le fichier de validation diffère de celui du nettoyage")
    with validation.open(encoding="utf-8") as stream:
        texts = [json.loads(line)["text"] for line in stream if line.strip()]
    if len(texts) != 230:
        raise ValueError("Les 230 documents de validation publique sont requis")
    guard = ValidationGuard(texts)
    for source in SOURCES:
        start = perf_counter()
        path = source_path(stage, source)
        docs = byte_count = 0
        for row in read_rows(path):
            if row["source"] != source:
                raise ValueError(f"Source inattendue dans {path}")
            docs += 1
            byte_count += len(row["text"].encode("utf-8"))
            if guard.matches(row["text"]):
                raise ValueError(f"Recouvrement avec la validation dans {source}, id={row['id']}")
        if (docs, byte_count) != (counts[source]["docs"], counts[source]["bytes"]):
            raise ValueError(f"Compteurs de sortie incorrects : {path}")
        counts[source]["sha256"] = digest(path)
        counts[source]["verify_seconds"] = perf_counter() - start
        print(f"Vérification {source} : {counts[source]}", flush=True)
    return {"validation_docs": 230, "matching_training_docs": 0, "mean_overlap": 0.0,
            "flagged_validation_docs": 0, "validation_sha256": validation_sha}


def near(exact_folder, output, kit, threshold):
    """Écrit la sortie MinHash et la publie après relecture et audit."""
    report = json.loads((exact_folder / "stats.json").read_text(encoding="utf-8"))
    pilot = report["pilot"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as tmp:
        stage = Path(tmp) / "minhash"
        stage.mkdir()
        with (Path(tmp) / "rows.jsonl").open("w+b") as spool:
            start = perf_counter()
            links, sizes, offsets, intervals, memory = build_index(exact_folder, report, spool)
            index_seconds = perf_counter() - start
            print(f"Index : {memory} octets, {index_seconds:.1f} s", flush=True)

            def get_row(index):
                """Relit une ligne originale via sa position dans le fichier temporaire."""
                spool.seek(int(offsets[index]))
                return json.loads(spool.readline())

            @lru_cache(maxsize=128)
            def get_shingles(index):
                """Réutilise les shingles des candidats consultés récemment."""
                return shingles(get_row(index)["text"])

            start = perf_counter()
            # Répartit les exemples entre les trois sources du document examiné.
            groups = None
            if pilot:
                groups = np.repeat(np.arange(len(SOURCES)), [span["docs"] for span in intervals.values()])
            kept, examples = select_matches(
                links.copy() if pilot else links, sizes, get_shingles, threshold, inspect=pilot, groups=groups,
            )
            match_seconds = perf_counter() - start
            result = {}
            for source, interval in intervals.items():
                counts = dict(input_docs=interval["docs"], input_bytes=interval["bytes"],
                              docs=0, bytes=0)
                with ExitStack() as stack:
                    writer = open_output(stack, stage, source)
                    for index in range(interval["start"], interval["stop"]):
                        if kept[index]:
                            row = get_row(index)
                            counts["docs"] += 1
                            counts["bytes"] += len(row["text"].encode("utf-8"))
                            write_document(writer, row)
                result[source] = counts

            if pilot:
                sweep = {}
                for cutoff in (0.75, 0.8, 0.85, 0.9, 0.96, 0.97):
                    variant, _ = select_matches(
                        links.copy(), sizes, get_shingles, cutoff, inspect=False,
                    )
                    sweep[str(cutoff)] = {
                        source: int((~variant[span["start"]:span["stop"]]).sum())
                        for source, span in intervals.items()
                    }
                # Seuls les identifiants et les scores sont conservés dans le rapport.
                write_json(stage / "examples.json", {
                    label: [
                        {"left": get_row(left)["id"], "right": get_row(right)["id"], "score": score,
                         "left_source": get_row(left)["source"], "right_source": get_row(right)["source"]}
                        for left, right, score in pairs
                    ] for label, pairs in examples.items()
                })
                write_json(stage / "sweep.json", sweep)

        audit = verify(stage, kit, result, report["validation_sha256"])
        write_json(stage / "stats.json", {
            "pilot": pilot, "seed": SEED, "threshold": threshold, "bands": BANDS,
            "rows_per_band": ROWS, "wiki_sample_limit": WIKI_SIZE,
            "exact_stats_sha256": digest(exact_folder / "stats.json"),
            "exact": report["sources"], "minhash": result, "audit": audit,
            "index_arrays_bytes": memory, "index_seconds": index_seconds,
            "signature_inputs": intervals, "match_seconds": match_seconds,
        })
        stage.rename(output)


def prepare_full_run():
    """Vérifie le secteur et évite la veille pendant le traitement sous Windows."""
    import ctypes
    import sys

    if sys.platform == "win32":
        # Le premier octet vaut 1 si le secteur est connecté, 255 si inconnu.
        status = (ctypes.c_ubyte * 12)()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)) or status[0] != 1:
            raise RuntimeError("Branche le PC sur secteur avant le traitement complet")
        # Windows libère cette demande de maintien éveillé à la fin du processus.
        if not ctypes.windll.kernel32.SetThreadExecutionState(0x80000001):
            raise RuntimeError("Impossible d'empêcher la veille pendant le traitement")


def main():
    """Expose le pilote, le point de reprise et le traitement complet."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("pilot", "exact", "minhash", "all"))
    parser.add_argument("--clean", type=Path, default=Path("data/interim/clean"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--kit", type=Path, default=default_kit())
    parser.add_argument("--threshold", type=float)
    args = parser.parse_args()
    pilot = args.stage == "pilot"
    output = args.out or Path("data/interim/dedup-pilot" if pilot else "data/interim/dedup")
    if args.stage in ("minhash", "all") and (
        args.threshold is None or not 0 < args.threshold <= 1
    ):
        parser.error("Indique un seuil MinHash validé avec --threshold (entre 0 exclu et 1 inclus)")
    if not pilot:
        prepare_full_run()
    exact_folder = output / "exact"
    final_folder = output / "final"
    if args.stage in ("pilot", "minhash", "all") and final_folder.exists():
        raise FileExistsError(f"La sortie finale existe déjà : {final_folder}")
    if args.stage in ("exact", "all") or (pilot and not exact_folder.exists()):
        if exact_folder.exists():
            raise FileExistsError(f"Reprends avec minhash : {exact_folder}")
        exact(args.clean, exact_folder, pilot)
    if args.stage in ("pilot", "minhash", "all"):
        report = json.loads((exact_folder / "stats.json").read_text(encoding="utf-8"))
        if report["pilot"] != pilot:
            raise ValueError("Le dossier exact ne correspond pas au mode demandé")
        near(exact_folder, final_folder, args.kit, 0.97 if pilot else args.threshold)


if __name__ == "__main__":
    main()
