# wmts2mbtiles

Fonds de carte en MBTiles à partir d'un service de tuiles WMTS ou XYZ, comme ceux de la Géoplateforme de l'IGN (Plan IGN, SCAN 25 avec sa clé).

Le code est né dans [lidar2map](https://github.com/nico579/lidar2map), qui fabrique ses fonds ainsi depuis longtemps, et il est partagé avec [hike2gpx](https://github.com/nico579/hike2gpx), qui prépare des fonds pour son application Android. Le paquet regroupe ce que les deux font de la même façon :

- **producteur** : télécharge les tuiles d'une zone et de plusieurs zooms en parallèle, les garde en cache sur disque, et publie le MBTiles d'un coup, une fois complet et vérifié ;
- **wmts** : la grille de tuiles d'une zone, l'URL WMTS d'une tuile, des connexions maintenues ouvertes, une tuile téléchargée avec ses nouvelles tentatives ;
- **fusion** : plusieurs MBTiles en un seul, les tuiles transparentes composées par-dessus au lieu d'en remplacer d'autres (sans quoi les bords de blocs se trouent) ;
- **publication** : la base construite sous un nom `.part`, validée une fois fermée, puis renommée. Un `.mbtiles` présent est toujours complet.

Ce qui relie le producteur à l'application qui l'emploie (le téléchargement d'une tuile, la publication, l'arrêt demandé, les seuils) lui est passé à chaque appel, dans une structure de dépendances. Les modules `wmts` et `publication` en donnent les versions ordinaires.

## Installation

```
pip install wmts2mbtiles            # le producteur et la fusion
pip install "wmts2mbtiles[images]"  # avec Pillow : conversion PNG vers JPEG, composition des transparences
```

Python 3.8 ou plus récent. Seule dépendance : [nico579-commons](https://pypi.org/project/nico579-commons/), pour l'écriture atomique.

## Licence

GPL-3.0-or-later.
