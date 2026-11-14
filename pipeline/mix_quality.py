"""Prépare M4 avec un classement de Common Crawl appris sur des passages français."""

import argparse
from collections import Counter
import gzip
from itertools import islice
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

import numpy as np

from pipeline.ablation import KIT_REV, ROOT, SEED, read_json, sha256, write_json
from pipeline.mixes import MIXES, load_sources, prepare_mix, quotas, shuffled_texts


NAME = "M4CLASS"
WEB = "common_crawl"
MAX_CHARS = 1200
MIN_STOCK_PERCENT = 110
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
URL = re.compile(r"https?://|www\.", re.IGNORECASE)
FEATURE_NAMES = (
    "letters", "digits", "symbols", "urls", "short_lines", "repeated_lines",
    "repeated_trigrams", "sentence_endings", "long_words",
)
NAVIGATION = (
    "Accueil\nS'inscrire\nConnexion\nAccepter les cookies\n",
    "Menu\nActualités\nConditions d'utilisation\nTous droits réservés\n",
    "Retour\nEn savoir plus\nPartager\nMentions légales\n",
)


def passages(text):
    """Découpe un document en passages, de préférence avant un espace ou un saut de ligne."""
    start = 0
    while start < len(text):
        end = min(start + MAX_CHARS, len(text))
        if end < len(text):
            # Cherche une coupure dans le dernier quart du passage.
            boundary = max(text.rfind(" ", end - MAX_CHARS // 4, end),
                           text.rfind("\n", end - MAX_CHARS // 4, end))
            if boundary != -1:
                end = boundary + 1
        passage = text[start:end].strip()
        if passage:
            yield passage
        start = end


def features(text):
    """Mesure la structure d'un passage sans apprendre son vocabulaire ou sa source."""
    chars = max(1, sum(not char.isspace() for char in text))
    words = WORD.findall(text.lower())
    lines = [line.strip().casefold() for line in text.splitlines() if line.strip()]
    trigrams = list(zip(words, words[1:], words[2:]))
    return (
        sum(char.isalpha() for char in text) / chars,
        sum(char.isdigit() for char in text) / chars,
        sum(char in "|{}[]<>=#_" for char in text) / chars,
        len(URL.findall(text)) / chars,
        sum(len(line) < 25 for line in lines) / max(1, len(lines)),
        1 - len(set(lines)) / max(1, len(lines)),
        1 - len(set(trigrams)) / max(1, len(trigrams)) if trigrams else 0,
        sum(char in ".?!" for char in text) / max(1, len(words)),
        sum(len(word) > 18 for word in words) / max(1, len(words)),
    )


def noise(text, index):
    """Corrompt une copie avec du bruit web simulé pour produire un pseudo-label négatif."""
    mode = index % 3
    if mode == 0:
        navigation = NAVIGATION[(index // 3) % len(NAVIGATION)]
        return navigation + text[:len(text) // 2] + "\n" + navigation
    if mode == 1:
        # Simule un bloc de texte dupliqué au milieu de la page.
        fragment = text[:len(text) // 4].rsplit(" ", 1)[0]
        return "\n".join([fragment] * 3) + "\n" + text[len(text) // 2:]
    # Simule une ligne de résultats avec adresses et identifiants résiduels.
    links = "\n".join(f"[Lien {number}] https://exemple.invalid/page?id={number:06d}"
                      for number in range(8))
    return text[:len(text) // 2] + "\n" + links


def pseudo_examples(sources, scratch):
    """Collecte des paires originales/corrompues dans des archives françaises d'entraînement."""
    train, holdout = [], []
    counts = Counter()
    for source, rate in (("wikipedia_fr", 0.03), ("gutenberg_fr", 0.8), (WEB, 0.3)):
        path = sources[source][0]
        for text in shuffled_texts(path, rate, SEED, scratch):
            # Un passage au plus par texte conserve la séparation entre apprentissage et contrôle.
            passage = next((chunk for chunk in passages(text) if len(chunk) >= 700), None)
            if passage is None:
                continue
            original = features(passage)
            # Les positifs sont des passages avec du texte suivi et peu de balisage.
            if original[0] < 0.80 or original[2] > 0.015 or original[5] > 0.1:
                continue
            index = counts[source]
            pairs = holdout if index % 5 == 0 else train
            pairs.append((original, features(noise(passage, index))))
            counts[source] += 1
            if counts[source] == 600:
                break
        if counts[source] < 100:
            raise ValueError(f"Trop peu de pseudo-exemples pour {source}")
    return np.asarray(train), np.asarray(holdout), dict(counts)


def fit_classifier(training):
    """Ajuste une régression logistique régularisée sur les paires positives/négatives."""
    data = training.reshape(-1, training.shape[-1])
    targets = np.tile([1.0, 0.0], len(training))
    mean = data.mean(axis=0)
    scale = np.maximum(data.std(axis=0), 1e-6)
    matrix = (data - mean) / scale
    weights = np.zeros(matrix.shape[1])
    bias = 0.0
    # Descente pleine et initialisation nulle pour reproduire les coefficients.
    for _ in range(300):
        probabilities = 1 / (1 + np.exp(-np.clip(matrix @ weights + bias, -30, 30)))
        errors = probabilities - targets
        weights -= 0.15 * (matrix.T @ errors / len(matrix) + 0.015 * weights)
        bias -= 0.15 * errors.mean()
    return mean, scale, weights, bias


def score(rows, model):
    """Donne le logit du classifieur pour un ou plusieurs passages."""
    mean, scale, weights, bias = model
    return (np.asarray(rows) - mean) / scale @ weights + bias


def score_document(text, model):
    """Utilise le quartile bas, puis conserve ou rejette le document entier."""
    rows = [features(passage) for passage in passages(text)]
    return float(np.quantile(score(rows, model), 0.25))


def iter_documents(path):
    """Lit les documents indexés dans l'ordre de l'archive Common Crawl contrôlée."""
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for index, line in enumerate(stream):
            yield index, line, json.loads(line)["text"]


def rank_documents(path, model, tokenizer):
    """Mesure le nombre de tokens et le score de chaque document d'entraînement web."""
    documents = iter_documents(path)
    ranked = []
    while batch := list(islice(documents, 64)):
        texts = [text for _, _, text in batch]
        for (index, _, text), ids in zip(batch, tokenizer.encode_batch(texts), strict=True):
            # Même séparateur que pipeline.mixes. Les documents d'origine ont déjà été nettoyés.
            ranked.append((score_document(text, model), index, len(ids) + 1))
    # Les scores égaux sont départagés par la position dans l'archive de référence.
    return sorted(ranked, key=lambda row: (-row[0], row[1]))


def select_documents(ranked, requested):
    """Garde les meilleurs scores jusqu'à disposer d'une marge de tokens mesurée."""
    minimum = (MIN_STOCK_PERCENT * requested + 99) // 100
    accepted = set()
    tokens = 0
    for threshold, index, size in ranked:
        accepted.add(index)
        tokens += size
        if tokens >= minimum:
            return accepted, tokens, threshold
    raise ValueError(f"Common Crawl ne fournit que {tokens:,} tokens pour un stock cible de {minimum:,}")


def prepare(kit, interim, base, out):
    """Écrit le flux M4CLASS et les mesures du classement sans lancer l'entraînement officiel."""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    sys.path.insert(0, str(kit))
    from ftb import load_config
    from ftb.tokenizer import load_tokenizer

    if out.exists():
        raise FileExistsError(f"Choisis un dossier de sortie neuf : {out}")
    config = load_config()
    manifest = read_json(base / "manifest.json")
    if manifest["kit_revision"] != KIT_REV or manifest["config"] != config:
        raise ValueError("Le kit diffère du protocole M4")
    tokenizer_path = base / "tokenizer.json"
    if sha256(tokenizer_path) != manifest["tokenizer_sha256"]:
        raise ValueError("Le tokenizer partagé diffère de son manifeste")
    tokenizer = load_tokenizer(tokenizer_path)
    sources = load_sources(interim)
    train = config["train"]
    shares = MIXES["M4"]
    quota = quotas(train["max_steps"] * train["tokens_per_step"], shares)[WEB]
    path, _, parent_sha = sources[WEB]
    out.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(dir=out.parent) as temporary:
        scratch = Path(temporary)
        training, holdout, counts = pseudo_examples(sources, scratch)
        model = fit_classifier(training)
        control = score(holdout, model)
        print(f"{len(training)} paires d'apprentissage. Classement des contrôles : "
              f"{np.mean(control[:, 0] > control[:, 1]):.1%}", flush=True)
        ranked = rank_documents(path, model, tokenizer)
        accepted, selected_tokens, threshold = select_documents(ranked, quota)
        kept = scratch / "common_crawl.jsonl.gz"
        size = 0
        # Conserve les documents intacts et leur ordre avant le tirage commun des mélanges.
        with kept.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as output:
            for index, line, text in iter_documents(path):
                if index in accepted:
                    output.write(line.encode("utf-8"))
                    size += len(text.encode("utf-8"))
        mean, scale, weights, bias = model
        stats = {
            "source_sha256": parent_sha,
            "training_seed": SEED,
            "pseudo_pairs_by_source": counts,
            "holdout_pairs": len(holdout),
            "holdout_pairwise_accuracy": float(np.mean(control[:, 0] > control[:, 1])),
            "feature_means": dict(zip(FEATURE_NAMES, mean.tolist(), strict=True)),
            "feature_scales": dict(zip(FEATURE_NAMES, scale.tolist(), strict=True)),
            "weights_standardized": dict(zip(FEATURE_NAMES, weights.tolist(), strict=True)),
            "bias": float(bias),
            "docs_before": len(ranked), "docs_after": len(accepted),
            "tokens_before": sum(size for _, _, size in ranked), "tokens_after": selected_tokens,
            "threshold_logit": threshold,
            "quota_training_tokens": quota,
            "minimum_stock_percent": MIN_STOCK_PERCENT,
        }
        print(f"{len(accepted):,}/{len(ranked):,} documents, {selected_tokens:,} tokens retenus.", flush=True)
        sources[WEB] = (kept, size, sha256(kept))
        staged = scratch / "dataset"
        staged.mkdir()
        meta = prepare_mix(staged / NAME, sources, shares, tokenizer, config, scratch)
        if meta["passes_started_by_source"][WEB] != 1.0:
            raise ValueError("Le Common Crawl filtré a été répété")
        write_json(staged / "quality_classification.json", stats)
        shutil.copyfile(tokenizer_path, staged / "tokenizer.json")
        staged.rename(out)
    return meta


def main():
    """Vérifie le clone du kit et lance la préparation du mélange M4CLASS."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=ROOT / "kit/Piscine-official")
    parser.add_argument("--interim", type=Path, default=ROOT / "data/interim")
    parser.add_argument("--base", type=Path, default=ROOT / "data/processed/ablation")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    kit = args.kit.resolve()
    if subprocess.check_output(["git", "-C", str(kit), "rev-parse", "HEAD"], text=True).strip() != KIT_REV:
        raise ValueError(f"Clone du kit attendu à la révision {KIT_REV}")
    if subprocess.check_output(["git", "-C", str(kit), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("Le clone du kit contient des modifications")
    meta = prepare(kit, args.interim.resolve(), args.base.resolve(), args.out.resolve())
    print(meta["dataset_sha256"], flush=True)


if __name__ == "__main__":
    main()
