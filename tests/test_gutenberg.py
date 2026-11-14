"""Vérifie la collecte Gutenberg : catalogue, exclusions, nettoyage, contamination, dédup."""

import pytest

from pipeline.clean import ValidationGuard
from pipeline.gutenberg import (
    KIT_MOLIERE_IDS, dedup_books, exclusion_reason, parse_catalog, process_books, strip_gutenberg,
)

CATALOG = (
    "Text#,Type,Issued,Title,Language,Authors,Subjects,LoC Class,Bookshelves\n"
    '1,Text,2000-01-01,Un conte,fr,"Hugo, Victor, 1802-1885",,,\n'
    '2,Text,2000-01-01,English tale,en,"Poe, Edgar Allan",,,\n'
    '3,Sound,2000-01-01,Lecture audio,fr,"Zola, Émile",,,\n'
    '4,Text,2000-01-01,Mélange,fr; en,"Sand, George",,,\n'
    '40086,Text,2000-01-01,Les Fourberies,fr,"Anonyme",,,\n'
    '99,Text,2000-01-01,"Le Misanthrope, comédie",fr,"Molière, 1622-1673",,,\n'
)


def book(body, header="Préface de l'éditeur\n"):
    """Fabrique un livre Gutenberg avec son en-tête et son pied de page."""
    return (
        "The Project Gutenberg eBook of Test\n\n" + header
        + "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n\n" + body
        + "\n\n*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\nLicence ...\n"
    )


def test_catalog_keeps_french_text_only():
    """Ne garde que les textes dont la langue est exactement `fr`."""
    rows = parse_catalog(CATALOG)
    assert [row["id"] for row in rows] == [1, 40086, 99]


@pytest.mark.parametrize("book_id", [40086, 43535, 50173, 57270])
def test_kit_moliere_ids_excluded(book_id):
    """Les quatre eBooks du corpus Molière du kit sont toujours exclus."""
    assert book_id in KIT_MOLIERE_IDS
    assert exclusion_reason({"id": book_id, "title": "x", "authors": "y"}) == "kit_moliere_id"


def test_moliere_author_and_validation_titles_excluded():
    """Tout texte de Molière, et les pièces de la validation, sont exclus."""
    assert exclusion_reason({"id": 99, "title": "Tartuffe", "authors": "Molière, 1622-1673"}) == "moliere_author"
    assert exclusion_reason({"id": 5, "title": "Moliere", "authors": "MOLIERE"}) == "moliere_author"
    assert exclusion_reason({"id": 6, "title": "L'Avare", "authors": "Autre"}) == "validation_title"
    assert exclusion_reason({"id": 7, "title": "Le Sicilien ou l'Amour peintre", "authors": "X"}) == "validation_title"
    assert exclusion_reason({"id": 8, "title": "Les Misérables", "authors": "Hugo, Victor"}) is None


def test_strip_header_and_footer():
    """Retire tout ce qui précède START et suit END."""
    text, reason = strip_gutenberg(book("Il était une fois un roi.\n\nIl vécut."))
    assert reason is None
    assert text == "Il était une fois un roi.\n\nIl vécut."
    assert "Gutenberg" not in text and "Licence" not in text


def test_strip_requires_markers():
    """Sans marqueur, le livre est rejeté plutôt que gardé avec son en-tête."""
    assert strip_gutenberg("Juste du texte")[1] == "no_markers"


def test_strip_transcriber_note_and_toc():
    """Retire notes du transcripteur et tables des matières, garde le récit."""
    body = (
        "[Note du transcripteur : orthographe d'origine conservée.]\n\n"
        "TABLE DES MATIÈRES\n\nI. Le départ\n\nII. L'arrivée\n\nIII. La fin\n\n"
        + ("Un long paragraphe de récit qui dépasse largement la limite des entrées de table. " * 3)
        + "\n\nSuite du récit."
    )
    text, _ = strip_gutenberg(book(body))
    assert "transcripteur" not in text.lower()
    assert "MATIÈRES" not in text and "Le départ" not in text
    assert text.startswith("Un long paragraphe") and text.endswith("Suite du récit.")


def test_strip_keeps_short_story_text():
    """Un paragraphe court sans titre de table n'est pas retiré."""
    text, _ = strip_gutenberg(book("Bonjour.\n\nAu revoir."))
    assert text == "Bonjour.\n\nAu revoir."


def predict_fr(text):
    """Faux détecteur : tout est du français sûr."""
    return "fr", 0.99


VAL = ["Ceci est une phrase de validation assez longue pour contenir treize mots distincts exactement ici ok"]


def test_contamination_rejects_whole_book():
    """Un livre qui partage 13 mots avec la validation est écarté, pas tronqué."""
    guard = ValidationGuard(VAL)
    leak = "Ceci est une phrase de validation assez longue pour contenir treize mots distincts"
    rows = [
        {"id": 1, "text": "Un récit propre et sans rapport avec la validation, avec assez de lettres."},
        {"id": 2, "text": "Début. " + leak + ". Fin."},
    ]
    kept, stats = process_books(rows, predict_fr, guard)
    assert [row["id"] for row in kept] == [1]
    assert stats["rejected_docs_by_reason"] == {"validation_overlap": 1}


def test_bytes_counted_in_utf8():
    """Les octets comptent l'UTF-8 (é = 2 octets), pas les caractères."""
    guard = ValidationGuard(VAL)
    kept, stats = process_books([{"id": 1, "text": "été été été"}], predict_fr, guard)
    assert stats["bytes_after"] == len("été été été".encode("utf-8")) == 17


def test_low_letters_quality_reject():
    """Le filtre qualité actuel s'applique (moins de 30 % de lettres)."""
    guard = ValidationGuard(VAL)
    kept, stats = process_books([{"id": 1, "text": "1234 5678 90 12 34 56 a"}], predict_fr, guard)
    assert kept == [] and stats["rejected_docs_by_reason"] == {"low_letters": 1}


def test_dedup_exact_on_normalized_text():
    """Casse, espaces et accents décomposés ne cachent pas un doublon exact."""
    base = "Le petit chat boit du lait tous les matins dans la cuisine de la ferme voisine."
    rows = [
        {"id": 1, "text": base},
        {"id": 2, "text": "  " + base.upper().replace(" ", "  ") },
        {"id": 3, "text": "Tout autre sujet : la mer, le vent, les voiliers et les ports lointains du nord."},
    ]
    kept, stats = dedup_books(rows, 0.97)
    assert [row["id"] for row in kept] == [1, 3]
    assert stats["exact_rejected"] == 1 and stats["minhash_rejected"] == 0


def test_dedup_minhash_near_duplicate():
    """Deux éditions quasi identiques (un mot change) sont fusionnées à 0,97."""
    words = [f"mot{i}" for i in range(600)]
    a = " ".join(words)
    b = " ".join(words[:300] + ["autre"] + words[301:])
    c = " ".join(f"zzz{i}" for i in range(600))
    kept, stats = dedup_books([{"id": 1, "text": a}, {"id": 2, "text": b}, {"id": 3, "text": c}], 0.97)
    assert [row["id"] for row in kept] == [1, 3]
    assert stats["minhash_rejected"] == 1
