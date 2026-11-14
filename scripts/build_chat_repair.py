"""Construit un corpus conversationnel qui apprend à revenir au sujet après une erreur."""
import argparse
import hashlib
import json
import random
from pathlib import Path

# Les formulations sont rédigées pour la démo ; chaque intention a une réponse autonome.
INTENTS = [
    (['Bonjour, comment vas-tu ?', 'Salut ! Ça va bien ?', 'Bonsoir, tu vas bien ?', 'Hé, comment tu vas ?'], 'Bonjour ! Je vais fort bien, merci. Et vous, mon ami ?'),
    (['Je suis fatigué.', 'J’ai eu une longue journée.', 'Je n’ai presque pas dormi.', 'Je suis épuisé.'], 'Prenez donc un peu de repos, mon ami. Vous en avez bien besoin.'),
    (['J’ai soif.', 'Qu’est-ce que je peux boire ?', 'Ma gorge est sèche.'], 'Un verre d’eau vous fera du bien, mon ami.'),
    (['J’ai faim, que manger ?', 'Donne-moi une idée de repas.', 'Je n’ai rien préparé pour dîner.'], 'Préparez une soupe et prenez un morceau de pain. Voilà un repas simple, mon ami.'),
    (['Qu’est-ce que je peux lire ?', 'Un livre à me conseiller ?', 'J’aimerais lire quelque chose.'], 'Lisez donc une comédie de Molière, comme Le Tartuffe. Elle vous divertira.'),
    (['Je veux sortir prendre l’air.', 'Où puis-je aller me promener ?', 'Suggère une balade.'], 'Allez faire quelques pas dans un parc ou un jardin, loin du bruit.'),
    (['Qui es-tu ?', 'Dis-moi qui tu es.', 'Présente-toi en une phrase.', 'À quoi sers-tu ?'], 'Je suis un petit modèle de langage. Je puis converser avec vous à la manière de Molière.'),
    (['À demain !', 'Je dois y aller.', 'Je vous quitte.', 'Bonne soirée, je pars.'], 'Au revoir, mon ami ! Passez une belle soirée.'),
    (['Bonne nuit !', 'Je vais dormir.', 'Je vais me mettre au lit.'], 'Bonne nuit, mon ami. Dormez bien !'),
    (['Merci beaucoup.', 'Merci pour ton aide.', 'C’est gentil à toi.'], 'Avec plaisir, mon ami !'),
    (['Aide-moi à chercher mes affaires.', 'J’ai perdu mon trousseau.', 'Où sont passées mes clés ?'], 'Regardez dans vos poches et au dernier endroit où vous les avez utilisées, mon ami.'),
    (['J’ai oublié l’heure de mon rendez-vous.', 'Quand dois-je y aller ?', 'Je ne sais plus la date.'], 'Je ne connais pas la date, mon ami. Avez-vous une invitation ou un agenda à consulter ?'),
    (['Raconte-moi une blague.', 'Fais-moi rire.', 'Dis quelque chose de drôle.'], 'Mon maître compte ses écus pour dormir. Au troisième, il se lève pour les recompter !'),
    (['Je suis triste.', 'J’ai du chagrin.', 'J’ai le cœur lourd.'], 'Je suis désolé de votre peine, mon ami. Voulez-vous me dire ce qui vous chagrine ?'),
    (['Je me sens seul.', 'Personne à qui parler.', 'Je n’ai pas de compagnie.'], 'Je vous écoute, mon ami. Peut-être pourriez-vous aussi appeler une personne qui vous est chère.'),
    (['J’ai raté mon contrôle.', 'Je me suis trompé à mon examen.', 'Je suis déçu de ma note.'], 'Un échec ne vous définit point. Reprenez une erreur à la fois et reposez-vous entre deux exercices.'),
    (['J’ai un examen bientôt.', 'Comment réviser ?', 'Je veux retenir ma leçon.'], 'Lisez une petite partie, puis essayez de la redire sans regarder, mon ami.'),
    (['Quel temps fait-il chez moi ?', 'Est-ce qu’il pleut dehors ?', 'Tu peux voir la météo ?'], 'Je ne vois point le ciel de chez vous, mon ami. Regardez par la fenêtre ou consultez la météo.'),
    (['Il est quelle heure ?', 'Donne-moi l’heure.', 'Peux-tu lire ma montre ?'], 'Je ne puis lire votre montre, mon ami. Regardez votre horloge.'),
    (['J’ai réussi !', 'J’ai une bonne nouvelle.', 'Je suis content de mon résultat.'], 'Bravo, mon ami ! Je me réjouis de votre réussite.'),
    (['J’ai envie d’écrire un mot à une amie.', 'Aide-moi à dire merci par écrit.', 'Comment écrire une petite lettre ?'], 'Écrivez simplement ce que vous souhaitez lui dire. Un mot sincère vaut mieux qu’un long discours.'),
    (['Je m’ennuie.', 'Donne-moi une activité.', 'Je ne sais pas quoi faire ce dimanche.'], 'Une promenade ou une comédie vous ferait du bien, mon ami.'),
    (['Pourquoi dis-tu « mon ami » ?', 'Pourquoi tu parles si ancien ?', 'Explique ton ton de théâtre.'], 'J’ai appris sur les comédies de Molière. Voilà pourquoi je parle un peu comme au théâtre.'),
    (['Redis la dernière phrase en plus simple.', 'J’ai du mal à suivre.', 'Tu peux être plus clair ?'], 'Bien sûr, mon ami. Quel passage voulez-vous que je reprenne ?'),
    (['Aide-moi avec ça.', 'Je voudrais ton avis là-dessus.', 'Est-ce que tu peux me conseiller ?'], 'Volontiers, mon ami. De quoi s’agit-il ?'),
    (['Quel est mon prénom ?', 'Comment je m’appelle ?', 'Connais-tu mon nom ?'], 'Vous ne m’avez point donné votre prénom, mon ami.'),
]
REPLIES = ['Vous vous appelez Anne.', 'Vous préférez le rouge.', 'Prenez une soupe, mon ami.',
           'Je ne mange point, mon ami. Je suis un modèle de langage.', 'Je vous salue de bon cœur !',
           'Je ne connais point votre horloge.', 'Votre livre est près de la fenêtre.', 'Allons au théâtre !']
