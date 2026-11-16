# Courbes de tests et analyse des 3 meilleurs modèles

Rien n'a été relancé ni modifié : ce dossier ne contient que des graphiques et ce texte, produits en relisant les journaux déjà existants (`train_log.jsonl`, `evaluation.json`, `result.json`). Le script est `make_curves.py`.

**Le score.** Le meilleur run est **M4FINALEXCERPTS : 1,2767 BPB** (graine 1337) et 1,2786 (graine 1338), sur les 230 documents de validation publique, mesuré sur Colab. Ce run est sur la branche `codex/competition-night`, pas encore sur `main` (j'avais d'abord lu `main`, d'où mon « 1,27 introuvable » : c'était une erreur de ma part). Les courbes ci-dessous l'incluent maintenant.

## Ce que montrent les courbes (et leurs limites)

- **Courbes d'entraînement** : disponibles pour les 23 runs de mélange (loss tous les 10 pas, 3 052 pas). La loss est par token ; je la convertis en bits par octet avec le ratio octets/token de la validation pour pouvoir comparer des tokenizers différents. C'est une approximation, pas la mesure officielle.
- **Pas de courbe de validation en cours de run** : le kit n'évalue la validation qu'à la fin. Donc le BPB validation est un point par run, pas une courbe.
- **Ablation du pipeline (brut, nettoyé, dédup, qualité, PII)** : les logs de loss n'ont pas été conservés, seulement le BPB final. Elle est tracée en barres, pas en courbes.

| Figure | Contenu |
|---|---|
| `fig1_ablation_pipeline.png` | Effet de chaque étape du pipeline (barres) |
| `fig2_classement_runs.png` | BPB final de tous les runs de compétition, avec la zone de bruit |
| `fig3_top3_entrainement.png` | Courbes de loss et taux d'apprentissage du top 3 + M4 |
| `fig4_par_genre.png` | BPB par genre : d'où vient le gain |
| `fig5_toutes_les_courbes.png` | Une courbe d'entraînement par run (les 23) |
| `fig6_progression.png` | Progression du meilleur BPB au fil du projet |

## Les 3 meilleurs modèles

Classement par moyenne sur 2 graines (1337 et 1338). Architecture, hyperparamètres, nombre de pas (3 052) et budget (100 007 936 tokens) identiques pour tous : **seules les données changent**.

| Rang | Run | Graine 1337 | Graine 1338 | Moyenne |
|---|---|---|---|---|
| 1 | **M4FINALEXCERPTS** | 1,2767 | 1,2786 | **1,2777** |
| 2 | M4REFLOWBPE | 1,2874 | 1,2849 | 1,2861 |
| 3 | M4REFLOW | 1,2905 | 1,2938 | 1,2922 |
| réf. | M4BPE | 1,2992 | 1,2951 | 1,2971 |
| réf. | M4 (point de départ) | 1,3028 | 1,3066 | 1,3047 |
| réf. | 80/12/8 qualité (avant mélange) | 1,3304 | 1,3270 | 1,3296 (moy. 3 runs) |

D'autres variantes finales n'ont qu'une graine (BOOK35 1,2842, RETOK50 1,2839, ITALICS 1,2851) : elles sont dans le bruit par rapport à M4REFLOWBPE, donc on ne les classe pas. Seuil de bruit mesuré : environ 0,005 BPB (σ = 0,0023).

### Ce qui a fait baisser le score, étape par étape

