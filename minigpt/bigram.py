"""Bigramme par comptage sur les octets UTF-8 : le modèle de référence du bloc 1.

Idée : P(octet suivant | octet courant) = nombre de fois où la paire apparaît dans le train,
divisé par le nombre de fois où l'octet courant apparaît. On ajoute un lissage de Laplace
(alpha) pour qu'aucune paire n'ait une probabilité nulle sur la validation.

Comme les « tokens » sont des octets, le BPB est directement la moyenne de -log2 p par octet.

Usage : uv run python -m minigpt.bigram
"""

import math
import sys
from pathlib import Path

# 256 valeurs d'octets possibles ; l'indice 256 sert de contexte « début de texte ».
VOCAB = 256
BOS = 256

CORPUS = Path("kit/Piscine/corpus")


class ByteBigram:
    """Bigramme d'octets : une table de comptes 257 x 256 (contexte -> octet suivant)."""

    def __init__(self, alpha: float = 1.0):
        """alpha : lissage de Laplace ajouté à chaque case (0 = pas de lissage)."""
        self.alpha = alpha
        # counts[ctx][nxt] = nombre de fois où l'octet nxt suit le contexte ctx.
        self.counts = [[0] * VOCAB for _ in range(VOCAB + 1)]
        # totals[ctx] = somme de la ligne ctx, gardée à part pour ne pas la recalculer.
        self.totals = [0] * (VOCAB + 1)

    @staticmethod
    def pairs(data: bytes):
        """Itère sur les paires (contexte, suivant), en commençant par (BOS, premier octet)."""
        prev = BOS
        for byte in data:
            yield prev, byte
            prev = byte

    def fit(self, data: bytes) -> "ByteBigram":
        """Compte toutes les paires d'octets consécutifs du texte d'entraînement."""
        for ctx, nxt in self.pairs(data):
            self.counts[ctx][nxt] += 1
            self.totals[ctx] += 1
        return self

    def prob(self, ctx: int, nxt: int) -> float:
        """P(nxt | ctx) lissée : (compte + alpha) / (total + alpha * 256)."""
        denom = self.totals[ctx] + self.alpha * VOCAB
        if denom == 0:
            # Contexte jamais vu et pas de lissage : on retombe sur l'uniforme.
            return 1.0 / VOCAB
        return (self.counts[ctx][nxt] + self.alpha) / denom

    def bpb(self, data: bytes) -> float:
        """Bits par octet sur data : somme des -log2 p, divisée par le nombre d'OCTETS UTF-8."""
        total_bits = 0.0
        for ctx, nxt in self.pairs(data):
            p = self.prob(ctx, nxt)
            if p == 0.0:
                return math.inf  # paire jamais vue sans lissage : le modèle « explose »
            total_bits -= math.log2(p)
        # data est déjà en octets : len(data) compte les octets, pas les caractères.
        return total_bits / len(data)


def load_utf8(path: Path) -> bytes:
    """Lit un fichier texte et renvoie ses octets UTF-8, fins de ligne normalisées en \\n.

    Sous Windows, git (core.autocrlf) ajoute un \\r par ligne au checkout : ces octets
    n'existent pas dans le kit d'origine et feraient baisser le BPB artificiellement.
    Le mode texte de Python convertit \\r\\n en \\n, comme ftb/evaluate.py du kit.
    """
    with open(path, encoding="utf-8") as f:
        return f.read().encode("utf-8")


def main() -> None:
    """Entraîne sur moliere_train.txt et affiche le BPB sur moliere_val.txt."""
    train = load_utf8(CORPUS / "moliere_train.txt")
    val = load_utf8(CORPUS / "moliere_val.txt")
    alpha = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    model = ByteBigram(alpha=alpha).fit(train)
    print(f"train : {len(train):,} octets | val : {len(val):,} octets | alpha = {alpha}")
    print(f"BPB train : {model.bpb(train):.4f}")
    print(f"BPB val   : {model.bpb(val):.4f}")


if __name__ == "__main__":
    main()
