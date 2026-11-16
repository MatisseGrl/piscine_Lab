# Démo Molière — budget de pré-entraînement

Expérience du 16 novembre 2026, hors classement. La référence [Chat v3](chat_demo.md#chat-v3--pré-entraînement-français-puis-molière-puis-dialogues-14-novembre) a été recalculée sur les trois poids d'origine.

| Poids de référence | BPB Molière recalculé | SHA-256 du checkpoint |
| --- | ---: | --- |
| Pré-entraînement français | 2,011198 | `d6e3588edfa3f965fab2998753cec4f2c42d6e74406f1791c57b2175ad1466ed` |
| Après Molière, pas 600 | 1,411092 | `839e7e4ceab4ad13b01615b263617b78b974b6d60c72192083631f6360e1721a` |
| Chat v5, pas 1 500 | 1,429137 | `e309d3d41963ebb725e7c8210cf5df6a89032ded38c4ac000eb288add463c0c9` |

Les 24 sorties historiques du chat sont identiques au fichier de référence, noté 13/24 en pertinence et 8/13 en suivi du contexte. Le pilote T4 de deux pas à chaque étape a parcouru la chaîne complète. Son BPB passe de 3,947256 après le pré-entraînement à 3,897567 après Molière, puis à 3,851989 après le chat. Le pilote vérifie le chargement et le calcul.

## Protocole

- Deux initialisations neuves à graine 1337, mini-GPT 12 805 120 paramètres, 6 couches, 5 têtes, largeur 320, contexte 512. Tokenizer de la démo à 8 192 entrées, SHA-256 `b2554a8221a55c19b4008f5b605b1b6e84b6a7f84058507c15aba34eca3b2379`.
- Le court budget lit les 3 052 premiers lots du long, soit 100 007 936 cibles sur 299 991 040. Chaque lot contient 64 × 512 cibles, micro-lots de 16. Même AdamW, montée de 150 pas et cosinus de 0,002 à 0,0002 recalés sur chaque horizon. Les calendriers divergent après la montée. Le pré-entraînement historique utilisait un autre mélange français.
- Sources prévues en tokens, avant arrondi par blocs de 8 192. Wikipédia 66 %, Gutenberg 23 %, Common Crawl 6 %, Assemblée nationale 3,5 %, Wikinews 1,5 %. Préfixes tirés dans les archives existantes, déduplication exacte des documents normalisés entre sources puis mélange des blocs sans remise. Les textes sont contrôlés au niveau document contre les séquences de 13 mots du train et de la validation Molière. La validation et les questions inédites sont également contrôlées contre les dialogues v5. Des reformulations ou quasi-doublons peuvent subsister.
- Même adaptation Molière pour les deux budgets. 1 500 pas, batch 16 × 512, cosinus de 1e-4 vers 1e-5, graine 1337. Sélection par la loss sur les 5 % finaux du train officiel aux paliers de 200 pas et au dernier pas. Pendant le SFT, le rappel reprend tout le train officiel comme dans la démo précédente.
- Même SFT sur les dialogues v5, 1 500 pas, batch 32 et rappel Molière par batch de 8, taux 1e-4 et pondération de rappel 0,3. Les candidats sont notés à 500, 1 000 et 1 500 pas sur DEV (20 tours, dont 9 de contexte). Sélection par pertinence, puis contexte, puis palier le plus précoce en cas d'égalité.
- Validation BPB Molière séparée, 260 488 octets UTF-8 après normalisation des fins de ligne. SHA-256 `c838b1836498ff0dfdc621cb0b45f5349c889ff5e1b81a1409197e5d2b420377`. Fenêtres et comptage identiques à `evaluate_bpb`.
- Comparaison finale entre le v5 historique et les candidats retenus. Six conversations inédites de quatre tours, dont 13 tours de contexte. Décodage glouton limité à 80 tokens, arrêt à la première double fin de ligne, historique alimenté par les réponses générées. Pertinence = réponse intelligible et adaptée au tour. Contexte = reprise de la bonne information, y compris la correction et le rappel de sa propre réponse. Les deux notes sont binaires. Le fichier de test reste local pendant la sélection.

## Reproduction

Depuis la racine du checkout, préparer les archives et les fichiers privés de la démo. Les chemins PowerShell ci-dessous correspondent à leur emplacement sur le poste.

```powershell
$p = 'C:/Users/mgarl/Documents/piscine_Lab'
$d = "$p/runs/kaggle-chat-ft-data"
$a = 'C:/Users/mgarl/Documents/Piscine-recuperation-20261115/archives-auditees'
uv run python -m scripts.build_chat_budget --archives "$a" --corpus "$d" --tokenizer "$d/tokenizer.json" --chat "$d/chat_v5_train.json" --exam runs/chat-budget/final.json --out runs/chat-budget/corpus
```

La commande écrit `kaggle/train.bin.gz` et `kaggle/manifest.json`. Le notebook vérifie les empreintes avant de lire le préfixe. Publier ces deux fichiers dans le dataset Kaggle **privé** `matissegarlot/piscine-chat-budget-fr` avec `kaggle datasets create -p <dossier>` et son fichier `dataset-metadata.json`. Le deuxième dataset privé, `matissegarlot/piscine-chat-ft`, contient le corpus du kit, le tokenizer et les dialogues v5. Les poids sortent dans les notebooks privés.

```powershell
$source = git rev-parse HEAD
uv run python -m scripts.launch_chat_budget_kaggle pretrain 100m --commit "$source"
uv run python -m scripts.launch_chat_budget_kaggle pretrain 300m --commit "$source"
# Après la publication des checkpoints par Kaggle.
uv run python -m scripts.launch_chat_budget_kaggle adapt 100m --commit "$source"
uv run python -m scripts.launch_chat_budget_kaggle adapt 300m --commit "$source"
```

Pour réévaluer localement après sélection, donner tous les checkpoints retenus dans la même invocation.

```powershell
uv run python -m minigpt.evaluate_chat --checkpoints <checkpoints> --tokenizer "$d/tokenizer.json" --validation "$d/moliere_val.txt" --bench runs/chat-budget/final.json --split final --out runs/chat-budget/comparaison-finale
```
