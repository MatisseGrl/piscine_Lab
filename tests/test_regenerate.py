"""Tests de la commande unique de régénération : ordre des étapes, reprise, contrôle du SHA-256."""

import json

import pytest

from pipeline import regenerate


def test_steps_are_in_dependency_order():
    """Le tokenizer vient avant Wikinews et le mélange ; le nettoyage avant la dédup, puis la qualité."""
    names = [step.name for step in regenerate.build_steps("M4")]
    order = ["collect", "clean", "dedup", "quality", "tokenizer", "wikinews", "gutenberg", "mix-M4"]
    positions = [names.index(name) for name in order]
    assert positions == sorted(positions)


def test_every_mix_has_an_expected_sha_or_is_known():
    """Les SHA de référence ne concernent que des mélanges qui existent, et font 64 caractères hex."""
    for mix, digest in regenerate.EXPECTED_SHA256.items():
        assert mix in regenerate.RECIPES
        assert len(digest) == 64 and int(digest, 16) >= 0


def test_order_variant_uses_the_matching_parent():
    """La variante combinée ordonne le flux qui porte déjà son mélange et son tokenizer."""
    steps = regenerate.build_steps("M4WIKIBPEORDER")
    parent, order = steps[-2:]
    assert parent.name == "mix-M4WIKIBPE"
    assert order.argv[order.argv.index("--parent") + 1] == str(parent.done.parent.parent)
    assert order.done.name == "data_meta.json"


def test_dry_run_launches_nothing(tmp_path, monkeypatch, capsys):
    """--dry-run affiche les étapes mais n'appelle jamais subprocess."""
    monkeypatch.setattr(regenerate.subprocess, "run",
                        lambda *a, **k: pytest.fail("aucune commande ne doit partir"))
    assert regenerate.run("M4", dry_run=True, root=tmp_path) == 0
    assert "mix-M4" in capsys.readouterr().out


def test_finished_steps_are_skipped(tmp_path, monkeypatch):
    """Une étape dont le témoin existe n'est pas relancée ; les autres le sont, dans l'ordre."""
    steps = regenerate.build_steps("M4")
    for step in steps[:5]:  # kit, kit-rev, collect, clean, dedup déjà faits
        (tmp_path / step.done).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / step.done).write_text("x")
    launched = []

    class Done:
        returncode = 0
        stdout = regenerate.KIT_REV + "\n"

    def run(argv, cwd, **kwargs):
        """Répond à la vérification Git et recense les étapes effectivement lancées."""
        if argv[-2:] != ["rev-parse", "HEAD"]:
            launched.append(argv)
        return Done()

    monkeypatch.setattr(regenerate.subprocess, "run", run)
    monkeypatch.setattr(regenerate, "verify_final", lambda mix, root: (True, "ok"))
    assert regenerate.run("M4", root=tmp_path) == 0
    assert len(launched) == len(steps) - 5
    assert "pipeline.quality" in launched[0]


def test_failure_stops_the_chain(tmp_path, monkeypatch):
    """Si une étape échoue, les suivantes ne partent pas."""
    calls = []

    class Failed:
        returncode = 2

    monkeypatch.setattr(regenerate.subprocess, "run", lambda argv, cwd: calls.append(argv) or Failed())
    assert regenerate.run("M4", root=tmp_path) == 1
    assert len(calls) == 1


def test_unknown_step_name_is_refused(tmp_path):
    """--only avec un nom inconnu s'arrête avec la liste des étapes valides."""
    with pytest.raises(SystemExit):
        regenerate.run("M4", only="nimporte", dry_run=True, root=tmp_path)


def write_mix(root, mix):
    """Crée un flux factice, son tokenizer local et les empreintes correspondantes."""
    folder = root / regenerate.final_dir(mix) / mix
    folder.mkdir(parents=True)
    (folder / "train.bin").write_bytes(b"\x00\x00\x01\x00")
    (folder / "tokenizer.json").write_text("{}", encoding="utf-8")
    digest = regenerate.sha256(folder / "train.bin")
    (folder / "data_meta.json").write_text(json.dumps({
        "dataset_sha256": digest,
        "tokenizer_sha256": regenerate.sha256(folder / "tokenizer.json"),
    }), encoding="utf-8")
    return folder, digest


def test_verify_accepts_identical_sha(tmp_path, monkeypatch):
    """Même SHA-256 que le run de référence : reproductible."""
    _, digest = write_mix(tmp_path, "M4")
    monkeypatch.setitem(regenerate.EXPECTED_SHA256, "M4", digest)
    ok, message = regenerate.verify_final("M4", tmp_path)
    assert ok and "identique" in message


def test_verify_rejects_different_sha(tmp_path):
    """Un SHA-256 différent est une erreur (graine, ordre ou version de dépendance)."""
    write_mix(tmp_path, "M4")
    ok, message = regenerate.verify_final("M4", tmp_path)
    assert not ok and "DIFFÉRENT" in message


def test_verify_without_reference_only_reports(tmp_path):
    """Sans SHA de référence (M5), on affiche le hash à noter dans le LOG sans échouer."""
    write_mix(tmp_path, "M5")
    ok, message = regenerate.verify_final("M5", tmp_path)
    assert ok and "pas de référence" in message


def test_verify_missing_output_fails(tmp_path):
    """Pas de sortie = échec explicite."""
    ok, _ = regenerate.verify_final("M4", tmp_path)
    assert not ok


def test_rejects_changed_bytes_with_valid_metadata(tmp_path, monkeypatch):
    """Un flux corrompu ne peut pas être validé par son manifeste d'origine."""
    folder, digest = write_mix(tmp_path, "M4")
    monkeypatch.setitem(regenerate.EXPECTED_SHA256, "M4", digest)
    (folder / "train.bin").write_bytes(b"\x01\x00\x00\x00")
    ok, message = regenerate.verify_final("M4", tmp_path)
    assert not ok and "data_meta.json" in message


def test_kit_witness_at_wrong_revision_is_incomplete(tmp_path, monkeypatch):
    """Le fichier Molière présent ne remplace pas le contrôle du commit Git."""
    step = regenerate.build_steps("M4")[1]
    (tmp_path / step.done).parent.mkdir(parents=True)
    (tmp_path / step.done).touch()
    monkeypatch.setattr(regenerate.subprocess, "run", lambda *args, **kwargs:
                        regenerate.subprocess.CompletedProcess(args, 0, stdout="0" * 40))
    assert not regenerate.step_is_done(step, tmp_path)
