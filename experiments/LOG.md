# Journal des expériences

Une ligne par entraînement. Même config du kit pour tous les essais, sinon la comparaison ne vaut rien.

Comparaison planifiée sur les 230 documents publics du kit entre le brut contrôlé, le nettoyé et la sortie finale MinHash. Même tokenizer, même mélange par source, même configuration et même budget. Les lignes des trois runs seront importées depuis leurs résultats Kaggle.

| Date | ID | Données (mélange, étapes) | Tokens vus | Hash dataset | BPB val | Soumis | Conclusion |
|---|---|---|---|---|---|---|---|
| 2026-11-08 | bigram-bytes-a1 | Bigramme d'octets par comptage, lissage Laplace alpha=1, `moliere_train.txt` du kit (CRLF -> LF) | 1 536 283 octets (1 passe) | train sha256 a140c09cd253, val e5dde8f5782f | 3.3544 | non | Référence du bloc 1 à battre. alpha=0.1 donne 3.3405, mais choisi en regardant la val : non retenu comme référence. |
| 2026-11-08 | bpe-moliere-1024 | Tokenizer BPE octet (pas un modèle), 768 merges, pré-découpage en mots, `moliere_train.txt` du kit (CRLF -> LF) | 1 536 283 octets | merges sha256 9c7ba507e0b0 | — | non | Compression : 2,511 octets/token en train, 2,488 en val (512 : 2,015 en val). 1 024 retenu pour le bloc 1 (validé par Matisse). |
| 2026-11-08 | gpt-moliere-2700 | Train et validation Molière du kit (CRLF vers LF), BPE 1 024 | 11 059 200 | SHA-256 train `a140c09cd253ba891e081ef246afeae6bbc99870fdaff3763d62ddd95973862e`, val `e5dde8f5782f15943443cddb056bf9fd19efd67822b9e36a875e2c2970ede12c` | 1.8237 | non | AdamW, 2 700 pas, batch 32, taux 3e-4, graine 42, 4 threads CPU, ~26 min. Gain de 1,5307 BPB sur le bigramme. |
