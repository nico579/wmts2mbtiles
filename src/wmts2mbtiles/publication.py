"""Publication atomique d'une base MBTiles : construite sous un nom ``.part``,
validée une fois fermée, puis renommée. Un ``.mbtiles`` présent est ainsi
toujours complet, même après une coupure en pleine écriture.

Ce sont les fonctions que lidar2map passe aux producteurs (``chemin_part``,
``nettoyer_sqlite_part``, ``valider_sqlite_part`` des structures de
dépendances), reprises de son ``_atomic_files.py`` ; ``chemin_part`` vient de
nico579_commons.atomique, comme chez lui.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from nico579_commons import atomique

SQLITE_SUFFIXES = atomique.SUFFIXES_ANNEXES


def chemin_part(path):
    """Chemin temporaire unique ``<nom>.<pid>.<jeton>.part`` à côté de path."""
    return atomique.chemin_part(path)


def nettoyer_sqlite_part(path):
    """Supprime un staging SQLite et ses sidecars, sans toucher au final."""
    path = Path(path)
    for suffixe in SQLITE_SUFFIXES:
        try:
            Path(str(path) + suffixe).unlink(missing_ok=True)
        except OSError:
            pass


def valider_sqlite_part(path, tables_attendues):
    """Valide une base staging fermée avant sa publication finale.

    ``tables_attendues`` associe chaque table à son nombre de lignes attendu
    (None : seulement présente). La réouverture en lecture seule prouve aussi
    que le fichier principal se suffit à lui-même (aucun WAL requis)."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise OSError(f"staging SQLite absent ou vide : {path}")
    for suffixe in SQLITE_SUFFIXES[1:]:
        if Path(str(path) + suffixe).exists():
            raise OSError(
                f"sidecar SQLite encore présent avant publication : "
                f"{path.name}{suffixe}"
            )
    connexion = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        curseur = connexion.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
        )
        try:
            presentes = {ligne[0] for ligne in curseur}
        finally:
            curseur.close()
        manquantes = set(tables_attendues) - presentes
        if manquantes:
            raise OSError(
                "table(s) SQLite manquante(s) : " + ", ".join(sorted(manquantes))
            )
        for table, attendu in tables_attendues.items():
            curseur = connexion.execute(f'SELECT COUNT(*) FROM "{table}"')
            try:
                obtenu = curseur.fetchone()[0]
            finally:
                curseur.close()
            if attendu is not None and obtenu != attendu:
                raise OSError(
                    f"SQLite {table}: {obtenu} ligne(s), {attendu} attendue(s)"
                )
    finally:
        connexion.close()
