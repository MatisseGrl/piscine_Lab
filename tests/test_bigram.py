"""Vérifie minigpt.bigram : probabilités et BPB calculés à la main sur des mini-textes."""

import math

import pytest

from minigpt.bigram import BOS, ByteBigram, load_utf8


def test_counts_on_tiny_text():
    # "aab" -> paires (BOS, a), (a, a), (a, b)
    model = ByteBigram(alpha=0.0).fit(b"aab")
    a, b = ord("a"), ord("b")
    assert model.counts[BOS][a] == 1
    assert model.counts[a][a] == 1
    assert model.counts[a][b] == 1
    assert sum(model.counts[b]) == 0  # rien ne suit "b"


def test_probabilities_without_smoothing():
    # Après "a" : une fois "a", une fois "b" -> 1/2 chacun. Au début : toujours "a".
    model = ByteBigram(alpha=0.0).fit(b"aab")
    a, b = ord("a"), ord("b")
    assert model.prob(BOS, a) == 1.0
    assert model.prob(a, a) == 0.5
    assert model.prob(a, b) == 0.5


def test_bpb_by_hand_without_smoothing():
    # Bits sur "aab" : -log2(1) - log2(1/2) - log2(1/2) = 0 + 1 + 1 = 2 bits, 3 octets -> 2/3.
    model = ByteBigram(alpha=0.0).fit(b"aab")
    assert model.bpb(b"aab") == pytest.approx(2 / 3)


def test_probabilities_with_laplace_smoothing():
    # alpha = 1 : P(suivant | ctx) = (compte + 1) / (total_ctx + 256)
    model = ByteBigram(alpha=1.0).fit(b"aab")
    a, b, z = ord("a"), ord("b"), ord("z")
    assert model.prob(BOS, a) == pytest.approx(2 / 257)
    assert model.prob(a, b) == pytest.approx(2 / 258)
    assert model.prob(a, z) == pytest.approx(1 / 258)  # jamais vu, mais pas zéro
    assert model.prob(b, a) == pytest.approx(1 / 256)  # contexte jamais vu -> uniforme


def test_probabilities_sum_to_one():
    model = ByteBigram(alpha=0.5).fit("Le Misanthrope, été".encode("utf-8"))
    for ctx in (BOS, ord("e"), 0xC3, ord("q")):
        assert sum(model.prob(ctx, nxt) for nxt in range(256)) == pytest.approx(1.0)


def test_bpb_divides_by_utf8_bytes_not_characters():
    # Modèle vide + lissage -> uniforme sur 256 octets -> exactement 8 bits par octet.
    # "été" = 3 caractères mais 5 octets UTF-8 : diviser par les caractères donnerait 8 * 5 / 3.
    model = ByteBigram(alpha=1.0)
    text = "été".encode("utf-8")
    assert len(text) == 5
    assert model.bpb(text) == pytest.approx(8.0)


def test_load_utf8_strips_windows_carriage_returns(tmp_path):
    # Un fichier en CRLF doit donner les mêmes octets que sa version LF.
    path = tmp_path / "crlf.txt"
    path.write_bytes("été\r\nfin\r\n".encode("utf-8"))
    assert load_utf8(path) == "été\nfin\n".encode("utf-8")


def test_unseen_pair_without_smoothing_is_infinite():
    # Sans lissage, une paire jamais vue a une proba nulle -> BPB infini. D'où alpha > 0.
    model = ByteBigram(alpha=0.0).fit(b"aab")
    assert math.isinf(model.bpb(b"ba"))
