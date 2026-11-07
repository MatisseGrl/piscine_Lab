"""Télécharge les pièces de Molière depuis Wikisource FR en texte brut UTF-8.

Pour chaque pièce listée sur la page de l'auteur, choisit une édition (Louandre 1910
si elle existe : relue et homogène), récupère la page de l'édition et toutes ses
sous-pages (actes, liste des personnages), puis convertit le HTML rendu en texte brut.

Le texte des pièces (Molière seul) va dans data/raw/moliere/. Les notices d'éditeur
et textes de tiers (Louandre 1910, Neuf-Villenaine) vont dans data/raw/moliere_notices/ :
ce n'est pas le style de Molière, mais de la prose française du domaine public,
gardée pour la compétition.

Usage :
    uv run python scripts/fetch_moliere.py          # écrit data/raw/moliere{,_notices}/
    uv run python scripts/fetch_moliere.py --limit 2  # test rapide sur 2 pièces

Bibliothèque standard uniquement : tourne sans environnement virtuel.
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

API = "https://fr.wikisource.org/w/api.php"
USER_AGENT = "piscine-lab-moliere/0.1 (student project; https://github.com/MatisseGrl/piscine_Lab)"
AUTHOR_PAGE = "Auteur:Molière"
PREFERRED_EDITION = "Édition Louandre, 1910"
# Sous-pages écrites par des éditeurs ou des tiers, pas par Molière : sauvées à part.
NOTICE_SUBPAGES = ("Notice", "Neuf-Villenaine")
# Sous-pages ignorées : une liste de chanteurs, et un doublon des actes.
EXCLUDED_SUBPAGES = NOTICE_SUBPAGES + ("Noms des personnes", "Texte entier")
# Un début de page plus court que ça n'est qu'un titre et des liens de sommaire, pas une notice.
MIN_NOTICE_BYTES = 500
REQUEST_DELAY_S = 0.5


def api_get(**params):
    params.update(format="json", formatversion="2", maxlag="5")
    url = API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
        except OSError:
            time.sleep(2 ** attempt)
            continue
        if data.get("error", {}).get("code") == "maxlag":
            time.sleep(5)
            continue
        time.sleep(REQUEST_DELAY_S)
        return data
    raise RuntimeError(f"API request failed: {url}")


def wikitext(title):
    data = api_get(action="parse", page=title, prop="wikitext", redirects="1")
    return data["parse"]["title"], data["parse"]["wikitext"]


def wiki_links(text):
    """Cibles des [[liens]] du wikitext, dans l'ordre d'apparition."""
    targets = []
    for match in re.finditer(r"\[\[([^\]|#]+)", text):
        target = match.group(1).strip().replace("_", " ")
        if target and ":" not in target and target not in targets:
            targets.append(target)
    return targets


def list_plays():
    """(année, titre) de chaque pièce de la page auteur, lus dans les modèles {{document}}."""
    _, text = wikitext(AUTHOR_PAGE)
    section = text.split("=== Pièces de théâtre ===")[1].split("{{liste documents fin}}")[0]
    plays = []
    for doc in re.findall(r"\{\{document\|(.*?)\}\}", section):
        fields = dict(part.split("=", 1) for part in doc.split("|") if "=" in part)
        value = fields.get("éditions") or fields.get("titre") or ""
        links = wiki_links(value)
        title = links[0] if links else value.strip()
        plays.append((fields.get("date", "").strip(), title))
    return plays


def subpages(title):
    data = api_get(action="query", list="allpages", apnamespace="0",
                   apprefix=title + "/", aplimit="max")
    return [page["title"] for page in data["query"]["allpages"]]


def rendered_links(title):
    """Liens de la page rendue, pour les listes générées par des modèles."""
    data = api_get(action="parse", page=title, prop="links", redirects="1")
    return [link["title"] for link in data["parse"]["links"] if link["ns"] == 0 and link.get("exists")]


def choose_edition(title):
    """Renvoie la page qui contient le texte : une édition de la pièce, ou la page elle-même."""
    title, text = wikitext(title)
    links = wiki_links(text)
    # La page est déjà la pièce quand elle pointe vers ses propres actes.
    if any(link.startswith(title + "/Acte") for link in links):
        return title
    is_editions_list = (PREFERRED_EDITION in text or "liste documents" in text
                        or "{{œuvre" in text or "{{molière" in text)
    if not is_editions_list:
        return title
    if not links:
        links = rendered_links(title)
    # Les pages rendues pointent aussi vers d'autres pièces (navigation) : ne garder que les éditions de celle-ci.
    base = re.sub(r"\s*\(.*?\)$", "", title)
    editions = [link for link in links
                if link.startswith(base) and link != title
                and ("/" in link or "Édition" in link)
                and not any(word in link for word in EXCLUDED_SUBPAGES)]
    for edition in editions:
        if PREFERRED_EDITION in edition:
            return edition
    return editions[0] if editions else title


def edition_pages(edition):
    """(pages de la pièce dans l'ordre de lecture, pages de notice) pour une édition."""
    _, text = wikitext(edition)
    all_children = subpages(edition)
    children = [page for page in all_children
                if not any(word in page for word in EXCLUDED_SUBPAGES)]
    notices = [page for page in all_children
               if any(word in page for word in NOTICE_SUBPAGES)]
    linked = [link for link in wiki_links(text) if link in children]
    ordered = linked + [page for page in children if page not in linked]
    # La liste des personnages n'est pas toujours dans le sommaire : la mettre avant les actes.
    ordered.sort(key=lambda page: not page.endswith(("/Personnages", "/Prologue")))
    return [edition] + ordered, notices


class TextExtractor(HTMLParser):
    """HTML rendu de Wikisource vers texte brut, sans la navigation ni les notes."""

    SKIP_CLASSES = ("ws-noexport", "noprint", "reference", "mw-references-wrap",
                    "references", "pagenum", "ws-pagenum", "mw-editsection", "headertemplate")
    BLOCK_TAGS = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "dd", "dt", "table"}
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
    VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "wbr"}
    # Marque l'endroit d'une ligne vide : avant chaque nom de locuteur et chaque titre.
    PARAGRAPH = "\x00"

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []  # True pour chaque élément ouvert qui est ignoré

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        if tag in self.VOID_TAGS:
            return
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if "personnage" in classes or tag in self.HEADING_TAGS:
            self.parts.append(self.PARAGRAPH)
        # Les vers partagés répètent le demi-vers précédent dans un span caché pour aligner le texte.
        hidden = "visibility:hidden" in (attributes.get("style") or "").replace(" ", "")
        skipped = (any(name in classes for name in self.SKIP_CLASSES) or hidden
                   or tag in ("style", "script", "sup"))
        self.stack.append(skipped or (bool(self.stack) and self.stack[-1]))

    def handle_endtag(self, tag):
        if tag in self.VOID_TAGS:
            return
        if self.stack:
            self.stack.pop()
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not (self.stack and self.stack[-1]):
            self.parts.append(data)

    def text(self):
        raw = "".join(self.parts).replace("\xa0", " ")
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.split("\n")]
        text = re.sub(r"\n{2,}", "\n", "\n".join(line for line in lines if line != ""))
        text = re.sub(r"\n?\x00+\n?", "\n\n", text)
        text = "\n".join(line.strip() for line in text.split("\n"))
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def page_text(title):
    data = api_get(action="parse", page=title, prop="text|revid",
                   disableeditsection="1", disabletoc="1", redirects="1")
    extractor = TextExtractor()
    extractor.feed(data["parse"]["text"])
    return extractor.text(), data["parse"].get("revid")


