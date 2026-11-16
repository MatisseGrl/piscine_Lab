# Démo Molière — budget de pré-entraînement

Expérience du 16 novembre 2026, hors classement. La référence [Chat v3](chat_demo.md#chat-v3--pré-entraînement-français-puis-molière-puis-dialogues-14-novembre) a été recalculée sur les trois poids d'origine.

| Poids de référence | BPB Molière recalculé | SHA-256 du checkpoint |
| --- | ---: | --- |
| Pré-entraînement français | 2,011198 | `d6e3588edfa3f965fab2998753cec4f2c42d6e74406f1791c57b2175ad1466ed` |
| Après Molière, pas 600 | 1,411092 | `839e7e4ceab4ad13b01615b263617b78b974b6d60c72192083631f6360e1721a` |
| Chat v5, pas 1 500 | 1,429137 | `e309d3d41963ebb725e7c8210cf5df6a89032ded38c4ac000eb288add463c0c9` |

Les 24 sorties historiques du chat sont identiques au fichier de référence, noté 13/24 en pertinence et 8/13 en suivi du contexte. Le pilote T4 de deux pas à chaque étape a parcouru la chaîne complète. Son BPB passe de 3,947256 après le pré-entraînement à 3,897567 après Molière, puis à 3,851989 après le chat. Le pilote vérifie le chargement et le calcul.

Le pilote de débit de 60 pas a pris 181 s sur T4 avec le calcul explicite. Une tentative L4 n'a fourni aucun GPU. Le run long avec les noyaux accélérés a atteint le pas 60 en 16 s sur T4. Le premier lancement s'est arrêté avant l'entraînement, car Kaggle décompresse le fichier `train.bin.gz` au montage. La relance vérifie le flux binaire monté.

## Protocole

- Deux initialisations neuves à graine 1337, mini-GPT 12 805 120 paramètres, 6 couches, 5 têtes, largeur 320, contexte 512. Tokenizer de la démo à 8 192 entrées, SHA-256 `b2554a8221a55c19b4008f5b605b1b6e84b6a7f84058507c15aba34eca3b2379`.
- Le court budget lit les 3 052 premiers lots du long, soit 100 007 936 cibles sur 299 991 040. Chaque lot contient 64 × 512 cibles, micro-lots de 16. Même AdamW, montée de 150 pas et cosinus de 0,002 à 0,0002 recalés sur chaque horizon. Les calendriers divergent après la montée. Les deux essais utilisent les noyaux accélérés d'attention et de normalisation uniquement pendant le pré-entraînement. Le test vérifie les logits et les gradients en float64. Le pré-entraînement historique utilisait un autre mélange et le calcul PyTorch explicite.
- Sources prévues en tokens, avant arrondi par blocs de 8 192. Wikipédia 66 %, Gutenberg 23 %, Common Crawl 6 %, Assemblée nationale 3,5 %, Wikinews 1,5 %. Préfixes tirés dans les archives existantes, déduplication exacte des documents normalisés entre sources puis mélange des blocs sans remise. Les textes sont contrôlés au niveau document contre les séquences de 13 mots du train et de la validation Molière. La validation et les questions inédites sont également contrôlées contre les dialogues v5. Des reformulations ou quasi-doublons peuvent subsister.
- Même adaptation Molière pour les deux budgets. 1 500 pas, batch 16 × 512, cosinus de 1e-4 vers 1e-5, graine 1337. Sélection par la loss sur les 5 % finaux du train officiel aux paliers de 200 pas et au dernier pas. Pendant le SFT, le rappel reprend tout le train officiel comme dans la démo précédente.
- Même SFT sur les dialogues v5, 1 500 pas, batch 32 et rappel Molière par batch de 8, taux 1e-4 et pondération de rappel 0,3. Les candidats sont notés à 500, 1 000 et 1 500 pas sur DEV (20 tours, dont 9 de contexte). Sélection par pertinence, puis contexte, puis palier le plus précoce en cas d'égalité.
- Validation BPB Molière séparée, 260 488 octets UTF-8 après normalisation des fins de ligne. SHA-256 `e5dde8f5782f15943443cddb056bf9fd19efd67822b9e36a875e2c2970ede12c`. Fenêtres et comptage identiques à `evaluate_bpb`.
- Comparaison finale entre le v5 historique et les candidats retenus. Six conversations inédites de quatre tours, dont 13 tours de contexte. Décodage glouton limité à 80 tokens, arrêt à la première double fin de ligne, historique alimenté par les réponses générées. Pertinence = réponse intelligible et adaptée au tour. Contexte = reprise de la bonne information, y compris la correction et le rappel de sa propre réponse. Les deux notes sont binaires. Le fichier de test reste local pendant la sélection.

## Corpus construit

| Source | Documents utilisés sur 300 M | Cibles 100 M | Cibles 300 M |
| --- | ---: | ---: | ---: |
| Wikipédia | 205 029 | 65 740 800 | 197 992 448 |
| Gutenberg | 572 | 23 330 816 | 69 001 216 |
| Common Crawl | 8 262 | 5 914 624 | 17 997 824 |
| Assemblée nationale | 5 961 | 3 620 864 | 10 502 144 |
| Wikinews | 16 311 | 1 400 832 | 4 497 408 |
| **Total** | **236 135** | **100 007 936** | **299 991 040** |

Chaque bloc est visité une fois par entraînement. Le BPE coupe les textes longs par morceaux d'au plus 8 192 caractères. Sept documents sont exclus au contrôle Molière (cinq Gutenberg, deux Wikipédia). Aucune question du test inédit n'a été trouvée dans les documents parcourus, le train Molière ou les dialogues v5. Les cinq empreintes d'archives du manifeste correspondent aux statistiques des archives récupérées.

Fiches des archives [Wikipédia](../sources/wikipedia-fr.md), [Gutenberg](../sources/gutenberg-fr.md), [Common Crawl](../sources/common-crawl.md), [Assemblée nationale](../sources/assemblee-nationale-16.md) et [Wikinews](../sources/wikinews-fr.md).

| Entrée | SHA-256 |
| --- | --- |
| Flux 100 M, préfixe avec sa cible frontière | `9a8fcca8e8c82961fe0e1b4c39c61cc631c79950277e998636145057695fce17` |
| Flux 300 M, dernière cible incluse | `e654437a5fef65ae557452c5845859e66a583043864a4dafb3725fd76047c13d` |
| Gzip du flux complet | `b7ec62de467e202f77d70724dc2ac30befe0331ced9c2cd45eea92482f7cd8f6` |
| Dialogues v5 | `376c76a46a02b03ab0b4bd7734bcef6deedfa75cdabfb15c63879c5b2c281eb4` |
| Test de conversations inédites | `e5f13fbb99da77539c3dd215e06c461d852234c0fb645b7bed1c7d3216fcd675` |

## Mesures des candidats

| Pré-entraînement | Matériel et PyTorch | BPB avant Molière | SHA-256 des poids |
| --- | --- | ---: | --- |
| 100 M, graine 1337 | Colab T4, 2.14.1+cu130 | 1,715294 | `4549e6303b48b4b415492e2801630877a0fd93740f1f48be6eadcf648e503c46` |
| 300 M, graine 1337 | Kaggle T4, 2.11.0+cu130 | — | — |

Les deux environnements utilisent des versions différentes de PyTorch. L'architecture, le type de GPU, la recette de pré-entraînement et le protocole d'évaluation sont communs.

## Reproduction

Depuis la racine du checkout, préparer les archives et les fichiers privés de la démo. Les chemins PowerShell ci-dessous correspondent à leur emplacement sur le poste.

```powershell
$p = 'C:/Users/mgarl/Documents/piscine_Lab'
$d = "$p/runs/kaggle-chat-ft-data"
$a = 'C:/Users/mgarl/Documents/Piscine-recuperation-20261115/archives-auditees'
uv run python -m scripts.build_chat_budget --archives "$a" --corpus "$d" --tokenizer "$d/tokenizer.json" --chat "$d/chat_v5_train.json" --exam runs/chat-budget/final.json --out runs/chat-budget/corpus
```

La commande écrit `kaggle/train.bin.gz` et `kaggle/manifest.json`. Le notebook vérifie les empreintes avant l'entraînement. Placer les deux fichiers et `dataset-metadata.json` dans un dossier, s'y placer et lancer `kaggle datasets create -p .` en mode privé. Le dataset créé est `matissegarlot/piscine-chat-budget-fr`. Le deuxième dataset privé, `matissegarlot/piscine-chat-ft`, contient le corpus du kit, le tokenizer et les dialogues v5.

```powershell
$source = '3ff89a310c63cdadc0c1d894c5dec6cd654ba1d3'
uv run python -m scripts.launch_chat_budget_kaggle pretrain 300m --commit "$source"
# Après la mise à disposition du checkpoint par Kaggle.
uv run python -m scripts.launch_chat_budget_kaggle adapt 300m --commit "$source"
```

Kaggle a refusé le lancement court pendant l'attente du pilote de débit. Le court budget utilise une session T4 Colab privée. Le préfixe est envoyé par morceaux et vérifié intégralement avant le pré-entraînement.

```powershell
colab new --gpu T4 --session piscine-chat-budget-100m
$source = '9f6d46d54d6af4f68a6ba37091b7a352c23b5a92'
uv run python -m scripts.launch_chat_budget_colab --archive runs/chat-budget/corpus/kaggle/train.bin.gz --data "$d" --commit "$source"
```

Pour réévaluer localement après sélection, donner tous les checkpoints retenus dans la même invocation.

```powershell
uv run python -m minigpt.evaluate_chat --checkpoints <checkpoints> --tokenizer "$d/tokenizer.json" --validation "$d/moliere_val.txt" --bench runs/chat-budget/final.json --split final --out runs/chat-budget/comparaison-finale
```
