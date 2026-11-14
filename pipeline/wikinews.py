"""Collecte et nettoie Wikinews FR (presse libre) depuis le dump officiel Wikimedia.

Étapes, dans l'ordre : lecture du dump XML (articles de l'espace principal, sans
redirections) → retrait du wikitexte (modèles, catégories, images, bandeaux, sections de
fin « Sources / Articles connexes ») → étapes existantes de `pipeline.clean` (ftfy, filtre
de contamination 13-grammes contre la validation publique et la validation Molière,
langue fastText ≥ 0,80) → retrait des articles trop courts → dédup exacte sur textes
normalisés → MinHash 0,97 → filtre qualité actuel (`pipeline.quality`).
Aucun masquage PII (décision du plan). Octets comptés en UTF-8, graine 42.

    uv run python -m pipeline.wikinews --download
    uv run python -m pipeline.wikinews
"""

import argparse
import bz2
import html
import json
import re
from collections import Counter
from contextlib import ExitStack
from hashlib import md5
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

import numpy as np

from pipeline.clean import (
    INTERIM, MODEL, MODEL_HASH, MODEL_URL, RAW, ValidationGuard, default_kit, digest,
    open_output, process_source,
)
from pipeline.collect import download
from pipeline.dedup import ExactDeduper, SEED, build_links, select_matches, shingles, signature
from pipeline.quality import SHORT_MIN, evaluate, metrics

SOURCE = "wikinews_fr"
DUMP_DATE = "20261101"
DUMP_NAME = f"frwikinews-{DUMP_DATE}-pages-articles.xml.bz2"
DUMP_URL = f"https://dumps.wikimedia.org/frwikinews/{DUMP_DATE}/{DUMP_NAME}"
# Somme MD5 publiée par Wikimedia dans frwikinews-20261101-md5sums.txt (vérifiée à la collecte).
DUMP_MD5 = "06ca2a718c9f281d14a94f0df234744a"
DUMP_SIZE = 25_346_880
THRESHOLD_MINHASH = 0.97
# Sections de fin d'article (références, renvois) : elles et tout ce qui suit sont retirés.
END_SECTIONS = {
    "sources", "source", "articles connexes", "article connexe", "notes", "note", "liens externes",
    "voir aussi", "références", "notes et références", "sources externes", "articles liés",
    "lien externe", "liens", "annexes",
}
# Préfixes de liens à retirer entièrement (images, catégories, médias).
DROP_LINK_PREFIXES = {"image", "fichier", "file", "catégorie", "category", "média", "media"}
# Balises dont le contenu est supprimé avec la balise.
DROP_TAGS = re.compile(
    r"<(ref|gallery|references|math|imagemap|timeline|noinclude|score)\b[^>]*?(?:/>|>.*?</\1\s*>)",
    re.DOTALL | re.IGNORECASE,
)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
TAG = re.compile(r"</?[A-Za-z][^>]*>")
TABLE = re.compile(r"\{\|(?:(?!\{\|).)*?\|\}", re.DOTALL)
DATE_TEMPLATE = re.compile(r"\{\{\s*[Dd]ate\s*\|([^{}|]*)\}\}")
TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
LINK = re.compile(r"\[\[([^\[\]]*)\]\]")
EXTERNAL = re.compile(r"\[(?:https?:)?//[^\s\]]+(?:[ \t]+([^\]]*))?\]")
BARE_URL = re.compile(r"https?://[^\s<>\]]+")
HEADING = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$")
LIST_MARK = re.compile(r"^[*#:;]+\s*")
# Restes de tableaux mal formés (lignes « | », « ! », « |- ») et images dont le lien n'est pas fermé.
RESIDUE_LINE = re.compile(r"^(?:\||!|\{\|)|^\[\[(?:image|fichier|file)\s*:", re.IGNORECASE)
MAGIC = re.compile(r"__[A-Z]+__")


