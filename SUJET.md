# Feed the Beast : nourris ton propre GPT

**Piscine I Lab : Garbage In, GPT Out.** Le modèle est le même pour tout le monde. La différence, c'est la donnée.

Piscine individuelle de 3 semaines organisée par l'Intelligence Lab (I Lab) de l'ECE Paris. Mentor référent : Jean-Baptiste Caron.

Pendant 3 semaines, en solo et en autonomie, code un mini-GPT de zéro, puis construis le meilleur dataset français possible à partir du web brut : collecte, nettoyage, déduplication, filtrage qualité. En finale, le modèle et le budget de calcul sont les mêmes pour tous : seule la qualité de tes données fait la différence au classement.

| | |
|---|---|
| Format | Individuel, 3 semaines, en autonomie complète |
| Dates | 16 oct. 2026 → 16 nov. 2026 |
| Inscription | Directement sur la plateforme |
| GitHub | Compte lié au début du projet : tous les rendus s'y font |
| Thèmes | Python, PyTorch, Deep Learning, LLM, Transformer, NLP, Tokenization, Data Engineering, Data Cleaning, Web Scraping, Hugging Face, RGPD |

## Le pitch

Tout le monde parle des modèles. Les équipes qui construisent les meilleurs LLM savent pourtant que la vraie différence se joue ailleurs : dans les données. FineWeb, Lucie, Common Corpus, DCLM... une grande partie des progrès récents vient de pipelines de données mieux pensés, pas d'architectures plus exotiques.

En 3 semaines, tu dois :

- Construire un mini-GPT de zéro, de la dérivée au transformer, sans boîte noire.
- Transformer du web brut en données d'entraînement : collecte, nettoyage, déduplication, filtrage qualité.
- Affronter les autres participants dans une compétition où l'architecture et le budget de calcul sont figés pour tous. Seul ton dataset fait la différence.

À la fin, tu sauras expliquer précisément comment un LLM apprend, et surtout de quoi il apprend.

## Prérequis

- Obligatoire : être à l'aise en Python (fonctions, classes, listes, dictionnaires, lecture de fichiers).
- Utile : bases de maths (dérivées, matrices, probabilités).
- Pas besoin d'avoir déjà fait du machine learning.
- Matériel : un ordinateur portable, un compte GitHub, un compte Hugging Face, un compte Google (Colab) ou Kaggle. Le mini-GPT from scratch tourne sur CPU, les entraînements de la compétition sur les GPU gratuits de Colab ou Kaggle.

## Fonctionnement

- Aucun planning imposé. Seul le rendu final compte.
- Individuel. L'entraide est encouragée, mais le code et les données rendus sont les tiens.
- Kit de départ fourni au lancement : corpus Molière, configuration de référence du modèle, script d'évaluation, set de validation.
- Leaderboard ouvert pendant toute la piscine, 2 soumissions par jour maximum.
- **Assistants IA** (Claude, Copilot, ChatGPT...) : le mini-GPT doit être codé par toi, et tu dois pouvoir expliquer chaque ligne à la soutenance. Pour le reste, usage libre.

## Ce que tu dois produire

Trois blocs, dans l'ordre que tu veux. Le premier est un prérequis logique pour les deux autres.

### 1. Ton mini-GPT from scratch

Un modèle de langage complet, codé de tes mains, qui génère du texte à la manière de Molière à partir du corpus du kit.

- Un mini-autograd (classe `Value` avec `backward()`), vérifié contre PyTorch.
- Un modèle bigramme par comptage comme point de comparaison.
- Un tokenizer BPE implémenté from scratch (train, encode, decode).
- Un transformer décodeur (attention multi-têtes avec masque causal, LayerNorm, MLP, connexions résiduelles).
- Le modèle entraîné sur Molière avec ton tokenizer : courbe de loss, BPB sur la validation, 5 échantillons générés.

### 2. Ton pipeline de données

Un pipeline reproductible (une commande pour tout regénérer) qui transforme du web brut en données d'entraînement propres, et la preuve que chaque étape sert à quelque chose.

- **Collecte** : au moins un segment brut de Common Crawl + au moins 2 sources « propres » en français, avec une fiche par source (origine, licence, volume, période couverte, risques).
- **Nettoyage** : réparation de l'encodage, identification de la langue, suppression du boilerplate. Mesure la précision du filtre de langue sur un échantillon annoté à la main.
- **Déduplication** : exacte (hash) et quasi-doublons (MinHash + LSH), avec un seuil justifié.
- **Filtrage qualité** : heuristiques et/ou classifieur, plus le masquage des données personnelles.
- **Rapport d'ablation** (2 pages max) : le même modèle entraîné sur les données brutes, nettoyées, puis complètement traitées. Quelles étapes ont le plus d'impact ? Lesquelles ne servent à rien ?

