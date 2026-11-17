"""Génère le PowerPoint de soutenance « Feed the Beast » (8 diapos).

Tous les chiffres viennent de `Kaggle submissions/LOG.md`, `report/ablation.md`,
`report/courbes/RAPPORT_COURBES.md` et `report/chat_demo.md`. Rien n'est inventé :
si un chiffre change dans ces fichiers, on le change ici puis on regénère.

Usage (depuis la racine du dépôt) :
    uv run --with python-pptx python report/build_deck.py
"""
import re
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# Fichier produit (la version « demo » seule est remplacée par cette soutenance complète)
SORTIE = Path(__file__).resolve().parent / "Feed-the-Beast-soutenance.pptx"
NB_DIAPOS = 8

# ---------- Palette : théâtre (bordeaux dominant, or en accent, encre pour le fond sombre) ----------
ENCRE = RGBColor(0x1B, 0x1A, 0x24)      # fond sombre et texte principal
BORDEAUX = RGBColor(0x7A, 0x1F, 0x2E)   # couleur dominante
OR = RGBColor(0xC8, 0x96, 0x3E)         # accent : le résultat final
ROSE = RGBColor(0xC9, 0x9A, 0xA3)       # nuance claire du bordeaux
GRIS = RGBColor(0x6B, 0x6B, 0x76)       # texte secondaire
GRIS_CLAIR = RGBColor(0xA9, 0xA8, 0xB3) # barres de référence
TEINTE = RGBColor(0xF2, 0xF1, 0xF5)     # fond des cartes sur diapo claire
CARTE_SOMBRE = RGBColor(0x2A, 0x28, 0x35)
BLANC = RGBColor(0xFF, 0xFF, 0xFF)

TITRE = "Cambria"   # police des titres (serif, ambiance théâtre)
CORPS = "Calibri"   # police du texte (rendu fiable partout)


# ---------- Petits outils de mise en page ----------
def fr(chaine):
    """Typographie française : espace insécable avant « % » et dans les nombres à milliers (1 836)."""
    chaine = chaine.replace(" %", " %")
    return re.sub(r"(?<=\d) (?=\d{3}(?!\d))", " ", chaine)


def texte(diapo, x, y, w, h, paragraphes, taille=14, couleur=ENCRE, gras=False,
          police=CORPS, align=PP_ALIGN.LEFT, ancre=MSO_ANCHOR.TOP, nom=None,
          espace_apres=0):
    """Ajoute une zone de texte sans marge interne.

    `paragraphes` est une chaîne, ou une liste de paragraphes ; chaque paragraphe est une
    chaîne ou une liste de segments (texte, options) avec options = dict(taille, gras, couleur,
    police, italique).
    """
    zone = diapo.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if nom:
        zone.name = nom
    cadre = zone.text_frame
    cadre.word_wrap = True
    cadre.margin_left = cadre.margin_right = cadre.margin_top = cadre.margin_bottom = 0
    cadre.vertical_anchor = ancre
    if isinstance(paragraphes, str):
        paragraphes = [paragraphes]
    for i, para in enumerate(paragraphes):
        p = cadre.paragraphs[0] if i == 0 else cadre.add_paragraph()
        p.alignment = align
        p.space_after = Pt(espace_apres)
        segments = [(para, {})] if isinstance(para, str) else para
        for contenu, opts in segments:
            r = p.add_run()
            r.text = fr(contenu)
            r.font.size = Pt(opts.get("taille", taille))
            r.font.bold = opts.get("gras", gras)
            r.font.italic = opts.get("italique", False)
            r.font.name = opts.get("police", police)
            r.font.color.rgb = opts.get("couleur", couleur)
    return zone


def forme(diapo, x, y, w, h, fond, type_forme=MSO_SHAPE.ROUNDED_RECTANGLE, rayon=0.06, nom=None):
    """Ajoute un rectangle (arrondi par défaut) plein, sans contour."""
    f = diapo.shapes.add_shape(type_forme, Inches(x), Inches(y), Inches(w), Inches(h))
    if nom:
        f.name = nom
    f.fill.solid()
    f.fill.fore_color.rgb = fond
    f.line.fill.background()
    f.shadow.inherit = False
    if type_forme == MSO_SHAPE.ROUNDED_RECTANGLE:
        f.adjustments[0] = rayon
    return f


def etiquette(diapo, x, y, w, h, fond, lignes, taille=13, couleur=BLANC, gras=True, police=CORPS, nom=None):
    """Forme pleine avec texte centré (utilisée pour les boîtes du schéma)."""
    f = forme(diapo, x, y, w, h, fond, nom=nom)
    cadre = f.text_frame
    cadre.word_wrap = True
    cadre.margin_left = cadre.margin_right = Inches(0.05)
    cadre.margin_top = cadre.margin_bottom = Inches(0.03)
    cadre.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, ligne in enumerate(lignes):
        p = cadre.paragraphs[0] if i == 0 else cadre.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = fr(ligne)
        r.font.size = Pt(taille)
        r.font.bold = gras
        r.font.name = police
        r.font.color.rgb = couleur
    return f