def _replace_link(match):
    """Remplace un lien interne par son libellé, ou par rien pour images, catégories, langues."""
    content = match.group(1)
    target = content.split("|")[0].strip()
    # Un lien commençant par « : » est un lien normal vers un autre espace (ex. [[:en:x|y]]).
    if not target.startswith(":"):
        prefix = target.split(":")[0].strip().casefold() if ":" in target else ""
        # Les codes de langue (2 ou 3 lettres) sont des liens interlangues.
        if prefix in DROP_LINK_PREFIXES or re.fullmatch(r"[a-z]{2,3}(?:-[a-z]+)?", prefix):
            return ""
    label = content.rsplit("|", 1)[-1] if "|" in content else target
    return label.strip().lstrip(":")


def wikitext_to_text(wikitext):
    """Convertit du wikitexte en texte brut : retire modèles, liens techniques et bandeaux."""
    text = COMMENT.sub("", wikitext)
    text = DROP_TAGS.sub("", text)
    text = TAG.sub("", text)
    # Les tableaux sont retirés, du plus interne au plus externe.
    for _ in range(10):
        reduced = TABLE.sub("", text)
        if reduced == text:
            break
        text = reduced
    # Le modèle {{date|…}} porte la date de l'article : on garde son contenu.
    text = DATE_TEMPLATE.sub(lambda m: m.group(1).strip(), text)
    # Retire les modèles imbriqués en partant des plus internes.
    for _ in range(20):
        reduced = TEMPLATE.sub("", text)
        if reduced == text:
            break
        text = reduced
    text = text.replace("{{", "").replace("}}", "")
    # Liens internes imbriqués (légendes d'images) : du plus interne au plus externe.
    for _ in range(10):
        reduced = LINK.sub(_replace_link, text)
        if reduced == text:
            break
        text = reduced
    text = EXTERNAL.sub(lambda m: (m.group(1) or "").strip(), text)
    text = BARE_URL.sub("", text)
    text = MAGIC.sub("", text)
    text = text.replace("'''", "").replace("''", "")
    text = html.unescape(text).replace("\xa0", " ")
    lines = []
    for line in text.split("\n"):
        heading = HEADING.match(line.strip())
        if heading:
            title = heading.group(2).strip().casefold().rstrip(" :")
            # Une section de fin (sources, articles connexes…) coupe le reste de l'article.
            if title in END_SECTIONS:
                break
            lines.append(heading.group(2).strip())
            continue
        if RESIDUE_LINE.match(line.strip()):
            continue
        line = LIST_MARK.sub("", line.strip())
        lines.append(" ".join(line.split()))
    # Réduit les blancs successifs à une seule ligne vide.
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def iter_pages(path):
    """Lit le dump XML par flux : articles de l'espace principal, hors redirections."""
    with bz2.open(path, "rb") as stream:
        for _, node in ElementTree.iterparse(stream, events=("end",)):
            if not node.tag.endswith("}page"):
                continue
            namespace = node.findtext("{*}ns")
            if namespace == "0" and node.find("{*}redirect") is None:
                revision = node.find("{*}revision")
                text = revision.findtext("{*}text") or ""
                yield {
                    "page_id": node.findtext("{*}id"), "title": node.findtext("{*}title"),
                    "revision": revision.findtext("{*}id"),
                    "timestamp": revision.findtext("{*}timestamp"), "wikitext": text,
                }
            # Libère la mémoire de chaque page lue.
            node.clear()


def keep_long_enough(text):
    """Vrai si le texte a au moins SHORT_MIN caractères hors espaces (chiffre du filtre CC)."""
    return metrics(text)["non_space"] >= SHORT_MIN


def contaminated(text, guard):
    """Vrai si le texte partage 13 mots avec la validation (texte réparé ou brut)."""
    from pipeline.clean import repair_encoding

    repaired = repair_encoding(text)
    return guard.matches(repaired) or (repaired != text and guard.matches(text))


