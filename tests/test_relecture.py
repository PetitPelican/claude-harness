# -*- coding: utf-8 -*-
"""Cas limites de `relecture.py` ; chaque attendu a été relevé sur le Rust 0.12.8
(`harnais relecture` avec un faux `claude` dans `$HOME/.local/bin`, et des `.compteur` écrits à la main)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import relecture  # noqa: E402


class Verdict(unittest.TestCase):
    def test_un_contredit_garde_son_motif_en_entier(self):
        """Le motif suit « CONTREDIT » : le premier mot du motif ne perd pas sa première lettre."""
        self.assertEqual(relecture.normalise("CONTREDIT le motif"), "CONTREDIT le motif")
        self.assertEqual(relecture.normalise("contredit: x"), "CONTREDIT : x")
        self.assertEqual(relecture.normalise("\n\n  CONTREDIT   a b  \nsuite"), "CONTREDIT a b")

    def test_un_insuffisant_garde_ce_qui_manque_en_entier(self):
        self.assertEqual(relecture.normalise("INSUFFISANT il manque tout"), "INSUFFISANT il manque tout")
        self.assertEqual(relecture.normalise("insuffisant: preuve"), "INSUFFISANT : preuve")

    def test_confirme_ne_porte_rien_de_plus(self):
        self.assertEqual(relecture.normalise("CONFIRME parce que oui"), "CONFIRME")
        self.assertEqual(relecture.normalise("CONFIRMÉ"), "CONFIRME")

    def test_une_reponse_hors_jeu_n_est_jamais_un_accord(self):
        """Un juge muet ou bavard devient INSUFFISANT, avec le début de sa réponse (80 caractères)."""
        self.assertEqual(relecture.normalise("Peut-être."),
                         "INSUFFISANT le relecteur n'a pas rendu un verdict lisible (Peut-être.)")
        self.assertTrue(relecture.normalise("").startswith("INSUFFISANT le relecteur n'a pas rendu"))
        long = "x" * 100
        self.assertEqual(relecture.normalise(long),
                         "INSUFFISANT le relecteur n'a pas rendu un verdict lisible (%s)" % ("x" * 80))


class Compteur(unittest.TestCase):
    def dossier(self, texte):
        d = tempfile.mkdtemp(prefix="relecture-")
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, ".compteur"), "w", encoding="utf-8") as h:
            h.write(texte)
        return d

    def lis(self, nombre):
        d = self.dossier("%s %s" % (relecture.jour(), nombre))
        return relecture.compteur_jour(d)[1]

    def test_le_compte_du_jour_tient_dans_64_bits_non_signes(self):
        """`parse::<u64>` : 2^64 - 1 passe, 2^64 déborde et vaut zéro (Rust : 18446744073709551616
        → la relecture a lieu ; 18446744073709551615 → « plafond journalier atteint »)."""
        self.assertEqual(self.lis("18446744073709551615"), 2 ** 64 - 1)
        self.assertEqual(self.lis("18446744073709551616"), 0)
        self.assertEqual(self.lis("99999999999999999999999"), 0)

    def test_le_compte_du_jour_lit_les_formes_que_lit_le_rust(self):
        self.assertEqual(self.lis("11"), 11)
        self.assertEqual(self.lis("+3"), 3)
        self.assertEqual(self.lis("-3"), 0, "un signe moins n'est pas un u64")
        self.assertEqual(self.lis("x"), 0)

    def test_un_compte_d_un_autre_jour_repart_de_zero(self):
        d = self.dossier("1 7")
        self.assertEqual(relecture.compteur_jour(d)[1], 0)

    def test_u64(self):
        self.assertEqual(relecture._u64("0"), 0)
        self.assertEqual(relecture._u64("+7"), 7)
        self.assertIsNone(relecture._u64(""))
        self.assertIsNone(relecture._u64("1.5"))
        self.assertIsNone(relecture._u64("18446744073709551616"))


if __name__ == "__main__":
    unittest.main()
