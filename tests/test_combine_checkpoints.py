"""Vérifie la comparaison BPB et le lissage des probabilités de fréquences."""
import pytest
import torch

from minigpt.combine_checkpoints import ngram_probabilities, target_log_probs
from minigpt.model import GPT, GPTConfig, bits_per_byte, evaluate_bpb


def test_grouped_windows_match_reference():
    """Le dernier morceau incomplet conserve le même score que la boucle de référence."""
    torch.manual_seed(21)
    model = GPT(GPTConfig(vocab_size=8, block_size=4, n_layer=1, n_head=2, d_model=8))
    ids = [0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3]
    text = 'élève'
    logp = target_log_probs(model, torch.tensor(ids))
    assert logp.numel() == len(ids) - 1
    assert bits_per_byte(-logp.sum().item(), text) == pytest.approx(evaluate_bpb(model, ids, text), abs=1e-6)


def test_ngram_distribution_counts_only_real_followers():
    """Le préfixe en fin de train ne crée ni masse manquante ni token fictif."""
    train = [1, 2, 0, 1, 2]
    predictions = [ngram_probabilities(train, [1, 2, target], 4, 3)[0][-1].item() for target in range(3)]
    assert sum(predictions) == pytest.approx(1)
    assert predictions[0] > predictions[1]
