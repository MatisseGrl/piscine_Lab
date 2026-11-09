"""Vérifie les règles de nettoyage et le garde-fou de validation."""

from io import StringIO

import pytest

from pipeline.clean import ValidationGuard, clean_text, process_source, remove_boilerplate, select_wet


def test_wet_byte_cap_keeps_whole_prefix(tmp_path):
    """Inclut l'égalité au plafond et s'arrête avant l'archive suivante."""
    paths = []
    for index, size in enumerate((3, 5, 9, 1)):
        path = tmp_path / f"{index}.wet.gz"
        path.write_bytes(b"x" * size)
        paths.append(path)
    assert select_wet(paths, 8) == (paths[:2], 8)
    assert select_wet(paths, 10) == (paths[:2], 8)
    assert select_wet(paths, None) == (paths, 18)
    with pytest.raises(ValueError, match="première archive"):
        select_wet(paths, 2)


@pytest.mark.parametrize(
    ("language", "score", "reason"),
    [("fr", 0.80, None), ("en", 0.99, "non_french"), ("fr", 0.79, "low_confidence")],
)
def test_language(language, score, reason):
    """Applique la langue dominante et inclut exactement le seuil."""
    result = clean_text("Un texte à classifier.", "wikipedia_fr", lambda _: (language, score))
    assert result.reason == reason


def test_encoding():
    """Répare les accents avant la prédiction."""
    def predict(text):
        """Contrôle le texte effectivement fourni au détecteur."""
        assert text == "L’été est arrivé."
        return "fr", 0.99

    result = clean_text("Lâ€™Ã©tÃ© est arrivÃ©.", "wikipedia_fr", predict)
    assert result.text == "L’été est arrivé."


def test_boilerplate():
    """Retire les lignes parasites et conserve leurs mentions dans le corps."""
    body = ["Le texte parle des cookies et des mentions légales."] * 12
    lines = ["Rubrique", "Rubrique", "Rubrique", "Menu", "Accepter tous les cookies"]
    lines += body[:6] + ["Rubrique"] + body[6:] + ["Mentions légales"]
    text = "\n".join(lines)
    assert remove_boilerplate(text) == "\n".join(body[:6] + ["Rubrique"] + body[6:])
    assert clean_text(text, "assemblee_nationale", lambda _: ("fr", 1)).text == text


def test_boilerplate_only():
    """Écarte un document vide avant d'appeler le détecteur."""
    def predict(_):
        """Échoue si une prédiction est demandée sur du vide."""
        pytest.fail("Prédiction sur un document vide")

    assert clean_text("Menu\nAccepter tous les cookies", "common_crawl", predict).reason == "empty_after_cleaning"


def test_validation_excerpt():
    """Détecte aussi un extrait inséré dans une page plus grande."""
    validation = "un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze"
    guard = ValidationGuard([validation, "Une validation courte."])
    assert guard.matches("Introduction. " + validation.upper() + " Fin.")
    assert guard.matches("Intro : Une validation courte !")
    assert not guard.matches("un deux trois quatre cinq six sept huit neuf dix onze douze")


def test_validation_excluded_from_both_outputs():
    """Écarte aussi un passage de validation reconstitué par le nettoyage."""
    guard = ValidationGuard(["Une validation courte."])
    documents = [("rejected", "Une validation\nMenu\ncourte."), ("kept", "Un texte français.")]
    cleaned, raw = StringIO(), StringIO()
    stats = process_source(documents, "common_crawl", cleaned, raw, lambda _: ("fr", 0.99), guard)
    assert stats["rejected_docs_by_reason"] == {"validation_overlap": 1}
    assert stats["bytes_after"] == len("Un texte français.".encode("utf-8"))
    assert "rejected" not in cleaned.getvalue()
    assert "rejected" not in raw.getvalue()
    assert "kept" in cleaned.getvalue()
    assert "kept" in raw.getvalue()