def exact_step(rows):
    """Dédup exacte sur texte normalisé (minuscules, NFC, espaces) : garde le premier."""
    deduper = ExactDeduper()
    kept, rejected = [], 0
    for row in rows:
        if deduper.add(SOURCE, row["text"]) == "kept":
            kept.append(row)
        else:
            rejected += 1
    return kept, rejected


def minhash_step(rows, threshold=THRESHOLD_MINHASH):
    """Retire les quasi-doublons (Jaccard exact ≥ seuil sur suites de 5 mots) via MinHash+LSH."""
    if not rows:
        return rows, 0
    sets = [shingles(row["text"]) for row in rows]
    keys = np.stack([signature(words) for words in sets])
    sizes = np.array([len(words) for words in sets], dtype=np.uint32)
    kept, _ = select_matches(
        build_links(keys), sizes, lambda index: sets[index], threshold, inspect=False,
    )
    return [row for row, keep in zip(rows, kept) if keep], int((~kept).sum())


def quality_step(rows):
    """Applique le filtre qualité actuel (`pipeline.quality`) ; renvoie gardés et motifs."""
    kept, reasons = [], Counter()
    for row in rows:
        reason, _ = evaluate(row["text"], SOURCE)
        if reason:
            reasons[reason] += 1
        else:
            kept.append(row)
    return kept, dict(reasons)


def size_of(rows):
    """Octets UTF-8 cumulés des textes."""
    return sum(len(row["text"].encode("utf-8")) for row in rows)


def build(pages, guard, predict, titles=None):
    """Applique toute la chaîne à un itérable de pages ; renvoie les lignes finales et les stats."""
    pages = list(pages)
    stats = {"pages_main_namespace": len(pages)}
    wikitext_bytes = sum(len(p["wikitext"].encode("utf-8")) for p in pages)
    stats["wikitext_bytes"] = wikitext_bytes
    stamps = [p["timestamp"] for p in pages if p.get("timestamp")]
    # Dates de dernière révision de chaque article (pas la date de rédaction).
    stats["revision_timestamp_min"] = min(stamps, default=None)
    stats["revision_timestamp_max"] = max(stamps, default=None)
    if titles is not None:
        titles.update({f"{p['page_id']}:{p['revision']}": p["title"] for p in pages})
    documents = ((f"{p['page_id']}:{p['revision']}", wikitext_to_text(p["wikitext"])) for p in pages)
    # Réutilise telle quelle l'étape de nettoyage existante (ftfy, contamination, langue).
    stream = StringIO()
    clean_stats = process_source(documents, SOURCE, stream, None, predict, guard)
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    stats["clean"] = clean_stats
    short = [row for row in rows if not keep_long_enough(row["text"])]
    rows = [row for row in rows if keep_long_enough(row["text"])]
    stats["too_short_rejected"] = len(short)
    stats["after_short"] = {"docs": len(rows), "bytes": size_of(rows)}
    rows, exact_rejected = exact_step(rows)
    stats["exact_rejected"] = exact_rejected
    stats["after_exact"] = {"docs": len(rows), "bytes": size_of(rows)}
    rows, near_rejected = minhash_step(rows)
    stats["minhash_rejected"] = near_rejected
    stats["after_minhash"] = {"docs": len(rows), "bytes": size_of(rows)}
    rows, quality_rejected = quality_step(rows)
    stats["quality_rejected_by_reason"] = quality_rejected
    stats["final"] = {"docs": len(rows), "bytes": size_of(rows)}
    return rows, stats


def count_tokens(rows, tokenizer_path):
    """Estime les tokens avec le tokenizer 8 192 du kit (+1 séparateur de document)."""
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    total = 0
    for start in range(0, len(rows), 512):
        batch = [row["text"] for row in rows[start:start + 512]]
        total += sum(len(e.ids) + 1 for e in tokenizer.encode_batch(batch))
    return total


def repetitions(tokens, target=100_007_936):
    """Répétitions nécessaires pour couvrir 5 %, 10 % et 25 % du budget de tokens."""
    return {f"{int(share * 100)}%": round(share * target / tokens, 2) for share in (0.05, 0.10, 0.25)}


