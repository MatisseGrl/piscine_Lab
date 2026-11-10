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
        "tokenizer_sha256": "tok", "validation_documents": 230, "validation_bytes": 5000,
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
