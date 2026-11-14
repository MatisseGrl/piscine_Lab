"""Vérifie la collecte et le nettoyage de Wikinews FR."""

import bz2

from pipeline.clean import ValidationGuard
from pipeline.wikinews import (
    build, contaminated, exact_step, iter_pages, keep_long_enough, minhash_step,
    quality_step, repetitions, wikitext_to_text,
)

# Treize mots (ou plus) qui servent de séquence de validation.
VALIDATION = "le gouvernement a annoncé hier soir une série de mesures exceptionnelles pour soutenir les agriculteurs"
FRENCH = lambda text: ("fr", 0.99)


def phrase(n):
    """Texte français de plus de 100 caractères, distinct selon n."""
    return f"Article numéro {n} : les habitants du village ont célébré la fête locale avec de la musique et des danses pendant toute la soirée de samedi dernier, sans incident."


def test_contamination_13_words():
    """Un texte qui contient 13 mots de la validation est détecté, même en majuscules."""
    guard = ValidationGuard([VALIDATION])
    assert contaminated("Intro. " + VALIDATION.upper() + " Fin.", guard)
    # Douze mots seulement : pas de recouvrement de 13 mots.
    assert not contaminated(" ".join(VALIDATION.split()[:12]) + " autre chose entièrement.", guard)
    assert not contaminated("Un texte sans rapport avec la validation du kit.", guard)


def test_contamination_rejects_in_build():
    """build écarte l'article contaminé avec le motif validation_overlap."""
    guard = ValidationGuard([VALIDATION])
    pages = [
        {"page_id": "1", "title": "A", "revision": "10", "timestamp": "2020-01-01T00:00:00Z",
         "wikitext": phrase(1)},
        {"page_id": "2", "title": "B", "revision": "11", "timestamp": "2021-01-01T00:00:00Z",
         "wikitext": phrase(2) + " " + VALIDATION},
    ]
    rows, stats = build(pages, guard, FRENCH)
    assert [row["id"] for row in rows] == ["1:10"]
    assert stats["clean"]["rejected_docs_by_reason"] == {"validation_overlap": 1}
    assert stats["revision_timestamp_max"] == "2021-01-01T00:00:00Z"


def test_wikitext_removes_markup():
    """Retire modèles, catégories, images, bandeaux et sections de fin, garde les libellés."""
    source = (
        "[[Image:Harbin.png|thumbs|right|légende [[Chine]]]]\n"
        "{{date|25 novembre 2005}} Un [[w:Harbin|accident]] '''majeur''' a eu lieu "
        "[[Chine]]<ref>note</ref> ; voir [http://exemple.org le site] et http://x.fr/a.\n"
        "{{Archive}}\n"
        "== Réactions ==\n* Une réaction.\n"
        "==Sources==\n*{{en}}, Wikinews: [[:en:Titre|Titre]]\n"
        "[[Catégorie:Chine]]\n"
    )
    text = wikitext_to_text(source)
    assert text.startswith("25 novembre 2005 Un accident majeur a eu lieu Chine ; voir le site et")
    assert "Réactions\nUne réaction." in text
    for banned in ("Image", "{{", "[[", "Catégorie", "Sources", "Titre", "http", "'''"):
        assert banned not in text


def test_wikitext_table_and_langlink():
    """Les tableaux et liens interlangues disparaissent."""
    text = wikitext_to_text("Avant.\n{|\n| a || b\n|}\nAprès [[en:Foo]] fin.")
    assert text == "Avant.\n\nAprès fin."


def test_iter_pages_filters(tmp_path):
    """Ne garde que l'espace 0, sans redirection."""
    xml = (
        '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">'
        "<page><title>A</title><ns>0</ns><id>1</id><revision><id>9</id>"
        "<timestamp>2020-01-01T00:00:00Z</timestamp><text>Texte A</text></revision></page>"
        "<page><title>R</title><ns>0</ns><id>2</id><redirect title=\"A\"/><revision><id>8</id>"
        "<text>#REDIRECTION [[A]]</text></revision></page>"
        "<page><title>Modèle:X</title><ns>10</ns><id>3</id><revision><id>7</id>"
        "<text>x</text></revision></page></mediawiki>"
    )
    path = tmp_path / "d.xml.bz2"
    path.write_bytes(bz2.compress(xml.encode("utf-8")))
    pages = list(iter_pages(path))
    assert [(p["title"], p["revision"], p["wikitext"]) for p in pages] == [("A", "9", "Texte A")]


def test_exact_on_normalized_text():
    """Deux textes qui ne diffèrent que par casse, espaces et forme Unicode sont doublons."""
    rows = [{"text": "Été  chaud"}, {"text": "été CHAUD"}, {"text": "Autre"}]
    kept, rejected = exact_step(rows)
    assert len(kept) == 2 and rejected == 1


def test_minhash_threshold():
    """Un quasi-doublon (≥ 0,97) est retiré, un texte différent reste."""
    base = " ".join(f"mot{i}" for i in range(200))
    near = base + " ajout"
    other = " ".join(f"autre{i}" for i in range(200))
    kept, rejected = minhash_step([{"text": base}, {"text": near}, {"text": other}])
    assert rejected == 1 and [r["text"] for r in kept] == [base, other]


def test_short_and_quality():
    """Le seuil de longueur compte les caractères hors espaces ; low_letters rejette les chiffres."""
    assert not keep_long_enough("court")
    assert keep_long_enough(phrase(1))
    kept, reasons = quality_step([{"text": phrase(1)}, {"text": "1234 5678 " * 30}])
    assert len(kept) == 1 and reasons == {"low_letters": 1}


def test_repetitions():
    """Répétitions pour couvrir 5, 10 et 25 % de 100 007 936 tokens."""
    assert repetitions(10_000_000) == {"5%": 0.5, "10%": 1.0, "25%": 2.5}


def test_wikitext_residue_lines():
    """Les restes de tableaux sans « {| » et les images non fermées sont retirés."""
    brut = "Début.\n! Titre\n|-----\n| 29%\n[[Image:a.jpg|300px[right|thumb|Légende]]\nFin."
    assert wikitext_to_text(brut) == "Début.\nFin."
