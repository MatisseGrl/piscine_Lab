"""Vérifie les décisions de déduplication sur des documents courts."""

from contextlib import ExitStack

import numpy as np

from pipeline.clean import digest, open_output, write_document
from pipeline.dedup import (
    ExactDeduper, build_links, exact, normalize, read_rows, sample, select_matches,
    shingles, signature, source_path, write_json,
)


def test_normalize():
    """Uniformise la casse, les espaces et les accents décomposés."""
    assert normalize("  E\u0301TÉ\r\n\tà  Paris ! ") == "été à paris !"
    assert normalize("cote") != normalize("côte")


def test_exact_representative():
    """Garde la première source prioritaire et distingue les types de rejet."""
    deduper = ExactDeduper()
    rows = [
        ("assemblee_nationale", "ÉTÉ  À PARIS"),
        ("assemblee_nationale", "été à Paris"),
        ("wikipedia_fr", " été à paris "),
        ("common_crawl", "été à Paris"),
    ]
    assert [deduper.add(source, text) for source, text in rows] == [
        "kept", "within", "cross", "cross",
    ]


def test_exact_keeps_original_row(tmp_path):
    """Relit le représentant original et vérifie les compteurs de chaque rejet."""
    clean = tmp_path / "clean"
    clean.mkdir()
    stats = {
        "common_crawl_selection": {
            "max_bytes": 1_050_000_000, "archive_bytes": 1_019_886_136, "archives": list(range(10)),
        },
        "limit_per_source": None, "validation_sha256": "test", "sources": {},
    }
    original = {"id": "premier", "source": "assemblee_nationale",
                "text": "ÉTÉ  À PARIS", "language_score": 0.95}
    texts = {"assemblee_nationale": [original, dict(original, id="second", text="été à Paris")],
             "wikipedia_fr": [dict(original, source="wikipedia_fr", text=" été à paris ")],
             "common_crawl": []}
    for source, rows in texts.items():
        with ExitStack() as stack:
            writer = open_output(stack, clean, source)
            for row in rows:
                write_document(writer, row)
        stats["sources"][source] = {
            "clean_sha256": digest(source_path(clean, source)), "docs_after": len(rows),
            "bytes_after": sum(len(row["text"].encode("utf-8")) for row in rows),
        }
    write_json(clean / "stats.json", stats)
    output = tmp_path / "exact"
    counts = exact(clean, output, pilot=False)["sources"]
    assert list(read_rows(source_path(output, "assemblee_nationale"))) == [original]
    assert counts["assemblee_nationale"]["within"] == 1
    assert counts["wikipedia_fr"]["cross"] == 1
    assert counts["wikipedia_fr"]["docs"] == 0


def test_sample_positions_are_reproducible():
    """Tire sans remise et laisse la lecture restituer l'ordre du corpus."""
    assert sample(100, 5) == {3, 14, 35, 81, 94}
    assert sample(2, 5) == {0, 1}


def test_near_duplicates():
    """Confirme les collisions par Jaccard et ignore les représentants rejetés."""
    original = " ".join(f"mot{i}" for i in range(100))
    variants = [original, original + " annexe", original + " suite inédite",
                "Un texte vraiment sans rapport avec le reste du corpus."]
    sets = [shingles(text) for text in variants]
    keys = np.array([signature(words) for words in sets], dtype=np.uint64)
    assert np.array_equal(keys[0], signature(sets[0]))
    links = build_links(keys)
    kept, _ = select_matches(links, np.array(list(map(len, sets))), sets.__getitem__, 0.8)
    assert kept.tolist() == [True, False, False, True]


def test_lsh_collision_needs_verification():
    """Une collision de bandes seule ne suffit jamais à supprimer un texte."""
    sets = [shingles("un chat dort sur le toit"), shingles("un chat dort sur le mur")]
    links = build_links(np.zeros((2, 16), dtype=np.uint64))
    kept, pairs = select_matches(links, np.array(list(map(len, sets))), sets.__getitem__, 0.8)
    assert kept.tolist() == [True, True]
    assert pairs["0.2–0.6"][0][2] == 1 / 3


def test_short_documents():
    """Un document court utilise sa séquence entière et un texte vide reste indexable."""
    assert shingles("Été, ici !") == {"été ici"}
    assert shingles("!?!") == set()


def test_rejected_candidate_cannot_remove_next_document():
    """Deux liens voisins ne suffisent pas à fusionner une chaîne de documents."""
    first = {str(index) for index in range(10)}
    middle = first | {"x"}
    last = middle | {"y", "z"}
    sets = [first, middle, last]
    links = build_links(np.zeros((3, 16), dtype=np.uint64))
    kept, _ = select_matches(links, np.array(list(map(len, sets))), sets.__getitem__, 0.8)
    assert kept.tolist() == [True, False, True]
