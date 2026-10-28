# -*- coding: utf-8 -*-
"""Port des `#[test]` de `harnais/src/carnet.rs` (7 tests)."""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))

import carnet
import nature
from carnet import (arrondi0, arrondi1, chiffre, confiances, ecrire_etat, empreinte,
                    entrees, lecture, oubli, resume, slug, vise)


def carnet_essai(nom, liste):
    """Fabrique un carnet : une entrée par (auteur, texte, visée)."""
    esp = os.path.join(tempfile.gettempdir(), "harnais-carnet-%s-%d" % (nom, os.getpid()))
    shutil.rmtree(esp, ignore_errors=True)
    os.makedirs(esp)
    jour = datetime.datetime.now().strftime("%Y-%m-%d")
    for i, (auteur, texte, pour) in enumerate(liste):
        vise_ = "\n↗ %s : %s" % (pour, texte) if pour is not None else ""
        with open(os.path.join(esp, "%s-%d.md" % (jour, i)), "w", encoding="utf-8") as h:
            h.write("## %s 10:0%d · %s · réussi · mesuré\n%s%s\n" % (jour, i, auteur, texte, vise_))
    return esp


class Essais(unittest.TestCase):

    def test_l_arrondi_est_celui_de_python_au_pair(self):
        # PIÈGE SILENCIEUX : `f64::round` arrondirait 0,5 au supérieur.
        self.assertEqual(arrondi0(0.5), 0)
        self.assertEqual(arrondi0(1.5), 2)
        self.assertEqual(arrondi0(2.5), 2)
        self.assertEqual(arrondi1(82.35), 82.3)
        self.assertEqual(arrondi1(80.0 * 1.03), 82.4)

    def test_la_visee_atteint_le_nom_court_et_le_long(self):
        self.assertTrue(vise("PO", "Projet PO"))
        self.assertTrue(vise("Projet PO", "Projet PO"))
        self.assertTrue(vise("tous", "n'importe qui"))
        self.assertTrue(vise("équipe", "Projet QA"), "sans accents, dans les deux sens")
        # TÉMOINS NÉGATIFS : une visée qui rate ne doit RIEN servir.
        self.assertFalse(vise("OPS", "Projet PO"))
        self.assertFalse(vise("", "Projet PO"))
        self.assertFalse(vise("PO", ""))

    def test_le_chiffre_se_tait_avant_deux_mouvements(self):
        c = {}
        c["x"] = {"n": 82.4, "m": 1}
        self.assertIsNone(chiffre(c, "x"), "un seul mouvement : c'est le niveau déguisé")
        c["y"] = {"n": 82.4, "m": 2}
        self.assertEqual(chiffre(c, "y"), 82)
        self.assertIsNone(chiffre(c, "absent"))

    def test_la_ligne_qui_te_vise_porte_son_empreinte_et_les_autres_non(self):
        """LE SEUL GESTE SOCIAL DU CARNET. La ligne qui demande d'acquitter porte
        l'empreinte ; celle qui ne le demande pas ne la porte pas."""
        esp = carnet_essai("vise", [
            ("Projet PO", "la base change de forme", "QA"),
            ("Projet OPS", "le socle a bougé", None),
        ])
        try:
            lignes, servis = resume(esp, "Projet QA", 48, 8)
            pour_toi = [l for l in lignes if "POUR TOI" in l]
            self.assertEqual(len(pour_toi), 1, repr(lignes))
            ident = servis[0] if servis else ""
            self.assertTrue(ident and ("↩ %s" % ident) in pour_toi[0],
                            "l'empreinte demandée doit être dans la ligne : %r" % (lignes,))
            # TÉMOIN NÉGATIF : l'entrée qui ne vise personne n'en porte pas —
            # sinon « porte une empreinte » ne dirait rien de la visée.
            autres = [l for l in lignes if "POUR TOI" not in l]
            self.assertTrue(autres and all("↩ " not in l for l in autres), repr(lignes))
            # Et l'empreinte servie est bien celle que le fichier porte : un agent
            # qui la recopie acquitte VRAIMENT cette entrée.
            e = [e for e in entrees(esp, None) if e.auteur == "Projet PO"][0]
            self.assertEqual(ident, e.id)
        finally:
            shutil.rmtree(esp, ignore_errors=True)

    def test_l_instrument_distingue_le_dossier_absent_du_carnet_vide(self):
        """« Absent » et « vide » appellent deux gestes opposés."""
        nulle_part = os.path.join(tempfile.gettempdir(), "harnais-carnet-nulle-part-xyz")
        shutil.rmtree(nulle_part, ignore_errors=True)
        v, code = lecture(nulle_part, "X")
        self.assertEqual(code, 2)
        self.assertIn("n'existe pas", v.get("raison") or "", repr(v))

        esp = carnet_essai("vide", [])
        v, code = lecture(esp, "X")
        self.assertEqual(code, 0, "un carnet vide n'est pas une erreur")
        self.assertIs(v.get("vide"), True)
        self.assertIsNone(v.get("raison"), "vide n'est pas absent : %r" % (v,))

        # TÉMOIN : un carnet qui porte une entrée ne dit ni l'un ni l'autre.
        esp2 = carnet_essai("plein", [("Projet PO", "quelque chose", None)])
        v, code = lecture(esp2, "Projet QA")
        self.assertEqual(code, 0)
        self.assertTrue(v.get("vide") is None and v.get("raison") is None, repr(v))
        shutil.rmtree(esp, ignore_errors=True)
        shutil.rmtree(esp2, ignore_errors=True)

    def test_l_oubli_suit_la_nature_de_part_et_d_autre_de_chaque_seuil(self):
        esp = os.path.join(tempfile.gettempdir(), "harnais-carnet-oubli-nature-%d" % os.getpid())
        shutil.rmtree(esp, ignore_errors=True)
        os.makedirs(os.path.join(esp, ".etat"))

        def il_y_a(n):
            return (datetime.date.today() - datetime.timedelta(days=n)).strftime("%Y-%m-%d")
        d = {}
        for ident, niv, j in [("cro-14", "supposé", 14), ("cro-16", "supposé", 16),
                              ("exp-31", "observé", 31), ("exp-44", "mesuré", 44),
                              ("exp-46", "mesuré", 46)]:
            d[ident] = {"n": 50, "m": 0, "niveau": niv, "vu": il_y_a(j)}
        ecrire_etat(esp, d)
        oubli(esp, 30)
        c = confiances(esp)

        def n(ident):
            return float(c[ident]["n"])
        # Une CROYANCE attend 15 j : à 14 elle tient, à 16 elle descend d'un cran.
        self.assertEqual(n("cro-14"), 50.0)
        self.assertEqual(n("cro-16"), 48.5)
        # Une EXPÉRIENCE attend 45 j — et à 31 elle tient, là où la règle plate
        # d'avant l'aurait fait descendre. C'est le témoin du changement.
        self.assertEqual(n("exp-31"), 50.0)
        self.assertEqual(n("exp-44"), 50.0)
        self.assertEqual(n("exp-46"), 48.5)
        shutil.rmtree(esp, ignore_errors=True)

    def test_le_slug_et_l_empreinte_ne_bougent_pas(self):
        self.assertEqual(slug("Projet PO"), "Projet-PO")
        self.assertEqual(slug(""), "agent")
        # L'empreinte est le lien entre l'entrée et sa confiance : si elle
        # change, la confiance devient introuvable EN SILENCE.
        self.assertEqual(len(empreinte("2026-09-09", "10:00", "CTO", "un texte")), 12)
        self.assertNotEqual(empreinte("2026-09-09", "10:00", "CTO", "un texte"),
                            empreinte("2026-09-09", "10:00", "CTO", "un AUTRE texte"))


