# colab

Plan B quand Kaggle est bloqué : `mix_run.ipynb` entraîne un mélange (M1 à M5) avec le même protocole que `kaggle/mix-template/script.py`. Jeton Kaggle via les Secrets Colab (`KAGGLE_API_TOKEN`), jamais dans le notebook. Ouvrir depuis GitHub : colab.research.google.com → GitHub → `MatisseGrl/piscine_Lab` → `colab/mix_run.ipynb`.

`remote_mix.py` lance l'entraînement depuis une session CLI, avec les morceaux du flux
et les métadonnées dans `/content/data/<mélange>/`. Le fichier `/content/data/MIX`
contient le nom du mélange. Le tokenizer correspondant est envoyé dans
`/content/data/tokenizer.json`. Sans fichier `/content/data/SEED`, la graine officielle
1337 s'applique. Un fichier `SEED` contenant `1338` lance un contrôle de bruit et
enregistre ses sorties dans `/content/run-<mélange>-s1338/`.