def fond_diapo(diapo, couleur):
    """Colore le fond de toute la diapo."""
    diapo.background.fill.solid()
    diapo.background.fill.fore_color.rgb = couleur


def entete(diapo, rubrique, titre, sombre=False):
    """Rubrique en petites capitales + titre-message, au même endroit sur chaque diapo."""
    texte(diapo, 0.6, 0.4, 9, 0.3, rubrique, taille=12, gras=True,
          couleur=OR if sombre else BORDEAUX, nom="Rubrique")
    texte(diapo, 0.6, 0.72, 12.1, 0.8, titre, taille=30, gras=True, police=TITRE,
          couleur=BLANC if sombre else ENCRE, nom="Titre")


def pied(diapo, numero, sombre=False):
    """Pied de page : auteur à gauche, numéro à droite."""
    c = GRIS_CLAIR if sombre else GRIS
    texte(diapo, 0.6, 7.03, 8, 0.25, "Feed the Beast  ·  Matisse Garlot  ·  ECE IA Lab", taille=10, couleur=c,
          nom="Pied")
    texte(diapo, 11.2, 7.03, 1.53, 0.25, f"{numero} / {NB_DIAPOS}", taille=10, couleur=c,
          align=PP_ALIGN.RIGHT, nom="Numéro")


def notes(diapo, contenu):
    """Notes de l'orateur (ce que Matisse dit à l'oral)."""
    diapo.notes_slide.notes_text_frame.text = contenu


def style_graphique(graphique, taille=11, couleur=GRIS):
    """Police et couleur communes à tous les graphiques."""
    graphique.font.size = Pt(taille)
    graphique.font.name = CORPS
    graphique.font.color.rgb = couleur


def tableau(diapo, x, y, largeurs, lignes, hauteur_ligne=0.5, taille=12, nom=None):
    """Tableau sobre : entête bordeaux, lignes alternées blanc / teinte."""
    forme_t = diapo.shapes.add_table(len(lignes), len(largeurs), Inches(x), Inches(y),
                                     Inches(sum(largeurs)), Inches(hauteur_ligne * len(lignes)))
    if nom:
        forme_t.name = nom
    t = forme_t.table
    for j, l in enumerate(largeurs):
        t.columns[j].width = Inches(l)
    for i, ligne in enumerate(lignes):
        t.rows[i].height = Inches(hauteur_ligne)
        for j, valeur in enumerate(ligne):
            cellule = t.cell(i, j)
            cellule.margin_left = cellule.margin_right = Inches(0.1)
            cellule.margin_top = cellule.margin_bottom = Inches(0.04)
            cellule.vertical_anchor = MSO_ANCHOR.MIDDLE
            cellule.fill.solid()
            cellule.fill.fore_color.rgb = BORDEAUX if i == 0 else (BLANC if i % 2 else TEINTE)
            cadre = cellule.text_frame
            cadre.word_wrap = True
            p = cadre.paragraphs[0]
            r = p.add_run()
            r.text = fr(valeur)
            r.font.size = Pt(taille)
            r.font.name = CORPS
            r.font.bold = (i == 0)
            r.font.color.rgb = BLANC if i == 0 else ENCRE
    return forme_t


prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
VIDE = prs.slide_layouts[6]  # mise en page vide : tout est posé à la main

# =====================================================================================
# 1. Titre
# =====================================================================================
d = prs.slides.add_slide(VIDE)
fond_diapo(d, ENCRE)
texte(d, 0.8, 0.9, 8, 0.3, "ECE IA LAB  ·  PISCINE I LAB  ·  SOUTENANCE", taille=13, gras=True, couleur=OR)
texte(d, 0.8, 1.7, 7.4, 1.3, "Feed the Beast", taille=66, gras=True, police=TITRE, couleur=BLANC, nom="Titre")
texte(d, 0.8, 3.2, 6.6, 1.6,
      "Un mini-GPT codé from scratch, un pipeline de données français, et une compétition "
      "où seul le dataset fait la différence.",
      taille=20, couleur=RGBColor(0xDD, 0xDC, 0xE4))
texte(d, 0.8, 6.2, 7, 0.6, [[("Matisse Garlot", {"gras": True, "couleur": BLANC})],
                            "ING4 Data & IA  ·  rendu du 16 novembre 2026"],
      taille=14, couleur=GRIS_CLAIR)
