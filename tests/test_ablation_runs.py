"""Vérifie les contrôles de résultats, le journal et l'archive Kaggle de l'ablation."""

import copy
import json
from zipfile import ZipFile

import pytest

from pipeline.ablation import VARIANTS, write_json
from pipeline.ablation_runs import bundle, check_result, update_log

TRAIN = {"max_steps": 10, "tokens_per_step": 100, "budget_tokens": 1000}


def manifest():
    """Manifeste minimal cohérent avec trois variantes."""
    return {
        "tokenizer_sha256": "tok", "validation_sha256": "val", "validation_documents": 230, "validation_bytes": 5000,
        "config": {"train": TRAIN},
        "variants": {name: {"dataset_sha256": f"{name}{'0' * 60}"} for name in VARIANTS},
    }


def record(variant, bpb, created="2026-11-10T12:00:00+00:00"):
    """Résultat factice qui passe tous les contrôles."""
    return {
        "variant": variant,
        "checkpoint": {
            "official": True, "train_config": TRAIN, "tokens_seen": 1000, "created": created,
            "dataset_sha256": f"{variant}{'0' * 60}", "tokenizer_sha256": "tok",
            "device": "cuda:0", "precision": "bf16", "torch": "2", "tokenizers": "0.23", "python": "3.12",
        },
        "evaluation": {"tokenizer_sha256": "tok", "n_documents": 230, "n_octets": 5000, "bpb": bpb},
    }


def test_check_result_accepts_valid():
    """Un résultat conforme au protocole est accepté."""
    check_result(record("clean", 1.5), manifest(), "clean")


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["checkpoint"].update(official=False),
        lambda r: r["checkpoint"].update(tokens_seen=999),
        lambda r: r["checkpoint"].update(dataset_sha256="autre"),
        lambda r: r["checkpoint"].update(tokenizer_sha256="autre"),
        lambda r: r["checkpoint"]["train_config"].update(max_steps=11),
        lambda r: r["evaluation"].update(n_documents=229),
        lambda r: r["evaluation"].update(n_octets=4999),
        lambda r: r["evaluation"].update(bpb=0),
        lambda r: r["evaluation"].update(bpb=float("nan")),
        lambda r: r.update(variant="raw"),
    ],
)
def test_check_result_rejects(change):
    """Chaque écart de provenance, de budget ou d'unité est refusé."""
    bad = copy.deepcopy(record("clean", 1.5))
    change(bad)
    with pytest.raises(ValueError, match="incompatible"):
        check_result(bad, manifest(), "clean")


def prepare_results(tmp_path, bpbs):
    """Écrit un dossier de résultats et un journal vide."""
    results = tmp_path / "results"
    results.mkdir()
    write_json(results / "manifest.json", manifest())
    for variant, bpb in bpbs.items():
        (results / variant).mkdir()
        write_json(results / variant / "result.json", record(variant, bpb))
    log = tmp_path / "LOG.md"
    log.write_text("| Date | id |\n", encoding="utf-8")
    return results, log


