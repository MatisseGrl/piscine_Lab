"""Vérifie les sources des paires et le masquage de la consigne."""

import torch
import torch.nn.functional as F

from minigpt.dialogue import extract_pairs, masked_example


def test_pairs_do_not_cross_scene_boundaries():
    """Une nouvelle scène ne devient jamais la réponse d'un personnage."""
    text = "PAUL.\n\nBonjour.\n\nJEAN.\n\nBonsoir.\n\nSCÈNE II.\n\nPAUL.\n\nAdieu."
    assert extract_pairs(text) == [("Bonjour.", "Bonsoir.")]


def test_only_response_tokens_contribute_to_loss():
    """Le premier token de réponse est appris, la question et le padding ignorés."""
    x, targets = masked_example([1, 2, 3], [4, 5], 8)
    assert x.tolist() == [1, 2, 3, 4, 0, 0, 0, 0]
    assert targets.tolist() == [-100, -100, 4, 5, -100, -100, -100, -100]
    logits = torch.zeros(8, 6, requires_grad=True)
    loss = F.cross_entropy(logits, targets)
    loss.backward()
    assert logits.grad[:2].abs().sum() == 0
    assert logits.grad[2:4].abs().sum() > 0
    assert logits.grad[4:].abs().sum() == 0
