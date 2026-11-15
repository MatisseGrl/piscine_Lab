"""Recolle les lignes de prose Gutenberg coupées à largeur fixe et contrôle le résultat."""

import argparse
import gzip
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.ablation import read_json, sha256, write_json
from pipeline.clean import INTERIM, default_kit
from pipeline.gutenberg import SOURCE, load_guard

# Les lignes blanches, l'indentation et les débuts typiques d'une réplique signalent une structure.
PARAGRAPH_BREAK = re.compile(r"(\n[ \t]*\n+)")
STRUCTURAL_PREFIXES = ("-", "–", "—", "«", "#", "*", "[")


def reflow_paragraph(paragraph):
    """Remplace les sauts de ligne internes par des espaces si la prose semble coupée au bord."""
    lines = paragraph.split("\n")
    if len(lines) < 3 or any(not line or line != line.strip() for line in lines):
        return paragraph
    if any(line.startswith(STRUCTURAL_PREFIXES) for line in lines):
        return paragraph
    # Les lignes non finales doivent toutes atteindre une même marge à quelques mots près.
    widths = [len(line) for line in lines[:-1]]
    if min(widths) < 55 or max(widths) > 86 or max(widths) - min(widths) > 12:
        return paragraph
    if len(lines[-1]) > max(widths):
        return paragraph
    # Deux reprises au milieu d'une phrase écartent les vers et les listes à débuts réguliers.
    continuations = sum(line[0].islower() for line in lines[1:])
    if continuations < 2 or 2 * continuations < len(lines):
        return paragraph
    return " ".join(lines)


def reflow_text(text):
    """Recolle la prose et conserve les lignes blanches entre les paragraphes."""
    parts = PARAGRAPH_BREAK.split(text)
    for index in range(0, len(parts), 2):
        parts[index] = reflow_paragraph(parts[index])
    return "".join(parts)


def load_reflowed_source(interim, original, kit):
    """Vérifie les audits et la filiation de l'archive avant de l'utiliser dans un mélange."""
    folder = interim / "gutenberg-reflow"
    stats = read_json(folder / "stats.json")
    archive = folder / f"{SOURCE}.jsonl.gz"
    final = stats["final"]
    if stats["parent_sha256"] != original[2] or final["bytes"] != original[1]:
        raise ValueError("La variante recollée ne correspond pas à la source Gutenberg auditée")
    if (stats["validation_sha256"], stats["moliere_validation_sha256"]) != (
        sha256(kit / "data/validation.jsonl"), sha256(kit / "corpus/moliere_val.txt")
    ):
        raise ValueError("Validations différentes de celles de l’audit après recollage")
    if final["overlap_with_validation_docs"] or sha256(archive) != final["sha256"]:
        raise ValueError("Archive recollée différente de sa version auditée")
    return (archive, final["bytes"], final["sha256"]), stats


def prepare(kit, source_dir, out):
    """Contrôle la filiation, transforme l'archive et vérifie les textes modifiés après recollage."""
    audit = read_json(source_dir / "stats.json")
    source = source_dir / f"{SOURCE}.jsonl.gz"
    guard, validation, moliere = load_guard(kit)
    validation_sha, moliere_sha = sha256(validation), sha256(moliere)
    if (audit["validation_sha256"], audit["moliere_validation_sha256"]) != (validation_sha, moliere_sha):
        raise ValueError("Validations différentes de celles de l’audit Gutenberg")
    if audit["final"]["overlap_with_validation_docs"] or sha256(source) != audit["final"]["sha256"]:
        raise ValueError("Archive Gutenberg différente de sa version auditée")
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    documents = n_bytes = changed = joined = 0
    with TemporaryDirectory(dir=out.parent) as name:
        staged = Path(name) / "gutenberg-reflow"
        staged.mkdir()
        archive = staged / source.name
        with gzip.open(source, "rb") as rows, archive.open("wb") as stream:
            with gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0, compresslevel=6) as dest:
                for line in rows:
                    row = json.loads(line)
                    original = row["text"]
                    updated = reflow_text(original)
                    documents += 1
                    n_bytes += len(updated.encode("utf-8"))
                    if updated != original:
                        # Les documents inchangés restent couverts par l'audit de l'archive d'origine.
                        if guard.matches(updated):
                            raise ValueError(f"Recouvrement après recollage pour le document {row['id']}")
                        changed += 1
                        joined += original.count("\n") - updated.count("\n")
                        row["text"] = updated
                        line = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
                    dest.write(line)
        if (documents, n_bytes) != (audit["final"]["docs"], audit["final"]["bytes"]):
            raise ValueError("Le recollage modifie le nombre de documents ou d’octets")
        final = {
            "docs": documents, "bytes": n_bytes, "sha256": sha256(archive),
            "max_overlap_13_words": 0, "overlap_with_validation_docs": 0,
        }
        write_json(staged / "stats.json", {
            "validation_sha256": validation_sha, "moliere_validation_sha256": moliere_sha,
            "parent_sha256": audit["final"]["sha256"], "final": final,
            "reflow": {"changed_documents": changed, "joined_line_breaks": joined},
        })
        staged.rename(out)
    print(f"{changed:,} documents modifiés, {joined:,} sauts de ligne recollés", flush=True)


def main():
    """Prépare la variante Gutenberg à partir de l'archive d'origine auditée."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=default_kit())
    parser.add_argument("--source", type=Path, default=INTERIM / "gutenberg")
    parser.add_argument("--out", type=Path, default=INTERIM / "gutenberg-reflow")
    args = parser.parse_args()
    prepare(args.kit.resolve(), args.source.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