### 3. La compétition

Le modèle, les hyperparamètres et le budget sont identiques pour tous : seul ton dataset compte.

| Paramètre | Règle |
|---|---|
| Architecture | Configuration officielle du kit (environ 10M de paramètres), non modifiable |
| Hyperparamètres | Figés (learning rate, batch, seed, longueur de contexte) |
| Budget d'entraînement | [À COMPLÉTER : nombre de tokens vus], calibré pour tenir en moins d'une heure sur un GPU gratuit |
| Tokenizer | Libre (BPE entraîné par toi sur tes propres données), taille de vocabulaire fixée à 8 192 |
| Données | Toute source légalement utilisable, documentée dans la datasheet |
| Données synthétiques | Autorisées, plafonnées à 20 % des tokens, générées par un modèle open weights, prompts publiés |
| Interdit | Initialiser à partir de poids pré-entraînés, distiller les logits d'un autre modèle, chercher à reconstituer le test set |
| Soumissions | 2 par jour maximum : checkpoint + tokenizer + logs d'entraînement + hash du dataset |
| Vérification | Les meilleurs participants sont ré-entraînés par l'orga avec le script officiel. Un écart inexpliqué disqualifie. |

Le test set est caché. Il est composé de textes français variés (encyclopédique, littéraire, presse, dialogue) publiés après le début de la piscine : impossible de les avoir dans ses données, même par accident. Le set de validation public du kit a la même composition.

#### Les bits par octet (BPB)

La perplexité dépend du tokenizer : un modèle avec de gros tokens n'est pas comparable à un modèle avec de petits tokens. Le BPB mesure combien de bits le modèle a besoin, en moyenne, pour encoder chaque octet du texte. Il est indépendant du tokenizer, c'est donc la métrique officielle de la compétition.

```
BPB = (somme sur les tokens de -log2 p(token | contexte)) / (nombre d'octets UTF-8 du texte)
```

Avec une loss moyenne en nats : `BPB = loss × nb_tokens / (ln(2) × nb_octets)`. Plus c'est bas, mieux c'est.

#### Pistes à explorer

- Le mélange des sources : quelle proportion de web, de livres, d'encyclopédie, de dialogues ?
- Les seuils de filtrage : filtrer fort donne des données plus propres mais moins variées. Où est l'optimum ?
- Répéter les meilleures données : vaut-il mieux voir 2 fois un bon document qu'une fois un document moyen ?
- Le tokenizer : un tokenizer entraîné sur ton mix compresse mieux, donc ton modèle voit plus de texte pour le même budget.
- L'ordre des données : garder les données de meilleure qualité pour la fin de l'entraînement.
- Les données synthétiques : histoires simples, mini-manuels générés par un LLM.

## Rendu final

- Classement final sur le test set caché.
- Vote à l'aveugle : le jury et le public notent des générations anonymisées de chaque modèle.
- Soutenance : choix de données, ablations, échecs, et code du mini-GPT.
- Datasheet du dataset final, sur le modèle de *Datasheets for Datasets* (Gebru et al. 2018).

## Barème

| Critère | Poids |
|---|---|
| Classement BPB sur le test set caché | 40 % |
| Rapport d'ablation, datasheet et soutenance | 30 % |
| Mini-GPT et pipeline (complétude, reproductibilité, qualité du code) | 15 % |
| Vote à l'aveugle sur les générations | 15 % |

Prix bonus : meilleure ablation, meilleur dataset publié sur Hugging Face (avec une vraie dataset card), et le prix du pire échantillon généré de la piscine.

## Ressources

### Réseaux de neurones et rétropropagation
- Vidéo : Karpathy, *building micrograd* ; code : `karpathy/micrograd`
- Intuition visuelle : 3Blue1Brown, *Neural Networks*
- PyTorch, *Learn the Basics*

### Modèles de langage
- Vidéo : Karpathy, *building makemore* puis *makemore part 2 (MLP)* ; code : `karpathy/makemore`
- Cours : Jurafsky & Martin, *Speech and Language Processing*, chapitre N-gram
- Paper : Bengio et al. 2003, *A Neural Probabilistic Language Model*
- Source du corpus du kit : Molière sur Wikisource

### Tokenizer
- Vidéo : Karpathy, *Let's build the GPT Tokenizer* ; code : `karpathy/minbpe`
- Paper : Sennrich et al. 2016, BPE pour la traduction
- Bac à sable : Tiktokenizer

