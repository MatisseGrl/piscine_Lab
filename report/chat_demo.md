# Démo conversationnelle : protocole de travail

La demande du 11 novembre autorise le SFT et des dialogues distincts pour la démo du bloc 1. Le bloc 3 reste inchangé. La PR #18 est la référence technique et la PR #20 documente l'autorisation.

## Critères fixés avant la sélection

- Pertinence (0/1 par tour) : réponse compréhensible qui traite effectivement la demande. Une formule polie hors sujet vaut 0.
- Contexte (0/1 sur les tours dépendants) : utilise la bonne information de l'historique, dont les corrections. Un prénom inventé ou une ancienne préférence vaut 0.
- Couleur théâtrale (0/1) : tournure de civilité ou lexique théâtral lisible, sans charabia. Ce critère modeste ne prouve pas une imitation littéraire fidèle de Molière.
- BPB Molière : évaluation complète identique à la référence, UTF-8 et fins de ligne normalisées. Critère secondaire pour choisir la démo.

La sélection repose sur le développement. Le lot final est figé dans `minigpt/chat_bench.py` et ses réponses ne seront lues qu'après sélection. Les discussions utilisent les réponses réellement produites, sans historique oracle. Décodage glouton, maximum 80 nouveaux tokens, arrêt à la double fin de ligne. Les échecs et sorties brutes sont conservés.

## Données

Version 1 : 543 conversations, 1 408 fenêtres supervisées. Dialogues rédigés dans le script, variations combinatoires déterministes. Inspection : questions autonomes, réponses courtes, aucun extrait de scène dépendant d'un contexte absent. Défaut constaté après le pilote : corrections trop souvent vers Camille ou une salade, et ordre des tours insuffisamment varié.

Version 2 : 7 619 conversations. Ordre des demandes varié, corrections sur plusieurs valeurs, demandes de répétition, conseils qui dépendent de l'état exprimé. Les scripts constituent la trace exacte de génération. L'assistant a rédigé les exemples et le code de déclinaison dans cette session ; aucun appel à un générateur externe, aucune distillation de logits. Les réponses de l'application sont exclusivement produites par le mini-GPT entraîné.

Source littéraire : train officiel du kit, édition Chasles 1888 de Molière, Projet Gutenberg. Domaine public d'après le manifeste officiel. Ebooks 40086, 43535, 50173, 57270. Aucun ajout de Wikisource : il contient les pièces réservées à la validation.

Le rappel Molière est une pondération de la loss, pas une proportion du nombre de conversations : `(1 - replay) × loss_chat + replay × loss_moliere`. Batch chat 32, batch littéraire 8, contexte 128. Le corpus littéraire n'est jamais transformé en réponses de chat.

## Contexte et supervision

Format commun : `VOUS.\n...\n\nMOI.\n...\n\n`. Chaque réponse est supervisée avec l'historique précédent. Questions et padding portent la cible -100. Le premier token de réponse et sa terminaison participent à la loss. Les réponses longues sont découpées en tranches de 32 cibles, sans perdre de cible. Le modèle garde ses 128 positions et son tokenizer BPE initial.

À l'inférence, on conserve les 128 derniers tokens. Au SFT, une tranche réserve sa place dans la fenêtre et conserve autant de contexte antérieur que possible. Il existe donc moins de contexte au début d'une tranche qu'au premier token de génération : c'est documenté, et les tests vérifient la borne et les cibles. L'interface affiche le nombre de tokens d'historique sortis du contexte. Il n'existe ni résumé caché ni mémoire externe.

## Premier résultat

Au pas 300 du pilote, « Bonjour, comment ça va ? » obtient « Bonjour ! Je vais bien, merci. Et vous, mon ami ? ». Les relances restent fragiles : « Moi je suis fatigué. » reçoit « Avec plaisir, mon ami ! ». BPB 1,934994. Ce checkpoint n'est pas une conversation libre réussie.

L'audit renforcé normalise mots et apostrophes. Il a repéré « Que dois-je faire ? » dans le préentraînement. Cette question du développement est remplacée avant les runs principaux, et les comparaisons seront recalculées sur le lot corrigé. Le pilote initial est conservé comme diagnostic historique, avec son ancien lot.

## Source extérieure examinée puis écartée

OpenAssistant/oasst1, révision `fdf72ae0827c1cda404aff25b6603abec9e3399b`, licence Apache 2.0, https://huggingface.co/datasets/OpenAssistant/oasst1. Le train contient 2 474 messages étiquetés français. Le filtre de racines autonomes, réponse humaine, rang 0 ou absent, question ≤50 tokens et réponse ≤80 tokens donne 37 candidats.