def run(out, kit, tokenizer_path, limit=None):
    """Exécute la chaîne complète et publie le dossier de sortie après relecture."""
    import fasttext

    if out.exists():
        raise FileExistsError(f"Choisis un dossier de sortie neuf : {out}")
    dump = RAW / "wikinews_fr" / DUMP_NAME
    # Le dump est vérifié par taille et MD5 (somme publiée par Wikimedia).
    if not dump.is_file() or dump.stat().st_size != DUMP_SIZE:
        raise FileNotFoundError(f"Dump absent ou incomplet, lance --download : {dump}")
    if md5(dump.read_bytes()).hexdigest() != DUMP_MD5:
        raise ValueError("MD5 du dump incorrect")
    validation = kit / "data" / "validation.jsonl"
    moliere = kit / "corpus" / "moliere_val.txt"
    with validation.open(encoding="utf-8") as stream:
        texts = [json.loads(line)["text"] for line in stream if line.strip()]
    if len(texts) != 230:
        raise ValueError("Les 230 documents de validation publique du kit sont requis")
    guard = ValidationGuard([*texts, *moliere.read_text(encoding="utf-8").split("=====")])
    download(MODEL_URL, MODEL, size=131_266_198, checksum=("sha256", MODEL_HASH))
    model = fasttext.load_model(str(MODEL))

    def predict(text):
        """Meilleure langue et score du modèle figé."""
        labels, scores = model.predict(text, k=1)
        return labels[0].removeprefix("__label__"), float(scores[0])

    pages = iter_pages(dump)
    if limit:
        from itertools import islice
        pages = islice(pages, limit)
    titles = {}
    rows, stats = build(pages, guard, predict, titles)
    # Relecture : aucun document final ne doit partager 13 mots avec la validation.
    overlaps = sum(guard.matches(row["text"]) for row in rows)
    if overlaps:
        raise ValueError(f"{overlaps} documents finaux recouvrent la validation")
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        with ExitStack() as stack:
            writer = open_output(stack, stage, SOURCE)
            for row in rows:
                writer.write(json.dumps(row, ensure_ascii=False) + "\n")
        stats["final"]["sha256"] = digest(stage / f"{SOURCE}.jsonl.gz")
        stats["final"]["overlap_with_validation_docs"] = overlaps
        tokens = count_tokens(rows, tokenizer_path)
        stats["tokens_estimated"] = tokens
        stats["tokenizer_path"] = str(tokenizer_path)
        stats["repetitions_needed"] = repetitions(tokens)
        stats.update({
            "seed": SEED, "language_threshold": 0.80, "minhash_threshold": THRESHOLD_MINHASH,
            "dump": {"url": DUMP_URL, "date": DUMP_DATE, "md5": DUMP_MD5, "bytes": DUMP_SIZE,
                     "sha256": digest(dump)},
            "validation_sha256": digest(validation), "moliere_validation_sha256": digest(moliere),
            "tokenizer_sha256": digest(tokenizer_path),
        })
        (stage / "stats.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n",
        )
        (stage / "titles.json").write_text(
            json.dumps(titles, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n",
        )
        stage.rename(out)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def main():
    """Commande : téléchargement du dump (--download) ou traitement complet."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="télécharge le dump officiel")
    parser.add_argument("--out", type=Path, default=INTERIM / "wikinews")
    parser.add_argument("--kit", type=Path, default=default_kit())
    parser.add_argument("--tokenizer", type=Path, default=INTERIM.parent / "processed" / "ablation" / "tokenizer.json")
    parser.add_argument("--limit", type=int, help="test borné : N premières pages")
    args = parser.parse_args()
    if args.download:
        download(DUMP_URL, RAW / "wikinews_fr" / DUMP_NAME, size=DUMP_SIZE, checksum=None)
        return
    run(args.out, args.kit, args.tokenizer, args.limit)


if __name__ == "__main__":
    main()
