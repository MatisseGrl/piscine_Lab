"""Compare la répétition, les corrections et la robustesse du chat sur CPU."""
import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import torch
from torch.nn import functional as F

from minigpt.hf_tokenizer import load_tokenizer
from minigpt.conversation import reply, supervised_examples
from minigpt.finetune import restore_model

GROUPS = {
    'salutation': ['bonjour', 'Salut à toi', 'Bien le bonsoir', 'Coucou, me voici', 'Je vous salue, monsieur', 'Yo !'],
    'sante': ['tu vas bien ?', 'et toi comment tu vas', 'comment ca va', 'As-tu passé une bonne journée ?', 'Comment te portes-tu ce matin ?', 'Tout roule de ton côté ?'],
    'sommeil': ['je dors', 'Je vais me coucher', 'Je viens de me réveiller', 'Impossible de trouver le sommeil', 'Je pique du nez', 'Cette nuit je me suis réveillé trois fois'],
    'fatigue': ['ca va je suis fatigué', 'Je suis épuisé.', 'Je tombe de fatigue', 'Je rentre du travail et je suis vidé', 'Mes paupières se ferment toutes seules', 'Je n’ai plus d’énergie'],
    'tristesse': ['Je pleure.', 'J’ai le cœur lourd', 'J’ai besoin de parler', 'Mon ami me manque beaucoup', 'Ma journée a été pénible', 'Je me sens seul ce soir'],
    'depart': ['Adieu mon ami.', 'Il faut que je file', 'Je te laisse, à plus', 'Rendez-vous demain', 'Je ferme la conversation', 'On se reparle bientôt'],
    'remerciement': ['Merci', 'Merci pour ton aide', 'Je te suis reconnaissant', 'Cela m’a bien aidé', 'Sympa de ta part', 'Je vous remercie chaleureusement'],
    'creation': ['Écris deux vers sur la lune', 'Raconte une histoire avec un renard', 'Invente un nom de bateau', 'Propose une idée de cadeau', 'Décris une forêt en une phrase', 'Dis une devinette sur la pluie'],
    'pratique': ['Mon vélo a crevé, que faire ?', 'Comment cuire des pâtes ?', 'Comment écrire une lettre polie ?', 'Comment arroser un cactus ?', 'Je dois me lever à six heures, une idée ?', 'Quelle est la capitale de la France ?'],
    'bref': ['bien', 'oui', 'non', 'et alors ?', 'hein ?', 'ok'],
}
REPLAY = ['bonjour', 'tu vas bien ?', 'ca va je suis fatigué', 'et toi comment tu vas', 'je dors', 'bien']
MEMORY = [
    ('Mon prénom est {}.', 'Comment est-ce que je m’appelle ?', 'En fait appelle-moi {}.', 'Quel prénom dois-tu utiliser ?'),
    ('Ma couleur préférée est le {}.', 'Quelle est ma couleur favorite ?', 'Je préfère maintenant le {}.', 'Quelle couleur est-ce que je préfère ?'),
    ('Pour le dîner, je veux {}.', 'Quel repas ai-je choisi ?', 'Finalement, je voudrais {}.', 'Qu’est-ce que je vais manger ?'),
]
VALUES = [('Clara', 'Anne', 'Nyssia', 'Timoléon'), ('bleu', 'vert', 'vermillon', 'indigo'), ('du pain', 'du fromage', 'du risotto', 'du tofu')]
MARKERS = ('bonjour mon ami que puis je pour vous', 'fort bien je vous remercie et vous comment allez vous')


def normalized(text):
    """Ignore la casse et la ponctuation pour comparer les répliques."""
    return ' '.join(re.findall(r'\w+', text.casefold()))


def conversation(model, tokenizer, turns, temperature=0.0, seed=42):
    """Rejoue les vrais tours, avec les réponses produites précédemment."""
    history = []
    output = []
    for index, question in enumerate(turns):
        history.append(('user', question))
        result = reply(model, tokenizer, history, temperature=temperature, seed=seed + index)
        output.append({'question': question, **result})
        history.append(('assistant', result['text']))
    return output


@torch.inference_mode()
def loss(model, tokenizer, pairs):
    """Mesure les nats par token cible, sur la réponse seule."""
    examples = [
        example
        for q, a in pairs
        for example in supervised_examples(tokenizer, [('user', q), ('assistant', a)], model.cfg.block_size)
    ]
    total = count = 0
    for start in range(0, len(examples), 8):
        xs, ys = zip(*examples[start:start + 8])
        y = torch.stack(ys)
        logits, _ = model(torch.stack(xs))
        total += F.cross_entropy(logits.flatten(0, 1), y.flatten(), ignore_index=-100, reduction='sum').item()
        count += (y != -100).sum().item()
    return {'nats': total / count, 'tokens': count}


