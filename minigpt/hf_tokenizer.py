"""Enveloppe du tokenizer 8 192 de la compétition (format Hugging Face `tokenizers`).

Même interface que `BPETokenizer` (encode, decode, vocab), pour réutiliser la démo et le SFT
sans les modifier. Le tokenizer est sans perte : decode(encode(texte)) == texte."""

import hashlib
from pathlib import Path

from tokenizers import Tokenizer


class HFTokenizer:
    def __init__(self, path):
        self.path = Path(path)
        self.tk = Tokenizer.from_file(str(self.path))
        # Empreinte du fichier : sert à vérifier que le checkpoint et le tokenizer vont ensemble.
        self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.vocab = self.tk.get_vocab(with_added_tokens=True)  # dict token -> id, len = taille

    @classmethod
    def load(cls, path):
        """Même nom que `BPETokenizer.load`."""
        return cls(path)

    def encode(self, text: str) -> list[int]:
        """Texte -> ids, sans ajouter de token spécial."""
        return self.tk.encode(text, add_special_tokens=False).ids

    def decode(self, ids: list[int]) -> str:
        """ids -> texte, en gardant les tokens spéciaux."""
        return self.tk.decode(ids, skip_special_tokens=False)
