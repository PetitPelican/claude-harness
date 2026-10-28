# -*- coding: utf-8 -*-
"""Port des `#[test]` de `harnais/src/curateur.rs` (7 tests, mêmes cas, mêmes assertions)."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_windows  # noqa: E402
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))

import curateur  # noqa: E402
from curateur import seuils, marque, g, doublons  # noqa: E402


class Curateur(unittest.TestCase):
    def test_une_supposition_perime_deux_fois_plus_vite_qu_une_mesure(self):
        vide = {}
        d_sup, _ = seuils(vide, "supposé", None)
        d_mes, _ = seuils(vide, "mesuré", None)
        self.assertLess(abs(d_mes / d_sup - 2.0), 1e-9)
        # Et un fait que le commanditaire a énoncé tient PLUS longtemps qu'une mesure :
        # il ne périme pas avec le temps, il périme quand il change d'avis.
        d_dit, _ = seuils(vide, "dit", None)
        self.assertGreater(d_dit, d_mes)

    def test_une_note_sans_niveau_n_est_PAS_punie(self):
        # LE CONTRE-EXEMPLE QUI COMPTE : les notes d'avant la règle n'en
        # portent pas, et les traiter comme des suppositions les archiverait.
        vide = {}
        self.assertEqual(seuils(vide, None, None), seuils(vide, "mesuré", None))

    def test_ce_qui_sert_perime_lentement_et_ce_qu_un_resultat_a_eprouve_encore_moins(self):
        jamais = seuils({}, "mesuré", None)
        lue = seuils({"n": 10}, "mesuré", None)
        eprouvee = seuils({"n": 10, "res": 1}, "mesuré", None)
        self.assertGreater(lue[0], jamais[0])
        self.assertLess(abs(eprouvee[0] / lue[0] - 2.0), 1e-9)

    def test_la_nature_etire_la_duree_et_une_supposition_n_en_sort_pas(self):
        vide = {}
        fait = seuils(vide, "mesuré", None)
        # Une nature déclarée contredit sa maison, dans les deux sens.
        exp = seuils(vide, "mesuré", "expérience")
        cro = seuils(vide, "mesuré", "croyance")
        self.assertLess(abs(exp[0] / fait[0] - 1.5), 1e-9, "une expérience s'endort 1,5 fois plus tard")
        self.assertLess(abs(fait[0] / cro[0] - 2.0), 1e-9, "une croyance, deux fois plus tôt")
        # LE CONTRE-EXEMPLE : une supposition ne se rachète pas par une étiquette.
        self.assertEqual(seuils(vide, "supposé", "fait"), seuils(vide, "supposé", None))
        # Et un mot inconnu ne vaut rien : ni puni, ni promu.
        self.assertEqual(seuils(vide, "mesuré", "peut-être"), fait)

    def test_la_marque_ne_dit_la_nature_que_quand_elle_n_est_pas_celle_de_la_maison(self):
        self.assertEqual(marque("mesuré", None), " [mesuré]")
        self.assertEqual(marque("supposé", None), " [supposé · croyance]")
        self.assertEqual(marque(None, "expérience"), " [expérience]")
        self.assertEqual(marque(None, None), "")

    def test_le_pourcent_g_de_Python(self):
        self.assertEqual(g(80.0), "80")
        self.assertEqual(g(42.5), "42.5")
        self.assertEqual(g(0.0), "0")

    def test_deux_descriptions_qui_partagent_trois_mots_rares_sont_signalees(self):
        notes = {
            "alpha": {"description": "le garde refuse toujours une ecriture directe"},
            "beta": {"description": "une ecriture directe est toujours refusee par le garde"},
            "gamma": {"description": "compter les sockets tmux avant de conclure"},
        }
        d = doublons(notes)
        self.assertEqual(len(d), 1, "un seul couple attendu, obtenu %r" % (d,))
        self.assertEqual((d[0][1], d[0][2]), ("alpha", "beta"))
        # Le contre-exemple : la troisieme note ne partage rien, elle ne doit
        # apparaitre dans aucune paire.
        self.assertFalse(any(x == "gamma" or y == "gamma" for (_, x, y, _) in d))


class Rapport(unittest.TestCase):
    """Le rapport de `harnais curateur --du <projet>`, sur une mémoire de fabrication ; le même jeu
    donne la même liste sur le Rust 0.12.8."""

    def rapport(self, notes, usage):
        base = tempfile.mkdtemp(prefix="curateur-")
        self.addCleanup(shutil.rmtree, base, True)
        mem = os.path.join(base, "proj", "memory")
        os.makedirs(mem)
        for nom, niveau in notes:
            with open(os.path.join(mem, nom + ".md"), "w", encoding="utf-8") as h:
                h.write("---\nname: %s\ndescription: d %s\n---\n> **%s** · 01/10/2026 — ok\n\ncorps\n"
                        % (nom, nom, niveau))
        with open(os.path.join(mem, ".usage.json"), "w", encoding="utf-8") as h:
            json.dump(usage, h)
        sortie = io.StringIO()
        env = {"CLAUDE_MEMOIRE_RACINE": base, "HOME": base}
        env = dict(env_windows.essentiel(), **env)
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(sortie):
            code = curateur.main(["--du", "proj"])
        self.assertEqual(code, 0)
        return sortie.getvalue()

    def test_une_supposition_lue_trois_fois_est_signalee_et_pas_deux(self):
        """Seuil de « supposé ET servi ≥3 fois » : 3 lectures en sont, 2 n'en sont pas, et une mesure
        très lue n'en est jamais (Rust 0.12.8 : lue3 (3 ×) et lue4 (4 ×) seulement)."""
        texte = self.rapport(
            [("lue1", "supposé"), ("lue2", "supposé"), ("lue3", "supposé"), ("lue4", "supposé"),
             ("mesuree5", "mesuré")],
            {"_depuis": "2026-09-01",
             "lue1": {"n": 1, "vu": "2026-10-10"}, "lue2": {"n": 2, "vu": "2026-10-10"},
             "lue3": {"n": 3, "vu": "2026-10-10"}, "lue4": {"n": 4, "vu": "2026-10-10"},
             "mesuree5": {"n": 5, "vu": "2026-10-10"}})
        self.assertIn("supposé ET servi ≥3 fois", texte)
        self.assertIn("      lue3 (3 ×)\n", texte)
        self.assertIn("      lue4 (4 ×)\n", texte)
        self.assertNotIn("lue2 (", texte)
        self.assertNotIn("lue1 (", texte)
        self.assertNotIn("mesuree5 (", texte)

    def test_sans_supposition_assez_lue_l_alerte_se_tait(self):
        texte = self.rapport([("lue2", "supposé"), ("mesuree5", "mesuré")],
                             {"_depuis": "2026-09-01",
                              "lue2": {"n": 2, "vu": "2026-10-10"}, "mesuree5": {"n": 5, "vu": "2026-10-10"}})
        self.assertNotIn("supposé ET servi", texte)


if __name__ == "__main__":
    unittest.main()
