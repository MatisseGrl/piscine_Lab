# Démo locale

`index.html` est la page « Feed the Beast — ECE IA Lab ». `minigpt.web_chat` la sert sur `127.0.0.1:8765` et exécute le vrai mini-GPT sur CPU. Aucun service externe de génération, aucune table de réponses.

Saisie libre, historique de session, indicateur de génération, nouvelle discussion. Le modèle reçoit les derniers 128 tokens et la page signale la perte de contexte. Les réponses sont insérées comme texte, jamais comme HTML.

Lancement : voir la commande vérifiée et le checkpoint retenu dans `report/chat_demo.md` à la fin des expériences. Le terminal historique `minigpt/chat.py` reste intact.