PLAY_START = re.compile(r"^(PERSONNAGES|ACTEURS|PROLOGUE|ACTE\b)", re.IGNORECASE)


def split_front_matter(text):
    """(début de page, pièce) : ce qui précède la pièce est le titre de l'édition,
    une notice d'éditeur s'il y en a une, et des liens de sommaire."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if PLAY_START.match(line) and line.isupper() or line in ("Prologue", "PROLOGUE"):
            return "\n".join(lines[:index]).strip(), "\n".join(lines[index:])
    return "", text


def slugify(title):
    title = re.sub(r"\s*\(Molière\)", "", title)
    slug = re.sub(r"[^\w]+", "_", title.lower(), flags=re.UNICODE).strip("_")
    return slug[:60]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("data/raw/moliere"))
    parser.add_argument("--notices-out", type=Path, default=Path("data/raw/moliere_notices"))
    parser.add_argument("--limit", type=int, default=None, help="seulement les N premières pièces")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.out.mkdir(parents=True, exist_ok=True)
    args.notices_out.mkdir(parents=True, exist_ok=True)

    plays = list_plays()[: args.limit]
    manifest, notices_manifest = [], []
    for year, title in plays:
        edition = choose_edition(title)
        pages, notice_pages = edition_pages(edition)
        chunks, revisions = [], {}
        for page in pages:
            text, revid = page_text(page)
            revisions[page] = revid
            if text:
                chunks.append(text)
        front, play = split_front_matter("\n\n".join(chunks))
        notice_chunks = [front] if len(front.encode("utf-8")) >= MIN_NOTICE_BYTES else []
        for page in notice_pages:
            text, revid = page_text(page)
            revisions[page] = revid
            if text:
                notice_chunks.append(text)

        entry = {"title": title, "year": year, "edition": edition, "pages": revisions}
        manifest.append({**entry, **write_text(args.out, title, play)})
        if notice_chunks:
            notices_manifest.append({**entry, **write_text(args.notices_out, title, "\n\n".join(notice_chunks))})
        print(f"{year}  {title:45.45}  {len(pages):2d} pages  {manifest[-1]['bytes'] / 1000:7.1f} ko"
              f"  notice {'oui' if notice_chunks else 'non'}  <- {edition}")

    write_manifest(args.out, manifest)
    write_manifest(args.notices_out, notices_manifest)
    print(f"\n{len(manifest)} pièces, {sum(m['bytes'] for m in manifest) / 1e6:.2f} Mo -> {args.out}")
    print(f"{len(notices_manifest)} notices, {sum(m['bytes'] for m in notices_manifest) / 1e6:.2f} Mo"
          f" -> {args.notices_out}")


def write_text(directory, title, text):
    body = text.strip() + "\n"
    path = directory / f"{slugify(title)}.txt"
    path.write_text(body, encoding="utf-8", newline="\n")
    data = body.encode("utf-8")
    return {"file": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_manifest(directory, items):
    (directory / "manifest.json").write_text(
        json.dumps({"source": "fr.wikisource.org", "author_page": AUTHOR_PAGE,
                    "fetched": time.strftime("%Y-%m-%d"),
                    "total_bytes": sum(item["bytes"] for item in items), "plays": items},
                   ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
