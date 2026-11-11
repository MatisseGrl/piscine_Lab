"""Contrôle la reprise des poids et les deux calendriers comparés."""

import pytest
import torch

from minigpt.model import GPT, GPTConfig
from minigpt.finetune import learning_rate, restore_model


def test_schedule_endpoints():
    """La décroissance atteint exactement les deux taux annoncés."""
    assert learning_rate(0, 1000, "cosine") == pytest.approx(1e-4)
    assert learning_rate(999, 1000, "cosine") == pytest.approx(1e-5)
    assert learning_rate(999, 1000, "constant") == pytest.approx(1e-4)


def test_resume_preserves_predictions_and_does_not_alias_weights():
    """La reprise conserve les prédictions sans modifier le checkpoint en mémoire."""
    torch.manual_seed(42)
    cfg = GPTConfig(vocab_size=8, block_size=4, n_layer=1, n_head=2, d_model=8)
    reference = GPT(cfg).eval()
    checkpoint = {"config": vars(cfg), "model": reference.state_dict()}
    resumed = restore_model(checkpoint).eval()
    ids = torch.tensor([[1, 2, 3]])
    torch.testing.assert_close(reference(ids)[0], resumed(ids)[0])
    with torch.no_grad():
        resumed.tok_emb.weight.add_(1)
    assert not torch.equal(reference.tok_emb.weight, resumed.tok_emb.weight)
