"""Vérifie l'étape commune : volumes, SHA-256, exemples, audit de validation, non-écrasement."""

from contextlib import ExitStack
import gzip
import json

import pytest

from pipeline.clean import digest, open_output, write_document
from pipeline.pii import PiiMasker
from pipeline.quality import QualityFilter
from pipeline.variants import SOURCES, project_seconds, run_stage

GOOD = "Le village se situe au bord de la rivière, non loin de la route nationale. " * 3


def make_kit(tmp_path):
    """Crée un faux kit avec 230 documents de validation aux mots tous différents."""
    folder = tmp_path / "kit" / "data"
    folder.mkdir(parents=True)
    with (folder / "validation.jsonl").open("w", encoding="utf-8") as stream:
        for index in range(230):
            words = " ".join(f"valmot{index}x{word}" for word in range(20))
            stream.write(json.dumps({"text": words}) + "\n")
    return tmp_path / "kit"


def make_input(tmp_path, rows):
    """Écrit un dossier au format de la sortie MinHash avec ses statistiques."""
    folder = tmp_path / "in"
    folder.mkdir()
    stats = {"minhash": {}}
    for source in SOURCES:
        subset = [row for row in rows if row["source"] == source]
        with ExitStack() as stack:
            writer = open_output(stack, folder, source)
            for row in subset:
                write_document(writer, row)
        stats["minhash"][source] = {
            "docs": len(subset), "bytes": sum(len(r["text"].encode("utf-8")) for r in subset),
            "sha256": digest(folder / f"{source}.jsonl.gz"),
        }
    (folder / "stats.json").write_text(json.dumps(stats), encoding="utf-8")
    return folder


def rows_fixture():
    """Quelques documents par source, avec rejets qualité et PII."""
    return [
        {"id": "w1", "source": "wikipedia_fr", "text": GOOD + " Écrire à jean@exemple.fr."},
        {"id": "w2", "source": "wikipedia_fr", "text": "1234 5678 9012"},
        {"id": "w3", "source": "wikipedia_fr", "text": GOOD},
        {"id": "a1", "source": "assemblee_nationale", "text": GOOD},
        {"id": "c1", "source": "common_crawl", "text": "court"},
        {"id": "c2", "source": "common_crawl", "text": GOOD + " https://x.fr/page"},
    ]


