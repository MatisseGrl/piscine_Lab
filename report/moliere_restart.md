# Reprise Molière : objectif 1,500 BPB et réparation des échanges

Pause demandée le 11/11. Les quatre entraînements de cette reprise ont été arrêtés. La page sur le port 8765 sert toujours le checkpoint du pas 1 000 de la PR #23.

| Essai | Dernier palier sauvegardé | Résultat au moment de l'arrêt |
|---|---|---|
| Continuation du train officiel, taux 2,5e-4 | `runs/deep-moliere-a/step-400.pt` | 1,790130 BPB, moins bon que le cosinus à 1,770614 |
| SFT réparation | `runs/chat-repair-a/step-250.pt` | 1,853007 BPB, 0/8 réparations pertinentes sur le développement, comme le chat précédent |
| Continuation avec dropout 0,1 | Aucun | Arrêt avant le premier palier |
| Continuation exploratoire avec cinq pièces Wikisource | Aucun | Arrêt avant le premier palier |

Les poids des deux paliers sont lisibles. La cible de 1,500 n'est pas atteinte et aucun nouveau modèle de chat n'a été retenu. Les réponses du premier palier de réparation sont dans `runs/chat-repair-a/repair-250-saved.json`. Le test inédit de réparation n'a pas été exécuté. Les huit cas de développement incluent une réplique hors sujet imposée, suivie d'une demande de clarification : cette mesure ne remplace pas l'évaluation d'une vraie discussion.

Le nouveau SFT rééquilibre le corpus v2 et ajoute 1 710 scénarios de réparation ou de clarification. La mauvaise réponse apparaît uniquement en entrée. 4 641 conversations au total, SHA-256 `4da4b69159d1541e2a1defca93e32cefee53ea562fb5409557d9ae8f7e0a4609`. L'audit ne trouve ni question réservée ni séquence commune de 13 mots avec la validation. L'échange signalé par Matisse a inspiré les exemples : il doit servir de test de régression et non de test inédit.

Les cinq pièces supplémentaires forment un essai exploratoire séparé de la référence du kit. Elles sont absentes du manifeste officiel et n'ont aucun recouvrement de 13 mots avec la validation. Les textes de Molière sont du domaine public ; pages et révisions Wikisource sous CC BY-SA 4.0 dans `runs/moliere-extra/manifest.json`. La fiche [Wikisource Molière](../sources/wikisource-moliere.md) décrit la collecte. L'export filtré compte 504 088 octets, SHA-256 `c4e30f6df669089fbc2cb013cdb45dd76588efb408e310167c5d8b46cb7a4f26`. Aucun texte n'entre dans les données de compétition.

## Reprendre les essais

Depuis le worktree `C:\Users\mgarl\Documents\piscine_Lab\runs\worktree-moliere-demo` :

```powershell
& .\scripts\run_moliere_night.ps1
```

Le script relance les quatre essais en série depuis leurs poids de départ, dans un nouveau `runs/night-…` ; il ne reprend pas l'état exact d'un entraînement interrompu. `-PlanOnly` vérifie les fichiers d'entrée et affiche les commandes sans lancer les entraînements. Les journaux et checkpoints sont dans le nouveau dossier. Pour la reprise, comparer le BPB au cosinus sans changer la validation, choisir le chat sur les mesures de développement, puis seulement mesurer les réparations inédites et tester le navigateur.
