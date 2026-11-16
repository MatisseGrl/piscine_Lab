"""Génère toutes les courbes de la compétition (aucun entraînement relancé).

Lecture seule : on relit les train_log.jsonl / evaluation.json déjà produits
par les runs Kaggle/Colab et les result.json de l'ablation de pipeline.

Usage : python make_curves.py <dossier "Kaggle submissions"> <dossier runs> <dossier sortie>
"""
import json
import math
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # pas de fenêtre, on écrit juste des PNG
import matplotlib.pyplot as plt

KAGGLE = Path(sys.argv[1])  # contient mixes/, noise/, submission-quality/, run-02/
RUNS = Path(sys.argv[2])    # contient ablation/ et ablation-extra/
OUT = Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)

BRUIT_MOY, SEUIL = 1.3296, 0.005  # moyenne du bruit 80/12/8 et seuil de significativité (report/noise.md)


def lire_log(dossier):
    """Renvoie (steps, loss, lr) du train_log.jsonl d'un run (loss tous les 10 pas)."""
    steps, loss, lr = [], [], []
    with open(dossier / "train_log.jsonl", encoding="utf-8") as f:
        for ligne in f:
            if not ligne.strip():
                continue
            d = json.loads(ligne)
            if "loss" in d:  # la ligne finale val_bpb n'a pas de loss
                steps.append(d["step"]); loss.append(d["loss"]); lr.append(d["lr"])
    return steps, loss, lr


def lire_eval(dossier):
    """Renvoie le dict evaluation.json (bpb, octets_par_token...)."""
    chemin = dossier / "evaluation.json"
    if not chemin.exists():  # le run de bruit stocke son évaluation à côté du dossier
        chemin = dossier.parent / "../s1338-evaluation.json"
    return json.load(open(chemin, encoding="utf-8"))


def genres(dossier):
    """BPB par genre : lu sur la ligne val_bpb_par_genre du train_log."""
    for ligne in open(dossier / "train_log.jsonl", encoding="utf-8"):
        if ligne.strip():
            d = json.loads(ligne)
            if "val_bpb_par_genre" in d:
                return d["val_bpb_par_genre"]


def lisser(y, k=5):
    """Moyenne glissante centrée sur 2k+1 points (le log est bruité)."""
    return [sum(y[max(0, i - k):i + k + 1]) / len(y[max(0, i - k):i + k + 1]) for i in range(len(y))]


def loss_vers_bpb(loss, opt):
    """Conversion approximative loss/token -> bits/octet avec le ratio octets/token de la validation."""
    return [l / math.log(2) / opt for l in loss]


# ---- Tous les runs "mélanges" : (nom affiché, dossier, famille) ----
M = KAGGLE / "mixes"
RUNS_MIX = [
    ("Réf. 80/12/8 (qualité)", KAGGLE / "submission-quality", "ref"),
    ("Réf. 80/12/8 graine 1338", KAGGLE / "noise/s1338/run-noise", "ref"),
    ("M1 35/15/20/30", M / "M1", "mix"), ("M2 25x4", M / "M2", "mix"),
    ("M3 50/15/10/25", M / "M3", "mix"), ("M3 (Kaggle)", M / "M3-kaggle", "mix"),
    ("M5 60/12/8/20", M / "M5", "mix"),
    ("M4 40/15/15/25/5", M / "M4", "m4"), ("M4 graine 1338", M / "M4-s1338", "m4"),
    ("M4 officiel", M / "M4-official", "m4"),
    ("M4ORDER", M / "M4ORDER", "ordre"), ("M4WIKI", M / "M4WIKI", "ordre"),
    ("M4WIKIBPEORDER", M / "M4WIKIBPEORDER", "ordre"), ("M4REPEAT", M / "M4REPEAT", "ordre"),
    ("M4CLASS", M / "M4CLASS", "ordre"),
    ("M4BPE", M / "M4BPE", "bpe"), ("M4BPE graine 1338", M / "M4BPE-s1338", "bpe"),
    ("M4BPE50", M / "M4BPE50", "bpe"), ("M4BPE50 graine 1338", M / "M4BPE50-s1338", "bpe"),
    ("M4REFLOW", M / "M4REFLOW", "reflow"), ("M4REFLOW graine 1338", M / "M4REFLOW-s1338", "reflow"),
    ("M4REFLOWBPE", M / "M4REFLOWBPE", "best"), ("M4REFLOWBPE graine 1338", M / "M4REFLOWBPE-s1338", "best"),
    # Runs finaux du 15/11 (branche codex/competition-night)
    ("M4FINALEXCERPTS", M / "M4FINALEXCERPTS", "final"), ("M4FINALEXCERPTS graine 1338", M / "M4FINALEXCERPTS-s1338", "final"),
    ("M4FINALBOOK30", M / "M4FINALBOOK30", "final2"), ("M4FINALBOOK35", M / "M4FINALBOOK35", "final2"),
    ("M4FINALBOOKSHUFFLE", M / "M4FINALBOOKSHUFFLE", "final2"), ("M4FINALITALICS", M / "M4FINALITALICS", "final2"),
    ("M4FINALRETOK", M / "M4FINALRETOK", "final2"), ("M4FINALRETOK50", M / "M4FINALRETOK50", "final2"),
]
COUL = {"ref": "#888888", "mix": "#4c78a8", "m4": "#f58518", "ordre": "#b279a2",
        "bpe": "#54a24b", "reflow": "#e45756", "best": "#b6992d", "final": "#d62728", "final2": "#17becf"}
