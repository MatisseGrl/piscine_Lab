"""Audit reproductible des dialogues : volumes, mélange, exclusions et exemples."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from minigpt.bpe import BPETokenizer
from minigpt.chat_bench import DEV, FINAL
from minigpt.repair_bench import REPAIR_DEV, REPAIR_FINAL
from minigpt.bigram import load_utf8
from minigpt.conversation import prompt_ids


def words(text):
    """Normalise apostrophes et casse avant toute comparaison de textes."""
    return re.findall(r'\w+', text.casefold().replace('’', "'"))


def shingles(text, size=13):
    """Construit les séquences de mots employées pour détecter les recouvrements."""
    tokens = words(text)
    return {tuple(tokens[i:i + size]) for i in range(len(tokens) - size + 1)}


def main():
    """Vérifie les exclusions avant le run et écrit les éléments à inspecter."""
    parser = argparse.ArgumentParser()
    for name in ['data', 'tokenizer', 'corpus', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(args.data.read_text(encoding='utf-8'))
    tokenizer = BPETokenizer.load(args.tokenizer)
    validation = load_utf8(args.corpus / 'moliere_val.txt').decode('utf-8')
    val_shingles = shingles(validation)
    source = load_utf8(args.corpus / 'moliere_train.txt').decode('utf-8')
    questions = set()
    families, turns, counts = Counter(), Counter(), Counter()
    overlaps, samples = [], []
    for index, record in enumerate(records):
        messages = record['messages']
        assert len(messages) % 2 == 0
        families[record['family']] += 1
        turns[len(messages) // 2] += 1
        for position, (role, text) in enumerate(messages):
            assert role == ('user' if position % 2 == 0 else 'assistant')
            counts[role + '_tokens'] += len(tokenizer.encode(text))
            if role == 'user':
                questions.add(tuple(words(text)))
            else:
                _, dropped = prompt_ids(tokenizer, messages[:position])
                counts['responses'] += 1
                counts['responses_with_truncation'] += dropped > 0
            if shingles(text) & val_shingles:
                overlaps.append(index)
        if len(samples) < 12 and (not samples or samples[-1]['family'] != record['family']):
            samples.append(record)
    # Le lot final sert seulement à vérifier l'absence de contamination, jamais à optimiser.
    reserved = [question for discussion in DEV + FINAL for question in discussion]
    reserved.extend(followup for _, _, followup, _ in REPAIR_DEV + REPAIR_FINAL)
    normalized_source = ' '.join(words(source))
    leaks = [q for q in reserved if tuple(words(q)) in questions or ' '.join(words(q)) in normalized_source]
    assert not leaks, f'Questions réservées présentes : {leaks}'
    assert not overlaps, f'Recouvrements avec les pièces de validation : {overlaps[:10]}'
    result = {'sha256': hashlib.sha256(args.data.read_bytes()).hexdigest(), 'conversations': len(records),
              'families': dict(families), 'turns': dict(turns), 'counts': dict(counts),
              'reserved_question_leaks': leaks, 'validation_13_word_overlaps': overlaps,
              'inspection_examples': samples}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'inspection_examples'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
