# -*- coding: utf-8 -*-
"""Le garde des questions aux boutons (0.19.17) : une question sans motif de la
liste fermée ne part pas ; avec son motif, elle part ; un agent dont le métier est
de questionner (`HARNAIS_QUESTIONS=libres`) n'est pas filtré."""
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import questions  # noqa: E402

LANCEUR = os.path.join(os.path.dirname(__file__), "..", "bin", "harnais")


def appel(*textes):
    return {"tool_name": "AskUserQuestion", "tool_input": {"questions": [
        {"header": "Q%d" % i, "question": t, "multiSelect": False,
         "options": [{"label": "Oui", "description": "x"}, {"label": "Non", "description": "y"}]}
        for i, t in enumerate(textes)]}}


class Garde(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {"HARNAIS_QUESTIONS": ""})
        p.start()
        self.addCleanup(p.stop)

    def test_sans_motif_elle_ne_part_pas(self):
        m = questions.juge(appel("J'envoie le code en revue sur la branche de travail ?"))
        self.assertIsNotNone(m)
        self.assertIn("Motif →", m)
        self.assertIn("décide toi-même", m)

    def test_avec_son_motif_elle_part(self):
        for t in ("Je publie la version ? Motif → production.",
                  "Copie complète des classeurs, noms et ventes compris : as-tu l'accord du "
                  "propriétaire ? Motif → données",
                  "On supprime l'ancien dépôt ? motif: irréversible",
                  "Je l'ouvre au public ? Motif -> périmètre"):
            self.assertIsNone(questions.juge(appel(t)), t)

    def test_un_mot_hors_liste_ne_vaut_pas_motif(self):
        self.assertIsNotNone(questions.juge(appel("On garde le prénom ? Motif → confort")))

    def test_dans_un_lot_seules_les_questions_sans_motif_sont_nommees(self):
        m = questions.juge(appel("Je publie ? Motif → production", "Quel nom pour la branche ?"))
        self.assertIn("[Q1]", m)
        self.assertNotIn("[Q0]", m)

    def test_un_agent_qui_questionne_par_metier(self):
        with mock.patch.dict(os.environ, {"HARNAIS_QUESTIONS": "libres"}):
            self.assertIsNone(questions.juge(appel("Python : où en es-tu ?")))

    def test_autre_outil_ou_entree_bizarre(self):
        self.assertIsNone(questions.juge({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
        self.assertIsNone(questions.juge({"tool_name": "AskUserQuestion", "tool_input": {}}))


class Lanceur(unittest.TestCase):
    def lance(self, entree, **env):
        return subprocess.run(["sh", LANCEUR, "questions"], input=json.dumps(entree).encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=dict(os.environ, HARNAIS_QUESTIONS="", **env), timeout=30)

    def test_sans_motif_refus(self):
        o = self.lance(appel("Quel nom pour la branche ?"))
        self.assertEqual(o.returncode, 0, o.stderr)
        self.assertEqual(json.loads(o.stdout.decode("utf-8"))["hookSpecificOutput"]["permissionDecision"],
                         "deny")

    def test_avec_motif_rien(self):
        o = self.lance(appel("Je publie ? Motif → production"))
        self.assertEqual((o.returncode, o.stdout), (0, b""), o.stderr)


if __name__ == "__main__":
    unittest.main()