# Bloc résultat à droite : le chiffre qui résume tout
forme(d, 8.5, 1.4, 4.0, 4.6, CARTE_SOMBRE, rayon=0.04, nom="Carte résultat")
texte(d, 8.85, 1.75, 3.3, 0.3, "RÉSULTAT FINAL", taille=12, gras=True, couleur=OR)
texte(d, 8.85, 2.15, 3.4, 1.2, "1,2767", taille=66, gras=True, police=TITRE, couleur=OR, nom="Score final")
texte(d, 8.85, 3.45, 3.3, 0.4, "bits par octet (BPB)", taille=16, couleur=BLANC)
texte(d, 8.85, 4.2, 3.4, 1.6,
      ["contre 1,3538 avec les données brutes", "soit −5,7 % avec le même modèle",
       "validation publique du kit"],
      taille=14, couleur=GRIS_CLAIR, espace_apres=6)
notes(d, "Le modèle est le même pour tout le monde : c'est la donnée qui change le score. "
         "Résultat : 1,2767 BPB sur la validation publique, contre 1,3538 pour les données brutes, "
         "avec exactement la même architecture, le même budget et le même nombre de pas.")

# =====================================================================================
# 2. Le projet en un coup d'œil
# =====================================================================================
d = prs.slides.add_slide(VIDE)
entete(d, "LE PROJET", "Trois blocs, une idée : la donnée fait le modèle")
cartes = [
    ("BLOC 1", "Mini-GPT from scratch", "1,41 BPB", "validation Molière, pré-entraîné (bigramme : 3,35)",
     "Autograd maison, bigramme, BPE, transformer décodeur (attention causale, LayerNorm, résiduels). "
     "Tests écrits avant le code, comparés à PyTorch."),
    ("BLOC 2", "Pipeline de données", "320 098 docs", "1,05 Go de texte français, 5 sources",
     "Collecte, nettoyage, déduplication exacte + MinHash, filtre qualité, tokenizer. "
     "Une commande régénère le flux, graines fixées."),
    ("BLOC 3", "Compétition", "1,2767 BPB", "validation publique (1,2786 en graine 1338)",
     "Modèle et budget figés : seul le dataset change. 23 runs de mélange comparés, "
     "bruit mesuré avant de conclure."),
]
largeur_carte = (12.13 - 2 * 0.3) / 3
for i, (bloc, titre_c, gros, legende, corps) in enumerate(cartes):
    x = 0.6 + i * (largeur_carte + 0.3)
    forme(d, x, 1.8, largeur_carte, 3.75, TEINTE, nom=f"Carte {bloc}")
    texte(d, x + 0.3, 2.0, largeur_carte - 0.6, 0.3, bloc, taille=12, gras=True, couleur=BORDEAUX)
    texte(d, x + 0.3, 2.3, largeur_carte - 0.6, 0.45, titre_c, taille=20, gras=True, police=TITRE)
    texte(d, x + 0.3, 2.9, largeur_carte - 0.6, 0.75, gros, taille=36, gras=True, police=TITRE, couleur=BORDEAUX)
    texte(d, x + 0.3, 3.65, largeur_carte - 0.6, 0.3, legende, taille=12, couleur=GRIS)
    texte(d, x + 0.3, 4.1, largeur_carte - 0.6, 1.4, corps, taille=14)
forme(d, 0.6, 5.85, 12.13, 1.0, ENCRE, nom="Règle du jeu")
texte(d, 0.9, 5.97, 6.6, 0.8,
      [[("Règle du jeu  ", {"gras": True, "couleur": OR}),
        ("Même architecture (≈ 10 M de paramètres), mêmes hyperparamètres, même budget : "
         "100 007 936 tokens, une T4, moins d'une heure.", {})]],
      taille=13, couleur=BLANC, ancre=MSO_ANCHOR.MIDDLE)
texte(d, 7.9, 5.97, 4.5, 0.8,
      [[("Démo  ", {"gras": True, "couleur": OR}),
        ("chat façon Molière avec le mini-GPT du bloc 1, demandé par le mentor.", {})]],
      taille=13, couleur=BLANC, ancre=MSO_ANCHOR.MIDDLE)
pied(d, 2)
notes(d, "Trois blocs : un mini-GPT écrit de zéro, un pipeline qui transforme du web brut en données propres, "
         "et la compétition où le modèle est figé. La métrique est le BPB, bits par octet UTF-8, indépendante du "
         "tokenizer, donc comparable entre toutes les données. Le chat façon Molière est la démo demandée par JB.")

