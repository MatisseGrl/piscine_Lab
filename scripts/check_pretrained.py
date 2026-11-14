"""Contrôles du mini-GPT pré-entraîné : rechargement strict, hash du tokenizer, BPB zéro coup
sur la validation Molière, et recherche de fuite (13-grammes de mots) dans le texte nettoyé."""
import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

import torch

from minigpt.bigram import load_utf8
from minigpt.finetune import restore_model
from minigpt.hf_tokenizer import HFTokenizer
from minigpt.model import evaluate_bpb

EXPECTED_TOKENIZER = 'b2554a8221a55c19b4008f5b605b1b6e84b6a7f84058507c15aba34eca3b2379'


def ngrams(text, n=13):
    """Ensemble des séquences de n mots (minuscules, lettres seulement) d'un texte."""
    words = re.findall(r'\w+', text.casefold())
    return {' '.join(words[i:i + n]) for i in range(len(words) - n + 1)}


def main():
    """Lance les trois contrôles et écrit un rapport JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint', 'tokenizer', 'corpus', 'cleaned', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--max-docs', type=int, default=200000)
    args = parser.parse_args()
    torch.set_num_threads(4)
    saved = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    model = restore_model(saved)  # strict=True : échoue si un poids manque ou est en trop
    tokenizer = HFTokenizer.load(args.tokenizer)
    report = {'config': saved['config'], 'params': model.num_params(),
              'tokenizer_sha256_ok': tokenizer.sha256 == EXPECTED_TOKENIZER,
              'vocab_ok': len(tokenizer.vocab) == model.cfg.vocab_size}
    # Lecture en mode texte : CRLF normalisé, sinon le compte d'octets est faux.
    val_text = load_utf8(args.corpus / 'moliere_val.txt').decode('utf-8')
    report['val_bytes'] = len(val_text.encode('utf-8'))
    report['zero_shot_bpb'] = evaluate_bpb(model, tokenizer.encode(val_text), val_text)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    # Fuite : 13-grammes de la validation retrouvés dans les documents nettoyés.
    val_grams = ngrams(val_text)
    hits, docs, scanned_bytes = {}, 0, 0
    for path in sorted(args.cleaned.glob('*.jsonl.gz')):
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for line in f:
                if docs >= args.max_docs:
                    break
                text = json.loads(line).get('text', '')
                docs += 1
                scanned_bytes += len(text.encode('utf-8'))
                common = ngrams(text) & val_grams
                if common:
                    hits[path.name] = hits.get(path.name, []) + [sorted(common)[:3]]
    report.update(leak_docs_scanned=docs, leak_bytes_scanned=scanned_bytes, val_13grams=len(val_grams),
                  leak_docs_with_hits=sum(len(v) for v in hits.values()), leak_examples=hits)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'leak_examples'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
