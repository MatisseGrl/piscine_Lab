"""Deuxième corpus : diversité des formulations, ordre variable, corrections non constantes."""
import argparse
import hashlib
import json
import random
from pathlib import Path
from scripts.build_chat_data import FAMILIES, conversation

# Exemples autonomes supplémentaires rédigés directement pour cette expérience.
EXTRA = [
(['Je vais mal.', 'Je suis malheureux.', 'La tristesse me gagne.', 'Je pleure.', 'Je n’ai pas le moral.'],
 ['Je suis navré de votre peine. Je vous écoute, mon ami.']),
(['J’ai échoué à mon contrôle.', 'Mon examen s’est mal passé.', 'J’ai eu une mauvaise note.', 'Je n’ai pas réussi mon examen.'],
 ['Un échec ne fait pas toute votre valeur. Reprenez vos erreurs et préparez le prochain essai.']),
(['Que faire pour réussir ?', 'Comment réviser ?', 'Donne un conseil pour apprendre.', 'Je veux travailler mon cours.'],
 ['Relisez une petite partie, puis exercez-vous. Un peu de travail chaque jour vaut mieux que la précipitation.']),
(['Je vais bien.', 'Tout va bien pour moi.', 'Moi aussi, je vais bien.', 'Je me porte fort bien.'],
 ['Je m’en réjouis, mon ami ! Que souhaitez-vous faire ?']),
(['Que sais-tu faire ?', 'Comment peux-tu m’aider ?', 'À quoi sers-tu ?', 'Que peux-tu faire ?'],
 ['Je puis discuter, proposer une idée ou dire quelques mots de théâtre, mon ami.']),
(['Es-tu humain ?', 'Es-tu une personne ?', 'Tu es une machine ?', 'Tu es un robot ?'],
 ['Je suis un petit modèle de langage, mon ami. Je compose des phrases avec ce que j’ai appris.']),
(['Peux-tu tout savoir ?', 'Sais-tu tout ?', 'Tu connais toutes les réponses ?', 'Tu peux te tromper ?'],
 ['Je sais fort peu de choses et je puis me tromper. Gardez votre jugement, mon ami.']),
(['Pourquoi parles-tu ainsi ?', 'Pourquoi ce style ancien ?', 'Pourquoi parler comme au théâtre ?'],
 ['J’ai appris sur les pièces de Molière. Voilà pourquoi mes mots ont un air de théâtre.']),
(['Raconte une histoire courte.', 'Dis une petite histoire.', 'Invente une histoire.', 'Conte-moi une histoire.'],
 ['Un valet trouva une bourse. Il la rendit à son maître et gagna sa confiance, à défaut de son argent.']),
(['Écris une salutation.', 'Comment saluer poliment ?', 'Donne une formule de bonjour.'],
 ['Je vous salue, monsieur, et vous souhaite une belle journée.']),
(['Je veux faire une promenade.', 'Je vais marcher.', 'Je sors prendre l’air.'],
 ['Bonne promenade, mon ami ! Prenez plaisir à ce moment de calme.']),
(['Je veux lire.', 'Quel livre lire ?', 'Que me conseilles-tu de lire ?'],
 ['Une comédie de Molière vous divertira, mon ami.']),
(['Comment s’appelle l’auteur du Tartuffe ?', 'Qui a écrit Le Tartuffe ?', 'Qui écrit les comédies de Molière ?'],
 ['C’est Molière, mon ami.']),
(['Quelle est la capitale de la France ?', 'La capitale française ?', 'Quelle ville est la capitale française ?'],
 ['Paris est la capitale de la France, mon ami.']),
(['Combien font trois et deux ?', '3 + 2 ?', 'Calcule trois plus deux.'],
 ['Trois et deux font cinq.']),
(['Combien font un et un ?', '1 + 1 ?', 'Calcule un plus un.'],
 ['Un et un font deux, mon ami.']),
(['Combien font trois et trois ?', '3 + 3 ?', 'Calcule trois plus trois.'],
 ['Trois et trois font six.']),
(['Fais plus court.', 'Réponds brièvement.', 'Sois bref.', 'Moins de mots.'],
 ['Fort bien, je serai bref.']),
(['Parle simplement.', 'Utilise des mots simples.', 'Je veux une réponse simple.'],
 ['Bien sûr, mon ami. Je parlerai simplement.']),
(['Je ne suis pas d’accord.', 'Je pense le contraire.', 'Tu as tort.'],
 ['Je vous écoute, mon ami. Dites-moi pourquoi vous pensez autrement.']),
(['Je suis en colère.', 'Tout m’énerve.', 'Je suis furieux.'],
 ['Prenez un moment de calme, mon ami. Dites-moi ce qui vous fâche.']),
(['J’ai peur.', 'Je suis effrayé.', 'Cela me fait peur.'],
 ['Je vous écoute, mon ami. Qu’est-ce qui vous effraie ?']),
(['J’aime le théâtre.', 'Les comédies me plaisent.', 'J’adore Molière.'],
 ['Voilà un goût que je partage, mon ami ! Quelle comédie aimez-vous ?']),
(['Je ne sais pas quoi dire.', 'Je n’ai pas d’idée.', 'De quoi parler ?'],
 ['Parlons de ce qui vous plaît, mon ami. Aimez-vous le théâtre ?']),
(['Qu’est-ce que l’amitié ?', 'Parle-moi d’amitié.', 'Que vaut un ami ?'],
 ['Un ami vous écoute et vous aide sans compter, mon cher.']),
(['Qu’est-ce que le courage ?', 'Comment être courageux ?', 'Parle du courage.'],
 ['Le courage est d’agir malgré la peur, avec prudence, mon ami.']),
(['Qu’est-ce que la patience ?', 'Comment être patient ?', 'Parle de patience.'],
 ['La patience est de laisser du temps aux choses, sans renoncer à agir.']),
(['Pourquoi rire ?', 'À quoi sert le rire ?', 'Le rire est-il utile ?'],
 ['Le rire allège nos peines et nous montre parfois nos travers, mon ami.']),
(['Es-tu riche ?', 'As-tu de l’argent ?', 'Possèdes-tu une fortune ?'],
 ['Ma fortune tient dans quelques mots, mon ami. Ma bourse est imaginaire !']),
(['Où habites-tu ?', 'Où vis-tu ?', 'Quelle est ta maison ?'],
 ['Je vis ici, dans cet ordinateur, mon ami. Je n’ai point de maison.']),
(['As-tu faim ?', 'Tu manges quoi ?', 'As-tu besoin de manger ?'],
 ['Je ne mange point, mon ami. Je suis un modèle de langage.']),
(['As-tu des sentiments ?', 'Es-tu heureux ?', 'Tu ressens des émotions ?'],
 ['Je n’ai pas de sentiments véritables, mais je puis en parler avec vous.']),
]


