# Mini-GPT Molière : continuation et pilote conversationnel

Date : 11 novembre 2026. Bloc 1 uniquement.

## Résultat

| Essai | BPB Molière | Décision |
|---|---:|---|
| Référence, 2 700 pas | 1,823678 | Conservée intacte |
| Continuation cosinus, 1 000 pas | **1,770614** | Meilleur BPB, gain de 2,91 % |
| Continuation constante, 1 000 pas | 1,778539 | Moins bon que le cosinus |
| SFT sur répliques authentiques, 400 pas | 1,889077 | Non retenu pour remplacer le modèle |

Les deux continuations partent du même checkpoint et des mêmes tirages, avec un nouvel AdamW (l'ancien état n'était pas sauvegardé). Batch 32, contexte 128, graine 142, quatre threads CPU. Taux cosinus 1e-4 → 1e-5, taux constant 1e-4. Durées : 541 et 534 secondes, évaluations et échantillons compris. Même tokenizer et même évaluation BPB que la référence.

## Règles et données

Le sujet décrit le bloc 1 comme un modèle entraîné sur Molière à partir du corpus du kit. Il ne précise pas expressément le régime des dialogues supplémentaires pour ce bloc. Les décisions du projet imposent le train du kit seul : ce pilote respecte cette limite conservatrice. La règle de 20 % synthétique apparaît dans la compétition et n'est pas transposée au bloc 1. Aucun texte synthétique d'entraînement, modèle externe, poids externes, ni changement du bloc 3.

7 403 paires consécutives candidates extraites du train, 5 920 retenues après limite de contexte. Les noms de personnages sont remplacés par SGANARELLE et DON JUAN ; les espaces sont normalisés, les répliques ne sont pas réécrites. Les scènes et paragraphes intermédiaires cassent les paires. Ces échanges ne sont pas tous des questions/réponses autonomes : beaucoup dépendent de la scène originale, une limite importante.

Train SHA-256 : `a140c09cd253ba891e081ef246afeae6bbc99870fdaff3763d62ddd95973862e`.

Paires SHA-256 : `0339142225f83eee909c59a135834c1a678203697b0631003dd8bb81dddc5b02`.

Tokenizer SHA-256 : `9c7ba507e0b0bc27ad602faf40282e03a4d89d4ce58b67a258af10fbc8b5e6f4`.

## Protocole SFT et évaluation

Départ : meilleur checkpoint cosinus. 400 pas fixés avant consultation des sorties, batch 16, AdamW 5e-5, graine 2026. La loss ne porte que sur les tokens de réponse et sa fin de réplique. La question et le padding ont une cible -100 ; le premier token de réponse est bien supervisé. Les tests vérifient les gradients nuls sur les positions ignorées.

Huit questions inédites sont définies avant le pilote, vérifiées absentes du texte de préentraînement normalisé, jamais utilisées dans les gradients ni pour sélectionner les pas. Les deux questions courtes déjà utilisées par Matisse sont des diagnostics séparés. Aucun historique de conversation. Température 0,7, 80 nouveaux tokens, graine 42 réinitialisée pour chaque question. L'interface coupe à la première ligne vide ; aucune correction des sorties.

La réinitialisation de graine par question diffère d'une session interactive continue, où le générateur avance : les sorties après la première question peuvent donc différer des anciens essais manuels.

