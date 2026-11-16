# Passation : ablation des sources (mélanges M1 à M5), état au 14/11/2026 soir

À lire par la session qui reprend les phases C et D. Plan complet d'origine : `docs/PROMPT_ablation_sources.md` du checkout principal (non versionné). Règles : `AGENTS.md` (surtout 6, 9, 10).

## Fait

- **Phase A** : Gutenberg FR (PR #32, 4 094 livres, 1,64 Go UTF-8, ~470 M tokens), Wikinews FR (PR #31, 19 309 docs, ~5,5 M tokens). Sorties dans `data/interim/gutenberg/` et `data/interim/wikinews/` du checkout principal (hors git).
- **Bruit** (PR #33, `report/noise.md`) : même flux dédup+qualité 80/12/8 → 1,3304 / 1,3315 / 1,3270. Moyenne 1,3296, écart-type 0,0023. **Seuil de décision : ~0,005.**
- **Phase B** : `pipeline/mixes.py` (PR #34 puis cette PR). Flux construits dans le checkout principal :
  - `data/processed/mixes-m3/M3/` (SHA `b771c8aa…`)
  - `data/processed/mixes-rest/{M1,M4,M2,M5}/` (SHA M1 `7fafbea6…`, M4 `c6c628a6…`, M2 `6d2a5128…`, M5 `898b5ef8…`)
  - Répétitions : Assemblée 1,45 passe dans M1, 1,08 dans M4, 1,81 dans M2 ; tout le reste en une passe.
  - Datasets Kaggle privés `matissegarlot/piscine-mix-{m1,m2,m3,m4,m5}` à jour (version 2, avec `passes_over_data`).
- **Phase C, M1 fait** (Colab T4) : **1,3262**, soit −0,0034 vs la moyenne du bruit, donc **dans le bruit**. Par genre : littéraire 1,576 (−0,10), dialogue 1,084, encyclopédique 1,395 (+0,085), presse 1,252 (+0,046). Ligne dans `Kaggle submissions/LOG.md`, fichiers dans `Kaggle submissions/mixes/M1/`.

## Reste à faire

1. **Phase C : M3, puis M4, M2, M5**, un à la fois (Colab gratuit = un seul GPU ; Kaggle = 2 places en lot, une réservée au chat de la conversation « code », qui a la priorité).
2. **Phase D** : comparer au seuil de bruit, présenter le choix à Matisse, **attendre son « go » avant toute soumission** (`ftb.submit`, 2 par jour max, paquet existant `submissions/2026-11-14_182456` à ne pas toucher), puis mettre à jour `report/ablation.md`, `report/datasheet.md`, `report/soutenance.md`, le pptx, `sources/`, `docs/STATUS.md`. Gel des expériences : **dimanche 15/11 à 20 h**.

## Lancer un mélange sur Colab (CLI dans WSL, déjà authentifié par Matisse)

```bash
export MSYS_NO_PATHCONV=1          # sous Git Bash, sinon les chemins WSL sont cassés
C="wsl.exe -d Ubuntu -- /home/mgarl/.local/bin/colab --auth=oauth2"
$C new -s mix-m3 --gpu T4           # nommer la session d'après le mélange (demande de Matisse)
```

1. Créer `/content/data/M3/` avec un petit `colab exec -f mk.py` (`os.makedirs`).
2. Envoyer `data_meta.json` et `tokenizer.json` avec `colab upload` (chemins WSL `/mnt/c/...`).
3. `train.bin` (~200 Mo) : l'upload direct échoue (400). Découper en morceaux de 20 Mo (`split -b 20m -d train.bin part.`) et envoyer chaque `part.NN` dans `/content/data/M3/`.
4. Écrire le nom du mélange dans `/content/data/MIX` (fichier contenant `M3`), puis `colab exec -s mix-m3 -f colab/remote_mix.py` : recolle, vérifie le SHA-256, lance l'entraînement en arrière-plan (journal `/content/train-M3.log`, ~13 min sur T4).
5. Suivre avec un petit script `exec` qui lit la fin du journal (décoder en UTF-8 avec `errors="replace"`) ; fin quand `/content/run-M3/evaluation.json` existe.
6. `colab download` de `evaluation.json`, `train_log.jsonl`, `samples.txt` vers `Kaggle submissions/mixes/M3/`, copier `data_meta.json` local, ajouter la ligne au LOG.
7. **`colab stop -s mix-m3` dès la fin** (Matisse le demande ; une session ouverte bloque le seul GPU).

## Lancer un mélange sur Kaggle (si une place est libre)

`uv run python scripts/kaggle_mix_run.py M4` (kernel `piscine-run-m4`, dataset `piscine-mix-m4`). Kernel et dataset doivent avoir des slugs différents, sinon « 409 Conflict ». Une session **en file** compte déjà comme une des 2 places. Ne jamais pousser un 3e run GPU.

## Pièges rencontrés

- `ftb.train` lit `data_meta["passes_over_data"]` : corrigé dans `pipeline/mixes.py`, ne pas l'enlever.
- `kaggle datasets create -p <chemin absolu>` casse sous Windows : lancer depuis le dossier avec `-p .`.
- Chaque changement passe par une PR, que l'agent merge lui-même après relecture (accord de Matisse). Jamais de push direct sur `main`, aucune co-signature ni mention d'outil.

## Réserves

- **Une seule graine par mélange** : les écarts se lisent avec le bruit de `report/noise.md` (σ 0,0023, seuil ~0,005). **M4 (1,3028) est à confirmer par une 2e graine** (à faire par mixes-cd).
- M3 : fichiers récupérés à la main après perte de la session Colab, preuve indirecte, pas soumissible tel quel : voir `Kaggle submissions/mixes/M3/README.md`.
- Soumission de M4 (pas faite) : prérequis, réserve sur le littéraire et décisions pour Matisse dans `docs/SUBMISSION_M4.md`.
