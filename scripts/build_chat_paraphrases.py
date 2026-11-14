"""Élargit les formulations apprises et équilibre réponses directes et réparations."""
import argparse
import json
import random
from pathlib import Path

from minigpt.chat_bench import DEV, FINAL
from minigpt.repair_bench import REPAIR_DEV, REPAIR_FINAL
from scripts.audit_chat_data import words
from scripts.build_chat_repair import FOLLOWUPS, INTENTS, REPLIES

# L'ordre correspond aux intentions du corpus de réparation, sans réutiliser les tests.
PARAPHRASES = (
    'Salut à toi, comment te portes-tu ?|Coucou, tu te sens bien ?|Comment te sens-tu aujourd’hui ?|Bonjour, tout va bien pour toi ?|Je te salue, es-tu en forme ?|Alors, la forme aujourd’hui ?',
    'J’ai sommeil.|Je suis crevé ce soir.|La fatigue me gagne.|J’ai les paupières lourdes.|Je suis à bout de forces.|Il me faut une pause.|Je tombe de sommeil.',
    'J’ai la bouche sèche.|Quelque chose à boire, s’il te plaît.|Je voudrais me désaltérer.|Je suis assoiffé après le sport.|Que me conseilles-tu pour étancher ma soif ?',
    'Que préparer à manger ?|J’ai le ventre vide.|Il me faudrait un dîner simple.|On pourrait manger quoi ?|J’ai besoin d’un repas vite fait.|Qu’est-ce que tu ferais à dîner ?',
    'Recommande-moi un ouvrage.|Quelle lecture me proposes-tu ?|Je voudrais un roman ou une pièce.|Donne-moi le titre d’un livre.|Quel livre prendre pour ce soir ?|As-tu une idée de lecture ?',
    'J’aimerais marcher un peu.|Quel endroit choisir pour une balade ?|J’ai besoin de prendre l’air.|Une idée d’endroit pour marcher ?|Où faire quelques pas sans bruit ?',
    'Quel est ton rôle ?|Quelle sorte de programme es-tu ?|Peux-tu te présenter ?|Que fais-tu comme travail ?|Tu es quoi exactement ?|Quel assistant êtes-vous ?',
    'Je file, salut !|Nous nous reverrons demain.|Je vais devoir te laisser.|Au revoir et à bientôt.|Il est temps que je m’en aille.|On se quitte ici, à plus !',
    'Je pars me coucher.|Je vais éteindre et dormir.|Dors bien, à demain !|Je te souhaite une douce nuit.|Il est l’heure de dormir, bonne nuit.',
    'Je te suis reconnaissant.|Grand merci !|Merci, ça m’aide.|Je vous remercie bien.|Ça m’a rendu service, merci !',
    'J’ai égaré mes clés.|Je ne sais plus où j’ai posé mon sac.|Aide-moi à retrouver mon carnet.|Je cherche mon portefeuille partout.|J’ai perdu mes lunettes, où chercher ?|Mon cahier a disparu.',
    'J’ai un rendez-vous et je ne sais plus quand.|Connais-tu la date de mon entretien ?|Peux-tu me dire à quelle date je dois venir ?|Tu sais quand est prévue ma visite ?|À quel moment ai-je ce rendez-vous ?',
    'Dis-moi une plaisanterie.|Tu as une blague pour moi ?|Je voudrais rire un peu.|Raconte une histoire drôle.|Quelque chose d’amusant, je te prie.|Amuse-moi avec un bon mot.',
    'Je n’ai pas le moral.|Mon cœur est bien triste.|Je suis malheureux aujourd’hui.|J’ai envie de pleurer.|Je me sens découragé.|Ça ne va pas fort, j’ai de la peine.',
    'Je me sens isolé.|Je n’ai personne avec qui discuter.|Je suis seul ce soir.|Tout le monde est parti et je me sens seul.|Il me manque un peu de compagnie.',
    'J’ai eu une mauvaise note.|Mon épreuve s’est mal passée.|J’ai échoué au dernier examen.|Je suis déçu de mon résultat.|J’ai fait plein d’erreurs au contrôle.',
    'Aide-moi à étudier.|Quelle méthode pour apprendre mon cours ?|Je dois travailler pour une épreuve.|Comment mémoriser cette leçon ?|Mon examen approche, par où commencer ?',
    'Est-ce qu’il va faire beau ?|Peux-tu me dire la météo d’ici ?|Faut-il un parapluie aujourd’hui ?|Quel temps fait-il dehors ?|Vérifie si le ciel est couvert chez moi.',
    'Sais-tu quelle heure il est ?|J’aimerais connaître l’heure.|Mon réveil est illisible, quelle heure est-il ?|As-tu l’heure ?|Combien d’heures indique ma montre ?',
    'J’ai eu mon examen !|J’ai obtenu le résultat que je voulais.|Je suis fier, ça a marché !|Quel bonheur, j’ai réussi.|J’ai remporté mon concours !',
    'Je dois écrire à quelqu’un.|Comment rédiger une lettre courte ?|Aide-moi à formuler ce que j’ai à lui dire.|Je veux envoyer un mot sincère.|Peux-tu m’aider à écrire à un proche ?',
    'Je ne sais pas comment m’occuper.|Je tourne en rond.|Comment passer le temps ?|Trouve-moi de quoi me divertir.|J’aimerais faire quelque chose d’agréable.',
    'Pourquoi cette manière de parler ?|Tu as un ton très théâtral, pourquoi ?|Pourquoi ce langage un peu ancien ?|D’où vient ta façon de t’exprimer ?|Pourquoi t’exprimes-tu comme dans une pièce ?',
    'Répète-le plus simplement.|Je n’ai pas compris ce passage.|Explique en termes plus clairs.|Tu peux reformuler ?|Éclaire-moi sur ce point, je n’ai pas saisi.',
    'J’aurais besoin de ton aide.|Peux-tu me donner un coup de main ?|Je te demande un conseil.|J’aimerais te poser une question.|J’ai une demande à te faire.',
    'Dis-moi comment je me nomme.|Est-ce que je t’ai dit mon prénom ?|Tu connais mon petit nom ?|Sais-tu comment je m’appelle ?|Devines-tu mon prénom ?',
)


