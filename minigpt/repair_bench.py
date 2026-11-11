"""Préfixes gelés pour mesurer si le modèle répare une réplique hors sujet."""
from minigpt.conversation import reply

# Chaque cas fournit la mauvaise réponse, puis la relance et le but de l'annotation.
REPAIR_DEV = [
    ('Bonjour à vous, la forme ?', 'Vous souhaitez du pain.', 'Quel rapport avec ma question ?', 'saluer et dire comment il va'),
    ('Que puis-je lire avant de dormir ?', 'Je vous appelle Louise.', 'Pourquoi me parles-tu de mon nom ?', 'suggérer une lecture'),
    ('J’ai soif après ma course.', 'Je suis votre valet de théâtre.', 'Tu réponds à côté, là.', 'suggérer une boisson'),
    ('Je suis las ce soir.', 'Quelle belle comédie !', 'Reviens plutôt à ce que je viens de dire.', 'réagir à la fatigue'),
    ('Je ne trouve plus mes clés.', 'Les roses sont fort belles.', 'Cesse de changer de sujet.', 'aider à chercher les clés'),
    ('Parle-moi de ton travail.', 'Je vais fort bien.', 'En termes simples, que fais-tu ?', 'expliquer sa fonction'),
    ('Quel jour tombe mon rendez-vous ?', 'La bourse est bien pleine.', 'D’où sors-tu cela ?', 'demander la date sans en inventer'),
    ('Je vais me coucher, bonne nuit !', 'Vous préférez le vert.', 'Tu as compris ce que je t’ai dit ?', 'souhaiter bonne nuit'),
]
REPAIR_FINAL = [
    ('Salutations, comment vous portez-vous ce soir ?', 'Je compose une soupe, monsieur.', 'Attends, tu m’expliques le lien ?', 'saluer et dire comment il va'),
    ('Propose-moi une promenade tranquille.', 'Vous vous nommez Paul.', 'Laissons mon prénom, réponds à ma demande.', 'suggérer une promenade'),
    ('On dîne dans dix minutes et rien n’est prêt.', 'Je puis réciter une comédie.', 'Ce n’était pas le sens de ma remarque.', 'proposer un repas rapide'),
    ('Je n’arrive plus à rester éveillé.', 'Vous préférez le rose.', 'Ta réponse n’a aucun rapport.', 'réagir à la fatigue'),
    ('Peux-tu me faire rire un instant ?', 'Je ne connais pas l’heure.', 'Je n’ai pas posé de question sur l’heure.', 'raconter une plaisanterie'),
    ('As-tu vu où j’ai laissé mon cahier ?', 'Vous voulez des pommes.', 'Qu’essayais-tu de me dire au juste ?', 'expliquer qu’il ne voit pas le cahier ou aider à le chercher'),
    ('Dites-moi à qui j’ai affaire.', 'Le soleil est fort chaud.', 'Je te demandais autre chose, non ?', 'se présenter'),
    ('Il se fait tard, on se reparle demain.', 'Qu’est-ce qui vous fâche ?', 'Je ne suis pas fâché, relis ma dernière phrase.', 'prendre congé sans supposer de colère'),
]


def evaluate_repairs(model, tokenizer, cases):
    """Joue les relances à contexte imposé, à distinguer d'une discussion libre."""
    return [dict(question=question, previous_reply=wrong, followup=followup, expected=expected,
                 **reply(model, tokenizer, [('user', question), ('assistant', wrong), ('user', followup)]))
            for question, wrong, followup, expected in cases]