Inspection complète : plusieurs réponses hors sujet, datées, factuellement douteuses ou sans intérêt pour cette démo (exemples : réponse « Ça tourne ! » à une demande de service Angular, météo affirmée sans contexte temporel). Source **non utilisée dans l'entraînement**. Le nombre de candidats pertinents ne justifie pas ce mélange pour l'expérience actuelle. Les candidats et la révision sont conservés localement sous `runs/oasst-inspection/`.

### Dépendances annotées

Indices de tours à partir de 1. Développement : D1 T3 ; D3 et D4 T2–T4 ; D5 T2 ; D6 T3. Final : F1 T2 ; F2, F3 et F4 T2–T4 ; F5 T2 ; F6 T3–T4. La correction compte si le modèle adopte la nouvelle valeur. La simple répétition d'un mot d'un tour précédent ne suffit pas.

Pour choisir sur le développement : vérifier que la salutation de JB et sa relance sont pertinentes, puis privilégier le nombre de bonnes réponses sur l'ensemble, départager par le suivi de contexte, puis par le BPB. Le score de style demande un marqueur lisible (civilité, lexique ou rythme théâtral), au-delà du seul vouvoiement.

## Reproduction depuis le worktree

```powershell
uv sync --frozen
uv run --frozen python -m scripts.build_chat_data_v2 --out runs/chat-data-v2
uv run --frozen python -m scripts.audit_chat_data --data runs/chat-data-v2/train.json --tokenizer ../../data/processed/bpe_moliere_1024.json --corpus ../../kit/Piscine/corpus --out runs/chat-data-v2/audit.json
uv run --frozen python -m minigpt.chat_sft --checkpoint ../moliere-continuation-20261111/cosine/best.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --data runs/chat-data-v2/train.json --corpus ../../kit/Piscine/corpus --out runs/chat-main-v2-r30 --steps 4000 --every 500 --lr 0.0001 --replay 0.3
```

Utiliser des dossiers de sortie neufs pour une répétition. Les 2 833 réponses dont le préfixe dépasse déjà 128 tokens représentent 11,5 % des réponses de v2. Les entrées sont 1 564 dialogues autonomes et 6 055 dialogues de deux à cinq tours. Exemples inspectés : une demande de reposer la question, une conversation de correction de prénom, puis une demande de conseil conditionnée par la fatigue. Les dialogues mélangés de manière aléatoire sont un exercice de changement de sujet, pas un échantillon de conversations naturelles.

### Variantes supplémentaires

- Rappel à 60 % : même v2, mêmes tirages et même taux `1e-4`, départ cosinus ; 1 500 pas. La proportion concerne la pondération de la loss, pas le nombre de tokens.
- Mélange de poids : interpolation à 75 % et 90 % du SFT du pas 1 000, le reste provenant de son parent cosinus. Pas de gradient. BPB respectifs 1,829656 et 1,844335, mais perte de pertinence sur la discussion de JB. Sorties sous `runs/mix-1000/`.
- v3 : les dialogues de v2 plus 128 scènes d'humour et 520 scènes de conseil, 8 267 conversations et 26 958 réponses. La réponse à une relance dépend du cas précédent. Audit : aucune question réservée ni recouvrement de 13 mots avec la validation Molière. Nouveau départ depuis le pas 1 000 à 30 %, nouvel AdamW, taux `5e-5`, rappel à 40 %, 600 pas.

```powershell
uv run --frozen python -m scripts.build_chat_data_v3 --base runs/chat-data-v2/train.json --out runs/chat-data-v3
uv run --frozen python -m scripts.audit_chat_data --data runs/chat-data-v3/train.json --tokenizer ../../data/processed/bpe_moliere_1024.json --corpus ../../kit/Piscine/corpus --out runs/chat-data-v3/audit.json
uv run --frozen python -m minigpt.chat_sft --checkpoint ../moliere-continuation-20261111/cosine/best.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --data runs/chat-data-v2/train.json --corpus ../../kit/Piscine/corpus --out runs/chat-main-v2-r60 --steps 1500 --every 500 --lr 0.0001 --replay 0.6
uv run --frozen python -m minigpt.chat_sft --checkpoint runs/chat-main-v2-r30/step-1000.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --data runs/chat-data-v3/train.json --corpus ../../kit/Piscine/corpus --out runs/chat-repair-v3 --steps 600 --every 200 --lr 0.00005 --replay 0.4
uv run --frozen python -m minigpt.interpolate_chat --base ../moliere-continuation-20261111/cosine/best.pt --chat runs/chat-main-v2-r30/step-1000.pt --tokenizer ../../data/processed/bpe_moliere_1024.json --validation ../../kit/Piscine/corpus/moliere_val.txt --out runs/mix-1000
```

### Contrôle de l'historique et de la troncature

