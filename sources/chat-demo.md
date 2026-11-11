# Données de la démo conversationnelle

## Corpus Molière du kit

- Nom : Œuvres complètes de J.-B. Poquelin Molière, édition Philarète Chasles, 1888, Projet Gutenberg.
- Liens : https://www.gutenberg.org/ebooks/40086, https://www.gutenberg.org/ebooks/43535, https://www.gutenberg.org/ebooks/50173, https://www.gutenberg.org/ebooks/57270.
- Statut : domaine public selon le manifeste du kit. Les pages Gutenberg affichent « Public domain in the USA ». Le kit retire les notices et notes, puis sépare les pièces.
- Usage : poids de départ du bloc 1 et rappel de langue pendant le SFT, sur `moliere_train.txt` uniquement.
- Exclusions : Le Misanthrope, L'Avare et Le Sicilien, réservés à la validation du kit. Le corpus Wikisource collecté séparément n'est pas utilisé.
- Référence exacte : `kit/Piscine/corpus/moliere_manifest.json`, empreintes du train et de la validation dans le checkpoint de référence.

## Dialogues originaux du projet

- Nom : dialogues conversationnels Molière, versions 1 et 2.
- Source reproductible : `scripts/build_chat_data.py` et `scripts/build_chat_data_v2.py` dans ce dépôt.
- Production : exemples questions/réponses rédigés par l'assistant dans la session du 11 novembre 2026, puis permutations et déclinaisons déterministes par Python. Aucun dataset tiers de dialogue, appel API de génération, modèle externe local ou distillation de logits.
- Instruction de génération : répondre d'abord à la demande, en français clair avec une civilité de théâtre, construire des relances et corrections, varier les valeurs corrigées, garder des réponses courtes adaptées à 128 tokens.
- Licence : les gabarits et leurs textes, versionnés dans les scripts, relèvent de la licence MIT du dépôt. L'export local n'a pas de licence tierce de dataset. Les phrases ne sont pas présentées comme des citations authentiques de Molière.
- Version 2 : 7 619 conversations, 24 706 réponses. 1 564 conversations à un tour ; 881 à deux ; 740 à trois ; 3 010 à quatre ; 1 424 à cinq.
- Mélange en conversations : 1 564 demandes autonomes, 2 500 suites de demandes, 1 398 échanges sur les noms, 1 397 sur les couleurs, 315 sur les repas, 180 sur les conseils et 265 sur la répétition.
- Empreinte v2 : `13a7d2cf042b0b1b352cb55f849ecfe170b93477ffeab3f38debbef92257684a`.
- Risques : diversité limitée, stéréotypie du style, mémorisation de gabarits. L'évaluation hors entraînement et les sorties brutes rendent ces limites visibles.
- Audit : aucune question de développement ou de test final après normalisation en mots, aucun recouvrement de 13 mots avec la validation Molière. Ce contrôle ne prouve pas l'absence de tout recouvrement sémantique.

Ces données et entraînements servent uniquement à la démo du bloc 1, conformément à l'autorisation spécifique de JB transmise par Matisse. Ils ne servent pas à la compétition du bloc 3.


La version 3 ajoute 648 conversations (128 d'humour et 520 de conseil). Même origine et même licence des gabarits. Le script `scripts/build_chat_data_v3.py` prend l'export v2 en entrée. SHA-256 v3 : `1586f1747a8427b1b76f208b1ad463b7176921ab993b127aeec64419e603b87b`. L'audit v3 confirme les mêmes exclusions.