### Transformer
- Vidéo : Karpathy, *Let's build GPT from scratch* ; code : `karpathy/nanoGPT`, `karpathy/build-nanogpt`
- Visuel : *The Illustrated Transformer* (Jay Alammar) ; interactif : *Transformer Explainer*
- Paper : Vaswani et al. 2017, *Attention Is All You Need*

### Collecte et aspects légaux
- Common Crawl, *Get Started* (formats WARC, WAT, WET)
- trafilatura, extraction de texte depuis le HTML
- CNIL, fiches pratiques IA et RGPD

### Sources françaises à explorer

| Source | Contenu | Lien |
|---|---|---|
| Wikipédia FR | Encyclopédie | Dumps ou version HF |
| Wikisource FR | Textes du domaine public | fr.wikisource.org |
| Gallica (BnF) | Livres et presse numérisés | gallica.bnf.fr et API BnF |
| Project Gutenberg | Livres du domaine public | Livres en français |
| OPUS | Corpus parallèles, sous-titres | opus.nlpl.eu |
| Assemblée nationale | Débats, comptes rendus | data.assemblee-nationale.fr |
| data.gouv.fr | Données publiques françaises | data.gouv.fr |
| FineWeb-2 (config `fra_Latn`) | Web français déjà filtré | `HuggingFaceFW/fineweb-2` |
| Common Corpus | Textes ouverts, forte part de français | `PleIAs/common_corpus` |
| Lucie Training Dataset | Corpus du LLM français Lucie (licence non commerciale) | `OpenLLM-France/Lucie-Training-Dataset` |

### Nettoyage
- ftfy, réparation d'encodage (mojibake du type `Ã©` au lieu de `é`)
- fastText, identification de langue, et GlotLID
- Paper : CCNet (Wenzek et al. 2019), pipeline de nettoyage de Common Crawl
- Paper : T5 / C4 (Raffel et al. 2019), section 2.2 sur les règles de nettoyage de C4
- Outil : datatrove, la librairie utilisée pour FineWeb

### Déduplication
- Paper : Lee et al. 2021, *Deduplicating Training Data Makes Language Models Better*
- Cours : *Mining of Massive Datasets*, chapitre 3 (similarité, MinHash, LSH)
- Outils : datasketch, text-dedup

### Filtrage qualité et données personnelles
- Paper : Gopher (Rae et al. 2021), annexe sur les filtres qualité
- Paper : RefinedWeb (Penedo et al. 2023)
- Article : *FineWeb, decanting the web for the finest text data* ; modèle : FineWeb-Edu classifier
- Paper : FineWeb2 (Penedo et al. 2025), adapter un pipeline à chaque langue (dont le français)
- Paper : DataComp-LM / DCLM (Li et al. 2024), filtrage par classifieur fastText
- Outil : Microsoft Presidio, détection de données personnelles

### Ablations, mélange et données synthétiques
- Guide : *The Smol Training Playbook* (Hugging Face)
- Paper : Chinchilla (Hoffmann et al. 2022)
- Paper : DoReMi (Xie et al. 2023), optimiser le mélange des sources
- Paper : Muennighoff et al. 2023, *Scaling Data-Constrained Language Models*
- Papers : TinyStories (Eldan & Li 2023), *Textbooks Are All You Need* (Gunasekar et al. 2023)
- Article : Cosmopedia (Hugging Face)

### Pour aller plus loin
- Stanford CS336, *Language Modeling from Scratch* (Assignment 4 : Common Crawl brut → données d'entraînement)
- Karpathy, *Neural Networks: Zero to Hero* ; `karpathy/nanochat`
- Sebastian Raschka, *LLMs from Scratch*
- Lucie-7B et Common Corpus : deux papiers sur la construction de datasets ouverts français

### GPU gratuits
- Google Colab : GPU T4 gratuit, sessions limitées dans le temps
- Kaggle Notebooks : quota hebdomadaire de GPU gratuit

## FAQ

- **Jamais fait de machine learning ?** Le mini-GPT from scratch est fait pour ça.
- **Pas de GPU ?** Pas besoin : le mini-GPT tourne sur CPU, le budget de la compétition est calibré pour les GPU gratuits.
- **Travailler à plusieurs ?** Non, la piscine est individuelle. Échanger des idées oui, mais code et dataset personnels.
- **Pourquoi les licences ?** Savoir d'où viennent ses données et si on a le droit de s'en servir fait partie du travail, et c'est évalué.
- **Utiliser un LLM pour générer des données ?** Oui, dans la limite du règlement (20 % des tokens, modèle open weights, prompts publiés).
