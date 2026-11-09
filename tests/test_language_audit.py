"""Vérifie le tirage et le calcul de précision sur des annotations."""

from random import Random

import pytest

from pipeline.language_audit import precision, reservoir


def test_sampling():
    """Retrouve le même échantillon sans doublon avec la même graine."""
    first = reservoir(iter(range(100)), 10, Random(42))
    second = reservoir(iter(range(100)), 10, Random(42))
    assert first == second
    assert len(set(first)) == 10
    assert max(first) >= 10


def test_precision():
    """Compte seulement les documents annotés français au numérateur."""
    rows = [{"annotation": label} for label in ("fr", "autre", "fr", "mixte")]
    assert precision(rows) == {"annotated": 4, "french": 2, "precision": 0.5}
    with pytest.raises(ValueError, match="annotation"):
        precision(rows + [{"annotation": ""}])