def test_update_log_deltas_and_idempotence(tmp_path):
    """Écrit une ligne par run avec l'écart de BPB, sans doublon à la réimportation."""
    results, log = prepare_results(tmp_path, {"raw": 2.0, "clean": 1.9, "dedup": 1.95})
    update_log(results, log)
    update_log(results, log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    text = "\n".join(lines)
    assert "Baisse de 0.1 BPB par rapport à brut contrôlé" in text
    assert "Hausse de 0.05 BPB par rapport à nettoyé" in text
    assert "Référence sur les 230 documents publics." in text


def test_update_log_requires_results(tmp_path):
    """Refuse d'importer quand aucun résultat n'est complet."""
    results, log = prepare_results(tmp_path, {})
    with pytest.raises(ValueError, match="Aucun result.json"):
        update_log(results, log)


def test_update_log_rejects_mixed_environments(tmp_path):
    """Refuse des runs faits sur des environnements GPU différents."""
    results, log = prepare_results(tmp_path, {"raw": 2.0, "clean": 1.9})
    other = record("clean", 1.9)
    other["checkpoint"]["torch"] = "3"
    write_json(results / "clean" / "result.json", other)
    with pytest.raises(ValueError, match="même environnement"):
        update_log(results, log)


def test_bundle_contains_only_needed_files(tmp_path):
    """L'archive Kaggle contient le code, le manifeste, le tokenizer et les trois flux."""
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    write_json(prepared / "manifest.json", manifest())
    (prepared / "tokenizer.json").write_text("{}", encoding="utf-8")
    for variant in VARIANTS:
        (prepared / variant).mkdir()
        (prepared / variant / "train.bin").write_bytes(b"\0\0")
        (prepared / variant / "data_meta.json").write_text("{}", encoding="utf-8")
    out = tmp_path / "k.zip"
    bundle(prepared, out)
    with ZipFile(out) as archive:
        names = set(archive.namelist())
    assert {"pipeline/ablation.py", "pipeline/ablation_runs.py", "ablation/manifest.json",
            "ablation/tokenizer.json"} <= names
    assert len(names) == 4 + 2 * len(VARIANTS)
    with pytest.raises(FileExistsError):
        bundle(prepared, out)


EXTRA = ("quality", "pii", "quality_pii")


def extra_hash(variant):
    """Empreinte factice de 64 caractères pour une variante."""
    return f"{variant}{'0' * 64}"[:64]


def extra_manifest():
    """Manifeste d'une série qualité/PII, mêmes protocole et tokenizer que la série de base."""
    base = manifest()
    base["variants"] = {name: {"dataset_sha256": extra_hash(name)} for name in EXTRA}
    return base


def prepare_extra(tmp_path, bpbs, reference_bpb=None):
    """Écrit une série qualité/PII et, au besoin, une série de référence avec le dédupliqué."""
    results = tmp_path / "extra"
    results.mkdir()
    write_json(results / "manifest.json", extra_manifest())
    for variant, bpb in bpbs.items():
        (results / variant).mkdir()
        entry = record(variant, bpb)
        entry["checkpoint"]["dataset_sha256"] = extra_hash(variant)
        write_json(results / variant / "result.json", entry)
    reference = None
    if reference_bpb is not None:
        reference = tmp_path / "ref"
        reference.mkdir()
        write_json(reference / "manifest.json", manifest())
        (reference / "dedup").mkdir()
        write_json(reference / "dedup" / "result.json", record("dedup", reference_bpb))
    log = tmp_path / "LOG.md"
    log.write_text("| Date | id |\n", encoding="utf-8")
    return results, reference, log


def test_extra_series_compared_to_reference_dedup(tmp_path):
    """Les variantes qualité/PII se comparent au dédupliqué d'une autre série, sans l'y réécrire."""
    results, reference, log = prepare_extra(tmp_path, {"quality": 1.90, "pii": 1.96}, reference_bpb=1.95)
    update_log(results, log, reference)
    text = log.read_text(encoding="utf-8")
    assert "Baisse de 0.05 BPB par rapport à dédupliqué" in text
    assert "Hausse de 0.01 BPB par rapport à dédupliqué" in text
    assert "ablation-dedup-" not in text and text.count("ablation-") == 2


def test_extra_series_without_reference_waits(tmp_path):
    """Sans série de référence, la conclusion indique que la comparaison est en attente."""
    results, _, log = prepare_extra(tmp_path, {"quality": 1.9})
    update_log(results, log)
    assert "Comparaison en attente du run de référence." in log.read_text(encoding="utf-8")


def test_reference_with_other_tokenizer_refused(tmp_path):
    """Refuse une référence mesurée avec un autre tokenizer ou protocole."""
    results, reference, log = prepare_extra(tmp_path, {"quality": 1.9}, reference_bpb=1.95)
    other = manifest()
    other["tokenizer_sha256"] = "autre"
    write_json(reference / "manifest.json", other)
    with pytest.raises(ValueError, match="même protocole"):
        update_log(results, log, reference)


def test_bundle_follows_manifest_variants(tmp_path):
    """L'archive d'une série qualité/PII contient ses propres trois flux."""
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    write_json(prepared / "manifest.json", extra_manifest())
    (prepared / "tokenizer.json").write_text("{}", encoding="utf-8")
    for variant in EXTRA:
        (prepared / variant).mkdir()
        (prepared / variant / "train.bin").write_bytes(b"\0\0")
        (prepared / variant / "data_meta.json").write_text("{}", encoding="utf-8")
    bundle(prepared, tmp_path / "e.zip")
    with ZipFile(tmp_path / "e.zip") as archive:
        assert {f"ablation/{v}/train.bin" for v in EXTRA} <= set(archive.namelist())
