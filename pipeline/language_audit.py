"""Tire un échantillon de textes acceptés et mesure la précision annotée."""

import argparse
import gzip
import json
from pathlib import Path
from random import Random

from pipeline.clean import INTERIM


SEED = 42


def reservoir(documents, size, rng):
    """Tire uniformément sans remise avec une mémoire bornée."""
    selected = []
    for index, document in enumerate(documents):
        if index < size:
            selected.append(document)
            continue
        # Le nouveau document remplace une entrée avec une probabilité de taille / total.
        slot = rng.randrange(index + 1)
        if slot < size:
            selected[slot] = document
    return selected


def iter_accepted(folder):
    """Lit uniquement les sorties nettoyées déclarées dans les statistiques."""
    stats = json.loads((folder / "stats.json").read_text(encoding="utf-8"))
    for source in sorted(stats["sources"]):
        with gzip.open(folder / f"{source}.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                yield json.loads(line)


def precision(rows):
    """Calcule la part de français parmi tous les documents acceptés annotés."""
    if not rows:
        raise ValueError("Échantillon vide")
    labels = [row.get("annotation") for row in rows]
    if any(label not in ("fr", "autre", "mixte") for label in labels):
        raise ValueError("Chaque annotation doit être fr, autre ou mixte")
    french = labels.count("fr")
    return {"annotated": len(labels), "french": french, "precision": french / len(labels)}


def main():
    """Lit les options de tirage ou de calcul."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample", help="Tire les documents à annoter.")
    sample.add_argument("--input", type=Path, default=INTERIM / "clean")
    sample.add_argument("--out", type=Path, default=INTERIM / "language_annotations.json")
    sample.add_argument("--size", type=int, default=100)
    score = commands.add_parser("score", help="Calcule la précision du fichier annoté.")
    score.add_argument("annotations", type=Path)
    args = parser.parse_args()
    if args.command == "sample":
        if args.size < 1:
            parser.error("--size doit être positif")
        rows = reservoir(iter_accepted(args.input), args.size, Random(SEED))
        if not rows:
            parser.error("Aucun document accepté dans cette sortie")
        # Masque le score du modèle pour que l'annotation se fasse sur le texte seul.
        for row in rows:
            del row["language_score"]
            row["annotation"] = ""
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump({"seed": SEED, "documents": rows}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(f"{len(rows)} documents à annoter dans {args.out}")
    else:
        rows = json.loads(args.annotations.read_text(encoding="utf-8-sig"))["documents"]
        print(json.dumps(precision(rows), indent=2))


if __name__ == "__main__":
    main()