def read_all(folder, source):
    """Relit une sortie gzip."""
    with gzip.open(folder / f"{source}.jsonl.gz", "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def test_quality_stage_counts_and_hashes(tmp_path):
    """Compte documents et octets avant/après, rejets par règle et SHA-256 relus."""
    kit, src = make_kit(tmp_path), make_input(tmp_path, rows_fixture())
    out = tmp_path / "out"
    stats = run_stage(src, out, QualityFilter(), kit, name="quality", check_power=False)
    wiki = stats["sources"]["wikipedia_fr"]
    assert (wiki["docs_before"], wiki["docs"]) == (3, 2)
    assert wiki["rejected"] == {"reject:low_letters": 1}
    assert wiki["bytes"] == sum(len(r["text"].encode("utf-8")) for r in read_all(out, "wikipedia_fr"))
    assert wiki["bytes_before"] > wiki["bytes"]
    assert wiki["sha256"] == digest(out / "wikipedia_fr.jsonl.gz")
    cc = stats["sources"]["common_crawl"]
    assert (cc["docs_before"], cc["docs"], cc["rejected"]) == (2, 1, {"reject:too_short": 1})
    assert stats["audit"]["matching_training_docs"] == 0
    assert stats["audit"]["validation_docs"] == 230
    assert json.loads((out / "stats.json").read_text(encoding="utf-8"))["sources"]["wikipedia_fr"]["sha256"] == wiki["sha256"]
    # Les exemples portent un identifiant et un extrait, jamais le texte entier.
    kept = wiki["examples"]["kept"][0]
    assert set(kept) == {"id", "snippet"} and len(kept["snippet"]) <= 120


def test_pii_stage_masks_and_keeps_order(tmp_path):
    """Masque sans supprimer de document et garde l'ordre ; exemples sans donnée brute."""
    kit, src = make_kit(tmp_path), make_input(tmp_path, rows_fixture())
    out = tmp_path / "out"
    stats = run_stage(src, out, PiiMasker(), kit, name="pii", check_power=False)
    rows = read_all(out, "wikipedia_fr")
    assert [r["id"] for r in rows] == ["w1", "w2", "w3"]
    assert rows[0]["text"].endswith("Écrire à [EMAIL].")
    wiki = stats["sources"]["wikipedia_fr"]
    assert wiki["docs"] == wiki["docs_before"] == 3
    assert wiki["tags"] == {"EMAIL": 1} and wiki["docs_with"] == {"EMAIL": 1}
    assert wiki["examples"]["EMAIL"][0]["snippet"] == "aaaa@aaaaaaa.aa"
    assert "jean" not in json.dumps(stats)
    assert stats["sources"]["common_crawl"]["tags"] == {"URL": 1}


def test_deterministic_and_no_overwrite(tmp_path):
    """Deux exécutions donnent les mêmes SHA-256 ; un dossier existant n'est jamais écrasé."""
    kit, src = make_kit(tmp_path), make_input(tmp_path, rows_fixture())
    first = run_stage(src, tmp_path / "o1", PiiMasker(), kit, name="pii", check_power=False)
    second = run_stage(src, tmp_path / "o2", PiiMasker(), kit, name="pii", check_power=False)
    for source in SOURCES:
        assert first["sources"][source]["sha256"] == second["sources"][source]["sha256"]
    with pytest.raises(FileExistsError):
        run_stage(src, tmp_path / "o1", PiiMasker(), kit, name="pii", check_power=False)


def test_input_hash_mismatch_refused(tmp_path):
    """Refuse une entrée dont le SHA-256 diffère des statistiques de la veille."""
    kit, src = make_kit(tmp_path), make_input(tmp_path, rows_fixture())
    stats = json.loads((src / "stats.json").read_text(encoding="utf-8"))
    stats["minhash"]["assemblee_nationale"]["sha256"] = "0" * 64
    (src / "stats.json").write_text(json.dumps(stats), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        run_stage(src, tmp_path / "out", QualityFilter(), kit, name="quality", check_power=False)
    assert not (tmp_path / "out").exists()


def test_validation_overlap_blocks_publication(tmp_path):
    """Un document qui reprend 13 mots de la validation fait échouer l'étape sans sortie."""
    kit = make_kit(tmp_path)
    leak = " ".join(f"valmot7x{word}" for word in range(20))
    rows = rows_fixture() + [{"id": "leak", "source": "wikipedia_fr", "text": GOOD + " " + leak}]
    src = make_input(tmp_path, rows)
    with pytest.raises(ValueError, match="validation"):
        run_stage(src, tmp_path / "out", PiiMasker(), kit, name="pii", check_power=False)
    assert not (tmp_path / "out").exists()


def test_chained_stage_reads_previous_stats(tmp_path):
    """La variante qualité puis PII lit les statistiques de l'étape qualité."""
    kit, src = make_kit(tmp_path), make_input(tmp_path, rows_fixture())
    quality = run_stage(src, tmp_path / "q", QualityFilter(), kit, name="quality", check_power=False)
    both = run_stage(tmp_path / "q", tmp_path / "qp", PiiMasker(), kit, name="pii", check_power=False)
    assert both["sources"]["wikipedia_fr"]["docs_before"] == quality["sources"]["wikipedia_fr"]["docs"]


def test_limit_and_projection(tmp_path):
    """Le pilote lit les N premiers documents et projette le temps sur tout le volume."""
    kit, src = make_kit(tmp_path), make_input(tmp_path, rows_fixture())
    stats = run_stage(src, tmp_path / "out", PiiMasker(), kit, name="pii", limit=1, check_power=False)
    assert all(stats["sources"][s]["docs_before"] == 1 for s in SOURCES)
    assert stats["pilot"] is True and stats["projection_seconds"] > 0
    assert project_seconds(60.0, 1_000, 10_000) == pytest.approx(600.0)
