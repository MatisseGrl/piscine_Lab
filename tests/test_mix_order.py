"""Vérifie la redistribution d'un vrai flux produit par le mélangeur M4."""

from itertools import islice

import numpy as np

from pipeline import mixes
from pipeline.mix_order import redistribute, window_blocks


def test_redistribute_preserves_tokens_and_order_inside_each_source(tmp_path, monkeypatch):
    """Conserve le contexte, les quotas et la séquence propre à chaque source."""
    shares = mixes.MIXES["M4"]
    source_numbers = {source: index for index, source in enumerate(shares, start=1)}
    config = {
        "kit_version": "1.0",
        "train": {"max_steps": 10, "tokens_per_step": 100, "shuffle_window_steps": 2,
                  "budget_tokens": 1000},
    }

    class Tokenizer:
        """Encodeur minimal pour les métadonnées exigées par le mélangeur."""

        eot_id = 65535
        sha256 = "tokenizer-de-test"

    def write_source(entry, target, tokenizer, stream, scratch):
        """Écrit des identifiants distincts et ordonnés pour chaque source."""
        base = entry[0] * 1000
        stream.write(np.arange(base, base + target, dtype="<u2").tobytes())
        return 1.0

    monkeypatch.setattr(mixes, "encode_repeating", write_source)
    sources = {source: (number, 0, source) for source, number in source_numbers.items()}
    reference = tmp_path / "M4"
    mixes.prepare_mix(reference, sources, shares, Tokenizer(), config, tmp_path)
    output = tmp_path / "reordered.bin"
    phases = redistribute(reference / "train.bin", output, 1000, 200, shares, tmp_path)
    original = np.fromfile(reference / "train.bin", dtype="<u2")
    reordered = np.fromfile(output, dtype="<u2")
    assert reordered[0] == original[0] == Tokenizer.eot_id
    assert len(reordered) == len(original) == 1001
    assert not np.array_equal(original, reordered)
    assert [phase["n_tokens"] for phase in phases] == [400, 600]
    early_shares = dict(zip(shares, (30, 22, 22, 20, 6)))
    for source, number in source_numbers.items():
        assert np.array_equal(reordered[reordered // 1000 == number], original[original // 1000 == number])
        assert np.count_nonzero(reordered[1:401] // 1000 == number) == 4 * early_shares[source]


def test_last_partial_window_keeps_exact_length_and_quotas():
    """Répartit les arrondis en gardant les frontières d'entraînement intactes."""
    from collections import Counter
    from random import Random

    totals = {"wiki": 393, "livres": 210, "web": 131}
    blocks = iter(window_blocks(734, 150, totals, Random(42)))
    observed = Counter()
    for size in (150, 150, 150, 150, 134):
        window = dict(islice(blocks, len(totals)))
        assert sum(window.values()) == size
        observed.update(window)
    assert observed == totals