# =====================================================================================
# 3. Architecture technique
# =====================================================================================
d = prs.slides.add_slide(VIDE)
entete(d, "ARCHITECTURE TECHNIQUE", "Du texte brut au score : deux chaînes")
texte(d, 0.6, 1.68, 9, 0.3, "CHAÎNE DONNÉES  ·  blocs 2 et 3  ·  dossier pipeline/", taille=12, gras=True, couleur=BORDEAUX)
chaine_a = [
    ("Collecte", "5 sources, une fiche par source", "collect.py"),
    ("Nettoyage", "ftfy, fastText ≥ 0,80, boilerplate", "clean.py"),
    ("Dédup + qualité", "SHA-256, MinHash 0,97, filtres", "dedup.py, quality.py"),
    ("Gutenberg", "lignes recollées, extraits de livres", "gutenberg_reflow.py"),
    ("Mélange", "40 / 15 / 15 / 25 / 5, compté en tokens", "mixes.py"),
    ("BPE 8 192", "appris sur 10 Mo du mélange", "tokenizer du kit"),
    ("Entraînement", "T4, 3 052 pas, 100 007 936 tokens", "ftb.train"),
    ("Évaluation", "230 textes publics, BPB en octets UTF-8", "ftb.evaluate"),
]
chaine_b = [
    ("Value", "autograd, vérifié contre PyTorch", "value.py"),
    ("Bigramme", "comptage : point de comparaison", "bigram.py"),
    ("BPE", "tokenizer écrit à la main", "bpe.py"),
    ("Transformer", "décodeur, attention causale", "model.py"),
    ("Entraînement", "boucle, loss et BPB", "train.py"),
    ("Pretrain", "12,8 M de param., contexte 512", "pretrain.py"),
    ("SFT chat", "dialogues, rappel Molière 30 %", "chat_sft.py"),
    ("Page web", "HTML local, 127.0.0.1:8765", "web_chat.py"),
]


def dessiner_chaine(y_boite, h_boite, y_legende, liste, fond_boites, fond_dernier, couleur_dernier):
    """Dessine une rangée de 8 boîtes reliées par des flèches, avec une légende sous chaque boîte."""
    pas = 1.5457
    for i, (nom_etape, detail, fichier) in enumerate(liste):
        x = 0.6 + i * pas
        dernier = i == len(liste) - 1
        etiquette(d, x, y_boite, 1.3, h_boite, fond_dernier if dernier else fond_boites, [nom_etape],
                  taille=12, couleur=couleur_dernier if dernier else BLANC, nom=f"Étape {nom_etape}")
        texte(d, x, y_legende, 1.34, 1.0,
              [[(detail, {})], [(fichier, {"italique": True, "couleur": BORDEAUX})]],
              taille=11, couleur=GRIS, espace_apres=2)
        if not dernier:
            fleche = forme(d, x + 1.3 + 0.03, y_boite + h_boite / 2 - 0.1, 0.19, 0.2, GRIS_CLAIR,
                           type_forme=MSO_SHAPE.RIGHT_ARROW)
            fleche.name = "Flèche"


dessiner_chaine(2.0, 0.85, 2.95, chaine_a, BORDEAUX, OR, ENCRE)
texte(d, 0.6, 4.12, 9, 0.3, "CHAÎNE MODÈLE  ·  bloc 1 et démo  ·  dossier minigpt/", taille=12, gras=True, couleur=BORDEAUX)
dessiner_chaine(4.44, 0.85, 5.39, chaine_b, ENCRE, ENCRE, BLANC)
forme(d, 0.6, 6.4, 12.13, 0.5, TEINTE, nom="Outils")
texte(d, 0.8, 6.4, 11.8, 0.5,
      [[("Outils  ", {"gras": True, "couleur": BORDEAUX}),
        ("uv, Python 3.12, PyTorch, pytest (202 tests), Kaggle CLI et Colab (T4), git : une branche et une PR par tâche", {})]],
      taille=13, ancre=MSO_ANCHOR.MIDDLE)
pied(d, 3)
notes(d, "Deux chaînes. En haut, les données : on collecte cinq sources, on nettoie, on déduplique, on filtre, "
         "on recolle les livres Gutenberg, on mélange en tokens, on apprend le BPE, puis on lance l'entraînement "
         "officiel du kit sur une T4 et on mesure le BPB sur 230 textes. En bas, le mini-GPT : autograd, bigramme, "
         "BPE, transformer, puis la version pré-entraînée sur notre dataset qui sert à la démo.")

# =====================================================================================
# 4. Sources et mélange
# =====================================================================================
d = prs.slides.add_slide(VIDE)
entete(d, "DONNÉES", "Cinq sources, un mélange réglé en tokens")
donnees = CategoryChartData()
donnees.categories = ["Wikipédia FR", "Common Crawl", "Assemblée nationale", "Gutenberg FR", "Wikinews FR"]
donnees.add_series("Part des tokens", (40, 15, 15, 25, 5), number_format='0"%"')
cadre_g = d.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, Inches(0.5), Inches(1.7), Inches(4.3), Inches(3.75), donnees)
cadre_g.name = "Mélange final"
g = cadre_g.chart
style_graphique(g, 12, ENCRE)
g.has_title = False
g.has_legend = True
g.legend.position = XL_LEGEND_POSITION.BOTTOM
g.legend.include_in_layout = False
g.legend.font.size = Pt(12)
couleurs_parts = [BORDEAUX, GRIS_CLAIR, CARTE_SOMBRE, OR, ROSE]
couleurs_texte = [BLANC, ENCRE, BLANC, ENCRE, ENCRE]
serie = g.plots[0].series[0]
for i in range(5):
    pt = serie.points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = couleurs_parts[i]
    etiq = pt.data_label
    etiq.font.size = Pt(12)
    etiq.font.bold = True
    etiq.font.color.rgb = couleurs_texte[i]
