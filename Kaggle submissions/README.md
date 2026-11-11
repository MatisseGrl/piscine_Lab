# Archives des entraînements

- `LOG.md` : journal des expériences et scores mesurés.
- `Kaggle.ipynb` : export des six essais de l'ablation, avec leurs sorties.
- `source-mix-74-18-8.ipynb` : export original de `notebook22e941a294.ipynb`, importé le 11 novembre 2026, avec code et sorties.
- `source-mix-74-18-8-evaluation.json` : copie de `evaluation (1).json`, cohérente avec la sortie du notebook (BPB 1,3324640181392153).
- `moliere_loss.png` et `moliere_samples.txt` : courbe et générations du mini-GPT initial.

Les fichiers du run 74/18/8 sont conservés sans modification. Le notebook fixe le kit à `3709c85ddaabfcd688d6eea80a5c5ed90605b549` et rapporte 100 007 936 tokens vus. L'évaluation indique le SHA-256 du tokenizer, mais pas celui du dataset ; il reste à récupérer depuis le manifeste du run. Aucun checkpoint ni corpus n'est inclus.

## Run 2 — Mélange à parts égales

Le [notebook exporté](run-02/piscine-source-mix.ipynb) conserve les logs de
l'entraînement CUDA et le [résultat brut](run-02/evaluation.json) détaille le BPB
par genre. Le code attend l'archive `source-mix-equal.zip` extraite en entrée,
ainsi qu'un environnement Kaggle avec GPU et Internet pour récupérer le kit.
Les métadonnées de l'export indiquent GPU et Internet désactivés.

Le flux local correspondant au manifeste contient 33 335 978 tokens Wikipédia FR,
33 335 979 Common Crawl et 33 335 979 Assemblée nationale parmi les tokens vus.
Pour atteindre ces quotas, 6 093 496 tokens de Common Crawl et 19 496 006 tokens
de l'Assemblée sont répétés. La comparaison au 80/12/8 inclut donc aussi
un changement de répétition.
