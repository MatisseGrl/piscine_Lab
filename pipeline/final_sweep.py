"""Prépare des variantes à partir du flux final vérifié et de Gutenberg audité."""

import argparse
import os
import random
import re
import shutil
import sys
from contextlib import ExitStack
from itertools import islice
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from pipeline.ablation import KIT_REV, SEED, read_json, sha256, train_tokenizer, write_json
from pipeline.gutenberg import load_guard
from pipeline.mix_order import reference_blocks, window_blocks
from pipeline.mixes import encode_repeating, shuffled_texts
from pipeline.regenerate import EXPECTED_SHA256


BOOK = "gutenberg_fr"
WEB = "common_crawl"
EXTRA_BOOKS = {"M4FINALBOOK30": 5, "M4FINALBOOK35": 10}
RETOKENIZED = {"M4FINALRETOK": 10_000_000, "M4FINALRETOK50": 50_000_000}
RECIPES = (*EXTRA_BOOKS, "M4FINALBOOKSHUFFLE", "M4FINALITALICS", "M4FINALEXCERPTS", *RETOKENIZED)
ITALICS = re.compile(r"(?<!\w)_([^_\s](?:[^_\n]{0,78}?[^_\s])?)_(?!\w)")
WHITESPACE = re.compile(r"\s+")
EXCERPT_CHARS = 48_000


def split_reference(path, parts, seen, window, shares):
    """Extrait les blocs dans l'ordre exact du mélange de référence."""
    with ExitStack() as stack:
        outputs = {name: stack.enter_context(item.open("wb")) for name, item in parts.items()}
        reader = stack.enter_context(path.open("rb"))
        context = reader.read(2)
        for source, count in reference_blocks(seen, window, shares):
            block = reader.read(2 * count)
            if len(block) != 2 * count:
                raise ValueError(f"Flux de référence tronqué pour {source}")
            outputs[source].write(block)
        if len(context) != 2 or reader.read(1):
            raise ValueError("Taille inattendue du flux de référence")
    return context


def write_blocks(path, parts, context, blocks):
    """Assemble les blocs des sources et contrôle leur taille à la lecture."""
    with ExitStack() as stack:
        inputs = {name: stack.enter_context(item.open("rb")) for name, item in parts.items()}
        output = stack.enter_context(path.open("wb"))
        output.write(context)
        for source, count in blocks:
            block = inputs[source].read(2 * count)
            if len(block) != 2 * count:
                raise ValueError(f"Stock insuffisant : {source}")
            output.write(block)


def spans(tokens, eot):
    """Découpe le flux source en documents terminés et conserve la dernière coupe."""
    left = 0
    for right in np.flatnonzero(tokens == eot):
        yield left, int(right + 1)
        left = int(right + 1)
    if left < len(tokens):
        yield left, len(tokens)


def shuffle_books(path, output, eot):
    """Mélange les livres échantillonnés, avec leurs séparateurs et leurs tokens d'origine."""
    tokens = np.fromfile(path, dtype="<u2")
    documents = list(spans(tokens, eot))
    tail = [documents.pop()] if documents and tokens[-1] != eot else []
    random.Random(SEED + 1).shuffle(documents)
    with output.open("wb") as stream:
        for start, end in documents + tail:
            stream.write(tokens[start:end].tobytes())


def book_texts(archive, size, original_count, variant, guard, scratch):
    """Lit la sélection originale ou propose des extraits plus diversifiés."""
    rate = 1 if variant == "M4FINALEXCERPTS" else min(1, 10 * original_count / size)
    rng = random.Random(SEED)
    for text in shuffled_texts(archive, rate, SEED, scratch):
        updated = text
        if variant == "M4FINALITALICS":
            updated = ITALICS.sub(r"\1", text)
        if variant == "M4FINALEXCERPTS" and len(text) > EXCERPT_CHARS:
            position = rng.randrange(len(text) - EXCERPT_CHARS + 1)
            left = WHITESPACE.search(text, position)
            if left:
                right = WHITESPACE.search(text, left.end() + EXCERPT_CHARS)
                updated = text[left.end():right.start() if right else len(text)]
        # Le texte original reste disponible si une transformation crée un recouvrement.
        yield text if updated != text and guard.matches(updated) else updated


def book_stream(path, texts, count, tokenizer):
    """Encode une seule passe jusqu'au quota et utilise le séparateur du kit."""
    with path.open("wb") as stream:
        while batch := list(islice(texts, 64)):
            for ids in tokenizer.encode_batch(batch):
                ids.append(tokenizer.eot_id)
                tokens = ids[:count]
                stream.write(np.asarray(tokens, dtype="<u2").tobytes())
                count -= len(tokens)
                if not count:
                    return
    raise ValueError(f"Stock Gutenberg insuffisant : {count} tokens manquants")


def retokenize_sources(parts, tokenizer, kit, guard, shares, totals, variant, scratch):
    """Décodage du flux vérifié, audit des textes décodés et nouvel encodage."""
    import gzip
    import json

    sources = {}
    for source, path in parts.items():
        archive = scratch / f"{source}.jsonl.gz"
        size = 0
        tokens = np.fromfile(path, dtype="<u2")
        # Le dernier fragment de chaque source peut s'arrêter au milieu d'un octet UTF-8.
        with gzip.open(archive, "wt", encoding="utf-8", newline="\n") as output:
            for start, end in spans(tokens, tokenizer.eot_id):
                right = end - int(tokens[end - 1] == tokenizer.eot_id)
                text = tokenizer.decode(tokens[start:right].tolist()).strip("\ufffd")
                if text and not guard.matches(text):
                    size += len(text.encode("utf-8"))
                    output.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
        sources[source] = (archive, size, sha256(path))
    trained, sample = train_tokenizer(kit, sources, scratch, shares, sample_bytes=RETOKENIZED[variant])
    from ftb.tokenizer import load_tokenizer

    tokenizer = load_tokenizer(trained)
    passes = {}
    for source, entry in sources.items():
        with parts[source].open("wb") as output:
            passes[source] = encode_repeating(entry, totals[source], tokenizer, output, scratch)
    return trained, sample, passes, tokenizer


