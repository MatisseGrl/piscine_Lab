"""Vérifie minigpt.model : formes, masque causal, LayerNorm, attention, surapprentissage, BPB."""

import math

import pytest
import torch
import torch.nn.functional as F

from minigpt.model import (
    GPT,
    CausalSelfAttention,
    GPTConfig,
    LayerNorm,
    bits_per_byte,
    evaluate_bpb,
)


def tiny_config(**kwargs) -> GPTConfig:
    """Petite config pour que les tests tournent en quelques secondes sur CPU."""
    base = dict(vocab_size=50, block_size=16, n_layer=2, n_head=2, d_model=32)
    base.update(kwargs)
    return GPTConfig(**base)


def test_output_shapes():
    # logits (B, T, V) ; loss scalaire si on donne des cibles, None sinon.
    torch.manual_seed(0)
    cfg = tiny_config()
    model = GPT(cfg)
    idx = torch.randint(0, cfg.vocab_size, (3, 10))
    logits, loss = model(idx)
    assert logits.shape == (3, 10, cfg.vocab_size)
    assert loss is None
    logits, loss = model(idx, targets=idx)
    assert loss.shape == ()
    # Modèle à l'initialisation : loss proche de ln(V) (prédiction quasi uniforme).
    assert abs(loss.item() - math.log(cfg.vocab_size)) < 0.5


def test_rejects_sequence_longer_than_context():
    cfg = tiny_config()
    model = GPT(cfg)
    with pytest.raises(ValueError):
        model(torch.zeros((1, cfg.block_size + 1), dtype=torch.long))


def test_causal_mask_future_tokens_do_not_change_past_logits():
    # On change les tokens après la position t : les logits des positions 0..t ne bougent pas.
    torch.manual_seed(0)
    cfg = tiny_config()
    model = GPT(cfg).eval()
    idx = torch.randint(0, cfg.vocab_size, (2, cfg.block_size))
    t = 7
    idx2 = idx.clone()
    idx2[:, t + 1 :] = (idx2[:, t + 1 :] + 1) % cfg.vocab_size
    with torch.no_grad():
        a, _ = model(idx)
        b, _ = model(idx2)
    torch.testing.assert_close(a[:, : t + 1], b[:, : t + 1])
    # Contrôle que le test teste quelque chose : les positions futures, elles, changent.
    assert not torch.allclose(a[:, t + 1 :], b[:, t + 1 :])


def test_attention_matches_pytorch_reference():
    # Mon attention écrite à la main == scaled_dot_product_attention de PyTorch (référence de test seulement).
    torch.manual_seed(0)
    cfg = tiny_config()
    attn = CausalSelfAttention(cfg).eval()
    x = torch.randn(2, 12, cfg.d_model)
    with torch.no_grad():
        mine = attn(x)
        # Recalcul avec PyTorch à partir des mêmes poids.
        B, T, C = x.shape
        q, k, v = attn.qkv(x).split(C, dim=2)
        hd = C // cfg.n_head
        q, k, v = (z.view(B, T, cfg.n_head, hd).transpose(1, 2) for z in (q, k, v))
        ref = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        ref = attn.proj(ref.transpose(1, 2).contiguous().view(B, T, C))
    torch.testing.assert_close(mine, ref)


def test_layernorm_matches_torch():
    # Ma LayerNorm == torch.nn.LayerNorm, avec des poids et biais non triviaux.
    torch.manual_seed(0)
    d = 24
    mine, ref = LayerNorm(d), torch.nn.LayerNorm(d)
    with torch.no_grad():
        w, b = torch.randn(d), torch.randn(d)
        mine.weight.copy_(w)
        mine.bias.copy_(b)
        ref.weight.copy_(w)
        ref.bias.copy_(b)
    x = torch.randn(4, 7, d) * 3 + 2
    torch.testing.assert_close(mine(x), ref(x))
    # Gradients identiques aussi.
    x1 = x.clone().requires_grad_(True)
    x2 = x.clone().requires_grad_(True)
    mine(x1).pow(2).sum().backward()
    ref(x2).pow(2).sum().backward()
    torch.testing.assert_close(x1.grad, x2.grad)


def test_overfits_one_minibatch():
    # Un modèle correct doit apprendre par coeur un mini-batch fixe : loss proche de 0.
    torch.manual_seed(0)
    cfg = tiny_config()
    model = GPT(cfg)
    x = torch.randint(0, cfg.vocab_size, (2, cfg.block_size + 1))
    inputs, targets = x[:, :-1], x[:, 1:]
    opt = torch.optim.AdamW(model.parameters(), lr=1e-2, weight_decay=0.0)
    for _ in range(300):
        _, loss = model(inputs, targets)
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert loss.item() < 0.05


def test_bits_per_byte_divides_by_utf8_bytes():
    # "été" = 3 caractères mais 5 octets UTF-8. 5 bits au total -> 1 bit/octet (pas 5/3).
    nll_nats = 5 * math.log(2)
    assert bits_per_byte(nll_nats, "été") == pytest.approx(1.0)
    assert len("été") == 3 and len("été".encode("utf-8")) == 5


def test_evaluate_bpb_uniform_model():
    # Tête de sortie à zéro -> logits nuls -> proba uniforme 1/V pour chaque token prédit.
    # Bits attendus : (n_tokens - 1) * log2(V), divisés par les octets du texte.
    torch.manual_seed(0)
    cfg = tiny_config()
    model = GPT(cfg)
    with torch.no_grad():
        model.head.weight.zero_()
    text = "Où est l'été ?"
    ids = [i % cfg.vocab_size for i in range(40)]  # 40 tokens, plus long que le contexte (16)
    expected = (len(ids) - 1) * math.log2(cfg.vocab_size) / len(text.encode("utf-8"))
    assert evaluate_bpb(model, ids, text) == pytest.approx(expected, rel=1e-5)


def test_generate_shapes_and_seed():
    torch.manual_seed(0)
    cfg = tiny_config()
    model = GPT(cfg)
    start = torch.zeros((1, 1), dtype=torch.long)
    # On génère plus que la longueur de contexte : le modèle doit recadrer sur les derniers tokens.
    g1 = torch.Generator().manual_seed(42)
    out1 = model.generate(start, max_new_tokens=30, temperature=0.8, generator=g1)
    g2 = torch.Generator().manual_seed(42)
    out2 = model.generate(start, max_new_tokens=30, temperature=0.8, generator=g2)
    assert out1.shape == (1, 31)
    assert out1.min() >= 0 and out1.max() < cfg.vocab_size
    assert torch.equal(out1, out2)  # même graine -> même texte
    with pytest.raises(ValueError):
        model.generate(start, max_new_tokens=1, temperature=0.0)
