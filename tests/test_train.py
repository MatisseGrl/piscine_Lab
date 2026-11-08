"""Vérifie les fenêtres aléatoires et l'apprentissage sur un mini-texte."""

import torch

from minigpt.model import GPT, GPTConfig
from minigpt.train import sample_batch, train_step


def test_batch_targets_are_shifted_by_one_token():
    ids = torch.arange(17)
    x, y = sample_batch(ids, 8, 5, torch.Generator().manual_seed(42))
    assert x.shape == y.shape == (8, 5)
    torch.testing.assert_close(x, x[:, :1] + torch.arange(5))
    torch.testing.assert_close(y, x + 1)
    # Une fenêtre de longueur maximale doit pouvoir commencer à zéro.
    x, y = sample_batch(ids, 1, 16, torch.Generator().manual_seed(42))
    torch.testing.assert_close(x[0], ids[:-1])
    torch.testing.assert_close(y[0], ids[1:])


def test_training_steps_reduce_loss_on_repeated_text():
    torch.manual_seed(42)
    text = torch.tensor(list(b"abc" * 16)) - ord("a")
    cfg = GPTConfig(vocab_size=3, block_size=6, n_layer=1, n_head=2, d_model=16)
    model = GPT(cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.02)
    generator = torch.Generator().manual_seed(42)
    x, y = sample_batch(text, 4, cfg.block_size, generator)
    with torch.no_grad():
        _, initial = model(x, y)
    for _ in range(12):
        train_step(model, optimizer, *sample_batch(text, 4, cfg.block_size, generator))
    with torch.no_grad():
        _, final = model(x, y)
    assert final.item() < initial.item() / 2
