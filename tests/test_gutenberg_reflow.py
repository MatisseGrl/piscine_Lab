"""Vérifie que le recollage des marges conserve les structures Gutenberg."""

import pytest

from pipeline.gutenberg_reflow import reflow_text


PROSE = (
    "Toute la famille s'était levée de bonne heure pour prendre le",
    "train qui partait à six heures et gagner la campagne où les",
    "enfants passeraient l'été.",
)


def test_wrap_is_joined_without_other_changes():
    """Les lignes de prose proches d'une même marge forment un seul paragraphe."""
    text = "\n".join(PROSE) + "\n \nDeuxième paragraphe."
    expected = " ".join(PROSE) + "\n \nDeuxième paragraphe."
    assert reflow_text(text) == expected
    assert len(reflow_text(text).encode("utf-8")) == len(text.encode("utf-8"))


@pytest.mark.parametrize("lines", [
    (PROSE[0], "— " + PROSE[1], PROSE[2]),
    (PROSE[0], " " + PROSE[1], PROSE[2]),
    (PROSE[0], PROSE[1].capitalize(), PROSE[2].capitalize()),
    ("Au jardin", "dans le vent", "dans le soir"),
    (PROSE[0], PROSE[1]),
])
def test_structural_or_ambiguous_breaks_stay(lines):
    """Les répliques, alinéas, vers et paragraphes ambigus gardent leur mise en page."""
    text = "\n".join(lines)
    assert reflow_text(text) == text
