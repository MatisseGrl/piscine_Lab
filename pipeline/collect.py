"""Télécharge les trois sources brutes retenues pour le bloc 2."""

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen


RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
CRAWL = "CC-MAIN-2025-05"
SEGMENT = "1736703361941.29"
CC_BASE = "https://data.commoncrawl.org"
WIKI_BASE = "https://huggingface.co"
WIKI_REPO = "datasets/wikimedia/wikipedia"
WIKI_REVISION = "b4c48878f631fc348dd47a4d89c3d1e4b928a0de"
WIKI_CONFIG = "20231101.fr"
ASSEMBLY_URL = (
    "https://data.assemblee-nationale.fr/static/openData/repository/"
    "16/vp/syceronbrut/syseron.xml.zip"
)
SAMPLE_BYTES = 1024 * 1024


def download(url, target, *, size=None, checksum=None, prefix=False):
    """Publie un fichier seulement après réception et vérification."""
    # Vérifie aussi les fichiers déjà présents pour permettre une relance.
    def valid(path, expected_size):
        """Contrôle la taille et, si disponible, l'empreinte publiée."""
        if not path.is_file() or path.stat().st_size != expected_size:
            return False
        if checksum is None:
            return True
        algorithm, expected = checksum
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, algorithm).hexdigest() == expected

    # Pour les WET complets, l'en-tête HEAD fournit la taille de référence.
    if size is None and not prefix:
        with urlopen(Request(url, method="HEAD"), timeout=60) as response:
            size = int(response.headers["Content-Length"])
    expected_size = SAMPLE_BYTES if prefix else size
    if valid(target, expected_size):
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Range": f"bytes=0-{SAMPLE_BYTES - 1}"} if prefix else {}
    print(f"Téléchargement : {target.relative_to(RAW)}", flush=True)
    with NamedTemporaryFile(dir=target.parent, suffix=".part", delete=False) as output:
        temporary = Path(output.name)
    try:
        with urlopen(Request(url, headers=headers), timeout=60) as response:
            with temporary.open("wb") as output:
                if prefix:
                    # Même si le serveur ignore Range, ne lire que le premier Mio.
                    if response.status == 206 and not response.headers.get(
                        "Content-Range", ""
                    ).startswith(f"bytes 0-{SAMPLE_BYTES - 1}/"):
                        raise ValueError(f"Plage inattendue pour {url}")
                    output.write(response.read(SAMPLE_BYTES))
                else:
                    shutil.copyfileobj(response, output, length=1024 * 1024)
        if not valid(temporary, expected_size):
            raise ValueError(f"Taille ou empreinte incorrecte pour {url}")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def collect(sample):
    """Sélectionne les fichiers dans les index officiels et les télécharge."""
    # Les préfixes de test ont un nom distinct des archives complètes.
    root = RAW / "_samples" if sample else RAW
    suffix = ".prefix" if sample else ""
    wet_dir = f"crawl-data/{CRAWL}/segments/{SEGMENT}/wet/"
    with urlopen(f"{CC_BASE}/crawl-data/{CRAWL}/wet.paths.gz", timeout=60) as response:
        # Trie les chemins pour que le premier fichier de test soit stable.
        with gzip.open(response, "rt", encoding="utf-8") as index:
            wet_paths = sorted(line.strip() for line in index if line.startswith(wet_dir))
    if len(wet_paths) != 900:
        raise ValueError(f"Index WET inattendu : {len(wet_paths)} chemins")
    for path in wet_paths[:1] if sample else wet_paths:
        target = root / "common_crawl" / CRAWL / SEGMENT / (Path(path).name + suffix)
        download(f"{CC_BASE}/{path}", target, prefix=sample)

    # Lit les tailles et les SHA-256 LFS dans l'arbre de la révision fixée.
    tree_url = f"{WIKI_BASE}/api/{WIKI_REPO}/tree/{WIKI_REVISION}/{WIKI_CONFIG}"
    with urlopen(tree_url, timeout=60) as response:
        shards = sorted(json.load(response), key=lambda item: item["path"])
    if len(shards) != 17 or any(not item["path"].endswith(".parquet") for item in shards):
        raise ValueError("Arbre Wikipédia inattendu")
    for shard in shards[:1] if sample else shards:
        path = shard["path"]
        target = root / "wikipedia_fr" / WIKI_CONFIG / (Path(path).name + suffix)
        checksum = None if sample else ("sha256", shard["lfs"]["oid"])
        url = f"{WIKI_BASE}/{WIKI_REPO}/resolve/{WIKI_REVISION}/{path}"
        download(url, target, size=shard["size"], checksum=checksum, prefix=sample)

    # Le ZIP est assez petit pour vérifier l'archive officielle dans les deux modes.
    download(
        ASSEMBLY_URL,
        root / "assemblee_nationale" / "16" / "syseron.xml.zip",
        size=57_553_703,
        checksum=("md5", "25eafad3378cde1b1c75ba8c3afdc0c7"),
    )


def main():
    """Lit les options et lance la collecte."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Collecte de vérification bornée.")
    collect(parser.parse_args().sample)


if __name__ == "__main__":
    main()
