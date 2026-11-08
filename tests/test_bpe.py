"""Vérifie minigpt.bpe : merges calculés à la main, aller-retour encode/decode, cas limites."""

from pathlib import Path

import pytest

from minigpt.bigram import load_utf8
from minigpt.bpe import BPETokenizer

VAL = Path("kit/Piscine/corpus/moliere_val.txt")


def test_first_merge_by_hand():
    # "aaabdaaabac" : paires (a,a)=4, (a,b)=2, les autres 1 -> premier merge (97, 97) -> 256.
    tok = BPETokenizer().train("aaabdaaabac", vocab_size=257)
    assert tok.merges == {(97, 97): 256}
    # aa|a b d aa|a b a c -> 9 tokens
    assert tok.encode("aaabdaaabac") == [256, 97, 98, 100, 256, 97, 98, 97, 99]


def test_three_merges_by_hand():
    # Après aa=256 : "Z a b d Z a b a c", (256,97)=2 et (97,98)=2 à égalité ;
    # on garde la paire vue en premier, (256,97) -> 257. Puis (257,98)=2 -> 258.
    tok = BPETokenizer().train("aaabdaaabac", vocab_size=259)
    assert tok.merges == {(97, 97): 256, (256, 97): 257, (257, 98): 258}
    assert tok.encode("aaabdaaabac") == [258, 100, 258, 97, 99]
    assert tok.vocab[258] == b"aaab"


def test_roundtrip_french_accents():
    tok = BPETokenizer().train("Le père et la mère étaient là, à côté.\n" * 20, vocab_size=300)
    text = "Où êtes-vous ? Ça, c'est l'œuvre de Molière : « Tartuffe » !\n\téàçùœ"
    assert tok.decode(tok.encode(text)) == text


def test_roundtrip_unseen_bytes():
    # Des caractères jamais vus à l'entraînement restent encodables (repli sur les 256 octets).
    tok = BPETokenizer().train("abc abc abc", vocab_size=260)
    text = "日本語 😀 ß"
    ids = tok.encode(text)
    assert all(0 <= i < len(tok.vocab) for i in ids)
    assert tok.decode(ids) == text


def test_empty_text():
    tok = BPETokenizer().train("abab", vocab_size=258)
    assert tok.encode("") == []
    assert tok.decode([]) == ""


def test_no_merge_crosses_word_boundary():
    # Le pré-découpage interdit les tokens à cheval sur deux mots (ex. "a b" collés).
    tok = BPETokenizer().train("ab ab ab ab", vocab_size=270)
    for piece in tok.vocab.values():
        assert b" " not in piece[1:]  # l'espace ne peut être qu'en tête de token


def test_save_load(tmp_path):
    tok = BPETokenizer().train("le chat et le chien", vocab_size=265)
    path = tmp_path / "bpe.json"
    tok.save(path)
    tok2 = BPETokenizer.load(path)
    assert tok2.merges == tok.merges
    assert tok2.encode("le chien") == tok.encode("le chien")


@pytest.mark.skipif(not VAL.exists(), reason="kit absent")
def test_roundtrip_on_validation():
    # Tokenizer entraîné sur un petit bout de la val, puis aller-retour sur toute la val.
    val = load_utf8(VAL).decode("utf-8")
    tok = BPETokenizer().train(val[:20_000], vocab_size=300)
    assert tok.decode(tok.encode(val)) == val
