# -*- coding: utf-8 -*-
"""Une question déjà posée ne se repose pas (constat du 14/10/2026 : le
commanditaire se voyait poser 4 fois la même question). Le briefing, servi avant chaque message —
ceux d'un pair compris — lit le registre de la garde de fin de tour."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import attente  # noqa: E402
import briefing  # noqa: E402

TODO = """# Ce qui attend

- [ ] !haut @user **Je relance les trois agents ? 1 oui / 2 non**
      1 → je relance.
      2 → rien.
      fini quand → ils répondent.
- [ ] !moyen @user **Je publie la version ? 1 oui / 2 non**
      1 → je publie.
      2 → j'attends.
      fini quand → la version est servie.
"""


class Posees(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="posees-")
        self.addCleanup(shutil.rmtree, self.d, True)
        p = mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": self.d, "ATTENTE_DESTINATAIRES": "user"})
        p.start()
        self.addCleanup(p.stop)
        os.makedirs(os.path.join(self.d, "attente"))
        for cible, val in (("racine_de", lambda ici: ("/x/Agent", None)), ("nom_agent", lambda r: "Agent")):
            m = mock.patch.object(attente, cible, val)
            m.start()
            self.addCleanup(m.stop)

    def inscrit(self, *titres):
        with open(attente.registre_posees("Agent"), "w", encoding="utf-8") as h:
            h.write("\n".join(attente.sha16(t) for t in titres))

    def test_rien_de_pose_demande_de_poser_une_fois(self):
        ligne = briefing.ligne_posees(TODO, "/x")
        self.assertIn("pose-la aux boutons", ligne)

    def test_tout_pose_interdit_de_reposer(self):
        titres = [q.titre for q in attente.questions_ouvertes(TODO)]
        self.assertEqual(len(titres), 2)
        self.inscrit(*titres)
        ligne = briefing.ligne_posees(TODO, "/x")
        self.assertIn("repose-les aux boutons", ligne)
        self.assertIn("jamais dans un tour lancé par un pair", ligne)
        self.assertNotIn("avant tout le reste", ligne)
        # 28/10/2026 : la ligne qui annonçait une réponse attendue sans la question.
        self.assertIn("jamais « ta réponse est attendue » sans la question", ligne)
        self.assertNotIn("au plus une ligne", ligne)

    def test_une_neuve_une_vue(self):
        """TÉMOIN : la neuve reste à poser — un briefing qui tairait tout passerait
        les deux autres essais."""
        self.inscrit(attente.questions_ouvertes(TODO)[0].titre)
        ligne = briefing.ligne_posees(TODO, "/x")
        self.assertIn("1 nouvelle(s) à poser aux boutons", ligne)
        self.assertIn("1 autre(s) sont déjà posées", ligne)

    def test_meme_titre_que_la_garde(self):
        """Le registre est écrit par la garde avec SES titres : le briefing doit
        lire les mêmes, sinon une question posée passerait pour neuve."""
        self.assertEqual(attente.questions_ouvertes(TODO)[0].titre,
                         "Je relance les trois agents ? 1 oui / 2 non")


if __name__ == "__main__":
    unittest.main()
