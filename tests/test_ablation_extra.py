"""Vérifie la préparation des variantes qualité/PII : provenance, empreintes, taille des flux."""

import gzip
import json
from contextlib import ExitStack

import numpy as np
import pytest

from pipeline import ablation_extra
from pipeline.ablation import SHARES, quotas
from pipeline.ablation_extra import EXTRA, extra_sources
from pipeline.clean import digest, open_output, write_document

AUDIT = {"validation_docs": 230, "matching_training_docs": 0, "mean_overlap": 0.0,
         "flagged_validation_docs": 0, "validation_sha256": "val"}


def make_interim(tmp_path, audit=AUDIT):
    """Fabrique les dossiers de sortie avec leurs statistiques, comme les étapes réelles."""
    interim = tmp_path / "interim"
    dedup = interim / "dedup/final"
    dedup.mkdir(parents=True)
    (dedup / "stats.json").write_text(json.dumps({"audit": AUDIT}), encoding="utf-8")
    for variant, folder in EXTRA.items():
        path = interim / folder
        path.mkdir(parents=True)
        stats = {"audit": audit, "sources": {}}
        for source in SHARES:
            rows = [{"id": f"{variant}-{source}", "source": source, "text": f"texte {source} {variant}"}]
            with ExitStack() as stack:
                writer = open_output(stack, path, source)
                for row in rows:
                    write_document(writer, row)
            stats["sources"][source] = {
                "docs": 1, "bytes": sum(len(r["text"].encode()) for r in rows),
                "sha256": digest(path / f"{source}.jsonl.gz"),
            }
        (path / "stats.json").write_text(json.dumps(stats), encoding="utf-8")
    return interim


def test_extra_sources_ok(tmp_path):
    """Retourne chemin, octets et SHA-256 vérifiés pour chaque variante et source."""
    sources = extra_sources(make_interim(tmp_path))
    assert set(sources) == {"quality", "pii", "quality_pii"}
    path, size, sha = sources["pii"]["wikipedia_fr"]
    assert path.name == "wikipedia_fr.jsonl.gz" and sha == digest(path) and size > 0


def test_extra_sources_hash_mismatch(tmp_path):
    """Refuse une archive modifiée depuis son audit."""
    interim = make_interim(tmp_path)
    with gzip.open(interim / "quality/final/common_crawl.jsonl.gz", "wb") as stream:
        stream.write(b'{"id":"x","source":"common_crawl","text":"autre"}\n')
    with pytest.raises(ValueError, match="SHA-256"):
        extra_sources(interim)


def test_extra_sources_audit_must_match_reference(tmp_path):
    """Refuse une sortie dont l'audit n'est pas à zéro ou vise une autre validation."""
    with pytest.raises(ValueError, match="Audit"):
        extra_sources(make_interim(tmp_path, dict(AUDIT, matching_training_docs=1)))
    with pytest.raises(ValueError, match="Audit"):
        extra_sources(make_interim(tmp_path / "b", dict(AUDIT, validation_sha256="autre")))


class FakeTokenizer:
    """Tokenizer factice : un token par caractère."""

    eot_id = 0
    sha256 = "tok"

    def encode_batch(self, batch):
        """Encode chaque texte en codes non nuls."""
        return [[ord(c) % 250 + 1 for c in text] for text in batch]


def test_build_variants_same_size_and_deterministic(tmp_path):
    """Les trois flux ont la taille du protocole et se reconstruisent à l'identique."""
    config = {"kit_version": "t", "train": {"max_steps": 4, "tokens_per_step": 50,
                                            "shuffle_window_steps": 2, "budget_tokens": 200}}
    sources = {}
    for variant in EXTRA:
        sources[variant] = {}
        for source in SHARES:
            path = tmp_path / f"{variant}-{source}.jsonl.gz"
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                for i in range(200):
                    stream.write(json.dumps({"id": str(i), "source": source, "text": "abcdefghij" * 3}) + "\n")
            sources[variant][source] = (path, 6000, "h")
    metas = ablation_extra.build_variants(tmp_path / "out", sources, FakeTokenizer(), config, tmp_path)
    again = ablation_extra.build_variants(tmp_path / "out2", sources, FakeTokenizer(), config, tmp_path)
    assert set(metas) == set(EXTRA)
    for variant, meta in metas.items():
        data = np.frombuffer((tmp_path / "out" / variant / "train.bin").read_bytes(), dtype="<u2")
        assert len(data) == 201 == meta["n_tokens"]
        assert meta["tokens_seen_by_source"] == quotas(200)
        assert again[variant]["dataset_sha256"] == meta["dataset_sha256"]
