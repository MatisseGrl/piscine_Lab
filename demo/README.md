# Démo locale

`index.html` est la page « Feed the Beast — ECE IA Lab ». `minigpt.web_chat` la sert sur `127.0.0.1:8765` et exécute le vrai mini-GPT sur CPU. Aucun service externe de génération, aucune table de réponses.

Saisie libre, historique de session, indicateur de génération, nouvelle discussion. Le modèle reçoit les derniers tokens de sa fenêtre (128 pour l'ancienne démo, 512 pour le chat v3, affiché sur la page) et la page signale la perte de contexte. Les réponses sont insérées comme texte, jamais comme HTML.

Lancement en une commande : `powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1` (chat v3 par défaut ; options `-Checkpoint`, `-Tokenizer`, `-Port`). Le lanceur vérifie les fichiers et le port, puis ouvre le navigateur. Les résultats sont dans `report/chat_demo.md`. Le terminal historique `minigpt/chat.py` reste intact.
