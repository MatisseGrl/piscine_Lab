"""Fabrique deux préfixes comparables des archives françaises pour la démo."""
import argparse
import gzip
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
from tokenizers import Tokenizer


# Les quotas portent sur des blocs de tokens, avec une marge sur les petites sources.
BLOCK = 8192
SOURCES = {
    "wikipedia_fr": ("quality/final", 0.66),
    "gutenberg_fr": ("gutenberg-reflow", 0.23),
    "common_crawl": ("quality/final", 0.06),
    "assemblee_nationale": ("quality/final", 0.035),
    "wikinews_fr": ("wikinews", 0.015),
}
TOKENIZER_HASH = "b2554a8221a55c19b4008f5b605b1b6e84b6a7f84058507c15aba34eca3b2379"


def digest(path):
    """Empreinte des octets du fichier, y compris pour une archive volumineuse."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def words(text):
    """Ignore la casse, la ponctuation et la forme de composition Unicode."""
    return re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())


def spans(tokens, size):
    """Parcourt les séquences de mots de longueur fixée."""
    return zip(*(tokens[i:] for i in range(size)))


def text_chunks(text):
    """Borne le coût du BPE sur les livres en coupant aux espaces."""
    start = 0
    while len(text) - start > 8192:
        end = text.rfind(" ", start + 1, start + 8192)
        if end == -1:
            end = start + 8192
        yield text[start:end]
        start = end
    yield text[start:]


def load_exclusions(corpus, chat, exam):
    """Protège la validation, le held-out Molière et les questions du test inédit."""
    train = (corpus / "moliere_train.txt").read_text(encoding="utf-8")
    val = (corpus / "moliere_val.txt").read_text(encoding="utf-8")
    val_grams = set(spans(words(val), 13))
    reserved = set(spans(words(train), 13)) | val_grams
    records = json.loads(chat.read_text(encoding="utf-8"))
    test = json.loads(exam.read_text(encoding="utf-8-sig"))["conversations"]
    questions = [tuple(words(turn)) for item in test for turn in item["turns"]]
    # La représentation en mots donne des bornes exactes, même sans ponctuation.
    learned = [" " + " ".join(words(train)) + " "]
    for record in records:
        for _, utterance in record["messages"]:
            tokens = words(utterance)
            if any(ngram in val_grams for ngram in spans(tokens, 13)):
                raise ValueError("Recouvrement SFT/validation Molière.")
            learned.append(" " + " ".join(tokens) + " ")
    for question in questions:
        needle = " " + " ".join(question) + " "
        if any(needle in item for item in learned):
            raise ValueError("Question du nouveau test présente dans le train.")
    return reserved, questions


def write_source(path, output, goal, tokenizer, reserved, questions, seen):
    """Écrit des documents filtrés dans l'ordre de l'archive jusqu'au quota."""
    stats = Counter()
    pending, pending_chars = [], 0
    # Compare les questions aux bornes de mots et vérifie les 13-grammes exacts.
    needles = [" " + " ".join(question) + " " for question in questions]
    endings = "\n\n"

    def flush(target):
        """Encode par lots avec le BPE de la démo et borne le dernier document."""
        nonlocal pending_chars
        chunks = [(chunk, i == 0) for text in pending for i, chunk in enumerate(text_chunks(text))]
        encodings = tokenizer.encode_batch([chunk for chunk, _ in chunks], add_special_tokens=False)
        for encoding, (_, begins_document) in zip(encodings, chunks, strict=True):
            ids = encoding.ids[:goal - stats["tokens"]]
            if not ids:
                break
            np.asarray(ids, dtype="<u2").tofile(target)
            stats["tokens"] += len(ids)
            stats["docs_used"] += begins_document
        pending.clear()
        pending_chars = 0

    with gzip.open(path, "rt", encoding="utf-8") as source, output.open("xb") as target:
        for line in source:
            text = json.loads(line)["text"].strip()
            if not text:
                continue
            stats["docs_read"] += 1
            tokens = words(text)
            normalized = " " + " ".join(tokens) + " "
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).digest()
            if fingerprint in seen:
                stats["duplicates"] += 1
                continue
            if any(ngram in reserved for ngram in spans(tokens, 13)):
                stats["moliere_overlap"] += 1
                continue
            if any(needle in normalized for needle in needles):
                stats["test_overlap"] += 1
                continue
            seen.add(fingerprint)
            pending.append(text + endings)
            pending_chars += len(text)
            if pending_chars >= 1_000_000:
                flush(target)
                if stats["tokens"] == goal:
                    break
        if pending:
            flush(target)
    if stats["tokens"] != goal:
        raise ValueError(f"Source {path.name} trop courte : {stats['tokens']} / {goal} tokens")
    print(path.name, dict(stats), flush=True)
    return dict(stats)


