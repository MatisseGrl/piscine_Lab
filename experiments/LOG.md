# Journal des expériences

Une ligne par entraînement. Même config du kit pour tous les essais, sinon la comparaison ne vaut rien.

| Date | ID | Données (mélange, étapes) | Tokens vus | Hash dataset | BPB val | Soumis | Conclusion |
|---|---|---|---|---|---|---|---|
| 2026-11-08 | bigram-bytes-a1 | Bigramme d'octets par comptage, lissage Laplace alpha=1, `moliere_train.txt` du kit (CRLF -> LF) | 1 536 283 octets (1 passe) | train sha256 a140c09cd253, val e5dde8f5782f | 3.3544 | non | Référence du bloc 1 à battre. alpha=0.1 donne 3.3405, mais choisi en regardant la val : non retenu comme référence. |