Critère de pertinence : réponse compréhensible qui accomplit la demande (saluer, dire son état, donner un nom, consoler, accepter/refuser une aide, accuser réception d'un remerciement ou prendre congé). Relecture qualitative par l'assistant, pas annotation indépendante : **0/8 réponses pertinentes pour chacun des trois checkpoints** sur ce petit lot, à cette graine. Cela ne mesure pas toutes les générations possibles. Pas de test statistique ni de revendication d'amélioration du style.

## Toutes les générations affichées

### 1. bonjour

Diagnostic déjà essayé.

**Référence 1,8237**

> Vous voyez bonne, et courons-nous,
> Rhicras, seul.

**Après continuation 1,7706**

> Vous voyez un peu, et sa femme est une bonne
> Qui d'expose une autre.

**Après SFT**

> Vous voyez un peu, et je vous en ai vu faire.

Verdict : hors sujet ou incohérent, pas de réussite validée.

### 2. tu vas bien ?

Diagnostic déjà essayé.

**Référence 1,8237**

> Vous voyez bonne, et sachante, à Clitidès.

**Après continuation 1,7706**

> Vous voyez que j'aurai bien fait, et je ne sais pas bien.

**Après SFT**

> Vous serez bonne, et courons-nous faire.

Verdict : hors sujet ou incohérent, pas de réussite validée.

### 3. Bonjour monsieur, êtes-vous de bonne humeur ce matin ?

Question inédite réservée au test.

**Référence 1,8237**

> Vous voyez que j'ai voulu, je ne vous ai pas davantagé,
> Et que quoi vous vous trouvsiez donc...

**Après continuation 1,7706**

> Vous voyez que j'aille, et que je vous ai dit d'extravagine.

**Après SFT**

> Vous serez bonne, et vous en souffrir, Et dès que je sois.

Verdict : hors sujet ou incohérent, pas de réussite validée.

### 4. Dites-moi, comment vous portez-vous aujourd'hui ?

Question inédite réservée au test.

**Référence 1,8237**

> Vous serez bonne, àpuis-je! Charharlot, à part.

**Après continuation 1,7706**

> Vous serez bonne, etpendant que je vous ai dit d'extrace.

**Après SFT**

> Vous serez bonne, et vous en souffrir Clitidas.

Verdict : hors sujet ou incohérent, pas de réussite validée.

### 5. Je vous salue, voulez-vous bien me saluer aussi ?

Question inédite réservée au test.

**Référence 1,8237**

> Vous voyez que j'en vais être en telon.

**Après continuation 1,7706**

> Vous serez bonne, et sa femme, à tort à la fin.

**Après SFT**

> Vous serez bonne, et courons-nous faire.

Verdict : hors sujet ou incohérent, pas de réussite validée.

### 6. Quel nom dois-je employer pour vous appeler, monsieur ?

Question inédite réservée au test.

**Référence 1,8237**

> Vous voyez que j'ai voulu, aurois-vous d'expliquer ainsi:
> Enfin, je vous l'avouerai mon habile,
> Et faites-moi tout à ma navelle éclat?

**Après continuation 1,7706**

> Vous serez bonne, àpuis qu'à Charlotte, et me donne bien annime
> d'abordsé de battre ou d'une grande tendresse.

**Après SFT**

> Vous serez bonne, et vous en souffrir Clitidas.

Verdict : hors sujet ou incohérent, pas de réussite validée.

### 7. Je suis fort triste ce soir, pouvez-vous me consoler ?

Question inédite réservée au test.

**Référence 1,8237**

> Vous voyez, madame, àpuis qu'à Charlotte,
> Après ce charmé du ciel, mon amour en l'échème;
> Et songe, dans vos yeux le raison,
> Son n'a généreux, sans doute, et ce valet,
> J'ai seigneur Alb

**Après continuation 1,7706**

> Vous êtes bien bonne, etpendant la tête.

**Après SFT**

> Vous serez bonne, et sa femme, a-t-on d'expose une chose.

Verdict : hors sujet ou incohérent, pas de réussite validée.

### 8. Accepteriez-vous de m'aider dans une petite affaire ?

Question inédite réservée au test.

**Référence 1,8237**

> Vous voyez que j'aille, pour la bonne ordre, c'est une chose.

**Après continuation 1,7706**

> Vous êtes bien bonne, etpendant que ta femme destinée.

**Après SFT**

> Vous êtes bien bonne, et vous en souhaiter à la fenêtre.

Verdict : hors sujet ou incohérent, pas de réussite validée.

### 9. Je vous remercie de votre aide, mon cher ami.

Question inédite réservée au test.

**Référence 1,8237**

> Vous voyez, madame, àpuis qu'à Charlus,
> Je me donne bien chargé.

**Après continuation 1,7706**

> Vous serez bonne, etpercevant Charlotte.

**Après SFT**

> Vous serez bonne, et vous l'aviez pris, si je vous ai pris.

Verdict : hors sujet ou incohérent, pas de réussite validée.

### 10. Il est temps pour moi de partir, je vous souhaite une bonne soirée.

Question inédite réservée au test.

**Référence 1,8237**

> Vous voyez que j'ai voulu, afin, à la fierté, et je m'y consens;
> Lorsqu'un, de besser le d'une femme, et l'engagez ma navelle
> en va doser sans croire en ce vie, de capable
> On diroit,

**Après continuation 1,7706**

> Vous êtes bien bonne, etpendant que je vous ai dit d'extravagance.

**Après SFT**

> Vous serez bonne, et vous l'avantage à la fin que je te promets.

Verdict : hors sujet ou incohérent, pas de réussite validée.

## Conclusion et fichiers

Le gain BPB est établi ; l'objectif conversationnel n'est pas atteint. Le pilote ne prouve pas que tout SFT échouerait, mais la simple remise en forme des répliques ne suffit pas ici. Une prochaine expérience devrait d'abord construire et vérifier des paires autonomes pertinentes provenant du train, et réserver de nouvelles questions de test : celles-ci sont maintenant connues. Tout ajout extérieur demande une clarification explicite du cadre du bloc 1, pas une déduction depuis les règles du bloc 3.

Meilleur checkpoint : `runs/moliere-continuation-20261111/cosine/best.pt`. Essai SFT : `runs/moliere-dialogue-20261111/dialogue.pt`. Référence inchangée : `checkpoints/moliere_gpt.pt`. `model`, `config` et `val_bpb` restent compatibles avec `minigpt/chat.py`, qui n'a pas été modifié dans cette tâche.

Les JSON bruts, manifestes, paires, historiques de mesures et checkpoints sont dans les deux dossiers `runs/`. Les sorties affichées sont aussi enregistrées dans `report/moliere_generations.json`.

Les quatre BPB du tableau ont été recalculés sur la validation Molière à partir des checkpoints locaux. Les 30 générations affichées correspondent aux sorties enregistrées dans le run du pilote.
Les 39 tests mini-GPT passent, dont les quatre tests de continuation et de dialogue.