g.plots[0].has_data_labels = True
g.plots[0].data_labels.number_format = '0"%"'
g.plots[0].data_labels.number_format_is_linked = False
g.plots[0].data_labels.show_value = True
sources = [
    ["Source", "Licence", "Lien"],
    ["Wikipédia FR (40 %)", "CC BY-SA 4.0 / GFDL", "huggingface.co/datasets/wikimedia/wikipedia"],
    ["Common Crawl (15 %)", "Conditions d'utilisation CC", "commoncrawl.org/terms-of-use"],
    ["Assemblée nationale (15 %)", "Licence Ouverte", "data.assemblee-nationale.fr/archives-16e/debats"],
    ["Gutenberg FR (25 %)", "Domaine public", "gutenberg.org/policy/license.html"],
    ["Wikinews FR (5 %)", "CC BY 2.5 / BY-SA 4.0", "fr.wikinews.org/wiki/Wikinews:Licence"],
]
tableau(d, 5.0, 1.75, [2.15, 1.8, 3.78], sources, hauteur_ligne=0.61, taille=11.5, nom="Sources")
tuiles = [("320 098", "documents, 1,05 Go de texte après nettoyage, dédup et qualité"),
          ("96 %", "des pages Common Crawl écartées : elles n'étaient pas en français"),
          ("13 mots", "communs avec la validation publique : document écarté")]
for i, (gros, legende) in enumerate(tuiles):
    x = 0.6 + i * (largeur_carte + 0.3)
    forme(d, x, 5.7, largeur_carte, 1.15, TEINTE, nom=f"Tuile {i + 1}")
    texte(d, x + 0.25, 5.7, 1.65, 1.15, gros, taille=26, gras=True, police=TITRE, couleur=BORDEAUX,
          ancre=MSO_ANCHOR.MIDDLE)
    texte(d, x + 1.95, 5.7, largeur_carte - 2.15, 1.15, legende, taille=12, ancre=MSO_ANCHOR.MIDDLE)
pied(d, 4)
notes(d, "Le mélange final est 40 % Wikipédia, 15 % Common Crawl, 15 % Assemblée nationale, 25 % Gutenberg et 5 % Wikinews, "
         "comptés en tokens et non en documents. Chaque source a une fiche avec origine, licence, volume et risques "
         "dans le dossier sources. Garde-fou : tout document qui partage 13 mots consécutifs avec la validation "
         "publique est écarté, vérifié sur chaque variante. Aucune donnée synthétique.")

# =====================================================================================
# 5. Ablation : progression
# =====================================================================================
d = prs.slides.add_slide(VIDE)
entete(d, "TESTS  ·  ABLATION", "De 1,3538 à 1,2767 BPB, étape par étape")
etapes = ["Brut", "Nettoyé", "Dédup", "+ Qualité", "Mélange M4", "+ Recollage", "+ BPE adapté", "+ Extraits (final)"]
valeurs = (1.3538, 1.3340, 1.3330, 1.3304, 1.3028, 1.2905, 1.2874, 1.2767)
donnees = CategoryChartData()
donnees.categories = etapes
donnees.add_series("BPB validation (graine 1337)", valeurs)
cadre_g = d.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.7), Inches(8.1), Inches(4.55), donnees)
cadre_g.name = "Progression BPB"
g = cadre_g.chart
style_graphique(g, 11, GRIS)
g.has_title = False
g.has_legend = False
plot = g.plots[0]
plot.gap_width = 45
plot.has_data_labels = True
plot.data_labels.number_format = "0.0000"
plot.data_labels.number_format_is_linked = False
plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
plot.data_labels.font.size = Pt(11)
plot.data_labels.font.bold = True
plot.data_labels.font.color.rgb = ENCRE
axe = g.value_axis
axe.minimum_scale = 1.25
axe.maximum_scale = 1.37
axe.major_unit = 0.02
axe.has_major_gridlines = True
axe.major_gridlines.format.line.color.rgb = RGBColor(0xE3, 0xE1, 0xE6)
axe.format.line.fill.background()
axe.tick_labels.number_format = "0.00"
axe.tick_labels.number_format_is_linked = False
g.category_axis.format.line.color.rgb = GRIS_CLAIR
g.category_axis.tick_labels.font.size = Pt(11)
for i in range(len(etapes)):
    pt = plot.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = GRIS_CLAIR if i == 0 else (OR if i == len(etapes) - 1 else BORDEAUX)
