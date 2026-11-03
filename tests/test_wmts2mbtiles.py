"""Le producteur MBTiles, la fusion et la publication, sans réseau : un faux
service de tuiles rend des images ; le reste est le vrai code."""

import io
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from wmts2mbtiles import fusion, producteur, publication, wmts

try:
    from PIL import Image
except ImportError:         # la composition des transparences demande Pillow
    Image = None

ZONE = (43.30, 6.00, 43.33, 6.04)      # sud, ouest, nord, est (Garéoult)


class HorsCouverture(Exception):
    pass


def png(couleur=(200, 30, 30, 255), taille=4):
    if Image is None:
        # Un PNG 1×1 suffit au producteur, qui ne lit que sa signature.
        return bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                             "1f15c4890000000d49444154789c6360f8cfc0000003010100c9fe92ef"
                             "0000000049454e44ae426082")
    tampon = io.BytesIO()
    Image.new("RGBA", (taille, taille), couleur).save(tampon, "PNG")
    return tampon.getvalue()


def dependances(telecharger, **autres):
    valeurs = dict(
        chemin_part=publication.chemin_part,
        nettoyer_sqlite_part=publication.nettoyer_sqlite_part,
        valider_sqlite_part=publication.valider_sqlite_part,
        telecharger_tuile=telecharger,
        est_image_valide=wmts._est_image_valide,
        fermer_connexions_wmts=lambda: None,
        log_req=lambda *a, **k: None,
        formater_duree=lambda s: f"{s:.0f}s",
        stop_event=threading.Event(),
        zone_hors_couverture=HorsCouverture,
        endpoint_prive="https://exemple.invalid/prive",
        endpoint_public="https://exemple.invalid/public",
        batch_insert=50,
        seuil_err_consec=1000,
        seuil_hors_couverture=10 ** 9,
    )
    valeurs.update(autres)
    return producteur._DependancesMbtilesWMTS(**valeurs)


def produire(chemin, zone=ZONE, zooms=(10, 12), telecharger=None):
    sud, ouest, nord, est = zone
    tuiles = list(wmts.calculer_grille_xyz(sud, ouest, nord, est, *zooms))
    telecharger = telecharger or (lambda z, x, y, *reste: png())
    return producteur.generer_mbtiles_wmts(
        Path(chemin), iter(tuiles), len(tuiles), "essai", "png", zooms[0], zooms[1],
        "ESSAI", "normal", "image/png", "", False, 2,
        bbox_wgs84=(ouest, sud, est, nord), dependances=dependances(telecharger)), tuiles


def lignes(chemin, requete):
    # Fermée explicitement : sous Windows, « with sqlite3.connect() » ne ferme
    # pas, et le dossier temporaire ne pourrait plus être effacé.
    base = sqlite3.connect(chemin)
    try:
        return base.execute(requete).fetchall()
    finally:
        base.close()


class Grille(unittest.TestCase):
    def test_compter_egale_la_grille(self):
        sud, ouest, nord, est = ZONE
        self.assertEqual(wmts.compter_tuiles_xyz(sud, ouest, nord, est, 6, 14),
                         len(list(wmts.calculer_grille_xyz(sud, ouest, nord, est, 6, 14))))

    def test_un_point_connu(self):
        # Paris (48,8566 N, 2,3522 E) au zoom 10 : la tuile OSM 518, 352.
        self.assertEqual(wmts.deg_to_tile(48.8566, 2.3522, 10), (518, 352))

    def test_images_reconnues_par_leur_signature(self):
        self.assertTrue(wmts._est_image_valide(png()))
        self.assertTrue(wmts._est_image_valide(b"\xff\xd8\xff\xe0" + b"0" * 20))
        self.assertFalse(wmts._est_image_valide(b"<html>erreur</html>"))
        self.assertFalse(wmts._est_image_valide(b""))


class Producteur(unittest.TestCase):
    def test_toutes_les_tuiles_publiees_y_en_tms(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin, tuiles = produire(Path(dossier) / "fond.mbtiles")
            self.assertTrue(chemin.is_file())
            self.assertEqual(lignes(chemin, "SELECT COUNT(*) FROM tiles")[0][0], len(tuiles))
            z, x, y = tuiles[0]
            rangee = 2 ** z - 1 - y          # MBTiles : y compté depuis le bas (TMS)
            self.assertEqual(lignes(chemin, f"SELECT COUNT(*) FROM tiles WHERE zoom_level={z} "
                                            f"AND tile_column={x} AND tile_row={rangee}")[0][0], 1)
            self.assertIn(("format", "png"), lignes(chemin, "SELECT name, value FROM metadata"))
            self.assertEqual(list(Path(dossier).glob("*.part*")), [], "aucun chantier ne reste")

    def test_rien_n_est_publie_si_trop_de_tuiles_echouent(self):
        def panne(*args):
            raise OSError("service muet")
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "fond.mbtiles"
            with self.assertRaises(BaseException):
                produire(chemin, telecharger=panne)
            self.assertFalse(chemin.exists(), "un MBTiles présent est toujours complet")


class Fusion(unittest.TestCase):
    def test_deux_zones_reunies(self):
        with tempfile.TemporaryDirectory() as dossier:
            dossier = Path(dossier)
            a, tuiles_a = produire(dossier / "a.mbtiles", zone=(43.30, 6.00, 43.33, 6.04))
            b, tuiles_b = produire(dossier / "b.mbtiles", zone=(44.30, 5.00, 44.33, 5.04))
            sortie = fusion.fusionner_mbtiles(
                [a, b], dossier / "tout.mbtiles",
                dependances=fusion.DependancesFusionMbtiles(
                    chemin_part=publication.chemin_part,
                    nettoyer_sqlite_part=publication.nettoyer_sqlite_part,
                    valider_sqlite_part=publication.valider_sqlite_part))
            attendu = len(set(tuiles_a) | set(tuiles_b))
            self.assertEqual(lignes(sortie, "SELECT COUNT(*) FROM tiles")[0][0], attendu)

    @unittest.skipIf(Image is None, "Pillow absent")
    def test_une_tuile_transparente_se_compose_par_dessus(self):
        dessous, dessus = png((200, 30, 30, 255)), png((0, 0, 0, 0))
        resultat = Image.open(io.BytesIO(fusion.composer_tuiles(dessous, dessus))).convert("RGBA")
        self.assertEqual(resultat.getpixel((0, 0)), (200, 30, 30, 255), "le dessous reste visible")
        opaque = png((10, 200, 10, 255))
        self.assertEqual(fusion.composer_tuiles(dessous, opaque), opaque, "opaque : le dessus gagne")


class Publication(unittest.TestCase):
    def test_une_base_au_compte_faux_est_refusee(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "x.mbtiles"
            base = sqlite3.connect(chemin)
            base.execute("CREATE TABLE tiles (a)")
            base.execute("INSERT INTO tiles VALUES (1)")
            base.commit()
            base.close()
            publication.valider_sqlite_part(chemin, {"tiles": 1})
            with self.assertRaises(OSError):
                publication.valider_sqlite_part(chemin, {"tiles": 2})
            with self.assertRaises(OSError):
                publication.valider_sqlite_part(chemin, {"metadata": None})


if __name__ == "__main__":
    unittest.main()
