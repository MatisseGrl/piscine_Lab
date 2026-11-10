"""Vérifie les filtres qualité : seuils exacts, règles propres à Common Crawl, ordre des motifs."""

import pytest

from pipeline.quality import evaluate, metrics

LONG_LINE = "Menu principal du site numéro {}"  # 28 caractères hors espaces environ


def test_metrics_values():
    """Calcule la part de lettres, la ponctuation et la longueur moyenne des mots."""
    values = metrics("Salut, toi !")
    assert values["letter_ratio"] == pytest.approx(8 / 10)
    assert values["punctuation_ratio"] == pytest.approx(2 / 10)
    assert values["mean_word_length"] == pytest.approx(4.0)
    assert metrics("   ")["letter_ratio"] == 0.0


def test_letter_threshold_is_strict():
    """Garde exactement 30 % de lettres et rejette en dessous, sur les trois sources."""
    # 120 caractères dont 36 lettres = 30 % pile ; 24 lettres = 20 %. Assez long pour Common Crawl.
    exactly = "abc1234567" * 12
    below = "ab12345678" * 12
    for source in ("wikipedia_fr", "assemblee_nationale", "common_crawl"):
        assert evaluate(exactly, source)[0] is None
        assert evaluate(below, source)[0] == "low_letters"


def test_short_rule_only_common_crawl():
    """Le seuil de 100 caractères hors espaces ne vaut que pour Common Crawl."""
    text99 = "a" * 99 + " " * 50
    text100 = "a" * 100 + " " * 50
    assert evaluate(text99, "common_crawl")[0] == "too_short"
    assert evaluate(text100, "common_crawl")[0] is None
    assert evaluate(text99, "wikipedia_fr")[0] is None
    assert evaluate(text99, "assemblee_nationale")[0] is None


def test_repeated_lines_threshold():
    """Rejette au-delà de 60 % de lignes répétées, à partir de 10 lignes non vides."""
    same = LONG_LINE.format(1)
    # 8 fois la même ligne + 2 différentes = 7 répétitions sur 10 : rejeté.
    rejected = "\n".join([same] * 8 + [LONG_LINE.format(2), LONG_LINE.format(3)])
    assert evaluate(rejected, "common_crawl")[0] == "repeated_lines"
    # 4 lignes distinctes sur 10 = 6 répétitions : exactement 60 %, gardé.
    exactly = "\n".join([same] * 7 + [LONG_LINE.format(i) for i in (2, 3, 4)])
    assert evaluate(exactly, "common_crawl")[0] is None
    # Moins de 10 lignes non vides : jamais rejeté pour ce motif.
    short = "\n".join([same] * 9)
    assert evaluate(short, "common_crawl")[0] is None
    # Les lignes vides ne comptent pas et la règle ne vise que Common Crawl.
    assert evaluate(rejected + "\n\n\n", "common_crawl")[0] == "repeated_lines"
    assert evaluate(rejected, "wikipedia_fr")[0] is None


def test_first_matching_rule_wins():
    """Attribue le rejet au premier motif dans l'ordre lettres, longueur, répétition."""
    assert evaluate("12 34", "common_crawl")[0] == "low_letters"
    assert evaluate("abc def", "common_crawl")[0] == "too_short"


def test_normal_text_kept():
    """Un texte français ordinaire passe toutes les règles."""
    text = "Le village se situe au bord de la rivière, non loin de la route nationale. " * 3
    assert evaluate(text, "common_crawl")[0] is None
    assert evaluate(text, "wikipedia_fr")[0] is None
