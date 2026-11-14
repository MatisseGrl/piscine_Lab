# Préparer la soumission de M4 (non faite)

Rien n'a été soumis. Ce document dit ce qu'il faudrait faire et ce que Matisse doit trancher.

## Pourquoi M4

- BPB 1,3028 (Kaggle T4, graine 1337) contre 1,3296 de moyenne pour le 80/12/8 (σ 0,0023) : −0,027, soit environ 12 σ et très au-dessus du seuil de ~0,005.
- **Une seule graine** : à confirmer par une 2e graine (mixes-cd).
- Mélange : Wikipédia 40 / Common Crawl 15 / Assemblée 15 / Gutenberg 25 / Wikinews 5, dédup + qualité, sans PII. SHA-256 du flux `c6c628a6b44640db55654c68878a35d02748a860f7aad1ab4c9b9597349738a9`. Détails : ligne M4 de `Kaggle submissions/LOG.md`.

## État du paquet actuel

`submissions/2026-11-14_182456` est le run 80/12/8 (BPB 1,3315). Son `submission.json` pointe vers `dataset_url` = `.../piscine-ablation-extra`, **pas vers M4**. Il ne faut pas le modifier.

## Ce qu'il faut pour soumettre M4

1. **Un run officiel M4 avec checkpoint conservé.** Le run M4 déjà fait (`kaggle/mix-m4`, issu de `kaggle/mix-template/script.py`) a supprimé `ckpt.pt` (dernière ligne : `(out / "ckpt.pt").unlink()`), donc il n'y a rien à soumettre. Modification nécessaire dans une copie du script : supprimer cette ligne `unlink()` pour que `ckpt.pt` reste dans `/kaggle/working/run-M4/` (et donc dans les sorties du kernel), et récupérer aussi `train_log.jsonl`, `samples.txt`, `data_meta.json`, `tokenizer.json`. Aucun run poussé ici (les GPU sont gérés par mixes-cd). Le BPB du run officiel peut différer de 1,3028 (non-déterminisme GPU ~0,001).
2. **`python -m ftb.submit` en local** sur ce nouveau run, avec un nouveau `--dataset-url`. Options exactes de la commande : à compléter (voir le kit).
3. **Limite : 2 soumissions par jour.**

## Réserves

- Le gain de M4 vient surtout du **littéraire** (−0,126 ; dialogue −0,036 ; presse −0,006 ; encyclopédique +0,063). Le BPB global dépend du poids de chaque genre dans la validation.
- Le filtre 13-grammes ne protège pas contre un style proche de la validation publique (Gutenberg beaucoup plus présent) : le score caché peut s'écarter du score public.
- Une seule graine.

## Décisions qui attendent Matisse

1. Soumettre M4 ou garder le 80/12/8 (ou attendre M2/M5 et la 2e graine).
2. Quel `--dataset-url` : le dataset Kaggle `piscine-mix-m4` est **privé**, le mentor ne pourra pas l'ouvrir. Le rendre public, ou publier ailleurs (Hugging Face) ?
3. Autoriser un run officiel M4 avec checkpoint conservé (GPU, via mixes-cd).
4. Quel jour soumettre, vu la limite de 2 par jour et le gel des expériences (dimanche 15/11 à 20 h).
