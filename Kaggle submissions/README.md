# Essais Kaggle

Le notebook [Kaggle.ipynb](Kaggle.ipynb) regroupe les six essais d'ablation.
Le [journal](LOG.md) consigne les résultats et les empreintes des flux d'entraînement.

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
