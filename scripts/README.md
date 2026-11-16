# Scripts utilitaires

`fetch_moliere.py` récupère des textes et notices de Wikisource. `build_chat_data.py`, `build_chat_data_v2.py` et `build_chat_data_v3.py` construisent les dialogues originaux de la démo ; `audit_chat_data.py` contrôle les sources, les tours et les exclusions avant entraînement.

Les commandes, empreintes et limites du corpus de démo sont dans le [rapport](../report/chat_demo.md). Les exports et poids restent dans `runs/`.

`build_chat_paraphrases.py` produit les variantes du corpus de réparation. `build_moliere_extra.py` contrôle les cinq pièces supplémentaires pour les essais exploratoires du bloc 1.

`build_chat_budget.py` prépare deux préfixes de français pour comparer le budget de pré-entraînement de la démo. `run_chat_budget.py` et `launch_chat_budget_kaggle.py` exécutent les étapes GPU. Le [rapport dédié](../report/chat_pretrain_budget.md) donne le protocole et les commandes.

`audit_dialogue_stress.py` compare la répétition et la robustesse des checkpoints du chat. Le protocole est décrit dans le [rapport d’audit](../report/audit_20261115.md).

`verify_mentor_bundle.py` est livré sous le nom `verifier.py` dans le paquet de
compétition. Il vérifie les octets des fichiers listés dans `SHA256SUMS`.