data = {}
for nom, dossier, fam in RUNS_MIX:
    s, l, lr = lire_log(dossier)
    data[nom] = dict(steps=s, loss=l, lr=lr, ev=lire_eval(dossier), fam=fam)

# ---- Ablation du pipeline (pas de log de loss conservé : seulement le BPB final) ----
PIPE = []
for nom, chemin in [("Brut contrôlé", "ablation/raw"), ("Nettoyé", "ablation/clean"),
                    ("Dédupliqué", "ablation/dedup"), ("+ PII", "ablation-extra/pii"),
                    ("+ qualité + PII", "ablation-extra/quality_pii"), ("+ qualité", "ablation-extra/quality")]:
    r = json.load(open(RUNS / chemin / "result.json", encoding="utf-8"))
    PIPE.append((nom, r["evaluation"]["bpb"]))
PIPE.append(("Mélange parts égales", lire_eval(KAGGLE / "run-02")["bpb"]))

# ====== Figure 1 : ablation du pipeline ======
fig, ax = plt.subplots(figsize=(9, 4.5))
noms = [p[0] for p in PIPE]; vals = [p[1] for p in PIPE]
bars = ax.bar(noms, vals, color=["#888"] + ["#4c78a8"] * 5 + ["#e45756"])
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.001, f"{v:.4f}", ha="center", fontsize=8)
ax.set_ylim(1.32, 1.36); ax.set_ylabel("BPB validation (plus bas = mieux)")
ax.set_title("Ablation des étapes du pipeline (80/12/8, même modèle, même budget)")
ax.axhspan(BRUIT_MOY - SEUIL, BRUIT_MOY + SEUIL, color="orange", alpha=.2, label="zone de bruit (±0,005)")
ax.legend(); plt.xticks(rotation=20, ha="right"); plt.tight_layout()
fig.savefig(OUT / "fig1_ablation_pipeline.png", dpi=150); plt.close(fig)

# ====== Figure 2 : BPB final de tous les runs (classement) ======
fig, ax = plt.subplots(figsize=(9, 10))
ordre = sorted(data, key=lambda n: data[n]["ev"]["bpb"], reverse=True)
ax.barh(ordre, [data[n]["ev"]["bpb"] for n in ordre], color=[COUL[data[n]["fam"]] for n in ordre])
for i, n in enumerate(ordre):
    ax.text(data[n]["ev"]["bpb"] + 0.0005, i, f"{data[n]['ev']['bpb']:.4f}", va="center", fontsize=7)
ax.axvline(BRUIT_MOY, color="k", ls="--", lw=1, label="moyenne bruit 80/12/8 = 1,3296")
ax.set_xlim(1.26, 1.36); ax.set_xlabel("BPB validation publique (plus bas = mieux)")
ax.set_title("Classement de tous les runs de compétition"); ax.legend(loc="lower right")
plt.tight_layout(); fig.savefig(OUT / "fig2_classement_runs.png", dpi=150); plt.close(fig)

# ====== Figure 3 : courbes d'entraînement du top 3 (+ référence M4) ======
TOP = [("M4 40/15/15/25/5", "#f58518"), ("M4REFLOW", "#54a24b"),
       ("M4REFLOWBPE", "#b6992d"), ("M4FINALEXCERPTS", "#d62728")]