def prepare(kit, reference, gutenberg, variant, out):
    """Construit le candidat, conserve la filiation et publie les fichiers ensemble."""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    sys.path.insert(0, str(kit))
    from ftb import load_config
    from ftb.tokenizer import load_tokenizer

    if out.exists():
        raise FileExistsError(out)
    parent = read_json(reference / "data_meta.json")
    expected = EXPECTED_SHA256["M4REFLOWBPE"]
    if parent["dataset_sha256"] != expected or sha256(reference / "train.bin") != expected:
        raise ValueError("Empreinte du flux parent incorrecte")
    tokenizer_path = reference / "tokenizer.json"
    tokenizer = load_tokenizer(tokenizer_path)
    if tokenizer.sha256 != parent["tokenizer_sha256"]:
        raise ValueError("Empreinte du tokenizer parent incorrecte")
    train = load_config()["train"]
    seen = train["max_steps"] * train["tokens_per_step"]
    window = train["shuffle_window_steps"] * train["tokens_per_step"]
    shares = parent["source_percent"].copy()
    totals = parent["tokens_seen_by_source"].copy()
    passes = parent["passes_started_by_source"].copy()
    original_count = totals[BOOK]
    extra = EXTRA_BOOKS.get(variant, 0)
    transfer = seen * extra // 100
    shares[BOOK] += extra
    shares[WEB] -= extra
    totals[BOOK] += transfer
    totals[WEB] -= transfer
    sample = None
    if variant != "M4FINALBOOKSHUFFLE":
        guard, validation, moliere = load_guard(kit)
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as temporary:
        scratch = Path(temporary)
        parts = {source: scratch / f"{source}.bin" for source in shares}
        context = split_reference(reference / "train.bin", parts, seen, window, parent["source_percent"])
        if variant in RETOKENIZED:
            tokenizer_path, sample, passes, tokenizer = retokenize_sources(
                parts, tokenizer, kit, guard, shares, totals, variant, scratch,
            )
            context = np.asarray([tokenizer.eot_id], dtype="<u2").tobytes()
        elif variant == "M4FINALBOOKSHUFFLE":
            shuffled = scratch / "books-shuffled.bin"
            shuffle_books(parts[BOOK], shuffled, tokenizer.eot_id)
            parts[BOOK] = shuffled
        else:
            archive = gutenberg / "gutenberg_fr.jsonl.gz"
            audit = read_json(gutenberg / "stats.json")
            if (audit["validation_sha256"], audit["moliere_validation_sha256"]) != (
                sha256(validation), sha256(moliere)
            ):
                raise ValueError("Validations différentes de l'audit Gutenberg")
            final = audit["final"]
            if final["overlap_with_validation_docs"] or sha256(archive) != parent["input_sha256_by_source"][BOOK]:
                raise ValueError("Archive Gutenberg différente de la référence")
            expanded = scratch / "books-new.bin"
            texts = book_texts(archive, final["bytes"], original_count, variant, guard, scratch)
            book_stream(expanded, texts, totals[BOOK], tokenizer)
            if extra:
                # Le début doit être octet pour octet le même que dans le run officiel.
                with expanded.open("rb") as stream:
                    if stream.read(2 * original_count) != parts[BOOK].read_bytes():
                        raise ValueError("Le préfixe Gutenberg diffère du run officiel")
            parts[BOOK] = expanded
        staged = scratch / "dataset"
        folder = staged / variant
        folder.mkdir(parents=True)
        if extra:
            blocks = window_blocks(seen, window, totals, random.Random(SEED))
        else:
            blocks = reference_blocks(seen, window, shares)
        write_blocks(folder / "train.bin", parts, context, blocks)
        shutil.copyfile(tokenizer_path, staged / "tokenizer.json")
        meta = {
            **parent,
            "parent_dataset_sha256": expected,
            "dataset_sha256": sha256(folder / "train.bin"),
            "tokenizer_sha256": tokenizer.sha256,
            "source_percent": shares,
            "tokens_seen_by_source": totals,
            "passes_started_by_source": passes,
            "variant": variant,
        }
        if sample is not None:
            meta["tokenizer_sample"] = sample
        write_json(folder / "data_meta.json", meta)
        staged.rename(out)
    print(variant, meta["dataset_sha256"], flush=True)


def main():
    """Vérifie la révision du kit et assemble la variante demandée."""
    import subprocess

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=RECIPES)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--gutenberg", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    kit = args.kit.resolve()
    revision = subprocess.check_output(["git", "-C", str(kit), "rev-parse", "HEAD"], text=True).strip()
    if revision != KIT_REV:
        raise ValueError(f"Révision attendue : {KIT_REV}")
    prepare(kit, args.reference.resolve(), args.gutenberg.resolve(), args.variant, args.out.resolve())


if __name__ == "__main__":
    main()
