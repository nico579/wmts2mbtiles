"""Fonds de carte en MBTiles à partir d'un service de tuiles WMTS ou XYZ.

- producteur : téléchargement concurrent, cache disque, publication atomique ;
- wmts : grille de tuiles, URL WMTS, connexions maintenues, une tuile ;
- fusion : plusieurs MBTiles en un seul, transparences composées ;
- publication : la base construite sous un nom .part, validée, renommée.

Né dans lidar2map, partagé avec hike2gpx.
"""

__version__ = "0.1.1"
