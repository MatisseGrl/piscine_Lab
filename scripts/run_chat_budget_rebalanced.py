"""Affine plus brièvement le chat avec toutes les paires de théâtre et moins de variantes répétitives."""
import argparse
import hashlib
import json
import random
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import torch


# Conserve toutes les couleurs et les conseils. Contient les autres familles répétitives.
LIMITS = {"mixed": 300, "independent": 450, "name": 500, "food": 200, "repeat": 140}
V5_HASH = "376c76a46a02b03ab0b4bd7734bcef6deedfa75cdabfb15c63879c5b2c281eb4"


def select_dialogues(records):
    """Prend sans remise les sous-ensembles déterministes des familles v5."""
    groups, seen = defaultdict(list), set()
    for record in records:
        messages = json.dumps(record["messages"], ensure_ascii=False, separators=(",", ":"))
        if messages in seen:
            continue
        seen.add(messages)
        family = record.get("family") or record["source"]
        groups[family].append(record)
    rng = random.Random(1337)
    selected = []
    for family, group in sorted(groups.items()):
        if family in LIMITS:
            group = rng.sample(group, min(len(group), LIMITS[family]))
        selected.extend(group)
    # L'ordre mélangé évite de regrouper les familles dans la version dérivée.
    rng.shuffle(selected)
    return selected


def main():
    """Construit la variante sans ajout de texte puis lance les 750 pas sur T4."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("data", "checkpoint", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("GPU indisponible.")
    content = (args.data / "chat_v5_train.json").read_bytes()
    if hashlib.sha256(content).hexdigest() != V5_HASH:
        raise ValueError("Corpus v5 différent de la référence.")
    records = select_dialogues(json.loads(content))
    corpus = args.out / "rebalanced-train.json"
    with corpus.open("x", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False, separators=(",", ":"))
    # Les compteurs permettent de vérifier le mélange et le gain de diversité.
    counts = Counter(record.get("family") or record["source"] for record in records)
    responses = sum(sum(role == "assistant" for role, _ in record["messages"]) for record in records)
    manifest = {"documents": dict(counts), "responses": responses,
                "sha256": hashlib.sha256(corpus.read_bytes()).hexdigest()}
    (args.out / "rebalanced.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest), flush=True)
    subprocess.run([
        sys.executable, "-m", "minigpt.chat_sft", "--checkpoint", str(args.checkpoint),
        "--tokenizer", str(args.data / "tokenizer.json"), "--corpus", str(args.data), "--data", str(corpus),
        "--out", str(args.out / "chat"), "--steps", "750", "--every", "250",
        "--lr", "0.0001", "--replay", "0.3",
    ], check=True)


if __name__ == "__main__":
    main()
