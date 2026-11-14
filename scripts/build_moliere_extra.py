"""Prépare seulement des pièces de Molière absentes du kit pour un essai hors référence."""
import argparse
import hashlib
import json
from pathlib import Path

from minigpt.bigram import load_utf8
from scripts.audit_chat_data import shingles

# Liste revue contre le manifeste du kit ; aucune notice ou pièce de validation.
PLAY_FILES = (
    'la_comtesse_d_escarbagnas.txt', 'le_bourgeois_gentilhomme.txt', 'le_malade_imaginaire.txt',
    'les_femmes_savantes.txt', 'les_fourberies_de_scapin.txt',
)


def main():
    """Vérifie les empreintes Wikisource et refuse tout recouvrement avec la validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'corpus', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.source / 'manifest.json').read_text(encoding='utf-8'))
    plays = {entry['file']: entry for entry in manifest['plays']}
    validation = load_utf8(args.corpus / 'moliere_val.txt').decode('utf-8')
    validation_shingles = shingles(validation)
    docs, accepted, rejected = [], [], []
    for name in PLAY_FILES:
        data = load_utf8(args.source / name)
        metadata = plays[name]
        if hashlib.sha256(data).hexdigest() != metadata['sha256']:
            raise ValueError(f'Empreinte Wikisource non reproduite : {name}')
        content = data.decode('utf-8')
        # Un seul recouvrement suffit à écarter toute la pièce, avant entraînement.
        overlap = len(shingles(content) & validation_shingles)
        if overlap:
            rejected.append(dict(file=name, overlaps=overlap))
            continue
        docs.append(content.strip())
        accepted.append(metadata)
    if not docs:
        raise ValueError('Aucune pièce supplémentaire ne passe le contrôle.')
    args.out.mkdir(parents=True, exist_ok=False)
    text = '\n\n'.join(docs) + '\n'
    data = text.encode('utf-8')
    (args.out / 'train_extra.txt').write_bytes(data)
    audit = dict(accepted=accepted, rejected=rejected, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    (args.out / 'manifest.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(accepted=len(accepted), rejected=rejected, bytes=len(data), sha256=audit['sha256'])))


if __name__ == '__main__':
    main()