Diagnostic séparé du test final, checkpoint v2 au pas 1 000, décodage glouton : même question « Peux-tu me redire mon prénom ? », après « Mon prénom est Hugo. » puis après « Mon prénom est Lucie. » : les deux réponses changent et reprennent le bon nom. Avec « Éloïse », absent des exemples, le modèle répond hors sujet. Sans historique, il demande ce qu'il faut répéter. Le diagnostic est conservé dans `runs/probe-step-1000.json`.

Une requête longue finissant par la salutation de JB a laissé 795 tokens hors contexte. La génération s'est terminée normalement, mais a produit « qui alle rend, mon ami. ». Cela vérifie le fonctionnement technique de la fenêtre et montre que la présence de la question dans les derniers tokens ne suffit pas à garantir la pertinence. Dans Chrome, l'indicateur de génération et la remise à zéro ont fonctionné sur trois tours pertinents du scénario JB avec le pas 1 000.

### Exemples d'entraînement relus

- v2, mémoire et correction : « Je suis Lucie. » → « Enchanté, Lucie ! » ; « Quel prénom ai-je donné ? » → « Vous vous appelez Lucie. » ; « Non, appelle-moi Matisse. » → « Vous vous appelez Matisse. » ; rappel final de Matisse. La valeur à restituer change avec le contexte.
- v3, conseil : « Je viens de finir une longue journée. » → « Vous voilà bien las, mon ami. Prenez un peu de repos. » ; « Que ferais-tu à ma place ? » → « Couchez-vous tôt et laissez demain attendre son tour. » La relance n'énonce pas la fatigue une seconde fois.

## Résultat et choix de la démo

Le scénario JB réussit **3/3 tours** avec `runs/chat-main-v2-r30/step-1000.pt`. Le développement donne **16/20 réponses pertinentes** et **7/9 tours de contexte réussis**. Le modèle a été choisi avant de lancer le lot final. Empreinte SHA-256 du checkpoint retenu : `623e1677e8ceec169763204e864458fc1e6088fd5e79d9785e09ac4b517a0506`.

| Checkpoint | Pertinence /24 | Contexte /13 | Couleur théâtrale /24 | BPB Molière |
| --- | ---: | ---: | ---: | ---: |
| Continuation cosinus | 0 | 0 | 4 | **1,770614** |
| Ancien pilote, paires authentiques | 0 | 0 | 0 | 1,889077 |
| SFT v2, pas 1 000, rappel 30 % | **13** | **7** | **12** | 1,854847 |

Le lot final comprend six discussions inédites de quatre tours. Les scores sont des annotations qualitatives des sorties brutes, pas une mesure à l'aveugle par un jury. Tous les candidats du tableau ont reçu les mêmes rôles `VOUS/MOI`. Les deux références ont aussi été rejouées sur le développement avec `SGANARELLE/DON JUAN` : elles restent peu pertinentes. Les BPB du tableau sont recalculés, avec validation et tokenizer identiques. Le BPB de référence initial était de 1,823678.

Les répliques et leurs notes sont dans [les résultats bruts](chat_demo_results.json). Par exemple, la correction de Clara en Anne est mémorisée. En revanche, « Je change d'avis, je veux du pain » déclenche un prénom, et le rappel qui suit cite encore le fromage. Le modèle répond aussi à une salutation reformulée par « Je ne mange point, mon ami ». Les formules de civilité sont lisibles, mais répétitives. La saisie est libre ; la pertinence ne l'est pas sur tous les sujets.

Le rappel à 60 % donne 1,830091 BPB à 1 500 pas et perd la pertinence au dernier tour de JB. La v3 termine à 1,844633, sans gain sur cette discussion. Les interpolations descendent à 1,805440 mais échouent aussi sur ce scénario. Le run principal se termine à 1,819883 BPB au pas 4 000 ; il répète une salutation au moment de donner un conseil. Sa loss moyenne de réponse passe de 0,255338 au pas 500 à 0,023537 au pas 4 000, sans gain correspondant sur la démo. Le meilleur BPB Molière reste celui du cosinus.

Les sorties de tous les paliers, les manifestes, les loss et les poids intermédiaires sont conservés dans les dossiers `runs/` du worktree. Aucun poids n'est versionné.

## Lancement vérifié

```powershell
Set-Location 'C:\Users\mgarl\Documents\piscine_Lab\runs\worktree-moliere-demo'
uv run --frozen python -m minigpt.web_chat --checkpoint runs/chat-main-v2-r30/step-1000.pt --tokenizer ../../data/processed/bpe_moliere_1024.json
```

Ouvrir [http://localhost:8765](http://localhost:8765). Après redémarrage depuis un terminal neuf, Chrome a affiché les trois réponses attendues du scénario de démo, dont « Prenez quelque repos, je vous en prie. » au troisième tour. **135 tests passent** avec la validation Molière disponible dans le worktree. Les sources et leurs licences figurent aussi dans le [PPTX](Feed-the-Beast-demo.pptx).
