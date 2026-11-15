"""Déplace une partie de Wikipédia et Gutenberg vers la fin d'un flux de la famille M4."""

import argparse
from contextlib import ExitStack
from itertools import accumulate, pairwise
from pathlib import Path
import random
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory, TemporaryFile

from pipeline.ablation import KIT_REV, ROOT, SEED, read_json, sha256, write_json
from pipeline.mixes import MIXES, quotas


M4_HASH = "c6c628a6b44640db55654c68878a35d02748a860f7aad1ab4c9b9597349738a9"
TOKENIZER_HASH = "b2554a8221a55c19b4008f5b605b1b6e84b6a7f84058507c15aba34eca3b2379"
# Points de pourcentage ajoutés aux parts du flux parent dans la première phase.
EARLY_SHIFT = {
    "wikipedia_fr": -10,
    "common_crawl": 7,
    "assemblee_nationale": 7,
    "gutenberg_fr": -5,
    "wikinews_fr": 1,
}


def window_blocks(size, window, totals, rng):
    """Calcule les tranches par source, avec arrondis cumulés et ordre mélangé."""
    bounds = dict(zip(totals, pairwise(accumulate(totals.values(), initial=0))))
    for start in range(0, size, window):
        end = min(start + window, size)
        order = list(totals)
        rng.shuffle(order)
        for source in order:
            low, high = bounds[source]
            before = start * high // size - start * low // size
            after = end * high // size - end * low // size
            if after < before:
                raise ValueError("Fenêtre trop petite pour les quotas cumulés")
            yield source, after - before


def reference_blocks(size, window, shares):
    """Retrouve les longueurs et l'ordre exacts des blocs produits par pipeline.mixes."""
    rng = random.Random(SEED)
    for start in range(0, size, window):
        before = quotas(start, shares)
        after = quotas(min(start + window, size), shares)
        order = list(shares)
        rng.shuffle(order)
        for source in order:
            yield source, after[source] - before[source]


def redistribute(input_path, output_path, seen, window, shares, scratch):
    """Sépare les sources et redistribue les mêmes tokens sur deux phases."""
    # La transition tombe sur une frontière de fenêtre du mélangeur officiel.
    first_size = seen // (2 * window) * window
    last_size = seen - first_size
    total = quotas(seen, shares)
    first_shares = {source: count + EARLY_SHIFT[source] for source, count in shares.items()}
    first = quotas(first_size, first_shares)
    last = {source: total[source] - first[source] for source in shares}
    if not first_size or min(first.values()) < 0 or min(last.values()) < 0:
        raise ValueError("Quotas incompatibles avec le changement d'ordre M4")

    with ExitStack() as stack:
        inputs = {source: stack.enter_context(TemporaryFile(dir=scratch)) for source in shares}
        # Le premier token reste en place. Les autres sont les cibles d'entraînement.
        with input_path.open("rb") as input_stream:
            first_token = input_stream.read(2)
            for source, count in reference_blocks(seen, window, shares):
                inputs[source].write(input_stream.read(2 * count))
        for stream in inputs.values():
            stream.seek(0)

        with output_path.open("wb") as output:
            output.write(first_token)
            # Les flux propres à chaque source sont consommés dans leur ordre M4.
            rng = random.Random(SEED)
            for size, totals in ((first_size, first), (last_size, last)):
                for source, count in window_blocks(size, window, totals, rng):
                    output.write(inputs[source].read(2 * count))
        if any(stream.read(1) for stream in inputs.values()) or output_path.stat().st_size != 2 * (seen + 1):
            raise ValueError("La redistribution ne consomme pas exactement tous les tokens M4")

    return [
        {"n_tokens": first_size, "tokens_by_source": first},
        {"n_tokens": last_size, "tokens_by_source": last},
    ]


def prepare(parent, out, config, source_mix="M4"):
    """Valide le flux parent, écrit la variante et publie ses métadonnées."""
    source_folder = parent / source_mix
    input_path = source_folder / "train.bin"
    tokenizer = source_folder / "tokenizer.json"
    if not tokenizer.is_file():
        tokenizer = parent / "tokenizer.json"
    meta = read_json(source_folder / "data_meta.json")
    train = config["train"]
    tokens_per_step = train["tokens_per_step"]
    seen = train["max_steps"] * tokens_per_step
    window = train["shuffle_window_steps"] * tokens_per_step
    shares = meta["source_percent"]
    # L'ordre des sources dans le manifeste détermine l'agencement du flux de départ.
    if (
        "order_phases" in meta
        or list(shares) != list(MIXES["M4"])
        or meta["tokens_seen_by_source"] != quotas(seen, shares)
        or (source_mix == "M4" and shares != MIXES["M4"])
    ):
        raise ValueError("Le flux parent est incompatible avec la famille M4")
    source_hash = M4_HASH if source_mix == "M4" else meta["dataset_sha256"]
    tokenizer_hash = TOKENIZER_HASH if source_mix == "M4" else meta["tokenizer_sha256"]
    if meta["dataset_sha256"] != source_hash or sha256(input_path) != source_hash:
        raise ValueError("L'empreinte du flux parent ne correspond pas")
    if input_path.stat().st_size != 2 * (seen + 1) or meta["n_tokens"] != seen + 1:
        raise ValueError("Le flux M4 ne correspond pas au budget officiel")
    if meta["tokenizer_sha256"] != tokenizer_hash or sha256(tokenizer) != tokenizer_hash:
        raise ValueError("L'empreinte du tokenizer parent ne correspond pas")
    if out.exists():
        raise FileExistsError(f"Choisis un dossier de sortie neuf : {out}")
    out.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(dir=out.parent) as name:
        scratch = Path(name)
        staging = scratch / "dataset"
        variant = staging / f"{source_mix}ORDER"
        variant.mkdir(parents=True)
        output_path = variant / "train.bin"
        phases = redistribute(input_path, output_path, seen, window, shares, scratch)
        metadata = {
            **meta,
            "dataset_sha256": sha256(output_path),
            "parent_dataset_sha256": source_hash,
            "order_phases": phases,
            "order_seed": SEED,
        }
        shutil.copyfile(tokenizer, staging / "tokenizer.json")
        write_json(variant / "data_meta.json", metadata)
        staging.rename(out)
    return metadata


def main():
    """Charge la configuration officielle depuis le kit et prépare le flux M4ORDER."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=ROOT / "kit/Piscine-official")
    parser.add_argument("--parent", type=Path, required=True, help="Dossier avec le flux et son tokenizer")
    parser.add_argument("--source-mix", default="M4", help="Nom du flux de départ dans le dossier parent")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    kit = args.kit.resolve()
    if subprocess.check_output(["git", "-C", str(kit), "rev-parse", "HEAD"], text=True).strip() != KIT_REV:
        raise ValueError(f"Clone du kit attendu à la révision {KIT_REV}")
    if subprocess.check_output(["git", "-C", str(kit), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("Le clone du kit contient des modifications")
    sys.path.insert(0, str(kit))
    from ftb import load_config

    meta = prepare(args.parent.resolve(), args.out.resolve(), load_config(), args.source_mix)
    print(meta["dataset_sha256"])


if __name__ == "__main__":
    main()
