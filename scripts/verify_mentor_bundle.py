"""Contrôle les empreintes du paquet, sans installer PyTorch."""

from hashlib import file_digest
from pathlib import Path


def verify(root):
    """Relit chaque fichier listé dans le manifeste SHA-256."""
    manifest = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    checked = 0
    for line in manifest:
        expected, name = line.split("  ", 1)
        path = (root / name).resolve()
        # Refuse les chemins qui sortent du dossier ou pointent vers un fichier manquant.
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Fichier introuvable ou hors du paquet : {name}")
        with path.open("rb") as stream:
            obtained = file_digest(stream, "sha256").hexdigest()
        if obtained != expected:
            raise ValueError(f"Empreinte SHA-256 différente : {name}")
        checked += 1
    return checked


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    try:
        print(f"{verify(folder)} fichiers vérifiés.")
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
