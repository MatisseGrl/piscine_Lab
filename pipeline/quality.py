"""Filtres qualité par heuristiques : part de lettres, longueur minimale, lignes répétées.

Règles validées par Matisse (10/11), appliquées dans cet ordre, le premier motif atteint
gagne :
1. `low_letters` (trois sources) : moins de 30 % de lettres parmi les caractères hors espaces ;
2. `too_short` (Common Crawl) : moins de 100 caractères hors espaces ;
3. `repeated_lines` (Common Crawl) : à partir de 10 lignes non vides, plus de 60 % de ces
   lignes sont des répétitions d'une ligne déjà vue dans le document.
La ponctuation et la longueur moyenne des mots sont mesurées sans servir à rejeter.
"""

import argparse
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from pipeline.clean import WORD, default_kit
from pipeline.pii import mask
from pipeline.variants import run_stage, snippet_source

LETTER_MIN = 0.30
SHORT_MIN = 100
REPEAT_MAX = 0.60
REPEAT_FROM = 10
CRAWL = "common_crawl"

# Table de suppression des signes de ponctuation Unicode (catégories P*), construite une fois.
PUNCT_TABLE = {
    code: None for code in range(sys.maxunicode + 1) if unicodedata.category(chr(code)).startswith("P")
}


def metrics(text):
    """Mesure part de lettres, ponctuation et longueur moyenne des mots du document."""
    compact = "".join(text.split())
    size = len(compact)
    letters = sum(map(str.isalpha, compact))
    punctuation = size - len(compact.translate(PUNCT_TABLE))
    words = WORD.findall(text)
    return {
        "non_space": size,
        "letter_ratio": letters / size if size else 0.0,
        "punctuation_ratio": punctuation / size if size else 0.0,
        "mean_word_length": sum(map(len, words)) / len(words) if words else 0.0,
    }


def repeated_ratio(text):
    """Part des lignes non vides qui répètent une ligne déjà vue, et nombre de lignes."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return 0.0, 0
    return (len(lines) - len(set(lines))) / len(lines), len(lines)


def decide(text, source, values):
    """Renvoie le premier motif de rejet atteint, ou None si le document est gardé."""
    if values["letter_ratio"] < LETTER_MIN:
        return "low_letters"
    if source == CRAWL:
        if values["non_space"] < SHORT_MIN:
            return "too_short"
        ratio, count = repeated_ratio(text)
        if count >= REPEAT_FROM and ratio > REPEAT_MAX:
            return "repeated_lines"
    return None


def evaluate(text, source):
    """Évalue un texte : (motif de rejet ou None, mesures)."""
    values = metrics(text)
    return decide(text, source, values), values


class QualityFilter:
    """Étape de filtrage : supprime les documents rejetés et mesure les indicateurs."""

    name = "quality"
    params = {
        "letter_min": LETTER_MIN, "short_min_non_space": SHORT_MIN, "repeat_max": REPEAT_MAX,
        "repeat_from_lines": REPEAT_FROM, "crawl_only": ["too_short", "repeated_lines"],
    }

    def __init__(self):
        """Prépare les cumuls des mesures sur les documents lus et gardés."""
        self.sums = defaultdict(lambda: defaultdict(float))

    def apply(self, row):
        """Rejette ou garde un document, et cumule ses mesures par source."""
        source = row["source"]
        reason, values = evaluate(row["text"], source)
        for scope in ("all",) if reason else ("all", "kept"):
            cumul = self.sums[(source, scope)]
            cumul["docs"] += 1
            cumul["punctuation_ratio"] += values["punctuation_ratio"]
            cumul["mean_word_length"] += values["mean_word_length"]
            cumul["letter_ratio"] += values["letter_ratio"]
        if reason:
            return None, Counter({f"reject:{reason}": 1})
        return row, Counter()

    def view(self, row, new_row, tag):
        """Début du texte, avec les e-mails, téléphones, IBAN, URL et IP masqués."""
        return snippet_source(row["text"], mask)

    def summary(self):
        """Moyennes des mesures par source, sur tous les documents puis sur les gardés."""
        result = {}
        for (source, scope), cumul in sorted(self.sums.items()):
            docs = cumul["docs"]
            result.setdefault(source, {})[scope] = {
                "docs": int(docs),
                **{key: cumul[key] / docs for key in ("letter_ratio", "punctuation_ratio", "mean_word_length")},
            }
        return result


def main():
    """Applique les filtres qualité à un dossier JSONL.gz et publie la sortie après audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=Path("data/interim/dedup/final"))
    parser.add_argument("--out", type=Path, default=Path("data/interim/quality/final"))
    parser.add_argument("--kit", type=Path, default=default_kit())
    parser.add_argument("--limit", type=int, help="pilote : N premiers documents par source")
    args = parser.parse_args()
    run_stage(args.src, args.out, QualityFilter(), args.kit, name="quality", limit=args.limit)


if __name__ == "__main__":
    main()