fig, axs = plt.subplots(1, 3, figsize=(16, 4.8))
for nom, c in TOP:
    d = data[nom]; opt = d["ev"]["octets_par_token"]
    y = loss_vers_bpb(lisser(d["loss"]), opt)
    axs[0].plot(d["steps"], y, color=c, label=f"{nom} (final {d['ev']['bpb']:.4f})")
    axs[1].plot(d["steps"], y, color=c)
    axs[2].plot(d["steps"], d["lr"], color=c)
axs[0].set_ylim(1.2, 3.5); axs[0].set_title("Loss d'entraînement (≈ BPB), vue globale")
axs[1].set_xlim(1500, 3060); axs[1].set_ylim(1.18, 1.40); axs[1].set_title("Zoom sur la 2e moitié")
axs[2].set_title("Taux d'apprentissage (identique : config figée)")
for a in axs:
    a.set_xlabel("pas d'entraînement"); a.grid(alpha=.3)
axs[0].set_ylabel("bits par octet (approx.)"); axs[0].legend(fontsize=8)
plt.suptitle("Top 3 : courbes d'entraînement, graine 1337 (loss lissée, convertie avec le ratio octets/token de la validation)")
plt.tight_layout(); fig.savefig(OUT / "fig3_top3_entrainement.png", dpi=150); plt.close(fig)

# ====== Figure 4 : BPB final par genre, top 3 vs références ======
GEN = ["litteraire", "dialogue", "encyclopedique", "presse"]
dossiers = {"Réf. 80/12/8": KAGGLE / "submission-quality", "M4": M / "M4",
            "M4REFLOWBPE": M / "M4REFLOWBPE", "M4FINALEXCERPTS": M / "M4FINALEXCERPTS"}
fig, ax = plt.subplots(figsize=(10, 4.8)); w = 0.2
for i, (nom, dos) in enumerate(dossiers.items()):
    g = genres(dos); xs = [j + (i - 1.5) * w for j in range(4)]
    ax.bar(xs, [g[k] for k in GEN], w, label=nom, color=["#888", "#f58518", "#b6992d", "#d62728"][i])
    for x, k in zip(xs, GEN):
        ax.text(x, g[k] + 0.01, f"{g[k]:.2f}", ha="center", fontsize=7)
ax.set_xticks(range(4)); ax.set_xticklabels(["Littéraire", "Dialogue", "Encyclopédique", "Presse"])
ax.set_ylim(1.0, 1.75); ax.set_ylabel("BPB"); ax.legend(); ax.set_title("BPB par genre : d'où vient le gain ?")
plt.tight_layout(); fig.savefig(OUT / "fig4_par_genre.png", dpi=150); plt.close(fig)

# ====== Figure 5 : toutes les courbes d'entraînement (une vignette par run) ======
n = len(data); cols = 4; lignes = math.ceil(n / cols)
fig, axs = plt.subplots(lignes, cols, figsize=(16, 2.6 * lignes), sharex=True, sharey=True)
for a, nom in zip(axs.flat, data):
    d = data[nom]; opt = d["ev"]["octets_par_token"]
    a.plot(d["steps"], loss_vers_bpb(lisser(d["loss"]), opt), color=COUL[d["fam"]])
    a.set_ylim(1.2, 3.0); a.set_title(f"{nom}\nBPB final {d['ev']['bpb']:.4f}", fontsize=8); a.grid(alpha=.3)
for a in list(axs.flat)[n:]:
    a.axis("off")
plt.suptitle("Courbes d'entraînement de tous les runs (loss lissée ≈ BPB)"); plt.tight_layout()
fig.savefig(OUT / "fig5_toutes_les_courbes.png", dpi=130); plt.close(fig)

# ====== Figure 6 : progression du meilleur BPB au fil du projet ======
PROG = [("Brut", 1.3538), ("Nettoyé", 1.3340), ("Dédup", 1.3330), ("+ qualité", 1.3304),
        ("Mélange M4\n(+Gutenberg,\n+Wikinews)", 1.3028), ("+ BPE sur\nle mélange", 1.2992),
        ("+ recollage\nGutenberg", 1.2905), ("Recollage + BPE\n(final)", 1.2874)]
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.plot([p[0] for p in PROG], [p[1] for p in PROG], "o-", color="#b6992d", lw=2)
for i, p in enumerate(PROG):
    ax.annotate(f"{p[1]:.4f}", (i, p[1]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
ax.set_ylabel("BPB validation (graine 1337)"); ax.grid(alpha=.3)
ax.set_title("Progression du BPB : ce qui a fait baisser le score"); plt.tight_layout()
fig.savefig(OUT / "fig6_progression.png", dpi=150); plt.close(fig)
print("OK", sorted(os.listdir(OUT)))
