"""Lance les entraînements sur GPU et importe les résultats dans le journal."""

import argparse
from datetime import datetime
from hashlib import sha256 as digest_bytes
import json
import math
from pathlib import Path
import platform
import subprocess
from zoneinfo import ZoneInfo
from zipfile import ZIP_DEFLATED, ZipFile

from pipeline.ablation import KIT_REV, ROOT, VARIANTS, kit_command, read_json, sha256, write_json

LABELS = {"raw": "Brut contrôlé", "clean": "Nettoyé", "dedup": "Dédupliqué (exact + MinHash)"}
BASELINES = {"clean": "raw", "dedup": "clean"}


def bundle(prepared, output):
    """Crée l’archive à importer dans Kaggle, avec les seuls fichiers nécessaires."""
    read_json(prepared / "manifest.json")
    with ZipFile(output, "x", compression=ZIP_DEFLATED, compresslevel=1) as archive:
        for name in ("ablation.py", "ablation_runs.py"):
            archive.write(ROOT / "pipeline" / name, f"pipeline/{name}")
        for name in ("manifest.json", "tokenizer.json"):
            archive.write(prepared / name, f"ablation/{name}")
        for variant in VARIANTS:
            for name in ("train.bin", "data_meta.json"):
                archive.write(prepared / variant / name, f"ablation/{variant}/{name}")


def run(kit, prepared, results, variants):
    """Vérifie les entrées, puis utilise ftb.train et ftb.evaluate sur un seul GPU."""
    import sys

    import torch
    import tokenizers

    if not torch.cuda.is_available():
        raise RuntimeError("Active le GPU dans Kaggle avant de lancer cette commande")
    revision = subprocess.check_output(["git", "-C", str(kit), "rev-parse", "HEAD"], text=True)
    status = subprocess.check_output(["git", "-C", str(kit), "status", "--porcelain", "--untracked-files=no"])
    if revision.strip() != KIT_REV or status:
        raise ValueError("Il faut le clone intact du kit à la révision indiquée")
    sys.path.insert(0, str(kit))
    from ftb import VALIDATION_PATH, load_config

    manifest = read_json(prepared / "manifest.json")
    tokenizer = prepared / "tokenizer.json"
    validation = VALIDATION_PATH.read_text(encoding="utf-8")
    val_hash = digest_bytes(validation.encode("utf-8")).hexdigest()
    if (
        manifest["kit_revision"] != KIT_REV or load_config() != manifest["config"]
        or val_hash != manifest["validation_sha256"]
        or sha256(tokenizer) != manifest["tokenizer_sha256"]
    ):
        raise ValueError("Kit, validation ou tokenizer différent du manifeste")
    results.mkdir(parents=True, exist_ok=True)
    # Conserve le protocole complet avec les résultats transférables.
    protocol = results / "manifest.json"
    if protocol.exists() and read_json(protocol) != manifest:
        raise ValueError("Le dossier de résultats correspond à une autre préparation")
    write_json(protocol, manifest)
    environment = {
        "gpu": torch.cuda.get_device_name(0), "torch": str(torch.__version__),
        "cuda": torch.version.cuda, "python": platform.python_version(),
        "tokenizers": tokenizers.__version__, "micro_batch": 8,
    }
    environment_path = results / "environment.json"
    if environment_path.exists() and read_json(environment_path) != environment:
        raise ValueError("Reprends les runs avec le même environnement GPU")
    write_json(environment_path, environment)

    for variant in variants:
        folder = prepared / variant
        meta = manifest["variants"][variant]
        if read_json(folder / "data_meta.json") != meta or sha256(folder / "train.bin") != meta["dataset_sha256"]:
            raise ValueError(f"Jeu d’entraînement différent du manifeste : {variant}")
        if tokenizers.__version__ != meta["tokenizers_version"]:
            raise ValueError(f"Version de tokenizers requise : {meta['tokenizers_version']}")
        destination = results / variant
        run_meta = destination / "result.json"
        if run_meta.exists():
            check_result(read_json(run_meta), manifest, variant)
            print(f"{variant} déjà terminé", flush=True)
            continue
        checkpoint = destination / "ckpt.pt"
        # Reprend l'état officiel après une interruption, ou évalue un checkpoint déjà fini.
        if not checkpoint.is_file():
            resume = ["--resume"] if (destination / "state.pt").exists() else []
            kit_command(kit, "ftb.train", "--data", folder, "--tokenizer", tokenizer,
                        "--out", destination, "--device", "cuda:0", "--micro-batch",
                        environment["micro_batch"], *resume)
        evaluation = destination / "evaluation.json"
        kit_command(kit, "ftb.evaluate", "--ckpt", checkpoint, "--tokenizer", tokenizer,
                    "--data", VALIDATION_PATH, "--device", "cuda:0", "--out", evaluation)
        # Le checkpoint vient du lanceur officiel dans ce même dossier.
        checkpoint_meta = torch.load(checkpoint, map_location="cpu", weights_only=True)["meta"]
        record = {"variant": variant, "checkpoint": checkpoint_meta, "evaluation": read_json(evaluation)}
        check_result(record, manifest, variant)
        temporary = run_meta.with_suffix(".tmp")
        write_json(temporary, record)
        temporary.replace(run_meta)


