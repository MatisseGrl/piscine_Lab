"""Paires de répliques extraites de Claire / TheatreGratuit (CC-BY-NC-SA 4.0), pour le SFT du chat.

Usage interne à la démo, rien de dérivé n'est publié. Garde-fous :
- tout bloc (pièce ou scène) qui contient un nom de personnage de Molière est retiré ;
- tout bloc qui partage une séquence de 13 mots avec Molière (33 pièces Wikisource, train et
  validation du kit) ou avec les 230 documents publics du kit est retiré ;
- on ne garde que des échanges courts entre deux personnages, plafonnés en octets."""
import argparse
import hashlib
import json
import random
import re
from pathlib import Path

from scripts.check_pretrained import ngrams

# Personnages de Molière les plus fréquents : un seul suffit à écarter le bloc.
MOLIERE_NAMES = {'harpagon', 'alceste', 'sganarelle', 'tartuffe', 'orgon', 'argan', 'jourdain', 'scapin',
                 'célimène', 'philinte', 'arnolphe', 'mascarille', 'toinette', 'dorine', 'elmire', 'géronte',
                 'covielle', 'trissotin', 'philaminte', 'chrysale', 'pourceaugnac', 'dandin', 'amphitryon',
                 'sosie', 'dom juan', 'don juan', 'gorgibus', 'magdelon', 'cathos', 'la flèche', 'frosine',
                 'oronte', 'acaste', 'clitandre', 'arsinoé', 'agnès', 'horace', 'chrysalde', 'purgon', 'diafoirus'}
LINE = re.compile(r'^\[([^\]:]+):\]\s*(.+)$')  # format « [PERSONNAGE:] réplique »


def blocks(text):
    """Découpe le fichier en blocs séparés par des lignes vides (pièces ou scènes)."""
    return [b for b in re.split(r'\n\s*\n', text) if b.strip()]


def pairs(block, max_chars):
    """Échanges consécutifs A -> B entre deux personnages distincts, répliques courtes."""
    lines = [m.groups() for m in map(LINE.match, block.splitlines()) if m]
    out = []
    for (a, ta), (b, tb) in zip(lines, lines[1:]):
        if a != b and 3 <= len(ta) <= max_chars and 3 <= len(tb) <= max_chars:
            out.append((ta.strip(), tb.strip()))
    return out


def main():
    """Filtre, extrait, plafonne et écrit les conversations au format du SFT."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claire', type=Path, required=True)        # FR/TheatreGratuit/train.txt
    parser.add_argument('--moliere-dir', type=Path, required=True)   # data/raw/moliere
    parser.add_argument('--corpus', type=Path, required=True)        # kit/Piscine/corpus
    parser.add_argument('--public', type=Path, required=True)        # kit/Piscine/data/validation.jsonl
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--max-bytes', type=int, default=3_000_000)
    parser.add_argument('--max-chars', type=int, default=200)
    args = parser.parse_args()
    # Toutes les séquences de 13 mots interdites (Molière complet + documents publics).
    banned = set()
    for path in list(args.moliere_dir.glob('*.txt')) + [args.corpus / 'moliere_train.txt', args.corpus / 'moliere_val.txt']:
        banned |= ngrams(path.read_text(encoding='utf-8'))
    for line in args.public.read_text(encoding='utf-8').splitlines():
        banned |= ngrams(json.loads(line)['text'])
    stats = {'blocks': 0, 'dropped_names': 0, 'dropped_13grams': 0}
    candidates = []
    for block in blocks(args.claire.read_text(encoding='utf-8')):
        stats['blocks'] += 1
        low = block.casefold()
        if any(re.search(r'\b' + re.escape(n) + r'\b', low) for n in MOLIERE_NAMES):
            stats['dropped_names'] += 1
            continue
        if ngrams(block) & banned:
            stats['dropped_13grams'] += 1
            continue
        candidates += pairs(block, args.max_chars)
    # Aucune question du banc DEV/FINAL (normalisée) dans une paire apprise.
    from minigpt.chat_bench import DEV, FINAL
    reserved = [' '.join(q.casefold().split()) for d in DEV + FINAL for q in d]
    before = len(candidates)
    candidates = [p for p in candidates
                  if not any(r in ' '.join((p[0] + ' ' + p[1]).casefold().split()) for r in reserved)]
    stats['dropped_bench'] = before - len(candidates)
    random.Random(20261114).shuffle(candidates)  # graine fixe
    records, size = [], 0
    for question, answer in candidates:
        # Plafond en octets UTF-8 sur le texte gardé.
        size += len((question + answer).encode('utf-8'))
        if size > args.max_bytes:
            break
        records.append({'messages': [['user', question], ['assistant', answer]], 'source': 'claire-theatregratuit'})
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / 'claire_pairs.json'
    path.write_text(json.dumps(records, ensure_ascii=False), encoding='utf-8')
    stats.update(candidates=len(candidates), kept=len(records),
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                 source_sha256=hashlib.sha256(args.claire.read_bytes()).hexdigest())
    (args.out / 'claire_stats.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')
    print(json.dumps(stats))


if __name__ == '__main__':
    main()
