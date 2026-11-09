"""Nettoie les trois sources brutes et consigne les rejets par source."""

import argparse
from collections import Counter
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import file_digest
import gzip
from io import TextIOWrapper
from itertools import islice
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from xml.etree import ElementTree
from zipfile import ZipFile

import ftfy

from pipeline.collect import CRAWL, RAW, SEGMENT, WIKI_CONFIG, download


ROOT = RAW.parents[1]
INTERIM = ROOT / "data" / "interim"
MODEL = INTERIM / "models" / "lid.176.bin"
MODEL_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
MODEL_HASH = "7e69ec5451bc261cc7844e49e4792a85d7f09c06789ec800fc4a44aec362764e"
KIT = ROOT / "kit" / "Piscine-official"
THRESHOLD = 0.80
EDGE_LINES = 5
ASSEMBLY_TEXT = "{http://schemas.assemblee-nationale.fr/referentiel}texte"
WORD = re.compile(r"\w+")
BOILERPLATE = re.compile(
    r"(?:menu(?: principal)?|aller au contenu(?: principal)?|accueil|"
    r"(?:accepter|refuser) (?:tous )?les cookies|gérer (?:les|mes|vos) cookies|"
    r"paramètres des cookies|politique de cookies|mentions légales|"
    r"politique de confidentialité|tous droits réservés|"
    r"©[^\n]{1,100}|home|skip to (?:main )?content|"
    r"(?:accept|reject) (?:all )?cookies|privacy policy|all rights reserved)[.!…]?"
)


@dataclass(frozen=True)
class CleanResult:
    """Conserve le texte accepté ou le motif principal du rejet."""

    text: str | None
    reason: str | None
    score: float | None = None
    encoding_fixed: bool = False
    removed_lines: int = 0


def _strip_boilerplate(text):
    """Retire les motifs autonomes et les répétitions courtes aux bords."""
    lines = text.split("\n")
    # Ignore les lignes vides pour repérer les cinq premières et dernières lignes utiles.
    keys = [" ".join(line.casefold().split()) for line in lines]
    nonempty = [index for index, key in enumerate(keys) if key]
    edges = set(nonempty[:EDGE_LINES] + nonempty[-EDGE_LINES:])
    counts = Counter(key for key in keys if 0 < len(key) <= 25)
    kept = []
    for index, (line, key) in enumerate(zip(lines, keys)):
        if BOILERPLATE.fullmatch(key) or (index in edges and counts[key] >= 3):
            continue
        kept.append(line)
    return "\n".join(kept).strip(), len(lines) - len(kept)


def remove_boilerplate(text):
    """Renvoie le texte WET débarrassé des lignes parasites."""
    return _strip_boilerplate(text)[0]


def repair_encoding(text):
    """Répare le mojibake et uniformise les fins de ligne."""
    return ftfy.fix_encoding(text).replace("\r\n", "\n").replace("\r", "\n")


def clean_text(text, source, predict, *, repaired=None):
    """Répare le texte, retire le boilerplate WET et applique le filtre français."""
    if repaired is None:
        repaired = repair_encoding(text)
    if source == "common_crawl":
        cleaned, removed = _strip_boilerplate(repaired)
    else:
        cleaned, removed = repaired.strip(), 0
    details = {"encoding_fixed": repaired != text, "removed_lines": removed}
    if not cleaned:
        return CleanResult(None, "empty_after_cleaning", **details)

    # fastText attend une seule ligne par prédiction.
    language, score = predict(" ".join(cleaned.split()))
    if language != "fr":
        return CleanResult(None, "non_french", score, **details)
    if score < THRESHOLD:
        return CleanResult(None, "low_confidence", score, **details)
    return CleanResult(cleaned, None, score, **details)


class ValidationGuard:
    """Repère les séquences de 13 mots du kit, même à l'intérieur d'une page."""

    def __init__(self, texts):
        """Indexe les séquences normalisées par taille et premiers mots."""
        self.groups = {}
        for text in texts:
            words = WORD.findall(repair_encoding(text).lower())
            size = min(13, len(words))
            if not size:
                continue
            starts, sequences = self.groups.setdefault(size, (set(), set()))
            for index in range(len(words) - size + 1):
                sequence = tuple(words[index:index + size])
                starts.add(sequence[:2])
                sequences.add(sequence)
        if not self.groups:
            raise ValueError("Validation vide")

    def matches(self, text):
        """Teste un texte déjà réparé avec la tokenisation par mots du kit."""
        words = WORD.findall(text.lower())
        for size, (starts, sequences) in self.groups.items():
            # Évite de construire un tuple long quand le début ne correspond pas.
            for index in range(len(words) - size + 1):
                if tuple(words[index:index + min(size, 2)]) in starts:
                    if tuple(words[index:index + size]) in sequences:
                        return True
        return False


