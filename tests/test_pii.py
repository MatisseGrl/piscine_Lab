"""Vérifie le masquage PII par regex : cas masqués, cas laissés intacts, idempotence."""

import pytest

from pipeline.pii import mask, shape


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("écris à jean.dupont@example.fr merci", "écris à [EMAIL] merci"),
        ("Contact : a+b@sous.domaine.example.com.", "Contact : [EMAIL]."),
        ("Appelez le 01 23 45 67 89.", "Appelez le [TEL]."),
        ("Mobile +33 6 12 34 56 78 ou 06.12.34.56.78 ou 0033612345678", "Mobile [TEL] ou [TEL] ou [TEL]"),
        ("IBAN FR1420041010050500013M02606 ok", "IBAN [IBAN] ok"),
        ("IBAN FR14 2004 1010 0505 0001 3M02 606 ok", "IBAN [IBAN] ok"),
        ("Voir https://www.exemple.fr/page?x=1&y=2.", "Voir [URL]."),
        ("Voir (www.exemple.fr/a), puis la suite", "Voir ([URL]), puis la suite"),
        ("Serveur 192.168.1.1 actif", "Serveur [IP] actif"),
        ("Hôte 2001:db8::1 actif", "Hôte [IP] actif"),
    ],
)
def test_masked(text, expected):
    """Remplace chaque segment ciblé par son marqueur typé, sans toucher le reste."""
    assert mask(text)[0] == expected


@pytest.mark.parametrize(
    "text",
    [
        "Pas de donnée personnelle ici : 3,14 et 1789.",
        "Les années 1789 1799 1815 1830.",
        "Numéro trop long 0123456789012 ici.",
        "Un IBAN à clé fausse FR1520041010050500013M02606 reste.",
        "Adresse invalide 999.1.1.1 et version 1.2.3.",
        "Heure 10:30:45 et ratio 3:1 et std::vector.",
        "Arobase seule @ ou mot@ ou @mot restent.",
        "Un site sans schéma comme exemple.fr reste.",
    ],
)
def test_untouched(text):
    """Laisse intacts les nombres, dates, heures et formes invalides."""
    assert mask(text) == (text, {})


def test_counts_by_type():
    """Compte les segments masqués par type."""
    text = "a@b.fr et c@d.fr, tél 0123456789, https://x.fr"
    masked, counts = mask(text)
    assert masked == "[EMAIL] et [EMAIL], tél [TEL], [URL]"
    assert counts == {"EMAIL": 2, "TEL": 1, "URL": 1}


def test_url_wins_over_inner_email_and_ip():
    """Une URL est masquée d'un seul bloc, même avec un e-mail ou une IP dedans."""
    assert mask("lien https://x.fr/a@b.com et http://10.0.0.1/x")[0] == "lien [URL] et [URL]"


def test_idempotent_and_preserves_surroundings():
    """Un second passage ne change rien et les sauts de ligne sont conservés."""
    text = "ligne 1\n\n  mail: a@b.fr\tfin\n"
    once, _ = mask(text)
    assert once == "ligne 1\n\n  mail: [EMAIL]\tfin\n"
    assert mask(once) == (once, {})


def test_shape_hides_content():
    """La forme d'un segment ne garde ni lettres ni chiffres d'origine."""
    assert shape("jean.dupont@example.fr") == "aaaa.aaaaaa@aaaaaaa.aa"
    assert shape("01 23 45 67 89") == "99 99 99 99 99"
    assert shape("Ab1") == "aa9"
