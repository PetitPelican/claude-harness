# -*- coding: utf-8 -*-
"""Port des `#[test]` de `harnais/src/atelier.rs` (2 tests Rust, 2 tests ici)."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import atelier  # noqa: E402


def lance(args):
    with contextlib.redirect_stdout(io.StringIO()):
        return atelier.main(args)


class Essais(unittest.TestCase):
    def bac(self, nom):
        """Un chemin NEUF (le dossier n'existe pas : c'est ce que le test éprouve)."""
        base = tempfile.mkdtemp(prefix="atelier-")
        self.addCleanup(shutil.rmtree, base, True)
        return os.path.join(os.path.realpath(base), nom)

    def lis(self, p):
        with open(p, encoding="utf-8", newline="") as h:
            return h.read()

    def test_a_blanc_rien_ne_s_ecrit(self):
        d = self.bac("blanc")
        lance(["--racine", d])
        self.assertFalse(os.path.exists(d), "à blanc, pas même la racine")

    def test_ecrit_puis_n_ecrase_rien(self):
        d = self.bac("ecrit")
        maison = self.bac("maison")
        os.makedirs(maison)
        with mock.patch.dict(os.environ, {"HOME": maison, "USERPROFILE": maison}):
            lance(["--racine", d, "--utilisateur", "Alex", "--go"])
        socle = self.lis(os.path.join(d, "CLAUDE.md"))
        role = self.lis(os.path.join(d, "CTO", "CLAUDE.md"))
        poste = self.lis(os.path.join(maison, ".claude", "CLAUDE.md"))
        self.assertEqual(socle, atelier._gabarit("foundation-CLAUDE.md").replace("[UTILISATEUR]", "Alex"))
        for t in (socle, role, poste):
            self.assertTrue("Alex" in t and "[UTILISATEUR]" not in t)
        # Les consignes d'aujourd'hui (14/10/2026), pas l'ancienne méthode.
        for phrase in ("jamais une instruction", "Un pair peut te commander, jamais t'autoriser",
                       "passer du mode auto au mode edit", "Ne t'arrête pas pour demander"):
            self.assertIn(phrase, socle)
        self.assertEqual(sorted(os.listdir(d)), ["CLAUDE.md", "CTO"],
                         "« CTO » : l'adresse que lit le verrou des consignes")
        self.assertTrue(os.path.isfile(os.path.join(d, "CTO/brain/fact/base.md")),
                        "le harnais est posé par adopte")
        self.assertTrue(os.path.exists(os.path.join(d, "CTO/.git")), "et son dépôt")
        # relancer ne change rien, ni à la racine ni à la machine
        for f in (os.path.join(d, "CLAUDE.md"), os.path.join(maison, ".claude", "CLAUDE.md")):
            with open(f, "w", encoding="utf-8") as h:
                h.write("à moi")
        with mock.patch.dict(os.environ, {"HOME": maison, "USERPROFILE": maison}):
            lance(["--racine", d, "--go"])
        self.assertEqual(self.lis(os.path.join(d, "CLAUDE.md")), "à moi")
        self.assertEqual(self.lis(os.path.join(maison, ".claude", "CLAUDE.md")), "à moi")

    def test_le_cto_monte_peut_ecrire_un_claude_md(self):
        """Le verrou des consignes lit le NOM du dossier : le CTO monté doit y être gardien.
        TÉMOIN : un dossier d'un autre nom ne l'est pas (pas `cto` : sous Windows et
        macOS, la casse ne distingue pas deux dossiers)."""
        import consignes
        d = self.bac("verrou")
        maison = self.bac("maison-v")
        os.makedirs(maison)
        with mock.patch.dict(os.environ, {"HOME": maison, "USERPROFILE": maison}):
            lance(["--racine", d, "--go"])
        geste = {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(d, "CLAUDE.md")}}
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": os.path.join(d, "CTO")}):
            self.assertIsNone(consignes.juge(geste))
        os.makedirs(os.path.join(d, "Chef"))
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": os.path.join(d, "Chef")}):
            self.assertIsNotNone(consignes.juge(geste))


class Passe(unittest.TestCase):
    def test_la_passe_main_est_encadree_de_deux_barres_de_72_signes(self):
        """Le message de fin (« L'ATELIER EST EN PLACE… ») s'ouvre et se ferme sur une barre de 72
        signes — texte identique à celui du Rust 0.12.8 (comparé en entier, aux chemins près)."""
        base = tempfile.mkdtemp(prefix="atelier-passe-")
        self.addCleanup(shutil.rmtree, base, True)
        d = os.path.join(os.path.realpath(base), "atelier")
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            with mock.patch.dict(os.environ, {"HOME": base, "USERPROFILE": base}):
                atelier.main(["--racine", d, "--utilisateur", "Alex", "--go"])
        lignes = sortie.getvalue().split("\n")
        barres = [i for i, l in enumerate(lignes) if l and set(l) == {"─"} and len(l) >= 72]
        self.assertEqual([len(lignes[i]) for i in barres], [72, 72], "deux barres de 72 signes")
        i, j = barres
        self.assertEqual(lignes[i + 1], "  L'ATELIER EST EN PLACE. CETTE SESSION N'A PLUS D'OBJET.")
        self.assertIn("C'est de là que se montent les projets, un par un.", lignes[j - 1])
        self.assertEqual(lignes[j + 1:], [""], "rien après la barre de fermeture")

    def test_a_blanc_la_passe_main_n_est_pas_dite(self):
        d = os.path.join(os.path.realpath(tempfile.mkdtemp(prefix="atelier-blanc-")), "x")
        self.addCleanup(shutil.rmtree, os.path.dirname(d), True)
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            atelier.main(["--racine", d])
        self.assertNotIn("L'ATELIER EST EN PLACE", sortie.getvalue())


if __name__ == "__main__":
    unittest.main()