def iter_wet(paths):
    """Lit les enregistrements texte WET sans décompresser les archives sur disque."""
    from warcio.archiveiterator import ArchiveIterator

    for path in paths:
        with path.open("rb") as stream:
            for record in ArchiveIterator(stream, check_digests="raise"):
                if record.rec_type == "conversion":
                    text = record.content_stream().read().decode("utf-8", errors="replace")
                    yield record.rec_headers.get_header("WARC-Record-ID"), text


def iter_wikipedia(paths):
    """Lit uniquement les colonnes utiles, par lots Parquet."""
    from pyarrow.parquet import ParquetFile

    for path in paths:
        with ParquetFile(path) as parquet:
            for batch in parquet.iter_batches(columns=["id", "text"], batch_size=1024):
                for row in batch.to_pylist():
                    yield str(row["id"]), row["text"]


def iter_assembly(path):
    """Lit les sections des séances en conservant les prises de parole dans l'ordre."""
    with ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith("xml/compteRendu/") or not name.endswith(".xml"):
                continue
            with archive.open(name) as stream:
                root = ElementTree.parse(stream).getroot()
            content = root.find("{*}contenu")
            if content is None:
                raise ValueError(f"Corps de séance absent dans {name}")
            # Un recouvrement écarte une section plutôt que toute la séance.
            for index, section in enumerate(content):
                paragraphs = ["".join(node.itertext()) for node in section.iter(ASSEMBLY_TEXT)]
                if paragraphs:
                    yield f"{Path(name).stem}:{index}", "\n".join(paragraphs)


def sources(raw, limit):
    """Sélectionne les trois entrées de la collecte et vérifie leurs archives."""
    wet = sorted((raw / "common_crawl" / CRAWL / SEGMENT).glob("*.warc.wet.gz"))
    wiki = sorted((raw / "wikipedia_fr" / WIKI_CONFIG).glob("*.parquet"))
    assembly = raw / "assemblee_nationale" / "16" / "syseron.xml.zip"
    if not wet or not wiki or not assembly.is_file():
        raise ValueError("Une des trois sources brutes est absente")
    if limit is None and (len(wet), len(wiki)) != (900, 17):
        raise ValueError(f"Collecte incomplète : {len(wet)} WET et {len(wiki)} Parquet")
    return {
        "common_crawl": iter_wet(wet),
        "wikipedia_fr": iter_wikipedia(wiki),
        "assemblee_nationale": iter_assembly(assembly),
    }


def digest(path):
    """Calcule le SHA-256 du fichier en lecture séquentielle."""
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def write_document(stream, row):
    """Écrit une ligne JSON compatible avec les entrées du kit."""
    stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def process_source(documents, source, clean_stream, raw_stream, predict, guard):
    """Écrit les documents retenus et compte les rejets et octets UTF-8."""
    stats = dict(docs_before=0, docs_after=0, bytes_before=0, bytes_after=0,
                 docs_raw_safe=0, encoding_changed=0, boilerplate_lines_removed=0)
    rejected = Counter()
    rejected_bytes = Counter()
    for doc_id, raw_text in documents:
        size = len(raw_text.encode("utf-8"))
        stats["docs_before"] += 1
        stats["bytes_before"] += size
        repaired = repair_encoding(raw_text)
        # Vérifie aussi la représentation brute si ftfy a modifié ses mots.
        stats["encoding_changed"] += repaired != raw_text
        overlap = guard.matches(repaired) or (repaired != raw_text and guard.matches(raw_text))
        result = CleanResult(None, "validation_overlap") if overlap else clean_text(
            raw_text, source, predict, repaired=repaired,
        )
        stats["boilerplate_lines_removed"] += result.removed_lines
        # Le retrait de lignes peut créer un nouveau raccord dans le texte nettoyé.
        if result.removed_lines and result.text and guard.matches(result.text):
            overlap = True
        reason = result.reason
        if overlap:
            reason = "validation_overlap"
        elif raw_text.strip():
            stats["docs_raw_safe"] += 1
            if raw_stream is not None:
                write_document(raw_stream, {"id": doc_id, "source": source, "text": raw_text})
        if reason is not None:
            rejected[reason] += 1
            rejected_bytes[reason] += size
            continue
        stats["docs_after"] += 1
        stats["bytes_after"] += len(result.text.encode("utf-8"))
        write_document(clean_stream, {
            "id": doc_id, "source": source, "text": result.text, "language_score": result.score,
        })
    stats["docs_rejected_percent"] = 100 * sum(rejected.values()) / max(1, stats["docs_before"])
    stats["input_bytes_rejected_percent"] = 100 * sum(rejected_bytes.values()) / max(1, stats["bytes_before"])
    stats["rejected_docs_by_reason"] = dict(rejected)
    stats["rejected_input_bytes_by_reason"] = dict(rejected_bytes)
    return stats


