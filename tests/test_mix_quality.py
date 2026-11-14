"""Vérifie les bornes de passages, l'apprentissage des pseudo-labels et le stock web."""

import numpy as np
import pytest

from pipeline.mix_quality import MAX_CHARS, features, fit_classifier, noise, passages, score, select_documents


def test_passages_keep_all_words():
    """Chaque mot est présent une fois, et les passages ont une taille bornée."""
    words = ["phrase", "continue", "jusqu'à", "la", "dernière", "ligne."] * 110
    chunks = list(passages(" ".join(words)))
    assert len(chunks) > 1
    assert all(len(chunk) <= MAX_CHARS for chunk in chunks)
    assert " ".join(chunks).split() == words


def test_classifier_gives_more_weight_to_clean_structure():
    """Le classifieur sépare des passages suivis de leurs versions bruitées."""
    train = [
        "La pluie s'arrête au début de la soirée. Le sol reste humide.",
        "La bibliothèque a ouvert ses portes. Elle propose un atelier de lecture.",
        "Un groupe traverse la place en chantant. Les passants se retournent.",
    ]
    pairs = np.asarray([(features(text), features(noise(text, index))) for index, text in enumerate(train)])
    model = fit_classifier(pairs)
    text = "Le randonneur prépare son sac avant le départ. Son itinéraire traverse la forêt."
    assert all(score(features(text), model) > score(features(noise(text, index)), model) for index in range(3))


def test_selection_preserves_token_headroom():
    """Le nombre de tokens conservés couvre 110 % du quota demandé."""
    ranked = [(2.0, 2, 9), (1.0, 5, 3), (0.0, 9, 15)]
    assert select_documents(ranked, 10) == ({2, 5}, 12, 1.0)
    with pytest.raises(ValueError, match="ne fournit que"):
        select_documents(ranked, 25)
