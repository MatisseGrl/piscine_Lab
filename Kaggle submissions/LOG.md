# Journal des expériences

Une ligne par entraînement. Même config du kit pour tous les essais, sinon la comparaison ne vaut rien.

Comparaison planifiée sur les 230 documents publics du kit entre le brut contrôlé, le nettoyé et la sortie finale MinHash. Même tokenizer, même mélange par source, même configuration et même budget. Les lignes des trois runs seront importées depuis leurs résultats Kaggle.

| Date | ID | Données (mélange, étapes) | Tokens vus | Hash dataset | BPB val | Soumis | Conclusion |
|---|---|---|---|---|---|---|---|
| 2026-11-08 | bigram-bytes-a1 | Bigramme d'octets par comptage, lissage Laplace alpha=1, `moliere_train.txt` du kit (CRLF -> LF) | 1 536 283 octets (1 passe) | train sha256 a140c09cd253, val e5dde8f5782f | 3.3544 | non | Référence du bloc 1 à battre. alpha=0.1 donne 3.3405, mais choisi en regardant la val : non retenu comme référence. |
| 2026-11-08 | bpe-moliere-1024 | Tokenizer BPE octet (pas un modèle), 768 merges, pré-découpage en mots, `moliere_train.txt` du kit (CRLF -> LF) | 1 536 283 octets | merges sha256 9c7ba507e0b0 | — | non | Compression : 2,511 octets/token en train, 2,488 en val (512 : 2,015 en val). 1 024 retenu pour le bloc 1 (validé par Matisse). |
| 2026-11-08 | gpt-moliere-2700 | Train et validation Molière du kit (CRLF vers LF), BPE 1 024 | 11 059 200 | SHA-256 train `a140c09cd253ba891e081ef246afeae6bbc99870fdaff3763d62ddd95973862e`, val `e5dde8f5782f15943443cddb056bf9fd19efd67822b9e36a875e2c2970ede12c` | 1.8237 | non | AdamW, 2 700 pas, batch 32, taux 3e-4, graine 42, 4 threads CPU, ~26 min. Gain de 1,5307 BPB sur le bigramme. |
| 2026-11-10 | ablation-raw-151ca028be94 | Brut contrôlé, 80/12/8 en tokens | 100 007 936 | SHA-256 `151ca028be94476949cc43504323741076a017e63ca307dbc2dbc2240962d8f0` | 1.3537937339565447 | non | Référence sur les 230 documents publics. |
| 2026-11-10 | ablation-clean-71c5a146a046 | Nettoyé, 80/12/8 en tokens | 100 007 936 | SHA-256 `71c5a146a04676041e37b64d2d7e295a88f64915a304b22e523302c6872a4002` | 1.3340045107570024 | non | Baisse de 0.0197892 BPB par rapport à brut contrôlé. |
| 2026-11-11 | ablation-dedup-56ee10c62f6d | Dédupliqué (exact + MinHash), 80/12/8 en tokens | 100 007 936 | SHA-256 `56ee10c62f6d9c2a6c2d48a060c2eae3850819f46c62ecd782a2c0a7ee7faaad` | 1.3329558392762333 | non | Baisse de 0.00104867 BPB par rapport à nettoyé. |
| 2026-11-11 | ablation-quality-f6ad793c15f0 | Dédupliqué + qualité, 80/12/8 en tokens | 100 007 936 | SHA-256 `f6ad793c15f01cfbcc297e30048061b8619c769bb100e9d9a9b2bc4ffa94c9cf` | 1.3304248963817598 | non | Baisse de 0.00253094 BPB par rapport à dédupliqué (exact + minhash). |
| 2026-11-11 | ablation-pii-5b3b0e9d2c63 | Dédupliqué + PII, 80/12/8 en tokens | 100 007 936 | SHA-256 `5b3b0e9d2c63086425c0f6c76499fc2d2745b2ff8045d32788ccac99dc14d401` | 1.3321957183097648 | non | Baisse de 0.000760121 BPB par rapport à dédupliqué (exact + minhash). |
| 2026-11-11 | ablation-quality_pii-62d9a968e184 | Dédupliqué + qualité + PII, 80/12/8 en tokens | 100 007 936 | SHA-256 `62d9a968e184b11d2923f38188bfda3a1e5427369b3820cc9c17cff4870fd033` | 1.331524294931342 | non | Baisse de 0.00143154 BPB par rapport à dédupliqué (exact + minhash). |