def open_output(stack, folder, source):
    """Ouvre un JSONL compressé avec un en-tête gzip reproductible."""
    raw = stack.enter_context((folder / f"{source}.jsonl.gz").open("wb"))
    compressed = stack.enter_context(gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=3))
    return stack.enter_context(TextIOWrapper(compressed, encoding="utf-8", newline="\n"))


def run(raw, output, kit, limit, include_raw):
    """Traite un flux stable et publie le dossier seulement après succès."""
    import fasttext

    if output.exists():
        raise FileExistsError(f"Choisis un dossier de sortie neuf : {output}")
    inputs = sources(raw, limit)
    validation = kit / "data" / "validation.jsonl"
    moliere = kit / "corpus" / "moliere_val.txt"
    with validation.open(encoding="utf-8") as stream:
        texts = [json.loads(line)["text"] for line in stream if line.strip()]
    if len(texts) != 230:
        raise ValueError("Les 230 documents de validation publique du kit sont requis")
    guard = ValidationGuard([*texts, *moliere.read_text(encoding="utf-8").split("=====")])
    download(MODEL_URL, MODEL, size=131_266_198, checksum=("sha256", MODEL_HASH))
    model = fasttext.load_model(str(MODEL))

    def predict(text):
        """Renvoie la meilleure langue et le score du modèle figé."""
        labels, scores = model.predict(text, k=1)
        return labels[0].removeprefix("__label__"), float(scores[0])

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        if include_raw:
            (stage / "raw").mkdir()
        stats = {
            "language_threshold": THRESHOLD, "model_sha256": MODEL_HASH, "limit_per_source": limit,
            "validation_sha256": digest(validation), "moliere_validation_sha256": digest(moliere),
            "sources": {},
        }
        for source, documents in inputs.items():
            print(f"Nettoyage : {source}", flush=True)
            # L'échantillon technique garde un préfixe stable dans chaque source.
            with ExitStack() as stack:
                stack.callback(documents.close)
                clean_stream = open_output(stack, stage, source)
                raw_stream = open_output(stack, stage / "raw", source) if include_raw else None
                source_stats = process_source(
                    islice(documents, limit), source, clean_stream, raw_stream, predict, guard,
                )
            source_stats["clean_sha256"] = digest(stage / f"{source}.jsonl.gz")
            if include_raw:
                source_stats["raw_sha256"] = digest(stage / "raw" / f"{source}.jsonl.gz")
            stats["sources"][source] = source_stats
            print(json.dumps(source_stats, ensure_ascii=False), flush=True)
        (stage / "stats.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n",
        )
        stage.rename(output)


def main():
    """Expose une commande de nettoyage complète et un mode de vérification borné."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=INTERIM / "clean")
    parser.add_argument("--kit", type=Path, default=KIT)
    parser.add_argument("--limit-per-source", type=int)
    parser.add_argument("--include-raw", action="store_true", help="Écrit aussi la variante brute contrôlée.")
    args = parser.parse_args()
    if args.limit_per_source is not None and args.limit_per_source < 1:
        parser.error("--limit-per-source doit être positif")
    if args.limit_per_source is not None and args.out == INTERIM / "clean":
        parser.error("Indique --out pour séparer le test borné de la sortie complète")
    run(RAW, args.out, args.kit, args.limit_per_source, args.include_raw)


if __name__ == "__main__":
    main()
