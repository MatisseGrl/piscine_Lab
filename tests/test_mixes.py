"""Tests des mélanges M1 à M5 : quotas exacts et répétition bornée d'une source trop petite."""

import gzip
import io
import json

import numpy as np
import pytest

from pipeline.mixes import MIXES, encode_repeating, quotas


class FakeTokenizer:
    """Tokenizer factice : un token par caractère, séparateur de document = 0."""

    eot_id = 0

    def encode_batch(self, texts):
        """Renvoie une liste d'identifiants par texte, comme le tokenizer du kit."""
        return [[ord(c) for c in text] for text in texts]


def write_archive(path, texts):
    """Écrit une archive JSONL gzip au format des sorties du pipeline."""
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for text in texts:
            stream.write(json.dumps({"text": text}) + "\n")


def test_every_mix_sums_to_100():
    """Chaque mélange fait exactement 100 % (sinon le flux n'a pas la bonne taille)."""
    for shares in MIXES.values():
        assert sum(shares.values()) == 100


def test_quotas_are_exact_for_odd_sizes():
    """La somme des quotas vaut la taille demandée, même quand les arrondis tombent mal."""
    for size in (1, 7, 32_768, 100_007_936):
        for shares in MIXES.values():
            assert sum(quotas(size, shares).values()) == size


def test_quotas_reject_wrong_total():
    """Un mélange qui ne fait pas 100 % est refusé (cas de la note « 15 25 25 10 »)."""
    with pytest.raises(ValueError):
        quotas(100, {"a": 15, "b": 25, "c": 25, "d": 10})


def test_no_repetition_when_stock_is_enough(tmp_path):
    """Une source assez grande remplit son quota en une passe : 1,0 passe."""
    archive = tmp_path / "big.jsonl.gz"
    write_archive(archive, ["abcdefghi"] * 100)  # 100 documents de 10 tokens (avec séparateur)
    stream = io.BytesIO()
    passes = encode_repeating((archive, 900, "x"), 50, FakeTokenizer(), stream, tmp_path)
    assert passes == 1.0
    assert len(np.frombuffer(stream.getvalue(), dtype="<u2")) == 50


def test_small_source_is_repeated_and_counted(tmp_path):
    """Stock de 30 tokens, quota de 75 : deux passes complètes et la moitié d'une troisième."""
    archive = tmp_path / "small.jsonl.gz"
    write_archive(archive, ["abcdefghi", "jklmnopqr", "stuvwxyz!"])  # 3 × 10 tokens
    stream = io.BytesIO()
    passes = encode_repeating((archive, 27, "x"), 75, FakeTokenizer(), stream, tmp_path)
    tokens = np.frombuffer(stream.getvalue(), dtype="<u2")
    assert len(tokens) == 75
    assert passes == pytest.approx(2.5)


def test_too_many_passes_are_refused(tmp_path):
    """Au-delà de trois passes, on s'arrête au lieu de répéter sans limite."""
    archive = tmp_path / "tiny.jsonl.gz"
    write_archive(archive, ["abcdefghi"])  # 10 tokens
    with pytest.raises(ValueError):
        encode_repeating((archive, 9, "x"), 31, FakeTokenizer(), io.BytesIO(), tmp_path)
