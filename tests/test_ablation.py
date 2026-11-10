"""Vérifie le mélange 80/12/8 en tokens, les graines et les tailles de l'ablation."""

import io
import json
from contextlib import ExitStack

import numpy as np
import pytest

from pipeline import ablation
from pipeline.ablation import SEED, SHARES, VARIANTS, quotas, shuffled_texts
from pipeline.clean import open_output, write_document


def test_constants():
    """Le mélange validé et la graine ne bougent pas."""
    assert SHARES == {"wikipedia_fr": 80, "common_crawl": 12, "assemblee_nationale": 8}
    assert sum(SHARES.values()) == 100
    assert SEED == 42
    assert set(VARIANTS) == {"raw", "clean", "dedup"}


@pytest.mark.parametrize("size", [0, 1, 7, 99, 100, 101, 10_000_000, 100_007_936])
def test_quotas_sum_and_shares(size):
    """Les quotas somment exactement à la taille et suivent 80/12/8 à un token près."""
    result = quotas(size)
    assert sum(result.values()) == size
    for source, percent in SHARES.items():
        assert abs(result[source] - size * percent / 100) < 1


def test_quotas_official_budget():
    """Sur le budget officiel de 100 007 936 tokens, les parts sont celles du mélange."""
    assert quotas(100_007_936) == {
        "wikipedia_fr": 80_006_348, "common_crawl": 12_000_953, "assemblee_nationale": 8_000_635,
    }


def test_quotas_cumulative_has_no_rounding_drift():
    """Les quotas cumulés par fenêtre rejoignent le total sans propager les arrondis."""
    seen, window = 100_007_936, 7_000_003
    totals = dict.fromkeys(SHARES, 0)
    for start in range(0, seen, window):
        before, after = quotas(start), quotas(min(start + window, seen))
        for source in SHARES:
            totals[source] += after[source] - before[source]
    assert totals == quotas(seen)


def write_archive(path, texts):
    """Écrit une archive JSONL gzip de documents numérotés."""
    folder = path.parent
    with ExitStack() as stack:
        writer = open_output(stack, folder, path.name.removesuffix(".jsonl.gz"))
        for index, text in enumerate(texts):
            write_document(writer, {"id": str(index), "source": "x", "text": text})


def test_shuffled_texts_seeded_and_without_replacement(tmp_path):
    """Même graine, même ordre ; taux 1 rend chaque document une seule fois."""
    path = tmp_path / "s.jsonl.gz"
    texts = [f"doc {i}" for i in range(200)]
    write_archive(path, texts)
    first = list(shuffled_texts(path, 1, tmp_path))
    second = list(shuffled_texts(path, 1, tmp_path))
    assert first == second
    assert sorted(first) == sorted(texts) and first != texts
    sample = list(shuffled_texts(path, 0.25, tmp_path))
    assert sample == list(shuffled_texts(path, 0.25, tmp_path))
    assert 0 < len(sample) < 200 and len(set(sample)) == len(sample)


class FakeTokenizer:
    """Tokenizer factice : un token par caractère, avec un séparateur de document."""

    eot_id = 0
    sha256 = "fake"

    def encode_batch(self, batch):
        """Encode chaque texte en codes de caractères non nuls."""
        return [[ord(c) % 250 + 1 for c in text] for text in batch]


def test_encode_source_exact_size(tmp_path):
    """Écrit exactement le nombre de tokens demandé, en uint16 petit-boutiste."""
    path = tmp_path / "s.jsonl.gz"
    write_archive(path, ["abcdefghij"] * 50)
    stream = io.BytesIO()
    ablation.encode_source((path, 500, "h"), 123, FakeTokenizer(), stream, tmp_path)
    assert len(stream.getvalue()) == 2 * 123
    assert np.frombuffer(stream.getvalue(), dtype="<u2").max() <= 251


def test_encode_source_insufficient_quota(tmp_path):
    """Signale un quota insuffisant plutôt que de répéter des documents."""
    path = tmp_path / "s.jsonl.gz"
    write_archive(path, ["abc"])
    with pytest.raises(ValueError, match="Quota insuffisant"):
        ablation.encode_source((path, 3, "h"), 10_000, FakeTokenizer(), io.BytesIO(), tmp_path)


def test_prepare_variant_mix_and_size(tmp_path):
    """Le flux final a la bonne taille, commence par le séparateur et respecte le mélange."""
    config = {
        "kit_version": "test",
        "train": {"max_steps": 10, "tokens_per_step": 100, "shuffle_window_steps": 5, "budget_tokens": 1000},
    }
    sources = {}
    for source in SHARES:
        # Un caractère distinct par source pour retrouver la composition dans le flux.
        path = tmp_path / f"{source}.jsonl.gz"
        write_archive(path, [chr(65 + list(SHARES).index(source)) * 40] * 200)
        sources[source] = (path, 40 * 200, f"hash-{source}")
    folder = tmp_path / "variant"
    meta = ablation.prepare_variant(folder, sources, FakeTokenizer(), config, tmp_path)
    data = np.frombuffer((folder / "train.bin").read_bytes(), dtype="<u2")
    assert len(data) == 1001 == meta["n_tokens"]
    assert data[0] == FakeTokenizer.eot_id
    body = data[1:]
    shares = {source: int((body == ord(chr(65 + i)) % 250 + 1).sum()) for i, source in enumerate(SHARES)}
    # Les séparateurs (0) sont comptés à part : au plus un par document.
    assert meta["tokens_seen_by_source"] == quotas(1000)
    for source, count in shares.items():
        assert abs(count - quotas(1000)[source]) <= 25
    # Deux préparations avec la même graine donnent des flux identiques.
    again = tmp_path / "variant2"
    meta2 = ablation.prepare_variant(again, sources, FakeTokenizer(), config, tmp_path)
    assert meta2["dataset_sha256"] == meta["dataset_sha256"]
    assert json.loads((folder / "data_meta.json").read_text(encoding="utf-8")) == meta