texte(d, 0.6, 6.35, 8.1, 0.6,
      "Graine 1337, même config, même budget (100 007 936 tokens). Axe tronqué à 1,25. Dédup (−0,001) et qualité (−0,003) "
      "restent dans le bruit mesuré (σ 0,0023, seuil ≈ 0,005).",
      taille=11, couleur=GRIS)
gains = [("−0,020", "Nettoyage : encodage cassé, non-français, boilerplate"),
         ("−0,028", "Mélange M4 : Gutenberg à 25 %, Wikinews à 5 %"),
         ("−0,012", "Recollage des lignes coupées des livres Gutenberg"),
         ("−0,011", "Extraits : 1 836 extraits au lieu de 204 livres entiers")]
for i, (delta, legende) in enumerate(gains):
    y = 1.75 + i * 1.2
    forme(d, 9.0, y, 3.73, 1.08, TEINTE, nom=f"Gain {i + 1}")
    texte(d, 9.2, y, 1.3, 1.08, delta, taille=26, gras=True, police=TITRE, couleur=BORDEAUX, ancre=MSO_ANCHOR.MIDDLE)
    texte(d, 10.55, y, 2.1, 1.08, legende, taille=12, ancre=MSO_ANCHOR.MIDDLE)
pied(d, 5)
notes(d, "Même modèle, même budget, seules les données changent. Le nettoyage fait −0,020 d'un coup. Ensuite la déduplication "
         "et le filtre qualité apportent très peu, dans le bruit que j'ai mesuré sur trois runs identiques. "
         "Le gros gain suivant vient du choix des sources : ajouter Gutenberg et Wikinews donne −0,028. "
         "Puis recoller les lignes coupées des livres, et passer de 204 livres entiers à 1 836 extraits, "
         "donnent encore −0,012 et −0,011. Score final 1,2767.")

# =====================================================================================
# 6. Genres et échecs
# =====================================================================================
d = prs.slides.add_slide(VIDE)
entete(d, "TESTS  ·  LECTURE ET ÉCHECS", "D'où vient le gain, et ce qui n'a pas marché")
genres = CategoryChartData()
genres.categories = ["Littéraire", "Dialogue", "Encyclopédique", "Presse"]
genres.add_series("Référence 80/12/8", (1.68, 1.13, 1.31, 1.21))
genres.add_series("M4", (1.55, 1.09, 1.37, 1.20))
genres.add_series("Recollage + BPE", (1.48, 1.09, 1.38, 1.20))
genres.add_series("Final (extraits)", (1.46, 1.08, 1.37, 1.20))
cadre_g = d.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.7), Inches(6.4), Inches(4.3), genres)
cadre_g.name = "BPB par genre"
g = cadre_g.chart
style_graphique(g, 11, GRIS)
g.has_title = False
g.has_legend = True
g.legend.position = XL_LEGEND_POSITION.BOTTOM
g.legend.include_in_layout = False
g.legend.font.size = Pt(11)
plot = g.plots[0]
plot.gap_width = 60
plot.overlap = -5
axe = g.value_axis
axe.minimum_scale = 1.0
axe.maximum_scale = 1.8
axe.major_unit = 0.2
axe.has_major_gridlines = True
axe.major_gridlines.format.line.color.rgb = RGBColor(0xE3, 0xE1, 0xE6)
axe.format.line.fill.background()
axe.tick_labels.number_format = "0.0"
axe.tick_labels.number_format_is_linked = False
for serie, couleur in zip(plot.series, [GRIS_CLAIR, ROSE, BORDEAUX, OR]):
    serie.format.fill.solid()
    serie.format.fill.fore_color.rgb = couleur
# Valeurs affichées seulement sur la référence et le final : on lit l'écart sans surcharger
for idx in (0, 3):
    etiq = plot.series[idx].data_labels
    etiq.show_value = True
    etiq.number_format = "0.00"
    etiq.number_format_is_linked = False
    etiq.position = XL_LABEL_POSITION.OUTSIDE_END
    etiq.font.size = Pt(10)
    etiq.font.bold = True
    etiq.font.color.rgb = ENCRE
texte(d, 0.6, 6.1, 6.4, 0.8,
      "Le gain vient du littéraire (Gutenberg) : 1,68 → 1,46. L'encyclopédique recule (1,31 → 1,37), "
      "largement compensé. Score hors littéraire quasi inchangé.",
      taille=12, couleur=ENCRE)
