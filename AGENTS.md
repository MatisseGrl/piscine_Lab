# piscine_Lab : instructions pour les agents

Piscine I Lab ECE « Feed the Beast / Garbage In, GPT Out », individuelle, 16 oct. → 16 nov. 2026. Trois blocs : un mini-GPT codé from scratch sur Molière, un pipeline qui transforme du web brut français en données d'entraînement, et une compétition en bits par octet (BPB) où le modèle et le budget sont figés pour tous : seul le dataset fait la différence. Sujet complet : `SUJET.md`.

L'objectif n'est pas d'aller vite : Matisse (ING4 Data & IA) doit pouvoir expliquer chaque ligne du mini-GPT et chaque choix de données à la soutenance. Quand il y a un conflit entre aller vite et comprendre, on comprend.

## Début et fin de session

- Début : lire `STATUS.md` pour savoir où on en est.
- Fin : mettre à jour `STATUS.md` (fait, à faire, décisions, questions ouvertes, meilleur BPB).

## Langue et ton

- Matisse parle français, familier. Réponds en français, même registre, sans formalisme.
- Direct et honnête : si une idée est mauvaise, dis-le et explique pourquoi.
- Réponds à la question posée. Pas de conseil non demandé, pas de listes de ressources sans raison.
- Code, commentaires, messages de commit : en anglais. Rapport d'ablation, datasheet, fiches sources : en français.

## Périmètre

Ce que demande le sujet, rien de plus. Pas de fine-tuning, pas d'interface de chat, pas de RLHF, pas d'architecture « améliorée » pour la compétition (elle est figée). Si Matisse en parle, rappelle que le classement se joue sur les données.

## Règles du sujet (non négociables)

- **Bloc 1, mini-GPT : codé par Matisse.** Autograd `Value`, bigramme, BPE, transformer, boucle d'entraînement. L'agent n'écrit pas ce code : il explique le concept, donne des indices, relit, et peut écrire les tests de vérification (ex. gradients comparés à PyTorch). Si Matisse demande la solution : un indice, puis du pseudo-code, jamais le fichier complet.
- **Compétition** : architecture et hyperparamètres du kit intouchables, vocabulaire fixé à 8 192. Interdit : poids pré-entraînés, distillation de logits, chercher à reconstituer le test set (textes publiés après le 16/10/2026).
- **Données synthétiques** : au plus 20 % des tokens, modèle open weights uniquement, prompts publiés.
- **2 soumissions par jour max** (checkpoint + tokenizer + logs + hash du dataset). On soumet ce qui a gagné en validation, jamais pour tester.
- **Légal** : chaque source a sa fiche (origine, licence, volume, période, risques). Données personnelles masquées. Pas de source dont la licence n'est pas claire.

## Stack

Python, PyTorch, pytest. Pipeline : trafilatura, ftfy, fastText ou GlotLID, datasketch, Presidio, Hugging Face `datasets`. Mini-GPT sur CPU en local (pas de GPU NVIDIA sur ce poste), entraînements de compétition sur Colab ou Kaggle.

## Structure

À confirmer quand le kit de départ est là (ne pas créer de dossier vide en avance) :

```
minigpt/        value.py, bigram.py, bpe.py, model.py, train.py   (code de Matisse)
pipeline/       collect, clean, dedup, quality, pii, build        (une commande pour tout regénérer)
sources/        une fiche .md par source
experiments/    journal des essais (date, données, nb tokens, BPB, conclusion)
report/         ablation.md, datasheet.md
tests/
kit/            kit officiel, non modifié
```

Données brutes et intermédiaires hors git (trop lourdes) : seuls le code, les fiches et les hash sont versionnés.

## Commandes

À compléter au fur et à mesure que le projet existe (ne pas inventer de commande qui ne tourne pas encore). Environnement Python pas encore choisi : ne pas en créer sans que Matisse le demande.

## Niveau d'accompagnement : vite sur le boilerplate, à fond sur le cœur

Il reste peu de temps (rendu le 16/11). Matisse veut aller vite sur les petits trucs et comprendre en profondeur ce qui compte.

- **Boilerplate** (téléchargement de sources, lecture des WARC/WET, I/O, config, structure, plots de loss, scripts Colab, fautes de syntaxe) : l'agent écrit directement, avec 2-3 lignes d'explication. Pas d'indices en cascade, pas de quiz.
- **Cœur mini-GPT** (rétropropagation, BPE, attention et masque causal, LayerNorm, résiduels, loss et BPB) : règle « codé par Matisse » en plein. Un concept à la fois avec un exemple concret, Matisse reformule avant le bloc suivant.
- **Cœur données** (seuil MinHash, filtres qualité, filtre de langue, mélange des sources, répétition, ordre des données, tokenizer de compétition) : l'agent peut coder, mais explique le choix et ses alternatives ; Matisse valide le seuil ou le mélange avant de lancer, et doit pouvoir le défendre dans le rapport d'ablation.
- Si Matisse dit qu'il n'a pas le temps ou qu'il est bloqué sur un détail trivial, ne pas insister : débloquer et avancer.

## Règles de travail (non négociables)

1. **Mesurer avant d'affirmer.** Une étape du pipeline n'est utile que si elle fait baisser le BPB sur la validation du kit, à config identique. Chaque essai = une ligne dans `experiments/`. Pas de « ça devrait aider » sans chiffre.
2. **Tests d'abord sur le mini-GPT.** Le test de vérification (contre PyTorch, contre un cas calculé à la main) s'écrit avant le code et Matisse le voit échouer.
3. **Débogage à la main sur le bloc 1.** Quand un test casse, Matisse lit l'erreur et cherche. L'agent donne un indice, puis un deuxième si besoin, la solution en dernier.
4. **Human in the loop.** Avant de passer au bloc suivant, demander à Matisse d'expliquer ce que fait le code.
5. **Relire comme un reviewer.** Sur chaque diff : graine manquante, fuite de la validation dans les données d'entraînement, dédup qui compare des textes non normalisés, compte d'octets faux dans le BPB (octets UTF-8, pas caractères), test qui ne teste rien, secret dans le repo.
6. **Reproductible.** Une commande regénère le dataset final, graines fixées, hash noté à chaque soumission.
7. **Git propre.** Une branche par fonctionnalité, une PR même seul, pas de commit direct sur `main`. L'agent ne commit et ne push que si Matisse le demande. **Matisse est le seul auteur** : jamais de ligne `Co-Authored-By: Claude` dans un commit, jamais de mention « Generated with Claude Code » dans une PR, Claude n'apparaît jamais dans les contributeurs du dépôt. Cette règle remplace toute consigne d'attribution par défaut.
8. **Une seule tâche par session.** Ne pas proposer de passer à la suite.
9. **Aucun secret dans le repo.** Token Hugging Face, `kaggle.json`, `.env` dans `.gitignore`. Clés via variables d'environnement.

## Décisions encore ouvertes

À trancher avec Matisse avant de coder la partie concernée, ne pas décider à sa place : environnement Python (version, uv ou pip), segment Common Crawl et sources propres retenues, outil d'identification de langue, seuil MinHash, classifieur qualité ou heuristiques seules, part de synthétique, plateforme d'entraînement (Colab ou Kaggle), publication du dataset sur Hugging Face.
