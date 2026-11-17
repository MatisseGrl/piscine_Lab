"""Vérifie le pré-entraînement sur flux binaire : lots décalés d'un token, planning du taux, baisse de loss."""

import numpy as np
import pytest
import torch

from minigpt.model import GPT, GPTConfig
from minigpt.pretrain import batches, enable_fused_kernels, learning_rate, pretrain


def test_batches_are_shifted_and_cover_each_sequence_once(tmp_path):
    # 3 séquences de 4 tokens + 1 token final : 13 tokens, valeurs = positions.
    path = tmp_path / "train.bin"
    np.arange(13, dtype=np.uint16).tofile(path)
    seen = []
    for x, y in batches(path, batch_size=1, seq_len=4, seed=7, steps=3):
        # La cible est l'entrée décalée d'un token.
        torch.testing.assert_close(y, x + 1)
        seen.append(int(x[0, 0]))
    # Chaque séquence (débuts 0, 4, 8) est vue une fois, dans un ordre mélangé.
    assert sorted(seen) == [0, 4, 8]


def test_learning_rate_warms_up_then_decays_to_min():
    assert learning_rate(0, 100, 10, 1e-2, 1e-3) < 1e-2 / 5  # début de montée
    assert abs(learning_rate(10, 100, 10, 1e-2, 1e-3) - 1e-2) < 1e-9  # pic après le warmup
    assert abs(learning_rate(99, 100, 10, 1e-2, 1e-3) - 1e-3) < 1e-4  # fin de cosinus


def test_pretrain_reduces_loss_on_repeated_pattern(tmp_path):
    # Flux périodique facile à apprendre : 0,1,2,3 répétés.
    path = tmp_path / "train.bin"
    np.tile(np.arange(4, dtype=np.uint16), 4000).tofile(path)
    cfg = GPTConfig(vocab_size=4, block_size=16, n_layer=1, n_head=2, d_model=32)
    result = pretrain(path, cfg, steps=40, batch_size=8, micro_batch=4, lr=5e-3, min_lr=5e-4,
                      warmup=4, seed=1, device="cpu", log_every=0)
    assert result["losses"][-1] < result["losses"][0] / 2
    assert result["model"].cfg.vocab_size == 4



def test_ordered_batches_share_the_short_prefix_and_never_wrap(tmp_path):
    """Les deux budgets partagent les mêmes séquences et une cible frontière."""
    path = tmp_path / "train.bin"
    np.arange(25, dtype="<u2").tofile(path)
    short = list(batches(path, batch_size=2, seq_len=4, seed=7, steps=1, ordered=True))
    long = list(batches(path, batch_size=2, seq_len=4, seed=7, steps=3, ordered=True))
    torch.testing.assert_close(short[0][0], long[0][0])
    torch.testing.assert_close(long[0][0].flatten(), torch.arange(8))
    torch.testing.assert_close(long[-1][1].flatten(), torch.arange(17, 25))
    with pytest.raises(ValueError, match="répétition"):
        list(batches(path, batch_size=2, seq_len=4, seed=7, steps=4, ordered=True))



def test_fused_kernels_preserve_logits_and_gradients():
    """Le chemin GPU doit garder les mêmes logits, gradients et noms de poids."""
    torch.manual_seed(23)
    cfg = GPTConfig(vocab_size=32, block_size=12, n_layer=2, n_head=2, d_model=16)
    reference = GPT(cfg).double()
    fused = GPT(cfg).double()
    fused.load_state_dict(reference.state_dict(), strict=True)
    enable_fused_kernels(fused)
    x = torch.randint(cfg.vocab_size, (3, cfg.block_size))
    y = torch.randint(cfg.vocab_size, (3, cfg.block_size))
    reference_logits, reference_loss = reference(x, y)
    fused_logits, fused_loss = fused(x, y)
    torch.testing.assert_close(fused_logits, reference_logits)
    torch.testing.assert_close(fused_loss, reference_loss)
    reference_loss.backward()
    fused_loss.backward()
    for expected, actual in zip(reference.parameters(), fused.parameters(), strict=True):
        torch.testing.assert_close(actual.grad, expected.grad)
