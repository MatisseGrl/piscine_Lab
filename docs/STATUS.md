# STATUS : piscine_Lab (Feed the Beast)

À lire au début de chaque session, à mettre à jour à la fin. Réécrit le 14 novembre 2026 (l'historique détaillé est dans git). **Rendu le 16 novembre 2026.**

## Dernier état (17 novembre)

- **Meilleur BPB : 1,2767** (M4FINALEXCERPTS, graine 1337 ; 1,2786 en graine 1338), détaillé dans `report/ablation.md` et `report/courbes/`. Les sections ci-dessous sont l'historique des essais du 15/11.
- **PowerPoint de soutenance refait** : `report/Feed-the-Beast-soutenance.pptx` (8 diapos : projet, architecture technique, sources et licences, ablation, genres et échecs, mini-GPT et démo, rendu et limites). Il remplace l'ancien `Feed-the-Beast-demo.pptx`, centré sur la démo seule et resté aux chiffres du 14/11. Il est généré par `uv run --with python-pptx python report/build_deck.py` : changer un chiffre dans le script puis regénérer.
- À vérifier par Matisse avant de présenter : le score du test caché (inconnu), et le lien public du dataset (toujours privé).

## Compétition, essais du 15 novembre

Le paquet de compétition retenu est **M4REFLOWBPE à 1,2874 BPB** en graine officielle
sur les 230 documents publics. Il combine le recollage des lignes de prose Gutenberg
et le BPE entraîné sur 10 Mo du mélange M4. Les 4 031 livres modifiés repassent les
gardes-fous de la validation publique et de Molière, avec zéro recouvrement détecté.

| Recette | Graine 1337 | Graine 1338 | Moyenne |
|---|---:|---:|---:|
| M4, référence | 1,3012 | 1,3066 | 1,3039 |
| M4, BPE adapté sur 10 Mo | 1,2992 | 1,2951 | 1,2971 |
| M4, BPE adapté sur 50 Mo | 1,2983 | 1,3038 | 1,3011 |
| M4REFLOW | 1,2905 | 1,2938 | 1,2922 |
| M4REFLOWBPE | **1,2874** | **1,2849** | **1,2861** |

Le recollage seul améliore le BPB de 0,0118 en moyenne, avec un gain littéraire de
0,0324 en graine officielle. La combinaison gagne 0,0178 sur les deux graines
testées et descend à 1,4826 en littéraire avec la graine officielle.

Le changement d'ordre vaut 1,3106, le mélange 45/15/10/25/5 vaut 1,3115, et leur
combinaison avec le BPE adapté vaut 1,3169. La répétition partielle donne 1,3172 et
le classifieur Common Crawl 1,3044. Les scores, logs et empreintes sont dans
[le journal des essais](../Kaggle%20submissions/LOG.md).

Les entraînements utilisent le kit 3709c85 et 100 007 936 tokens vus. La graine 1337
sert aux paquets de compétition. La graine 1338 sert au contrôle de stabilité.
Le [paquet vérifié](../submissions/2026-11-15_020424/) contient les poids en float16,
réévalués sur CPU à 1,2874 BPB. Son dataset est sur Kaggle en accès privé.
Le [guide de remise au mentor](RENDU_COMPETITION.md) accompagne l'archive privée
`Rendu-competition-M4REFLOWBPE-2026-11-15.zip`. Le ZIP contient le flux exact,
le kit figé et la soumission. Après extraction, les 51 empreintes ont été vérifiées,
le checkpoint a donné 1,287437 BPB sur CPU et le pilote d'entraînement a chargé
les données et terminé son pas de contrôle. La préparation finale depuis les
archives auditées a reproduit le SHA-256 du flux Kaggle. La collecte complète depuis
un dossier vide reste à vérifier.

### Vérifications du paquet 1,2874 (15/11)

- **Poids** : `ckpt.pt` réévalué sur CPU avec le kit officiel : 1,287437 BPB (1,287432 annoncé, écart dû au float16). SHA du tokenizer et du dataset conformes à `submission.json`.
- **Régénération** : `uv run python -m pipeline.regenerate --mix M4REFLOWBPE --from gutenberg-reflow` (recollage, BPE, mélange depuis `data/interim`) redonne le **SHA-256 identique** `f1730391…`. La chaîne depuis la collecte brute n'a pas été relancée.
- **Reste** : le dataset Kaggle `piscine-mix-m4reflowbpe` est privé. Le mentor reçoit le flux exact dans l'archive privée (voir ci-dessus) ; un lien public pour `--dataset-url` reste à décider par Matisse.

## Audit du 15 novembre (au matin, avant les essais ci-dessus)

- Les 189 tests passent avec le corpus Molière et le tokenizer 8 192. Le test de la démo v5 reproduit la boucle signalée, sans troncature de l’historique. Le [rapport d’audit](../report/audit_20261115.md) détaille les variantes, la répétition et les indices de mémorisation.
- **Meilleur BPB public compétition : 1,302769 (M4, graine officielle 1337)**. Le run M4 n’a pas conservé le checkpoint. Le paquet préparé est le 80/12/8 avec filtre qualité, réévalué à **1,331469** sur CPU avec le kit officiel. Score caché et soumission effective non vérifiés.
- À vérifier avant le rendu : aligner les chiffres du rapport et de la soutenance sur le paquet réellement remis. La commande de régénération contrôle le hash écrit dans le manifeste, donc calculer directement celui de `train.bin` pour vérifier le fichier.


## Où on en est

| Bloc | État |
|---|---|
| Bloc 1, mini-GPT (`minigpt/`) | Fait et mergé. BPB Molière : 1,8237 (base), **1,743** pour le meilleur modèle seul (continuation avec 5 pièces Wikisource contrôlées). Le 1,696 est un ensemble de 6 modèles avec fréquences réglées sur la validation : exploratoire, ne pas le présenter comme résultat propre. |
| Bloc 2, pipeline (`pipeline/`) | Fait : collecte, nettoyage, dédup (exact + MinHash 0,97), qualité, PII. Filtre de langue : 99/100 (échantillon surtout Wikipédia). |
| Bloc 3, compétition | Ablations et contrôles de stabilité terminés. Résultats récents dans la section du 15 novembre. |
| Démo chat (demandée par le mentor) | Prototype local `demo/` (PR #23) : tient 3 tours sur le scénario de JB, mais réponses médiocres en conversation libre. À refaire mieux (voir plan). |

## Ablation initiale sur la validation publique (tokenizer commun, 100 007 936 tokens, graine 1337)

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
- **Candidat avant l'ablation des sources : 80/12/8 dédupliqué + qualité** (1,3304).
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

## Ablation des sources : résultats (15/11, nuit)

Tous les mélanges ont tourné (détails : `report/ablation.md`, LOG). Référence 80/12/8 = 1,3296 (σ 0,0023, seuil ~0,005).
- M1 1,3262 (bruit), M2 1,3469 (pire), M3 1,3151 (1,3146 en relance), M5 1,3138, **M4 1,3028 / 1,3066 (2 graines)**.
- **Soumission M4 faite** (go de Matisse) : `submissions/2026-11-15_002554`, **BPB 1,3048**, run officiel Colab T4. **Meilleur BPB actuel.** Plus que 1 soumission possible le 15/11.
- À trancher par Matisse : visibilité du dataset Kaggle `piscine-mix-m4` (privé, cité comme `dataset_url`).
- Reste : pptx (diapo ablation et sources avec Gutenberg et Wikinews).