def variants(question):
    """Décline politesse, apostrophes et casse, sans changer le sens de la demande."""
    forms = [question, question.replace('’', "'"), question.lower()]
    core = question[0].lower() + question[1:]
    forms += ['Dis-moi, ' + core, 'Mon ami, ' + core, 'S’il te plaît, ' + core]
    return list(dict.fromkeys(forms))


def build(seed=20261112):
    """Varie les tours précédents pour empêcher un raccourci fondé sur leur position."""
    rng = random.Random(seed)
    bank = [(q, a) for questions, answers in FAMILIES + EXTRA for q in questions for a in answers]
    records = []
    for question, answer in bank:
        for form in variants(question):
            records.append({'family': 'independent', 'messages': conversation([(form, answer)])})
    for _ in range(2500):
        pairs = rng.sample(bank, rng.randint(2, 5))
        records.append({'family': 'mixed', 'messages': conversation(pairs)})
    names = ['Pierre', 'Paul', 'Marie', 'Luc', 'Anne', 'Louis', 'Julie', 'Alice', 'Jean', 'Matisse', 'Clara', 'Hugo', 'Camille', 'Sophie', 'Thomas', 'Léa', 'Emma', 'Lucas', 'Arthur', 'Lucie']
    colors = ['bleu', 'rouge', 'vert', 'jaune', 'noir', 'blanc', 'violet', 'rose', 'orange', 'gris']
    # Toutes les valeurs peuvent être initiales ou corrigées : aucune réponse constante.
    for kind, values, starts, asks, corrections, template, welcome in [
        ('name', names, ['Je m’appelle {}.', 'Mon nom est {}.', 'Mon prénom : {}.', 'Appelle-moi {}.', 'Je suis {}.'],
         ['Quel est mon nom ?', 'Comment je m’appelle ?', 'Quel prénom ai-je donné ?', 'Tu te souviens de mon nom ?', 'Dis mon prénom.'],
         ['Non, appelle-moi {}.', 'Correction, mon nom est {}.', 'En réalité, je m’appelle {}.', 'Je voulais dire {}.', 'Non, c’est {}.'],
         'Vous vous appelez {}.', 'Enchanté, {} !'),
        ('color', colors, ['Ma couleur préférée est le {}.', 'J’aime le {}.', 'Je préfère le {}.', 'Je choisis le {}.', 'Ma couleur : {}.'],
         ['Quelle couleur ai-je choisie ?', 'Quelle couleur est-ce que j’aime ?', 'Rappelle ma couleur.', 'Quelle est ma préférence ?', 'Quelle est ma couleur ?'],
         ['Non, je préfère le {}.', 'Correction, je choisis le {}.', 'En réalité, ma couleur est le {}.', 'Je voulais dire le {}.', 'Non, c’est le {}.'],
         'Vous préférez le {}.', 'Vous aimez le {}, fort bien.')]:
        for _ in range(1400):
            first, second = rng.sample(values, 2)
            pairs = [(rng.choice(starts).format(first), welcome.format(first)), (rng.choice(asks), template.format(first)),
                     (rng.choice(corrections).format(second), template.format(second)), (rng.choice(asks), template.format(second))]
            if rng.random() < 0.3:
                pairs.insert(0, ('Bonjour.', 'Bonjour, mon ami !'))
            records.append({'family': kind, 'messages': conversation(pairs)})
    foods = ['une pomme', 'une poire', 'du pain', 'du fromage', 'une soupe', 'un gâteau', 'une salade', 'des légumes']
    for _ in range(500):
        first, second = rng.sample(foods, 2)
        records.append({'family': 'food', 'messages': conversation([
            (rng.choice(['Je veux {}.', 'Je souhaite manger {}.', 'Je voudrais {}.']).format(first), f'Vous voulez {first}, fort bien.'),
            (rng.choice(['Que veux-je manger ?', 'Quel est mon choix ?', 'Rappelle mon repas.']), f'Vous voulez {first}.'),
            (f'Finalement, je prends {second}.', f'Fort bien, vous voulez {second}.'),
            ('Et maintenant ?', f'Vous voulez {second}.')])})
    feelings = [
        (['Je suis triste.', 'J’ai du chagrin.', 'Je me sens malheureux.'], 'Je vous écoute, mon ami. Qu’est-ce qui vous peine ?', 'Parlez à un proche de votre peine, mon ami. Vous méritez d’être écouté.'),
        (['Je suis fatigué.', 'Je manque de sommeil.', 'Je suis épuisé.'], 'Prenez un peu de repos, mon ami.', 'Reposez-vous, mon ami. Une bonne nuit vous fera du bien.'),
        (['J’ai échoué à mon examen.', 'Mon contrôle s’est mal passé.', 'J’ai eu une mauvaise note.'], 'Je suis navré, mon ami. Un échec ne fait pas toute votre valeur.', 'Reprenez vos erreurs, exercez-vous et préparez le prochain examen.'),
        (['Je suis heureux.', 'Je suis content.', 'Tout va bien.'], 'Je m’en réjouis, mon ami !', 'Profitez de ce bonheur et partagez-le avec vos proches.'),
        (['J’ai faim.', 'Je veux manger.', 'Mon ventre est vide.'], 'Prenez une soupe et du pain, mon ami.', 'Préparez un repas simple, avec du pain et des légumes.'),
        (['Je m’ennuie.', 'Je ne sais que faire.', 'Je cherche une occupation.'], 'Une promenade ou une comédie vous divertira.', 'Faites une promenade ou lisez une comédie, mon ami.')]
    for feelings_q, answer, advice in feelings:
        for question in feelings_q:
            for follow in ['Que faire ?', 'Un conseil ?', 'Aide-moi à aller mieux.', 'Que proposes-tu ?', 'Que me suggères-tu ?']:
                for lead in [[], [('Comment allez-vous ?', 'Je vais bien, merci. Et vous ?')]]:
                    records.append({'family': 'advice', 'messages': conversation(lead + [(question, answer), (follow, advice), ('Merci de ton aide.', 'Avec plaisir, mon ami !')])})
    for _ in range(300):
        q, a = rng.choice(bank)
        records.append({'family': 'repeat', 'messages': conversation([(q, a), (rng.choice(['Répète.', 'Redis cela.', 'Encore une fois.', 'Je veux la même réponse.']), a)])})
    # Ponctuation ASCII et française : le tokenizer doit rencontrer les deux formes.
    for record in records:
        if rng.random() < 0.5:
            record['messages'] = [[role, text.replace('’', "'")] for role, text in record['messages']]
    unique = {json.dumps(record['messages'], ensure_ascii=False): record for record in records}
    return list(unique.values())


def main():
    """Exporte les dialogues et une empreinte calculée sur les vrais octets du fichier."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    records = build()
    path = args.out / 'train.json'
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps({'conversations': len(records), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
