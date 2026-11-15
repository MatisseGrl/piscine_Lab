# STATUS : piscine_Lab (Feed the Beast)

À lire au début de chaque session, à mettre à jour à la fin. Réécrit le 14 novembre 2026 (l'historique détaillé est dans git). **Rendu le 16 novembre 2026.**

## Compétition, essais du 15 novembre

M4REFLOW atteint **1,2905 BPB** en graine officielle avec les mêmes quotas et le même
tokenizer que M4. Seuls des retours à la ligne de prose Gutenberg coupée à largeur fixe
sont remplacés par des espaces. Les blocs des autres sources sont identiques. Les 4 031
livres modifiés repassent les gardes-fous de la validation publique et de Molière,
avec zéro recouvrement détecté.

| Recette | Graine 1337 | Graine 1338 | Moyenne |
|---|---:|---:|---:|
| M4, référence | 1,3012 | 1,3066 | 1,3039 |
| M4, BPE adapté sur 10 Mo | 1,2992 | 1,2951 | 1,2971 |
| M4, BPE adapté sur 50 Mo | 1,2983 | 1,3038 | 1,3011 |
| M4REFLOW | **1,2905** | **1,2938** | **1,2922** |

Le recollage améliore le BPB de 0,0118 en moyenne sur les deux graines testées. En
graine officielle, le littéraire passe de 1,5394 à 1,5070. La combinaison du recollage
et du BPE adapté sur 10 Mo est en cours sur les deux graines.

Le changement d'ordre vaut 1,3106, le mélange 45/15/10/25/5 vaut 1,3115, et leur
combinaison avec le BPE adapté vaut 1,3169. La répétition partielle donne 1,3172 et
le classifieur Common Crawl 1,3044. Les scores, logs et empreintes sont dans
[le journal des essais](../Kaggle%20submissions/LOG.md).

Les entraînements utilisent le kit 3709c85 et 100 007 936 tokens vus. La graine 1337
sert aux paquets de compétition. La graine 1338 sert au contrôle de stabilité.

## Où on en est

| Bloc | État |
|---|---|
| Bloc 1, mini-GPT (`minigpt/`) | Fait et mergé. BPB Molière : 1,8237 (base), **1,743** pour le meilleur modèle seul (continuation avec 5 pièces Wikisource contrôlées). Le 1,696 est un ensemble de 6 modèles avec fréquences réglées sur la validation : exploratoire, ne pas le présenter comme résultat propre. |
| Bloc 2, pipeline (`pipeline/`) | Fait : collecte, nettoyage, dédup (exact + MinHash 0,97), qualité, PII. Filtre de langue : 99/100 (échantillon surtout Wikipédia). |
| Bloc 3, compétition | Ablation faite (8 variantes, BPB public ci-dessous). **Soumission officielle pas encore faite.** |
| Démo chat (demandée par le mentor) | Prototype local `demo/` (PR #23) : tient 3 tours sur le scénario de JB, mais réponses médiocres en conversation libre. À refaire mieux (voir plan). |

## BPB sur la validation publique du kit (même tokenizer 8 192, 100 007 936 tokens, graine 1337)

| Données | BPB |
|---|---|
| Brut contrôlé | 1,3538 |
| Nettoyé | 1,3340 |
| Dédupliqué | 1,3330 |
| Dédup + PII | 1,3322 |
| Dédup + qualité + PII | 1,3315 |
| **Dédup + qualité, 80/12/8 (meilleur)** | **1,3304** |
| Mélange 74/18/8 (dédup + qualité) | 1,3325 |
| Mélange parts égales (dédup + qualité) | 1,3362 |

Le nettoyage donne le gros du gain (−0,020). Les écarts suivants sont petits (0,001 à 0,003). Nettoyé → dédupliqué inclut aussi le plafonnement de Wikipédia à 300 000 articles : ce n'est pas l'effet de la dédup seule.

## Décisions de Matisse

- **Accord du mentor (JB) pour l'IA : confirmé** par Matisse, qui dit que JB veut même qu'on l'utilise pour le mini-GPT. Garder une trace écrite si possible.
- **Chat et fine-tuning : demandés par JB** (appel du 14/11, mail). Datasets externes autorisés, à **citer avec les liens dans le pptx**. On repart du modèle du bloc 1.
- **Soumission : le mentor teste sur sa machine.** Matisse lui envoie le paquet produit par `ftb.submit` : `ckpt.pt`, `tokenizer.json`, `train_log.jsonl`, `data_meta.json`, `samples.txt`, `submission.json` (dans `submissions/<date>/`). Il faut un lien vers le dataset (`--dataset-url`).
- **Dataset final retenu pour la soumission : 80/12/8 dédupliqué + qualité** (1,3304). À confirmer par Matisse.
- Mélange validé : Wikipédia FR 80 %, Common Crawl 12 %, Assemblée nationale 8 %. Tokenizer 8 192 commun, SHA-256 `b2554a8221a55c19b4008f5b605b1b6e84b6a7f84058507c15aba34eca3b2379`.
- Règle du sujet : interdit d'initialiser à partir de poids pré-entraînés pour la **compétition**. Ne concerne pas la démo.

## En cours (14/11, soir)

- **Pré-entraînement du mini-GPT du bloc 1 sur Kaggle** (config compétition, flux dédup + qualité 80/12/8, `minigpt/pretrain.py`, PR #27, branche `feat/chat-pretrain`). Matisse l'a lancé. Résultat attendu : `runs/chat-pretrain/pretrained.pt` + BPB indicatif. Ensuite : SFT chat puis page HTML.
- **Répartition des fichiers entre conversations.** Conversation « code » (chat, SFT, démo) : `minigpt/`, `demo/`, `scripts/` du chat, `tests/`. Conversation « docs et soutenance » : `report/`, `sources/`, `docs/`, `experiments/LOG.md`. Ne pas toucher aux fichiers de l'autre. Pas de `data/` ni de `runs/` dans git.

## Ablation des sources (14/11, soir)

Gutenberg et Wikinews collectés, bruit mesuré (σ 0,0023 sur 3 runs, seuil de décision ~0,005), flux M1 à M5 construits. **M1 = 1,3262** (dans le bruit ; littéraire −0,10, encyclopédique +0,085). Reste M3, M4, M2, M5 puis le choix final. Passation détaillée : [docs/HANDOFF_MIXES.md](HANDOFF_MIXES.md).

## Plan jusqu'au rendu

1. **Ordre** : sync `main`, STATUS/AGENTS à jour. *(fait le 14/11)*
2. **Paquet de soumission** : retrouver le checkpoint du run qualité sur le Kaggle de Matisse (onglet Output : `ckpt.pt`, logs, `data_meta.json`, `samples.txt`), lancer `python -m ftb.submit`, pousser. Sinon relancer le même flux (~13 min sur T4).
3. **Chat meilleur** : mini-GPT du bloc 1 en version plus grande avec le tokenizer 8 192, pré-entraîné sur le dataset final (Kaggle), puis fine-tuné sur Molière et dialogues. Banc fixe de prompts, comparaison honnête avec l'ancien chat. Arrêt dimanche midi.
4. **Maquette HTML** : une commande de lancement, reset de conversation, gestion des erreurs.
5. **Docs et soutenance** : rapport d'ablation, datasheet, pptx (avec les sources externes et liens), fiche de soutenance.

## Questions ouvertes

- Le dossier de run Kaggle du run qualité contient-il `ckpt.pt` ? (seuls les `result.json` sont en local)
- Publier le dataset sur Hugging Face (bonus, et utile comme `--dataset-url`) ?
- Dataset externe de dialogues en français : lequel, quelle licence ?
- Commande unique de régénération : `uv run python -m pipeline.regenerate --mix M4` (15/11). Dernière étape (mélange M4 depuis `data/interim`) **vérifiée : SHA-256 identique** au run Kaggle (`c6c628a6…`). La chaîne complète depuis la collecte (plusieurs heures, ~100 Go) n'a pas été relancée de bout en bout.
- Quota GPU Kaggle hebdomadaire : toujours pas vu où il s'affiche.

## Pièges

- Toujours lire le corpus Molière en mode texte (`load_utf8`) : sous Windows, CRLF fausse le compte d'octets et le BPB.
- Pas de `python` système : toujours `uv run python ...` et `uv run pytest`.
- Un seul dossier de travail : `C:\Users\mgarl\Documents\piscine_Lab`. Pas de copie OneDrive.