echecs = [
    ["Essai", "BPB", "Verdict"],
    ["Parts égales entre 4 sources", "1,3469", "pire de +0,017"],
    ["Ordre des données changé", "1,3106", "pire de +0,009"],
    ["Wikipédia à 45 %", "1,3115", "pire de +0,010"],
    ["Rejeu de tokens", "1,3172", "pire de +0,016"],
    ["Classifieur sur le web", "1,3044", "aucun gain (+0,003)"],
    ["Masquage des données perso", "1,3322", "aucun gain, non retenu"],
]
tableau(d, 7.3, 1.75, [2.55, 0.85, 2.03], echecs, hauteur_ligne=0.44, taille=12, nom="Essais sans gain")
forme(d, 7.3, 5.05, 5.43, 1.75, ENCRE, nom="Rigueur")
texte(d, 7.55, 5.2, 4.95, 1.5,
      [[("Rigueur", {"gras": True, "couleur": OR, "taille": 13})],
       "Bruit mesuré sur 3 runs identiques : σ 0,0023, donc on ne retient un gain qu'au-delà de ≈ 0,005. "
       "Les 4 recettes retenues sont confirmées sur 2 graines."],
      taille=14, couleur=BLANC, espace_apres=6)
pied(d, 6)
notes(d, "À gauche, le BPB par genre : le gain vient presque entièrement du littéraire, parce qu'on a ajouté des livres. "
         "L'encyclopédique recule un peu, c'est le compromis. À droite, six essais qui n'ont rien donné ou qui ont dégradé : "
         "parts égales, changer l'ordre, trop de Wikipédia, rejouer des tokens, un classifieur web, le masquage des données "
         "personnelles. Ces échecs sont aussi des résultats. J'ai mesuré le bruit avant de conclure.")

# =====================================================================================
# 7. Mini-GPT et démo
# =====================================================================================
d = prs.slides.add_slide(VIDE)
entete(d, "BLOC 1 ET DÉMO", "Le mini-GPT, et sa démo façon Molière")
perf = CategoryChartData()
perf.categories = ["Bigramme (comptage)", "Mini-GPT sur Molière seul", "Pré-entraîné sur notre dataset", "Idem, 3× plus de tokens (essai)"]
perf.add_series("BPB Molière", (3.3544, 1.8237, 1.4111, 1.3162))
cadre_g = d.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.7), Inches(6.0), Inches(3.05), perf)
cadre_g.name = "BPB Molière"
g = cadre_g.chart
style_graphique(g, 11, ENCRE)
g.has_title = False
g.has_legend = False
plot = g.plots[0]
plot.gap_width = 45
plot.has_data_labels = True
plot.data_labels.number_format = "0.00"
plot.data_labels.number_format_is_linked = False
plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
plot.data_labels.font.size = Pt(12)
plot.data_labels.font.bold = True
plot.data_labels.font.color.rgb = ENCRE
g.category_axis.reverse_order = True  # le premier de la liste en haut
g.category_axis.format.line.color.rgb = GRIS_CLAIR
g.value_axis.visible = False
g.value_axis.has_major_gridlines = False
g.value_axis.maximum_scale = 4.0
for i in range(4):
    pt = plot.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = OR if i == 2 else (GRIS_CLAIR if i == 0 else BORDEAUX)
texte(d, 0.6, 4.75, 6.0, 0.3, "BPB sur la validation Molière du kit (plus bas = mieux)", taille=11, couleur=GRIS)
forme(d, 0.6, 5.1, 6.0, 0.72, TEINTE, nom="Test inédit")
texte(d, 0.8, 5.1, 5.6, 0.72,
      [[("Conversations inédites (6 × 4 tours)  ", {"gras": True, "couleur": BORDEAUX}),
        ("2/24 réponses pertinentes pour le chat retenu, 5/24 avec 3× plus de tokens. "
         "Le BPB baisse plus vite que la qualité du dialogue.", {})]],
      taille=12, ancre=MSO_ANCHOR.MIDDLE)
# Conversation réelle (scénario du mentor), 3 tours sur 3
texte(d, 6.95, 1.7, 5.8, 0.3, "SCÉNARIO DU MENTOR  ·  3 TOURS SUR 3  ·  127.0.0.1:8765", taille=11, gras=True, couleur=BORDEAUX)
messages = [
    ("JB", "Bonjour, comment ça va ?", 0.46),
    ("Mini-GPT", "Bonjour ! Je vais bien, merci. Et vous, mon ami ?", 0.46),
    ("JB", "Moi je suis fatigué.", 0.46),
    ("Mini-GPT", "Prenez quelque repos, je vous en prie.", 0.46),
    ("JB", "Que me conseilles-tu ?", 0.46),
    ("Mini-GPT", "Reposez-vous un peu, mon ami. Le repos vous fera du bien.", 0.66),
]
y = 2.1
for qui, phrase, h in messages:
    du_modele = qui != "JB"
    x_bulle = 7.0 if du_modele else 8.4
    bulle = forme(d, x_bulle, y, 5.3 if du_modele else 4.33, h, BORDEAUX if du_modele else TEINTE, rayon=0.2,
                  nom=f"Bulle {qui}")
    texte(d, x_bulle + 0.2, y, (5.3 if du_modele else 4.33) - 0.4, h, phrase, taille=13,
          couleur=BLANC if du_modele else ENCRE, ancre=MSO_ANCHOR.MIDDLE)
    y += h + 0.1