def main():
    """Produit un flux compact, ses préfixes et un manifeste sans texte brut."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archives", "corpus", "tokenizer", "chat", "exam", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--steps", type=int, default=9155)
    parser.add_argument("--short-steps", type=int, default=3052)
    args = parser.parse_args()
    if not 1 <= args.short_steps <= args.steps:
        parser.error("Le petit budget doit être compris dans le grand.")
    if digest(args.tokenizer) != TOKENIZER_HASH:
        raise ValueError("Empreinte du tokenizer de la démo inattendue.")
    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    reserved, questions = load_exclusions(args.corpus, args.chat, args.exam)
    args.out.mkdir(parents=True, exist_ok=False)
    total = args.steps * 4
    short = args.short_steps * 4
    remaining = total
    order, stats, parts, seen = [], {}, {}, set()
    for name, (folder, fraction) in reversed(tuple(SOURCES.items())):
        count = round(total * fraction) if name != "wikipedia_fr" else remaining
        remaining -= count
        if not count:
            continue
        source = args.archives / folder / f"{name}.jsonl.gz"
        part = args.out / f"{name}.bin"
        stats[name] = write_source(source, part, count * BLOCK, tokenizer, reserved, questions, seen)
        stats[name]["archive_sha256"] = digest(source)
        parts[name] = np.memmap(part, dtype="<u2", mode="r", shape=(count, BLOCK))
        order.extend((name, i) for i in range(count))

    # Mélange sans remise une seule fois, puis réutilise le même préfixe à 100 M.
    random.Random(1337).shuffle(order)
    raw_hash, prefix_hash = hashlib.sha256(), hashlib.sha256()
    prefix_sources = Counter()
    package = args.out / "kaggle"
    package.mkdir()
    with (package / "train.bin.gz").open("xb") as compressed:
        with gzip.GzipFile(fileobj=compressed, filename="", mtime=0, compresslevel=1, mode="wb") as output:
            for index, (name, offset) in enumerate(order):
                block = parts[name][offset].tobytes()
                output.write(block)
                raw_hash.update(block)
                if index < short:
                    prefix_hash.update(block)
                    prefix_sources[name] += BLOCK
                elif index == short:
                    # Le court budget partage la première cible de la fenêtre suivante.
                    prefix_hash.update(block[:2])
            sentinel = np.asarray(tokenizer.encode("\n", add_special_tokens=False).ids[:1], dtype="<u2").tobytes()
            output.write(sentinel)
            raw_hash.update(sentinel)
            if short == total:
                prefix_hash.update(sentinel)

    manifest = {
        "sources": stats, "total_input_tokens": total * BLOCK + 1,
        "total_targets": total * BLOCK, "short_targets": short * BLOCK,
        "short_sources": dict(prefix_sources), "seed": 1337,
        "repeated_blocks": 0, "tokenizer_sha256": TOKENIZER_HASH,
        "max_tokenizer_chunk_chars": 8192,
        "train_bin_sha256": raw_hash.hexdigest(), "short_bin_sha256": prefix_hash.hexdigest(),
        "archive_sha256": digest(package / "train.bin.gz"), "exam_sha256": digest(args.exam),
        "chat_train_sha256": digest(args.chat),
        "moliere_validation_sha256": hashlib.sha256(
            (args.corpus / "moliere_val.txt").read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
    }
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
