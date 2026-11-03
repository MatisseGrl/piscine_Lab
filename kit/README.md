# kit

Kit officiel de la piscine : [Meuleur/Piscine](https://github.com/Meuleur/Piscine), cloné dans `kit/Piscine/` (commit 3709c85). Non versionné ici, jamais modifié : la config du modèle et les hyperparamètres de la compétition sont figés.

```bash
git clone https://github.com/Meuleur/Piscine kit/Piscine   # première fois
git -C kit/Piscine pull                                     # mises à jour (LEADERBOARD.md, correctifs)
```

| Chemin | Rôle |
|---|---|
| `corpus/moliere_train.txt`, `moliere_val.txt` | Bloc 1 : 25 pièces (1,6 Mo) / 3 pièces tenues à l'écart (Misanthrope, Avare, Sicilien). Éd. Chasles 1888, Gutenberg. Pièces séparées par `=====` |
| `config/official.json` | Config figée : 6 couches, 5 têtes, d_model 320, contexte 512, vocab 8 192, 100 M tokens vus, graine 1337 |
| `ftb/` | Modèle officiel, tokenizer (dont conversion depuis un BPE minbpe), prepare, train, evaluate (BPB), contamination, submit |
| `data/validation.jsonl` | Validation publique : 230 docs, 4 genres (encyclopédique, littéraire, presse, dialogue) à parts égales en octets |
| `notebooks/quickstart_colab.ipynb` | Toute la chaîne sur un T4 |
| `LEADERBOARD.md` | Classement, mis à jour par le mentor |