def check_result(record, manifest, variant):
    """Contrôle la provenance, le budget et les unités de la mesure."""
    train = manifest["config"]["train"]
    seen = train["max_steps"] * train["tokens_per_step"]
    checkpoint, evaluation = record["checkpoint"], record["evaluation"]
    if (
        record["variant"] != variant or checkpoint["official"] is not True
        or checkpoint["train_config"] != train or checkpoint["tokens_seen"] != seen
        or checkpoint["dataset_sha256"] != manifest["variants"][variant]["dataset_sha256"]
        or checkpoint["tokenizer_sha256"] != manifest["tokenizer_sha256"]
        or evaluation["tokenizer_sha256"] != manifest["tokenizer_sha256"]
        or evaluation["n_documents"] != manifest["validation_documents"]
        or evaluation["n_octets"] != manifest["validation_bytes"]
        or not math.isfinite(evaluation["bpb"]) or evaluation["bpb"] <= 0
    ):
        raise ValueError(f"Résultat incompatible avec le protocole : {variant}")


def update_log(results, log):
    """Ajoute ou remplace une ligne par run, avec les écarts calculés sur le BPB complet."""
    manifest = read_json(results / "manifest.json")
    records = {}
    for variant in VARIANTS:
        path = results / variant / "result.json"
        if path.is_file():
            record = read_json(path)
            check_result(record, manifest, variant)
            records[variant] = record
    if not records:
        raise ValueError("Aucun result.json complet à importer")
    # Contrôle l’environnement de calcul entre les résultats d’une même série.
    environments = {
        tuple(record["checkpoint"][key] for key in ("device", "precision", "torch", "tokenizers", "python"))
        for record in records.values()
    }
    if len(environments) != 1:
        raise ValueError("Les entraînements n’ont pas utilisé le même environnement GPU")

    lines = log.read_text(encoding="utf-8").splitlines()
    for variant, record in records.items():
        checkpoint, evaluation = record["checkpoint"], record["evaluation"]
        bpb = evaluation["bpb"]
        baseline = BASELINES.get(variant)
        if baseline is None:
            conclusion = "Référence sur les 230 documents publics."
        elif baseline not in records:
            conclusion = "Comparaison en attente du run de référence."
        else:
            delta = bpb - records[baseline]["evaluation"]["bpb"]
            if delta < 0:
                conclusion = f"Baisse de {-delta:.6g} BPB par rapport à {LABELS[baseline].lower()}."
            elif delta > 0:
                conclusion = f"Hausse de {delta:.6g} BPB par rapport à {LABELS[baseline].lower()}."
            else:
                conclusion = f"BPB identique à {LABELS[baseline].lower()}."
        date = datetime.fromisoformat(checkpoint["created"]).astimezone(ZoneInfo("Europe/Paris")).date()
        # La conversion en chaîne conserve la précision enregistrée par ftb.evaluate.
        dataset_hash = checkpoint["dataset_sha256"]
        row_id = f"ablation-{variant}-{dataset_hash[:12]}"
        tokens = f"{checkpoint['tokens_seen']:,}".replace(",", " ")
        row = (f"| {date} | {row_id} | {LABELS[variant]}, 80/12/8 en tokens | {tokens} | "
               f"SHA-256 `{dataset_hash}` | {bpb} | non | {conclusion} |")
        lines = [line for line in lines if f"| {row_id} |" not in line]
        lines.append(row)
    temporary = log.with_suffix(".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(log)


def main():
    """Sépare le lancement sur GPU de l’import local du journal."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    train = subparsers.add_parser("run", help="lance les modules officiels sur GPU")
    train.add_argument("--kit", type=Path, required=True)
    train.add_argument("--prepared", type=Path, required=True)
    train.add_argument("--results", type=Path, required=True)
    train.add_argument("--variant", choices=VARIANTS)
    log = subparsers.add_parser("log", help="importe les résultats terminés")
    log.add_argument("--results", type=Path, required=True)
    log.add_argument("--log", type=Path, default=ROOT / "experiments/LOG.md")
    pack = subparsers.add_parser("bundle", help="crée l’archive d’entrée Kaggle")
    pack.add_argument("--prepared", type=Path, default=ROOT / "data/processed/ablation")
    pack.add_argument("--out", type=Path, default=ROOT / "data/processed/ablation-kaggle.zip")
    args = parser.parse_args()
    if args.command == "run":
        run(args.kit.resolve(), args.prepared.resolve(), args.results.resolve(),
            [args.variant] if args.variant else VARIANTS)
    elif args.command == "log":
        update_log(args.results.resolve(), args.log.resolve())
    else:
        bundle(args.prepared.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