forme(d, 0.6, 5.98, 12.13, 0.9, TEINTE, nom="Sources démo")
texte(d, 0.8, 6.02, 11.75, 0.82,
      [[("Sources de la démo (hors compétition)  ", {"gras": True, "couleur": BORDEAUX}),
        ("Molière : Projet Gutenberg, éd. Chasles 1888, gutenberg.org/ebooks/40086, domaine public. "
         "Dialogues maison : scripts du dépôt, licence MIT. "
         "Claire / TheatreGratuit : 8 000 paires filtrées, huggingface.co/datasets/OpenLLM-France/Claire-Dialogue-French-0.1, "
         "CC BY-NC-SA 4.0 (arxiv.org/abs/2311.16840). OpenAssistant/oasst1 examiné puis écarté.", {})]],
      taille=10.5, ancre=MSO_ANCHOR.MIDDLE)
pied(d, 7)
notes(d, "Le mini-GPT est écrit de zéro. Sur Molière, le bigramme fait 3,35 BPB, le mini-GPT entraîné sur Molière seul 1,82. Quand on le pré-entraîne "
         "sur notre dataset français puis qu'on le reprend sur Molière, il tombe à 1,41 (1,32 avec trois fois plus de tokens) : c'est la démonstration que les données "
         "font le modèle. Le chat est fine-tuné sur des dialogues puis servi par une page HTML locale. Le scénario de JB passe "
         "3 tours sur 3, mais sur six conversations inédites le chat ne réussit que 2 réponses sur 24 : le modèle de "
         "12,8 millions de paramètres reste très fragile en conversation libre. Toutes les réponses "
         "sont générées par le modèle, rien n'est scripté. Les sources externes et leurs licences sont dans l'encadré du bas.")

# =====================================================================================
# 8. Rendu et limites (fond sombre : fin du sandwich)
# =====================================================================================
d = prs.slides.add_slide(VIDE)
fond_diapo(d, ENCRE)
entete(d, "RENDU", "Un rendu vérifiable, des limites assumées", sombre=True)
for x, titre_c, lignes in [
    (0.6, "Ce qui est remis",
     ["ZIP privé : flux d'entraînement exact, kit figé (révision 3709c85), checkpoint, tokenizer, logs et preuves.",
      "Checkpoint relu sur CPU avec le kit officiel : 1,276737 BPB (1,276738 sur GPU).",
      "Empreintes SHA-256 du flux, du tokenizer et de chaque fichier, contrôlées par verifier.py.",
      "Régénération du flux en une commande, SHA identique vérifié sur les mélanges M4 et M4REFLOWBPE."]),
    (6.85, "Limites assumées",
     ["Score du test caché inconnu au rendu : tous les BPB sont sur la validation publique (230 textes).",
      "Le gain vient surtout du genre littéraire : il dépend du poids de ce genre dans le test.",
      "Une à deux graines seulement ; un écart sous 0,005 est traité comme du bruit.",
      "Collecte complète depuis un dossier vide non rejouée de bout en bout."]),
]:
    forme(d, x, 1.8, 5.88, 3.95, CARTE_SOMBRE, rayon=0.04, nom=titre_c)
    texte(d, x + 0.35, 2.05, 5.2, 0.4, titre_c, taille=20, gras=True, police=TITRE, couleur=OR)
    texte(d, x + 0.35, 2.7, 5.2, 3.2, lignes, taille=15, couleur=BLANC, espace_apres=12)
texte(d, 0.6, 6.1, 12.13, 0.6,
      [[("Pour aller plus loin  ", {"gras": True, "couleur": OR}),
        ("publier le dataset sur Hugging Face avec sa dataset card, rejouer plusieurs graines pour des barres d'erreur.", {})]],
      taille=14, couleur=GRIS_CLAIR)
pied(d, 8, sombre=True)
notes(d, "Ce qui est remis : un ZIP avec le flux exact, le kit figé, le checkpoint et les preuves. Le checkpoint relu sur CPU "
         "redonne 1,276737. Les limites : je ne connais pas le score sur le test caché, le gain est concentré sur le littéraire, "
         "j'ai une à deux graines, et la collecte complète depuis zéro n'a pas été rejouée de bout en bout. "
         "Je préfère les dire que les cacher.")

prs.save(SORTIE)
print("écrit :", SORTIE)