1. **Le mélange M4 : −0,025.** On passe de 80 % Wikipédia / 12 % Common Crawl / 8 % Assemblée à 40 / 15 / 15 / 25 / 5, avec **25 % de livres Gutenberg** et 5 % de Wikinews. C'est le plus gros gain depuis le pipeline, confirmé sur 2 graines. Il vient du genre littéraire (1,68 vers 1,55), comme le montre `fig4`. Wikipédia baisse un peu en encyclopédique (1,31 vers 1,37), mais c'est largement compensé.
2. **Le recollage Gutenberg (M4REFLOW) : environ −0,011 à −0,013 (au-dessus du bruit, 2 graines).** Les livres avaient des retours à la ligne au milieu des phrases (typiques du format Gutenberg). On les a remplacés par des espaces (12,8 millions de sauts de ligne recollés dans 4 031 documents). Le texte d'entraînement ressemble alors plus à du texte normal : le BPB littéraire passe de 1,547 à 1,507. Aucun autre genre ne bouge.
3. **Le tokenizer BPE appris sur le mélange (M4BPE) : −0,004 (graine 1337) à −0,008 en moyenne.** Le vocabulaire de 8 192 entrées est appris sur le mélange réel (10 Mo), donc plus de texte tient dans chaque token (3,7745 octets par token contre 3,7396). Gain modeste, à la limite du bruit seul, mais il s'additionne bien avec le recollage.
4. **Recollage + BPE (M4REFLOWBPE).** Les deux gains s'additionnent presque : environ −0,018 vs M4 en moyenne (−0,0154 sur la graine 1337). Le BPB littéraire descend à 1,483.

### Pourquoi les courbes d'entraînement se ressemblent

Sur `fig3` (le top 3 plus M4 en référence), les quatre courbes sont presque superposées : même modèle, même taux d'apprentissage (identique, courbe de droite), même nombre de pas. Ce n'est pas un défaut, c'est ce qu'on veut : la différence finale vient des **données**, pas de l'entraînement. Les écarts apparaissent dans la deuxième moitié et sont petits (quelques millièmes), ce qui est cohérent avec les écarts de BPB final. Attention : la loss d'entraînement ne départage pas les runs (elle est mesurée sur des données d'entraînement différentes d'un run à l'autre et reste bruitée) ; le vrai juge est le BPB sur la validation publique, mesuré à la fin.

5. **Extraits Gutenberg (M4FINALEXCERPTS) : −0,0085 en moyenne, le meilleur.** Même mélange 40/15/15/25/5 et même quota de 25 001 984 tokens pour Gutenberg, mais au lieu de 204 livres complets on met 1 836 extraits d'environ 48 000 caractères. Le modèle voit beaucoup plus de textes, d'époques et de styles différents au lieu de quelques livres entiers. Le BPB littéraire descend à 1,457 (1,483 avant). Le gain dépasse le bruit sur les deux graines (−0,0107 et −0,0063), et le checkpoint exporté redonne 1,276737 sur CPU.

## Ce qui n'a pas marché (aussi dans les courbes)

| Essai | BPB | Verdict |
|---|---|---|
| M2 (4 sources à parts égales) | 1,3469 | Pire que la référence : répéter l'Assemblée ne compense pas la perte ailleurs |
| M4ORDER (changer l'ordre des données) | 1,3106 | Dégradation |
| M4WIKI (45 % Wikipédia) | 1,3115 | Dégradation sur le dialogue et le littéraire |
| M4REPEAT (rejouer Wikipédia et Gutenberg) | 1,3172 | Dégradation |
| M4CLASS (filtre structurel Common Crawl) | 1,3044 | Aucun gain mesuré |
| M4BPE50 (BPE sur 50 Mo) | 1,2983 / 1,3038 | Pas de gain net sur 2 graines |
| M4FINALBOOK30 / BOOK35 (plus de Gutenberg) | 1,2900 / 1,2842 | Dans le bruit |
| M4FINALBOOKSHUFFLE (livres permutés) | 1,2899 | Dans le bruit |
| M4FINALITALICS (marqueurs d'italique retirés) | 1,2851 | Dans le bruit |
| M4FINALRETOK / RETOK50 (BPE réappris) | 1,2982 / 1,2839 | Dégradation puis dans le bruit |
| PII (masquage) | 1,3322 | Aucun gain mesuré ; non retenu |

## Limites honnêtes

- M4FINALEXCERPTS : même validation publique que les runs précédents ; le gain vient toujours du littéraire, donc il dépend du poids de ce genre dans le test du mentor.

- Une seule validation publique de 230 documents. Le gain vient surtout du littéraire : si le test du mentor pèse moins ce genre, le gain peut être plus faible.
- M2 et M3 sont des lectures des notes orales du mentor, non confirmées par écrit.
- La conversion loss en BPB sur les courbes d'entraînement est approximative.
