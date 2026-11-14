# Scripts utilitaires

`fetch_moliere.py` récupère des textes et notices de Wikisource. `build_chat_data.py`, `build_chat_data_v2.py` et `build_chat_data_v3.py` construisent les dialogues originaux de la démo ; `audit_chat_data.py` contrôle les sources, les tours et les exclusions avant entraînement.

Les commandes, empreintes et limites du corpus de démo sont dans le [rapport](../report/chat_demo.md). Les exports et poids restent dans `runs/`.

`build_chat_paraphrases.py` produit les variantes du corpus de réparation. `build_moliere_extra.py` contrôle les cinq pièces supplémentaires pour les essais exploratoires du bloc 1.