class Debordement(unittest.TestCase):
    """Le compteur `m` d'un `i64` qui boucle au lieu de déborder (Rust 0.12.8, mode release :
    `i64::MAX + 1` rend `i64::MIN`, vérifié par `carnet-essai`)."""

    def test_le_compteur_boucle_au_plus_grand_i64(self):
        self.assertEqual(carnet._plus_un(2 ** 63 - 2), 2 ** 63 - 1, "juste avant la borne : pas de bouclage")
        self.assertEqual(carnet._plus_un(2 ** 63 - 1), -(2 ** 63))
        self.assertEqual(carnet._plus_un(-(2 ** 63)), -(2 ** 63) + 1)
        self.assertEqual(carnet._plus_un(0), 1)

    def test_un_mouvement_au_plafond_est_ecrit_modulo_2_puissance_64(self):
        """Par `bouge` puis `replancher`, comme le fait `carnet-essai` : `m` repart du plus petit i64."""
        esp = tempfile.mkdtemp(prefix="carnet-deborde-")
        self.addCleanup(shutil.rmtree, esp, True)
        ecrire_etat(esp, {
            "a": {"n": 50, "m": 2 ** 63 - 1, "niveau": "mesuré", "vu": "2026-10-01"},
            "b": {"n": 50, "m": 2 ** 63 - 2, "niveau": "observé", "vu": "2026-10-01"},
        })
        carnet.bouge(esp, ["a", "b"], nature.REUSSITE, True)
        c = confiances(esp)
        self.assertEqual(c["a"]["m"], -(2 ** 63))
        self.assertEqual(c["b"]["m"], 2 ** 63 - 1)
        carnet.replancher(esp, "a", "TIENT")
        self.assertEqual(confiances(esp)["a"]["m"], -(2 ** 63) + 1)


if __name__ == "__main__":
    unittest.main()
