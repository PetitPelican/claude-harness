# -*- coding: utf-8 -*-
"""Cas limites de `diagnostic.py` (sortie comparée au Rust 0.12.8 : même texte, aux lignes
propres au Python près)."""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import diagnostic  # noqa: E402


class Diagnostic(unittest.TestCase):
    def projet(self, nom, etat=None, todo=None, ancien=False):
        d = tempfile.mkdtemp(prefix="diagnostic-%s-" % nom)
        self.addCleanup(shutil.rmtree, d, True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.makedirs(os.path.join(d, "brain/fact"))
        os.makedirs(os.path.join(d, "brain/mind"))
        with open(os.path.join(d, "brain/fact/base.md"), "w", encoding="utf-8") as h:
            h.write("cap: x\n")
        for f, t in (("state.md", etat), ("todo.md", todo)):
            if t is not None:
                with open(os.path.join(d, "brain/mind", f), "w", encoding="utf-8") as h:
                    h.write(t)
        if ancien:
            os.makedirs(os.path.join(d, ".fact"))
            with open(os.path.join(d, ".fact/base.md"), "w", encoding="utf-8") as h:
                h.write("cap: x\n")
        return os.path.realpath(d)

    def lance(self, d):
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            diagnostic.main([d])
        return tampon.getvalue()

    def test_l_interpreteur_est_nomme_avec_ses_trois_numeros_de_version(self):
        """La ligne « interpréteur » donne majeur.mineur.micro de l'interpréteur qui tourne
        (ligne propre au Python : le Rust n'a pas d'interpréteur)."""
        sortie = self.lance(self.projet("interp"))
        v = sys.version_info
        self.assertIn("(Python %d.%d.%d)" % (v[0], v[1], v[2]), sortie)

    def test_les_deux_arbres_de_memoire_sont_signales_a_trancher(self):
        """Un projet à cheval sur `.fact/` et `brain/` : le diagnostic le dit en toutes
        lettres (Rust 0.12.8 : même bloc de trois lignes)."""
        sortie = self.lance(self.projet("cheval", ancien=True))
        self.assertIn("AMBIGUE", sortie)
        self.assertIn("CE PROJET PORTE LES DEUX ARBRES À LA FOIS", sortie)
        self.assertIn("ne sera lu au hasard, mais il faut trancher.", sortie)

    def test_une_memoire_nette_ne_declenche_pas_l_alerte_des_deux_arbres(self):
        """Témoin négatif : une seule forme de mémoire, aucune alerte de migration."""
        sortie = self.lance(self.projet("net"))
        self.assertNotIn("AMBIGUE", sortie)
        self.assertNotIn("DEUX ARBRES", sortie)

    def test_un_saut_de_ligne_final_n_ajoute_pas_de_ligne(self):
        """`str::lines().count()` : « a\\nb » et « a\\nb\\n » font 2 lignes, « a\\nb\\n\\n » en
        fait 3 (Rust 0.12.8 : `2 lignes`, `3 lignes`)."""
        d = self.projet("lignes", etat="a\nb", todo="a\nb\n\n")
        sortie = self.lance(d)
        self.assertIn("où on en est               2 lignes", sortie)
        self.assertIn("ce qui attend              3 lignes", sortie)

    def test_le_compte_des_lignes_d_un_fichier(self):
        d = tempfile.mkdtemp(prefix="diagnostic-n-")
        self.addCleanup(shutil.rmtree, d, True)
        cas = [("a\nb", 2), ("a\nb\n", 2), ("a\nb\n\n", 3), ("", 0), ("\n", 1), ("seule", 1)]
        for i, (texte, attendu) in enumerate(cas):
            p = os.path.join(d, "f%d" % i)
            with open(p, "w", encoding="utf-8", newline="") as h:
                h.write(texte)
            self.assertEqual(diagnostic._nb_lignes(p), attendu, repr(texte))
        self.assertEqual(diagnostic._nb_lignes(os.path.join(d, "absent")), 0)


if __name__ == "__main__":
    unittest.main()
