"""Vérifie la reprise sur Molière : découpage train / held-out sans recouvrement, planning cosinus."""
import torch

from minigpt.continue_pretrained import cosine_lr, split_holdout
from minigpt.model import GPT, GPTConfig
from minigpt.continue_pretrained import continue_training


def test_split_holdout_takes_tail_without_overlap():
    ids = torch.arange(100)
    train, held = split_holdout(ids, 0.1)
    # Le held-out est la fin du train officiel, jamais la validation.
    assert held.tolist() == list(range(90, 100))
    assert train.tolist() == list(range(90))


def test_cosine_lr_goes_from_max_to_min():
    assert abs(cosine_lr(0, 100, 1e-4, 1e-5) - 1e-4) < 1e-12
    assert abs(cosine_lr(100, 100, 1e-4, 1e-5) - 1e-5) < 1e-12
    assert 1e-5 < cosine_lr(50, 100, 1e-4, 1e-5) < 1e-4


def test_continue_training_lowers_heldout_loss_on_pattern():
    torch.manual_seed(0)
    model = GPT(GPTConfig(vocab_size=8, block_size=8, n_layer=1, n_head=1, d_model=16))
    ids = torch.arange(400) % 4  # motif périodique facile
    history = continue_training(model, ids[:300], ids[300:], steps=60, every=30, batch_size=8,
                                lr=1e-2, min_lr=1e-3, seed=1)
    # Une mesure au départ, puis tous les 30 pas, et la loss held-out baisse.
    assert [h['step'] for h in history] == [0, 30, 60]
    assert history[-1]['holdout_loss'] < history[0]['holdout_loss']