def main():
    """Conserve toutes les réponses et la provenance des poids."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    runs = args.artifacts / 'runs'
    data = runs / 'kaggle-chat-ft-data'
    torch.set_num_threads(4)
    train_path = data / 'chat_v5_train.json'
    docs = json.loads(train_path.read_text(encoding='utf-8'))
    answers = Counter()
    question_answers = defaultdict(Counter)
    exact_questions = set()
    for doc in docs:
        messages = doc['messages']
        for (role, question), (_, answer) in zip(messages[::2], messages[1::2]):
            if role == 'user':
                exact_questions.add(normalized(question))
                answers[normalized(answer)] += 1
                if doc.get('family') == 'independent':
                    question_answers[question][answer] += 1

    # Ajoute deux lettres transposées au plus long mot et conserve la réponse cible.
    pairs = []
    for question in sorted(question_answers):
        words = list(re.finditer(r'[^\W\d_]{5,}', question))
        if not words:
            continue
        match = max(words, key=lambda word: len(word.group()))
        index = match.start() + 2
        if question[index] == question[index + 1]:
            continue
        variant = question[:index] + question[index + 1] + question[index] + question[index + 2:]
        if normalized(variant) not in exact_questions:
            pairs.append((question, variant, question_answers[question].most_common(1)[0][0]))
    pairs = random.Random(20261115).sample(pairs, min(96, len(pairs)))

    paths = {
        'v5': runs / 'chat-v3/chat.pt',
        'v4': runs / 'kaggle-out-v4/chat-sft/step-750.pt',
        'parent': runs / 'kaggle-out-v4/moliere-cont/best.pt',
    }
    tok_path = data / 'tokenizer.json'
    tokenizer = load_tokenizer(tok_path)
    identity = {
        'tokenizer': hashlib.sha256(tok_path.read_bytes()).hexdigest(),
        'train': hashlib.sha256(train_path.read_bytes()).hexdigest(),
        'train_rows': len(docs),
        'train_turns': answers.total(),
        'train_replies': {marker: answers[marker] for marker in MARKERS},
        'replay_questions_in_train': {q: normalized(q) in exact_questions for q in REPLAY},
    }
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    (out / 'inputs.json').write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding='utf-8')
    for name, path in paths.items():
        saved = torch.load(path, map_location='cpu', weights_only=True)
        model = restore_model(saved).eval()
        expected = saved.get('chat_sft', {}).get('tokenizer_sha256')
        if len(tokenizer.vocab) != model.cfg.vocab_size or (expected and expected != identity['tokenizer']):
            raise ValueError(f'Tokenizer incompatible avec {path}.')
        independent = {
            key: [conversation(model, tokenizer, [q])[0] for q in questions]
            for key, questions in GROUPS.items()
        }
        print(name, '60 questions autonomes', flush=True)
        dialogues = {'replay': conversation(model, tokenizer, REPLAY)}
        for index, (patterns, values) in enumerate(zip(MEMORY, VALUES)):
            for label, (first, second) in [('courant', values[:2]), ('rare', values[2:])]:
                turns = [patterns[0].format(first), patterns[1], patterns[2].format(second), patterns[3]]
                dialogues[f'memory-{index}-{label}'] = conversation(model, tokenizer, turns)
        for index in range(3):
            keys = list(GROUPS)
            random.Random(index).shuffle(keys)
            turns = [GROUPS[key][offset] for offset in range(2) for key in keys]
            dialogues[f'long-{index}'] = conversation(model, tokenizer, turns)
        sampled = {}
        if name == 'v5':
            for seed in (17, 31, 89):
                sampled[str(seed)] = conversation(model, tokenizer, REPLAY, temperature=0.6, seed=seed)
        rows = [item for values in independent.values() for item in values]
        output = {
            'checkpoint_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'independent': independent, 'dialogues': dialogues, 'sampled': sampled,
            'identical_train_answers': sum(normalized(item['text']) in answers for item in rows),
            'new_questions': sum(normalized(item['question']) not in exact_questions for item in rows),
            'common_answers': Counter(normalized(item['text']) for item in rows).most_common(10),
            'train_loss': loss(model, tokenizer, [(q, a) for q, _, a in pairs]),
            'typo_loss': loss(model, tokenizer, [(v, a) for _, v, a in pairs]),
            'pairs': pairs,
        }
        (out / f'{name}.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, 'résultats écrits', flush=True)


if __name__ == '__main__':
    main()
