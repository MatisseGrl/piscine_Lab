# Bruit d'entraînement de l'ablation

Question du mentor : les écarts de 0,001 à 0,003 BPB entre variantes sont-ils au-dessus du bruit ? On mesure le même flux « dédup + qualité 80/12/8 » (SHA-256 `f6ad793c15f01cfbcc297e30048061b8619c769bb100e9d9a9b2bc4ffa94c9cf`), config `config/official.json`, kit `3709c85`, 3 052 pas, 100 007 936 tokens vus, même tokenizer, GPU T4, 230 documents publics.

## Mesures (3 points seulement)

| Run | Graine | BPB global | Encyclo. | Littéraire | Presse | Dialogue |
|---|---:|---:|---:|---:|---:|---:|
| Ablation (kernel de l'ablation) | 1337 | 1,3304249 | 1,3102 | 1,6738 | 1,2064 | 1,1299 |
| Relance de la soumission (`piscine-submission-quality`, PR #29) | 1337 | 1,3314701 | 1,3131 | 1,6751 | 1,2076 | 1,1287 |
| Bruit (`noise-quality-s1338`) | 1338 | 1,3270291 | 1,3089 | 1,6692 | 1,2051 | 1,1235 |
| **Moyenne** | | **1,32964** | 1,31073 | 1,67271 | 1,20637 | 1,12734 |
| **Écart-type** (échantillon, n = 3) | | **0,00232** | 0,00213 | 0,00309 | 0,00124 | 0,00341 |
| Étendue (max − min) | | 0,00444 | 0,00414 | 0,00588 | 0,00248 | 0,00643 |

Une graine 2027 était prévue mais n'a pas pu tourner (voir limites). Fichiers bruts : `Kaggle submissions/noise/`.

## Ce que ça montre

- Deux runs à **graine identique (1337)** donnent 1,3304 et 1,3315 : écart de **0,0010** sans rien changer aux données ni à la graine. C'est la non-reproductibilité du GPU (opérations flottantes non déterministes, fp16), pas un effet des données.
- Une autre graine (1338) donne 1,3270, soit **0,0034** de moins que l'ablation. L'étendue totale sur 3 runs est de 0,0044 et l'écart-type de 0,0023.
- Par genre, le bruit est du même ordre (0,001 à 0,003 d'écart-type).

## Comparaison avec les écarts du rapport d'ablation

| Écart | Valeur | Verdict |
|---|---:|---|
| nettoyé → dédup | −0,0010 | dans le bruit (≤ écart de deux runs identiques) |
| dédup → qualité | −0,0025 | dans le bruit (≈ 1 écart-type) |
| dédup → PII | −0,0008 | dans le bruit |
| qualité+PII vs dédup | +0,0011 (dégradation vs qualité) | dans le bruit |
| 74/18/8 vs 80/12/8 | +0,0020 | dans le bruit |
| parts égales vs 80/12/8 | +0,0058 | au-dessus d'un écart-type (≈ 2,5), à peine au-dessus de l'étendue observée (0,0044) ; probable mais pas démontré |
| brut → nettoyé | −0,0198 | très au-dessus du bruit |

**Verdict honnête :** les écarts de 0,001 à 0,003 entre variantes (dédup, qualité, PII, 74/18/8) **ne sont pas distinguables du bruit** : on ne peut pas dire que ces étapes aident, ni qu'elles ne servent à rien. Seul le gain du nettoyage (≈ 0,02) est clair, et le mauvais résultat des parts égales (+0,006) est vraisemblable. Le classement fin des variantes dans `report/ablation.md` doit se lire comme « pas de différence démontrée ».

## Limites

- **Trois points seulement** : l'écart-type est lui-même très incertain (avec n = 3, l'intervalle de confiance est très large). Les deux points à graine 1337 ne sont pas indépendants du même effet « graine ».
- La graine 1337 a deux valeurs : l'écart de 0,0010 mesure le bruit matériel/numérique seul ; l'écart avec 1338 mélange ce bruit et l'effet de la graine (ordre des données, initialisation).
- Le run à graine 2027 n'a pas été exécuté : le kernel était resté en file Kaggle (limite de 2 sessions GPU en lot) et a été supprimé pour libérer une place.
- Une seule validation publique (230 documents, 813 051 octets UTF-8).
- Pour retenir une amélioration, la règle du plan est de dépasser le bruit mesuré : ici environ **0,005 BPB** (étendue observée) en attendant mieux.

## Reproduire

`uv run python scripts/kaggle_noise_run.py <graine>` pousse un kernel Kaggle qui change seulement `train.seed` dans la config du kit.
