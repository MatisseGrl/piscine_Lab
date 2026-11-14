# Wikinews en français

| Champ | Valeur |
|---|---|
| Origine | Dump officiel Wikimedia `frwikinews-20261101-pages-articles.xml.bz2` ([dumps.wikimedia.org/frwikinews/20261101](https://dumps.wikimedia.org/frwikinews/20261101/)), 25 346 880 octets, MD5 `06ca2a718c9f281d14a94f0df234744a` (conforme à `md5sums.txt` publié), SHA-256 `7ae2fe2cf8857df30e33b2ee2030a39509dba588aacfc49dff4a136314af4d5f`. Génération du 1er novembre 2026 (MediaWiki 1.48.0-wmf.1). Texte de la dernière révision de chaque article de l'espace principal, sans redirections. |
| Licence | Les articles Wikinews FR sont sous [Creative Commons Attribution 2.5](https://creativecommons.org/licenses/by/2.5/deed.fr) d'après la page [Wikinews:Licence](https://fr.wikinews.org/wiki/Wikinews:Licence) ; l'API du site annonce aussi CC BY-SA 4.0 pour le contenu actuel (l'API `rightsinfo` renvoie CC BY-SA 4.0). Lequel s'applique à quel article n'est pas tranché : citer la source, les deux licences et garder les titres pour l'attribution. Usage pour l'entraînement : à confirmer par l'organisateur. |
| Volume | Avant : 24 220 pages de l'espace principal, 90 936 113 octets de wikitexte. Après retrait du wikitexte : 21 424 695 octets UTF-8. Après tout le pipeline : **19 309 documents, 20 768 387 octets UTF-8**. Tokens estimés avec le tokenizer 8 192 du kit (SHA-256 `b2554a82…2379`, +1 séparateur par document) : **5 483 404**. |
| Période couverte | Articles de 2005 à 2026 (le wikitexte contient des dates de 2005). Dates de dernière révision : 2007-04-04 → 2026-05-06. La date de rédaction de chaque article n'est pas extraite : à compléter. |
| Date de collecte | 2026-11-14 |
| Type de texte | Presse libre (dépêches et brèves rédigées par des contributeurs, beaucoup traduites de Wikinews anglais). |

## Répétitions nécessaires (budget 100 007 936 tokens, plafond ~3 répétitions)

| Part visée | Tokens | Répétitions |
|---|---:|---:|
| 5 % | 5 000 397 | 0,91 (une passe suffit) |
| 10 % | 10 000 794 | 1,82 |
| 25 % | 25 001 984 | 4,56 (**dépasse le plafond de 3**) |

À 3 répétitions, Wikinews ne peut fournir que 16 450 212 tokens, soit environ 16,4 % du budget. Le mélange M4 (5 %) tient en une passe.

## Risques

- Recouvrement avec la validation : 111 articles écartés par le filtre 13-grammes (0,46 % des pages, 190 027 octets), signe que la validation publique contient de la presse proche de Wikinews. Zéro recouvrement mesuré sur la sortie finale.
- Qualité très inégale : 4 101 articles sont des brèves de moins de 100 caractères hors espaces (écartés).
- Texte parfois traduit de l'anglais, fautes et typographie variables. Dates et noms propres réels : pas de masquage PII (décision du plan), seules les URL sont retirées avec le wikitexte.
- Le wikitexte est converti par des expressions régulières maison : quelques restes de mise en forme possibles (tableaux mal formés, liens non fermés). Contrôle fait sur l'échantillon : plus de modèles, de catégories, de liens `[[…]]`, de balises ni d'entités dans la sortie.
- Époque différente du reste du mélange pour les actualités (2005-2026).

## Traitement

Commande : `uv run python -m pipeline.wikinews --download` puis `uv run python -m pipeline.wikinews` (code dans `pipeline/wikinews.py`, graine 42, sortie `data/interim/wikinews/`, non versionnée). Chiffres complets dans [`wikinews-fr.stats.json`](wikinews-fr.stats.json).

1. Wikitexte → texte : retrait des commentaires, `<ref>`, galeries, balises, tableaux, modèles (on garde le contenu de `{{date|…}}`), images, catégories, liens interlangues, liens externes et URL nues ; les liens internes gardent leur libellé ; sections de fin (Sources, Articles connexes, Notes, Liens externes…) coupées avec tout ce qui suit ; restes de tableaux et d'images mal formés retirés.
2. Étapes existantes de `pipeline.clean` : ftfy (0 article modifié), filtre de contamination 13-grammes contre les 230 documents de validation publique et la validation Molière (111 rejets), langue fastText `lid.176.bin` première langue française, score ≥ 0,80 (191 `non_french`, 256 `low_confidence`), 29 vides.
3. Articles de moins de 100 caractères hors espaces : 4 101 rejetés (même seuil que le filtre Common Crawl).
4. Dédup exacte sur textes normalisés (minuscules, NFC, espaces) : 222 doublons retirés.
5. MinHash 0,97 (suites de 5 mots, 16 bandes de 6) : 1 quasi-doublon retiré.
6. Filtre qualité actuel (`pipeline.quality`, règle `low_letters`) : 0 rejet.
7. Pas de PII. Relecture finale : 0 document partageant 13 mots avec la validation. SHA-256 de `wikinews_fr.jsonl.gz` : `0735341f9c1308303ccd30e31a5375617d61a48b15475f298a637ffba12a0bdc`.

Les passes ne sont pas encore entrées dans `pipeline.build` ni dans les mélanges : la sortie est un JSONL gzip compatible avec `ftb.prepare` (champs `id`, `source`, `text`, `language_score`), l'`id` est `<id de page>:<id de révision>` et `titles.json` donne les titres.
