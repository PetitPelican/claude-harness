# -*- coding: utf-8 -*-
"""Le carnet des rechutes que la garde SERT est celui que les agents ÉCRIVENT.

Mesuré le 14/10/2026 : la garde servait la copie livrée (dossier de données du
plugin absent → paquet) pendant que les agents écrivaient `~/.claude/rechutes.md`.
"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import attente  # noqa: E402

CARNET = """# Avant d'affirmer

## Partout

- **Ton instrument a-t-il répondu à LA question posée ?** Long détail
  sur plusieurs lignes, récidives datées, qu'on ne sert pas.
- **Une question écrite par un agent, sur
  deux lignes ?** Son détail.

%s

- **Ajoutée en fin de fichier, sous la ligne d'écriture ?** jamais relue.
""" % attente.SEP_RECHUTES


class Rechutes(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="rechutes-")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.maison = os.path.join(self.d, "maison")
        self.donnees = os.path.join(self.d, "donnees")
        self.livre = os.path.join(self.d, "paquet")
        for x in (os.path.join(self.maison, ".claude"), self.donnees, self.livre):
            os.makedirs(x)
        with open(os.path.join(self.livre, "rechutes.md"), "w", encoding="utf-8") as h:
            h.write("- **Copie livrée ?** amorce\n")
        p = mock.patch.dict(os.environ, {"HOME": self.maison, "CLAUDE_PLUGIN_DATA": self.donnees,
                                         "CLAUDE_PLUGIN_ROOT": self.livre})
        p.start()
        self.addCleanup(p.stop)

    def ecrit(self, t):
        with open(os.path.join(self.maison, ".claude", "rechutes.md"), "w", encoding="utf-8") as h:
            h.write(t)

    def test_le_carnet_ecrit_est_servi_sous_le_paquet(self):
        self.ecrit(CARNET)
        r = attente.rechutes()
        self.assertIn("Une question écrite par un agent, sur deux lignes ?", r)
        self.assertNotIn("Copie livrée", r)

    def test_seuls_les_titres_sont_servis(self):
        self.ecrit(CARNET)
        r = attente.rechutes()
        self.assertIn("- Ton instrument a-t-il répondu à LA question posée ?", r)
        self.assertNotIn("récidives datées", r)
        self.assertIn(os.path.join(self.maison, ".claude", "rechutes.md"), r, "le détail est nommé")

    def test_temoin_sous_la_ligne_d_ecriture_rien_n_est_servi(self):
        """TÉMOIN : une garde qui servirait tout le fichier passerait les autres essais."""
        self.ecrit(CARNET)
        self.assertNotIn("Ajoutée en fin de fichier", attente.rechutes())

    def test_sans_carnet_la_copie_livree(self):
        self.assertIn("Copie livrée ?", attente.rechutes())

    def test_plafond(self):
        self.ecrit("\n".join("- **Question %d ?** x" % i for i in range(200)))
        r = attente.rechutes()
        self.assertLessEqual(len(r.splitlines()), attente.RECHUTES_LIGNES_MAX + 3)
        self.assertIn("ligne(s) de plus", r)


if __name__ == "__main__":
    unittest.main()
