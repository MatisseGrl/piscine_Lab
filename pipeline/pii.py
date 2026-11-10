"""Masque les données personnelles évidentes par regex, avec des marqueurs typés.

Cibles : e-mails, téléphones français, IBAN français (clé vérifiée), URL explicites
(HTTP(S) ou www) et adresses IP (IPv4 et IPv6 valides). Les noms et adresses postales ne
sont PAS détectés (pas de NLP) : c'est la limite assumée de cette passe.
"""

import argparse
import ipaddress
import re
from collections import Counter
from pathlib import Path

from pipeline.clean import default_kit
from pipeline.variants import run_stage, snippet_source

# Ordre d'application : une URL est masquée d'un bloc avant ses e-mails ou IP internes.
TYPES = ("URL", "EMAIL", "IBAN", "TEL", "IP")

URL = re.compile(r"\b(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
EMAIL = re.compile(r"(?<![\w.+\-])[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
IBAN = re.compile(r"(?<!\w)FR\d{2}(?: ?[0-9A-Z]{4}){5} ?[0-9A-Z]{3}(?!\w)", re.IGNORECASE)
# Numéro français : 0X XX XX XX XX ou +33 / 0033 suivi de neuf chiffres, séparateurs facultatifs.
PHONE = re.compile(r"(?<![\w+.])(?:(?:\+|00)33[ .\-]?|0)[1-9](?:[ .\-]?\d{2}){4}(?!\w)")
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\w|\.\d)")
IPV6 = re.compile(r"(?<![\w:.])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])")


def _trim_url(url):
    """Retire la ponctuation finale qui appartient à la phrase, pas à l'URL."""
    while url:
        last = url[-1]
        if last in ".,;:!?":
            url = url[:-1]
        elif last in ")]}" and url.count(last) > url.count({")": "(", "]": "[", "}": "{"}[last]):
            # Parenthèse fermante sans ouvrante dans l'URL : elle vient du texte autour.
            url = url[:-1]
        else:
            break
    return url


def _find_urls(text):
    """Renvoie les intervalles des URL explicites, ponctuation finale exclue."""
    if "http" not in text and "www" not in text.lower():
        return
    for match in URL.finditer(text):
        trimmed = _trim_url(match.group())
        if len(trimmed) > len("www."):
            yield match.start(), match.start() + len(trimmed)


def _find_emails(text):
    """Renvoie les intervalles des adresses e-mail."""
    if "@" in text:
        for match in EMAIL.finditer(text):
            yield match.span()


def _iban_valid(candidate):
    """Contrôle la clé de l'IBAN : modulo 97 du nombre réarrangé égal à 1."""
    compact = candidate.replace(" ", "").upper()
    digits = "".join(str(int(char, 36)) for char in compact[4:] + compact[:4])
    return int(digits) % 97 == 1


def _find_ibans(text):
    """Renvoie les intervalles des IBAN français dont la clé est valide."""
    if "fr" in text.lower():
        for match in IBAN.finditer(text):
            if _iban_valid(match.group()):
                yield match.span()


def _find_phones(text):
    """Renvoie les intervalles des numéros de téléphone français."""
    for match in PHONE.finditer(text):
        yield match.span()


def _find_ips(text):
    """Renvoie, triés, les intervalles des IPv4 et IPv6 valides."""
    spans = []
    for match in IPV4.finditer(text):
        try:
            ipaddress.IPv4Address(match.group())
        except ValueError:
            continue
        spans.append(match.span())
    if text.count(":") >= 2:
        for match in IPV6.finditer(text):
            candidate = match.group()
            # Les formes très courtes (« a::b ») sont trop ambiguës pour être masquées.
            if len(candidate) < 5:
                continue
            try:
                ipaddress.IPv6Address(candidate)
            except ValueError:
                continue
            spans.append(match.span())
    yield from sorted(spans)


FINDERS = {
    "URL": _find_urls, "EMAIL": _find_emails, "IBAN": _find_ibans,
    "TEL": _find_phones, "IP": _find_ips,
}


def _replace(text, spans, marker):
    """Remplace chaque intervalle par le marqueur et garde le texte autour intact."""
    pieces, last = [], 0
    for start, end in spans:
        pieces.append(text[last:start])
        pieces.append(marker)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def mask(text):
    """Masque le texte et renvoie (texte masqué, nombre de segments par type)."""
    counts = {}
    for kind in TYPES:
        spans = list(FINDERS[kind](text))
        if spans:
            counts[kind] = len(spans)
            text = _replace(text, spans, f"[{kind}]")
    return text, counts


def shape(segment):
    """Ne garde que la forme d'un segment : lettres en « a », chiffres en « 9 »."""
    return "".join("9" if c.isdigit() else "a" if c.isalpha() else c for c in segment)


class PiiMasker:
    """Étape de masquage : ne supprime aucun document, remplace seulement les segments."""

    name = "pii"
    params = {"types": list(TYPES), "method": "regex", "iban": "FR, clé modulo 97"}

    def apply(self, row):
        """Masque le texte d'un document et renvoie le compte par type."""
        text, counts = mask(row["text"])
        if not counts:
            return row, Counter()
        return dict(row, text=text), Counter(counts)

    def view(self, row, new_row, tag):
        """Exemple sans donnée personnelle : forme du premier segment, ou début masqué."""
        if tag in FINDERS:
            for start, end in FINDERS[tag](row["text"]):
                return shape(row["text"][start:end])
        return snippet_source(row["text"], mask)

    def summary(self):
        """Pas de mesure supplémentaire pour cette étape."""
        return {}


def main():
    """Applique le masquage à un dossier JSONL.gz et publie la sortie après audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=Path("data/interim/dedup/final"))
    parser.add_argument("--out", type=Path, default=Path("data/interim/pii/dedup"))
    parser.add_argument("--kit", type=Path, default=default_kit())
    parser.add_argument("--limit", type=int, help="pilote : N premiers documents par source")
    args = parser.parse_args()
    run_stage(args.src, args.out, PiiMasker(), args.kit, name="pii", limit=args.limit)


if __name__ == "__main__":
    main()
