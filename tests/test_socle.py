# -*- coding: utf-8 -*-
"""Essais de `py/socle.py` — port de `mod essais` de `harnais/src/socle.rs`.

Six fonctions de test en Rust (huit occurrences de `#[test]` dans le module,
dont un attribut répété sur `la_cle_de_memoire_ignore_le_prefixe_canonique_windows`
et une mention dans un commentaire) : six ici. Seuls `cle_memoire`,
`chemin_affiche`, `dossier_de_la_memoire`, `memoire_auto` et `socle` sont
éprouvés — c'est le périmètre demandé.
Lancer : python3 -m unittest discover -s tests -p "test_socle.py"
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import socle  # noqa: E402
from socle import cle_memoire, chemin_affiche, dossier_de_la_memoire  # noqa: E402


class Essais(unittest.TestCase):

    # LE CHEMIN ANNONCÉ S'OUVRE DEPUIS OÙ ON TRAVAILLE — les deux sens.
    #
    # Défaut mesuré trois fois le 10/09/2026 (audit P1 et P4) : un chemin
    # recomposé à la main au lieu d'être dérivé. Sous le dossier de travail on
    # veut du relatif, court et lisible ; en dehors — mémoire déportée — on
    # veut l'ABSOLU, parce qu'un relatif y serait joli et faux.
    #
    # Le second sens compte autant : une fonction qui rendrait toujours
    # l'absolu passerait le premier cas sans le servir.
    def test_le_chemin_annonce_s_ouvre_depuis_ou_on_travaille(self):
        ici = "/d/projet/agents/Un Agent"
        # sous le dossier de travail -> relatif
        self.assertEqual(chemin_affiche(ici, ici + "/brain/fact/base.md"),
                         "brain/fact/base.md")
        # en dehors (mémoire déportée) -> absolu, jamais un relatif inventé
        dehors = "/d/projet/memoire/.fact/base.md"
        rendu = chemin_affiche(ici, dehors)
        self.assertEqual(rendu, "/d/projet/memoire/.fact/base.md")
        self.assertNotEqual(rendu, ".fact/base.md", "rend un relatif qui ne s'ouvre pas d'ici")
        # un nom d'agent à espace ne casse rien
        self.assertEqual(chemin_affiche("/d/Projet PO", "/d/Projet PO/x.md"), "x.md")

    # LE CONTRÔLE QUI COMPTE : le slug doit être celui de Python, à la lettre.
    #
    # LE PRÉFIXE CANONIQUE DE WINDOWS NE DOIT PAS ENTRER DANS LA CLÉ.
    #
    # Sous Windows `canonicalize()` rend `\\?\C:\x`, `Path.resolve()` de Python
    # rend `C:\x`. Slugifiés, ce sont DEUX adresses de mémoire — le programme
    # écrirait dans l'une, le repli dans l'autre, et personne ne le verrait avant
    # d'avoir perdu des notes.
    #
    # L'essai porte les deux sens : le préfixe est retiré quand il est là, et un
    # chemin qui n'en a pas n'est pas amputé.
    # LES DEUX ESSAIS QUI SUIVENT APPELLENT LA VRAIE FONCTION.
    #
    # Ils recopiaient sa logique dans une closure locale : ils éprouvaient donc la
    # copie, pas le code livré, et seraient restés verts pendant que la vraie clé
    # changeait. Et l'un des deux n'avait même pas son attribut `#[test]` — il n'a
    # jamais tourné.
    def test_la_cle_de_memoire_ignore_le_prefixe_canonique_windows(self):
        # Les deux formes du MÊME dossier doivent rendre la MÊME clé.
        self.assertEqual(cle_memoire(r"\\?\C:\Users\u\projet"),
                         cle_memoire(r"C:\Users\u\projet"))
        # Et un chemin POSIX n'est pas amputé au passage.
        self.assertEqual(cle_memoire("/Users/u/projet"), "-Users-u-projet")

        # Témoin négatif : sans le retrait du préfixe, les deux clés diffèrent.
        def sans_retrait(s):
            return "".join(c if (c.isascii() and c.isalnum()) else "-" for c in s)
        self.assertNotEqual(sans_retrait(r"\\?\C:\Users\u\projet"),
                            sans_retrait(r"C:\Users\u\projet"),
                            "le témoin ne prouve rien : les deux formes donnaient déjà la même clé")

    # UN TIRET PAR CARACTÈRE, JAMAIS FONDUS — la règle de Claude Code.
    #
    # Les trois premières assertions sont des chemins ordinaires : elles valaient
    # déjà avant le 10/09/2026, et elles doivent continuer de valoir, sinon la
    # mémoire des projets déménagerait sans prévenir.
    #
    # La quatrième est celle qui sépare l'ancienne règle de la nouvelle, et elle
    # est RELEVÉE SUR LE DISQUE, pas déduite : le dossier
    # `-Users-u-Agentic--worktrees-projet-audit` existe. L'ancienne règle
    # rendait `-worktrees` et cherchait donc un dossier qui n'a jamais existé.
    def test_la_cle_est_celle_que_claude_code_ecrit(self):
        self.assertEqual(cle_memoire("/Users/u/Agentic/CTO"), "-Users-u-Agentic-CTO")
        self.assertEqual(cle_memoire("/Users/u/Agentic/Projet Annexe"),
                         "-Users-u-Agentic-Projet-Annexe")
        self.assertEqual(cle_memoire("/Users/u/Agentic/Projet/agents/Projet OPS"),
                         "-Users-u-Agentic-Projet-agents-Projet-OPS")
        self.assertEqual(cle_memoire("/Users/u/Agentic/.worktrees/projet-audit"),
                         "-Users-u-Agentic--worktrees-projet-audit")

        # Témoin négatif : l'ancienne règle échouait sur ce dernier cas.
        def effondre(s):
            sortie = []
            t = False
            for c in s:
                if c.isascii() and c.isalnum():
                    sortie.append(c)
                    t = False
                elif not t:
                    sortie.append("-")
                    t = True
            return "".join(sortie)
        self.assertNotEqual(effondre("/Users/u/Agentic/.worktrees/projet-audit"),
                            cle_memoire("/Users/u/Agentic/.worktrees/projet-audit"),
                            "les deux règles s'accordent sur ce cas : il ne SÉPARE rien")

    def test_socle_retombe_sur_claude_hors_plugin(self):
        ancien = os.environ.pop("CLAUDE_PLUGIN_DATA", None)
        try:
            self.assertTrue(socle.socle().endswith(".claude"))
        finally:
            if ancien is not None:
                os.environ["CLAUDE_PLUGIN_DATA"] = ancien

    # LA FORME D'UNE ÉQUIPE, SUR UN BANC : un agent dans un sous-dossier de l'arbre
    # principal, un autre dans un arbre de travail annexe. Les deux doivent
    # tomber sur la racine de l'arbre principal — et un dossier hors dépôt, sur
    # lui-même (le témoin qui prouve que la fonction ne rend pas toujours la même
    # chose).
    def test_la_memoire_se_range_a_la_racine_du_depot(self):
        b = tempfile.mkdtemp(prefix="harnais-memoire-%d-" % os.getpid())
        self.addCleanup(shutil.rmtree, b, True)
        d = os.path.join(b, "projet")
        os.makedirs(os.path.join(d, "agents/Un Agent"))

        def g(dossier, *a):
            r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t"] + list(a),
                               cwd=dossier, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(r.returncode, 0, r.stderr)
        g(d, "init", "-q", "-b", "dev")
        with open(os.path.join(d, "agents/Un Agent/x"), "w") as f:
            f.write("x")
        g(d, "add", "-A")
        g(d, "commit", "-qm", "x")
        annexe = os.path.join(b, ".arbres/annexe")
        g(d, "worktree", "add", "-q", "-b", "annexe", annexe)
        racine = os.path.realpath(d)
        self.assertEqual(dossier_de_la_memoire(os.path.join(d, "agents/Un Agent")), racine)
        self.assertEqual(dossier_de_la_memoire(os.path.join(annexe, "agents/Un Agent")), racine)
        dehors = os.path.join(b, "hors-depot")
        os.makedirs(dehors)
        self.assertEqual(dossier_de_la_memoire(dehors), os.path.realpath(dehors))

    def test_memoire_absente_rend_none(self):
        self.assertIsNone(socle.memoire_auto("/private/tmp/nexiste-vraiment-pas"))


if __name__ == "__main__":
    unittest.main()
