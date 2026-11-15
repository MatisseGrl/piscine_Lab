# Rendu de compétition — M4REFLOWBPE

Matisse Garlot · Piscine Intelligence Lab ECE · 15 novembre 2026

Le run officiel donne **1,287432 BPB** sur les **230 textes publics** du kit.
Le modèle a vu **100 007 936 tokens** avec la graine **1337** et des micro-lots de
8 sur une Tesla T4. Le checkpoint fourni est exporté en float16 par `ftb.submit`.
Sa réévaluation sur CPU donne **1,287437 BPB**. Le contrôle à graine 1338 donne
1,284858 BPB.

## Contenu du paquet

| Dossier ou fichier | Contenu |
|---|---|
| `dataset/` | Flux d'entraînement `train.bin` en uint16 little-endian, tokenizer BPE de 8 192 entrées et `data_meta.json` |
| `soumission/` | Checkpoint officiel, tokenizer, métriques du run, journal, empreintes et cinq générations |
| `kit/` | Kit officiel à la révision `3709c85ddaabfcd688d6eea80a5c5ed90605b549`, avec l'évaluateur et la validation publique |
| `preuves/` | Évaluations, statistiques de traitement, manifeste du flux, fiches sources et journal des essais |
| `SHA256SUMS`, `verifier.py` | Contrôle d'intégrité du paquet |

Le SHA-256 du flux est
`f1730391ce68f2cd5425618fa0168c5225af8a177cb565533e9804c57a356627`.
Le SHA-256 du tokenizer est
`f7599e6ac535f9a6cbb36d2caa003b0fbb675428f2259ccf4ee03fe14b2af4bd`.

## Vérifier et relancer

Décompresser le ZIP et ouvrir un terminal à sa racine. Un environnement Python 3.12
avec PyTorch et les dépendances de `requirements-run.txt` suffit pour l'évaluation.
Pour le réentraînement GPU, utiliser un PyTorch avec CUDA et au moins 1 Go d'espace
libre après extraction pour les checkpoints et les sorties.

```bash
python verifier.py
cd kit
python -m ftb.evaluate --ckpt ../soumission/ckpt.pt --tokenizer ../soumission/tokenizer.json --data data/validation.jsonl --device cpu --out ../evaluation-checkpoint.json
python -m ftb.train --data ../dataset --tokenizer ../dataset/tokenizer.json --out ../reentrainement --device cuda:0 --micro-batch 8
python -m ftb.evaluate --ckpt ../reentrainement/ckpt.pt --tokenizer ../dataset/tokenizer.json --data data/validation.jsonl --device cuda:0 --out ../evaluation-reentrainement.json
```

La première évaluation relit les poids fournis. La commande d'entraînement initialise
un nouveau modèle avec le kit officiel et vérifie le hash du flux avant de démarrer.
Le run de référence a pris environ 15 minutes sur T4. Le score peut légèrement varier
avec le GPU et les versions de CUDA ou de PyTorch. Pour l'évaluation cachée, utiliser
le chemin du jeu de l'organisateur à la place de `data/validation.jsonl`.

## Régénérer le flux à partir des sources

À lancer à la racine du checkout de la [PR de compétition](https://github.com/MatisseGrl/piscine_Lab/pull/50).
La collecte intégrale nécessite de l'ordre de 100 Go d'espace libre avant les sorties
intermédiaires. Les catalogues et services tiers doivent encore proposer les données
utilisées lors de la collecte.

```bash
uv sync --locked
uv run python -m pipeline.regenerate --mix M4REFLOWBPE
```

Le flux est écrit sous `data/processed/final/M4REFLOWBPE/M4REFLOWBPE/`.
La commande relit les octets du flux et du tokenizer, puis vérifie le SHA-256 du flux
contre celui du run de référence. La phase finale a été reconstruite à partir des
archives de sources déjà auditées. La collecte intégrale depuis un dossier vide reste
à vérifier. Le ZIP contient déjà le flux nécessaire au réentraînement.

## Données

Les pourcentages sont comptés en tokens cibles. L'Assemblée est utilisée sur
environ 1,12 passe. Les quatre autres sources tiennent en une passe.

| Source | Part | Tokens cibles |
|---|---:|---:|
| Wikipédia FR | 40 % | 40 003 174 |
| Common Crawl | 15 % | 15 001 190 |
| Assemblée nationale | 15 % | 15 001 191 |
| Project Gutenberg FR | 25 % | 25 001 984 |
| Wikinews FR | 5 % | 5 000 397 |

Le flux inclut un token de contexte supplémentaire. Le dernier filtre Gutenberg
remplace par des espaces des coupures internes à la prose. Les livres modifiés
repassent les gardes-fous de validation publique et Molière. L'audit retrouve zéro
recouvrement de 13 mots pour ces contrôles. Le tokenizer est entraîné sur environ
10 Mo d'échantillon, aux mêmes proportions en octets. Les fiches sources détaillent
les licences et le traitement. Le flux final provient de la variante qualité sans
masquage PII et le paquet sert à la vérification du rendu en accès privé.