def build(base):
    """Associe chaque question à différents contextes en gardant la bonne cible."""
    rng = random.Random(2813)
    reserved = {tuple(words(q)) for discussion in DEV + FINAL for q in discussion}
    reserved.update(tuple(words(text)) for q, _, followup, _ in REPAIR_DEV + REPAIR_FINAL for text in (q, followup))
    result = rng.sample(base, min(1400, len(base)))
    for (questions, answer), expansion in zip(INTENTS, PARAPHRASES, strict=True):
        for raw in questions + expansion.split('|'):
            for question in dict.fromkeys([raw, raw.lower(), 'Dis-moi, ' + raw[0].lower() + raw[1:]]):
                if tuple(words(question)) in reserved:
                    continue
                result.append(dict(family='direct', messages=[['user', question], ['assistant', answer]]))
                # Le mauvais historique varie indépendamment du sujet à retrouver.
                for followup in rng.sample(FOLLOWUPS, 4):
                    wrong = rng.choice([text for text in REPLIES if text != answer])
                    correction = rng.choice(['Pardonnez-moi. ', 'Reprenons. ', '']) + answer
                    result.append(dict(family='repair', last_only=True, messages=[
                        ['user', question], ['assistant', wrong], ['user', followup], ['assistant', correction]]))
    rng.shuffle(result)
    return result


def main():
    """Exporte le corpus dans un dossier neuf pour conserver le précédent."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    records = build(json.loads(args.base.read_text(encoding='utf8')))
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'train.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf8', newline='\n')
    print(f'{len(records)} conversations')


if __name__ == '__main__':
    main()