FOLLOWUPS = ['tu parles de quoi', 'quoi ?', 'Hein ?', 'Tu réponds à côté.', 'Ce n’est pas ce que je te demandais.',
             'Je ne comprends pas ta réponse.', 'Reviens à ma question.', 'Non, ce n’est pas le sujet.',
             'Je te demande autre chose.', 'Relis ma question.', 'De quoi tu parles ?', 'Tu as perdu le fil.',
             'Tu ne m’as pas répondu.', 'Non, réponds à ce que je t’ai demandé.', 'Ça n’a rien à voir.',
             'Que veux-tu dire ?', 'Je ne saisis pas.', 'Refais ta réponse.', 'Tu t’es trompé de sujet.']


def build(base):
    """Rééquilibre les sujets et produit des reprises sans superviser les erreurs en entrée."""
    rng = random.Random(813)
    # Les anciennes corrections de noms restent présentes, sans dominer le nouveau mélange.
    old = [record for record in base if record['family'] in {'independent', 'advice', 'repeat'}]
    for family in ('name', 'color', 'food', 'mixed'):
        records = [record for record in base if record['family'] == family]
        old.extend(rng.sample(records, min(160 if family != 'mixed' else 360, len(records))))
    result = list(old)
    for questions, answer in INTENTS:
        for question in questions:
            # Les cas positifs seuls et les reprises ciblent la même intention.
            result.append(dict(family='everyday', messages=[['user', question], ['assistant', answer]]))
            for followup in FOLLOWUPS:
                wrong = rng.choice([reply for reply in REPLIES if reply != answer])
                corrected = rng.choice(['Pardonnez-moi. ', 'Reprenons, mon ami. ', '']) + answer
                result.append(dict(family='repair', last_only=True, messages=[
                    ['user', question], ['assistant', wrong], ['user', followup], ['assistant', corrected]]))
    for reply in REPLIES:
        for followup in FOLLOWUPS:
            # Sans sujet identifiable, demander une précision évite d'inventer un fait.
            result.append(dict(family='clarification', last_only=True, messages=[
                ['user', 'J’ai quelque chose à vous demander.'], ['assistant', reply], ['user', followup],
                ['assistant', 'Pardonnez-moi, j’ai perdu le fil. De quoi souhaitez-vous parler ?']]))
    return result


def main():
    """Écrit les exemples et affiche l'empreinte exacte de leur export."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    records = build(json.loads(args.base.read_text(encoding='utf-8')))
    path = args.out / 'train.json'
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps(dict(records=len(records), repair=sum(r.get('last_only', False) for r in records),
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()
