# -*- coding: utf-8 -*-
"""Le garde de l'ouverture de session (0.19.10) : un agent qui a déjà une
session, on lui écrit. Les trois cas réels du 03-04/11 refusés ; un dossier
sans session, le sien, une proposition déjà jugée passent."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import ouverture  # noqa: E402

LANCEUR = os.path.join(os.path.dirname(__file__), "..", "bin", "harnais")
START = "mcp__ccd_session__start_session"


class Base(unittest.TestCase):
    def setUp(self):
        self.h = os.path.realpath(tempfile.mkdtemp(prefix="ouv-"))
        self.addCleanup(shutil.rmtree, self.h, True)
        self.fiches = os.path.join(self.h, "app", "compte", "org")
        os.makedirs(self.fiches)
        self.atelier = os.path.join(self.h, "atelier")
        for a in ("Analyste", "Designer", "Editeur", "Harness", "Neuf",
                  "EquipeA/agents/PO", "EquipeB/agents/PO"):
            os.makedirs(os.path.join(self.atelier, a, ".claude"))
            open(os.path.join(self.atelier, a, ".claude", "settings.json"), "w").close()
        self.session("local_analyste", "ANALYSTE", "Analyste", "cli-analyste")
        self.session("local_designer", "Designer", "Designer", "cli-designer")
        self.session("local_editeur", "Editor", "Editeur", "cli-editeur")
        self.session("local_harness", "Harness", "Harness", "cli-harness")
        self.session("local_apo", "A-PO", "EquipeA/agents/PO", "cli-apo")
        self.session("local_vieux", "Neuf", "Neuf", "cli-vieux", archivee=True)
        env = mock.patch.dict(os.environ, {"HARNAIS_SESSIONS_APP": os.path.join(self.h, "app"),
                                           "CLAUDE_PROJECT_DIR": self.dossier("Analyste")})
        env.start()
        self.addCleanup(env.stop)

    def dossier(self, a):
        return os.path.join(self.atelier, *a.split("/"))

    def session(self, sid, titre, dossier, cli, archivee=False):
        with open(os.path.join(self.fiches, sid + ".json"), "w", encoding="utf-8") as h:
            json.dump({"sessionId": sid, "title": titre, "cwd": self.dossier(dossier),
                       "cliSessionId": cli, "isArchived": archivee}, h)

    def juge(self, entree, outil=START, moi="cli-analyste"):
        return ouverture.juge({"tool_name": outil, "session_id": moi,
                               "cwd": self.dossier("Analyste"), "tool_input": entree})


class Refus(Base):
    def test_le_cas_du_03_11_un_cwd_vers_un_agent_ouvert(self):
        m = self.juge({"initiation": "user_asked", "title": "Contrat d'Analyste dans le savoir-faire",
                       "cwd": self.dossier("Harness"), "prompt": "x"})
        self.assertIsNotNone(m)
        self.assertIn("local_harness", m)
        self.assertIn("SendMessage", m)

    def test_le_cas_du_04_11_un_titre_qui_nomme_l_agent(self):
        m = self.juge({"initiation": "user_asked", "title": "Designer — logo du portail, puis cadrage",
                       "name": "designer", "use_worktree": False, "prompt": "x"})
        self.assertIn("local_designer", m)

    def test_une_proposition_nommant_l_agent_aussi(self):
        """« offer » et « own_initiative » : la même erreur, une carte en plus."""
        for init in ("offer", "own_initiative"):
            m = self.juge({"initiation": init, "title": "Éditeur : page projet SEO sur le portail"})
            self.assertIn("local_editeur", m, init)

    def test_un_sous_dossier_de_l_agent_vise(self):
        self.assertIsNotNone(self.juge({"initiation": "user_asked", "title": "x",
                                        "cwd": os.path.join(self.dossier("Designer"), "docs")}))

    def test_un_agent_d_equipe_par_le_titre_de_sa_session(self):
        self.assertIn("local_apo", self.juge({"initiation": "offer", "title": "A-PO : la recette"}))

    def test_le_transfert_aussi(self):
        self.assertIsNotNone(self.juge({"title": "Designer : reprendre la maquette",
                                        "remaining_plan": "x"},
                                       outil="mcp__ccd_session__hand_off_to_session"))


class Passe(Base):
    def test_un_dossier_sans_session(self):
        """L'humain reste libre de lancer un agent sous un autre : sa carte suffit."""
        self.assertIsNone(self.juge({"initiation": "user_asked", "title": "x",
                                     "cwd": self.dossier("EquipeB/agents/PO")}))

    def test_une_session_archivee_ne_compte_pas(self):
        self.assertIsNone(self.juge({"initiation": "user_asked", "title": "Neuf : démarrer",
                                     "cwd": self.dossier("Neuf")}))

    def test_son_propre_dossier(self):
        self.assertIsNone(self.juge({"initiation": "user_asked", "title": "ANALYSTE : à côté",
                                     "cwd": self.dossier("Analyste")}))
        self.assertIsNone(self.juge({"initiation": "own_initiative", "title": "Ménage des accès",
                                     "prompt": "x"}))

    def test_un_titre_qui_cite_un_agent_sans_le_viser(self):
        self.assertIsNone(self.juge({"initiation": "offer",
                                     "title": "Contrat d'Analyste dans le savoir-faire du Designer"}))

    def test_le_nom_d_un_dossier_d_equipe_n_est_pas_un_agent(self):
        """`agents/PO` existe dans chaque équipe : « PO » seul ne désigne personne."""
        self.assertIsNone(self.juge({"initiation": "offer", "title": "PO : relire la recette"}))

    def test_une_proposition_deja_jugee(self):
        self.assertIsNone(self.juge({"proposal_id": "task_ab12cd34"}))

    def test_l_appelant_ne_se_compte_pas(self):
        """La seule session du dossier visé est celle qui appelle (lancée d'ailleurs) :
        elle ne se refuse pas à elle-même. TÉMOIN : un autre appelant est refusé."""
        def depuis(cli):
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.dossier("Neuf")}):
                return ouverture.juge({
                    "tool_name": START, "session_id": cli, "cwd": self.dossier("Neuf"),
                    "tool_input": {"initiation": "user_asked", "title": "x",
                                   "cwd": self.dossier("Editeur")}})
        self.assertIsNone(depuis("cli-editeur"))
        self.assertIsNotNone(depuis("cli-autre"))

    def test_sans_fiches_rien_n_est_refuse(self):
        with mock.patch.dict(os.environ, {"HARNAIS_SESSIONS_APP": os.path.join(self.h, "rien")}):
            self.assertIsNone(self.juge({"initiation": "user_asked", "title": "Designer — x"}))

    def test_un_autre_outil(self):
        self.assertIsNone(ouverture.juge({"tool_name": "Bash", "tool_input": {"command": "ls"}}))


class Lanceur(Base):
    """Le hook tel qu'il part : JSON passé au lanceur, décision en JSON, code 0."""

    def lance(self, entree):
        return subprocess.run(["sh", LANCEUR, "ouverture"], input=json.dumps(entree).encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ),
                              timeout=30)

    def test_session_ouverte_refus(self):
        o = self.lance({"tool_name": START, "session_id": "cli-analyste", "cwd": self.dossier("Analyste"),
                        "tool_input": {"initiation": "user_asked", "title": "x", "prompt": "x",
                                       "cwd": self.dossier("Editeur")}})
        self.assertEqual(o.returncode, 0, o.stderr)
        d = json.loads(o.stdout.decode("utf-8"))["hookSpecificOutput"]
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("local_editeur", d["permissionDecisionReason"])

    def test_dossier_sans_session_laisse_passer(self):
        o = self.lance({"tool_name": START, "session_id": "cli-analyste", "cwd": self.dossier("Analyste"),
                        "tool_input": {"initiation": "user_asked", "title": "x", "prompt": "x",
                                       "cwd": self.dossier("EquipeB/agents/PO")}})
        self.assertEqual((o.returncode, o.stdout), (0, b""), o.stderr)


if __name__ == "__main__":
    unittest.main()
