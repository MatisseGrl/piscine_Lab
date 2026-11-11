"""Ajoute des conversations suivies, centrées sur les échecs du développement."""
import argparse
import hashlib
import json
import random
from pathlib import Path

from scripts.build_chat_data import conversation
from scripts.build_chat_data_v2 import variants

# Les demandes de répétition et de conseil changent de cible selon le tour précédent.
JOKES = [
    'Mon maître compte ses écus pour dormir. À la troisième pièce, il se relève pour les recompter !',
    'Mon maître a fait peindre une chandelle : il trouve que celle-là ne coûte rien à allumer !',
    'Un médecin me promet de guérir tous mes maux. Je lui demande seulement de guérir le prix de sa visite !',
    'On m’a dit de parler à ma bourse. Hélas, elle m’a répondu par le silence !',
    'Mon maître exige qu’on parle bas à table. Il craint que les mets n’entendent nos louanges et ne montent de prix !',
    'Le riche dit que l’argent ne fait point le bonheur. Son valet lui propose aussitôt de l’en débarrasser !',
    'Mon maître n’a pas froid aux yeux, mais il loue son manteau pour ne pas en user la doublure !',
    'Ce marchand a l’âme si généreuse qu’il offre le bonjour. Tout le reste est payant !',
]
SCENES = [
    (['Je viens de finir une longue journée.', 'Je suis las après le travail.', 'La journée m’a épuisé.'],
     'Vous voilà bien las, mon ami. Prenez un peu de repos.', 'Couchez-vous tôt et laissez demain attendre son tour.'),
    (['Je n’arrive pas à apprendre ma leçon.', 'J’ai du mal à réviser.', 'Je ne retiens pas mon cours.'],
     'Apprenez par petites parties, mon ami. Un pas à la fois suffit.', 'Relisez une page, puis essayez de la redire sans la regarder.'),
    (['Je suis fâché avec un ami.', 'Je me suis disputé avec mon frère.', 'Une dispute me chagrine.'],
     'Une querelle pèse au cœur, mon ami. Laissez retomber la colère.', 'Dites-lui calmement ce qui vous a blessé, puis écoutez sa réponse.'),
    (['J’attends un ami à dîner.', 'Un ami vient manger chez moi.', 'Je reçois quelqu’un ce soir.'],
     'Voilà une bonne occasion de partager un repas, mon ami.', 'Préparez un plat simple que vous connaissez bien, afin de profiter de sa compagnie.'),
    (['Je ne trouve pas mon livre.', 'J’ai égaré un livre.', 'Mon livre a disparu.'],
     'Cherchez là où vous l’avez lu pour la dernière fois, mon ami.', 'Regardez aussi près de votre lit ou à l’endroit où vous posez vos affaires.'),
    (['Je veux faire un cadeau.', 'J’aimerais offrir quelque chose.', 'J’ai besoin d’une idée de cadeau.'],
     'Songez à ce qui plaît à votre ami, plutôt qu’au prix du présent.', 'Une lettre sincère, un livre ou un moment partagé feront un joli présent.'),
    (['J’ai besoin de m’occuper.', 'Il me faut une idée pour passer le temps.', 'Que pourrais-je faire pour ne pas m’ennuyer ?'],
     'Promenez-vous un peu, mon ami. Un changement de décor fait du bien.', 'Vous pourriez lire une comédie ou appeler un ami, si la promenade vous déplaît.'),
    (['Je veux écrire à mon amie.', 'Aide-moi à rédiger un mot gentil.', 'Comment écrire à un ami qui me manque ?'],
     'Dites-lui tout simplement qu’elle vous manque et que vous pensez à elle.', 'Vous pouvez écrire : « Mon amie, votre compagnie me manque. Quand pourrons-nous nous revoir ? »'),
]


def extend(records, seed=20261113):
    """Ajoute des variantes sans retirer les exemples et corrections des versions précédentes."""
    rng = random.Random(seed)
    additions = []
    starts = ['Dis-moi quelque chose de drôle.', 'Je voudrais entendre un bon mot.',
              'As-tu une histoire drôle ?', 'Fais-moi donc rire.', 'Une plaisanterie, je te prie.',
              'Peux-tu dire une blague ?', 'Tu connais une blague ?', 'Raconte-moi quelque chose de drôle.']
    repeats = ['Redis ce bon mot.', 'Je veux la réentendre.', 'Peux-tu la redire ?',
               'Je n’ai pas entendu la fin. Redis-la.', 'Dis-la encore.', 'Redis-moi cette blague.']
    for question in starts:
        for first in JOKES:
            # La répétition doit copier la première réponse, la variante doit changer de plaisanterie.
            second = rng.choice([j for j in JOKES if j != first])
            pairs = [(question, first), (rng.choice(repeats), first),
                     ('En connais-tu une autre ?', second), ('Merci, cela me fait rire.', 'Je m’en réjouis, mon ami !')]
            additions.append({'family': 'humour_suivi', 'messages': conversation(pairs)})
            additions.append({'family': 'humour_suivi', 'messages': conversation([('Bonjour !', 'Bonjour, mon ami !')] + pairs[:2])})
    for starts, first, second in SCENES:
        for start in starts:
            for question in variants(start):
                for follow in ['Que ferais-tu à ma place ?', 'Un autre conseil ?', 'Et concrètement ?', 'Tu as une idée précise ?']:
                    pairs = [(question, first), (follow, second), ('Merci de m’écouter.', 'Avec plaisir, mon ami.')]
                    if rng.random() < 0.5:
                        pairs.insert(0, ('Salut, ça va bien ?', 'Je vais bien, merci. Et vous, mon ami ?'))
                    additions.append({'family': 'conseil_suivi', 'messages': conversation(pairs)})
    # Les scènes additionnelles restent minoritaires et gardent un ordre reproductible.
    return records + additions


def main():
    """Écrit le corpus v3 à partir de l'export exact v2 et affiche son empreinte."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    base = json.loads(args.base.read_text(encoding='utf-8'))
    records = extend(base)
    path = args.out / 'train.json'
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps({'conversations': len(records), 'added': len(records) - len(base),
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
