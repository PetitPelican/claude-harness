# -*- coding: utf-8 -*-
"""Le verrou des consignes (décision du 14/10/2026) : seuls le CTO et Harness écrivent
un CLAUDE.md ; tout le monde lit. Chaque refus a son témoin qui passe."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import consignes  # noqa: E402

LANCEUR = os.path.join(os.path.dirname(__file__), "..", "bin", "harnais")


def bash(c):
    return {"tool_name": "Bash", "tool_input": {"command": c}}


def edit(p, outil="Edit"):
    return {"tool_name": outil, "tool_input": {"file_path": p}}


class Verrou(unittest.TestCase):

    def en(self, nom):
        d = os.path.join(tempfile.mkdtemp(prefix="consignes-"), nom)
        os.makedirs(d)
        p = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": d})
        p.start()
        self.addCleanup(p.stop)

    def test_un_agent_ne_modifie_pas_ses_consignes(self):
        self.en("Alpha PO")
        for d in (edit("/x/Alpha/agents/Alpha PO/CLAUDE.md"), edit("/x/CLAUDE.md", "Write"),
                  edit("/x/claude.md", "MultiEdit"),
                  bash("echo x >> CLAUDE.md"), bash("sed -i '' 's/a/b/' ../../CLAUDE.md"),
                  bash("git -C code rm CLAUDE.md"), bash("rm -f code/CLAUDE.md"),
                  bash("cat > \"/x/agents/Alpha QA/CLAUDE.md\" <<'EOF'\nx\nEOF"),
                  bash("python3 -c \"open('CLAUDE.md','w').write('x')\""),
                  bash("mv CLAUDE.md CLAUDE.md.vieux")):
            self.assertIsNotNone(consignes.juge(d), d)

    def test_temoin_lire_passe(self):
        """TÉMOIN : un verrou qui refuserait tout passerait l'essai précédent."""
        self.en("Alpha PO")
        for d in (bash("cat CLAUDE.md"), bash("grep -n memoire ../../CLAUDE.md"),
                  bash("head -20 CLAUDE.md | wc -l"), bash("git log --oneline -- CLAUDE.md"),
                  bash("diff a/CLAUDE.md b/CLAUDE.md"), edit("/x/agents/Alpha PO/todo.md"),
                  edit("/x/CLAUDE.md.notes"), {"tool_name": "Read", "tool_input": {"file_path": "/x/CLAUDE.md"}},
                  bash("echo x >> todo.md")):
            self.assertIsNone(consignes.juge(d), d)

    def test_temoin_nommer_n_est_pas_ecrire(self):
        """QA, 14/10 (0.18.2) : une ligne de todo qui CITE le fichier de consignes était
        refusée. Seule la cible d'une écriture compte."""
        self.en("Alpha QA")
        for d in (bash("cat >> todo.md <<'EOF'\n- [ ] le CLAUDE.md du projet cite memoire/\nEOF"),
                  bash('echo "voir CLAUDE.md" >> todo.md'), bash("cp CLAUDE.md /tmp/copie"),
                  bash("git -C code log -- CLAUDE.md > /tmp/hist"),
                  bash("python3 - <<'EOF'\nprint(open('CLAUDE.md').read())\nEOF"),
                  bash("grep -c x CLAUDE.md && echo ok >> todo.md")):
            self.assertIsNone(consignes.juge(d), d)

    def test_un_script_qui_ecrit_reste_refuse(self):
        self.en("Alpha QA")
        for d in (bash("python3 - <<'EOF'\nopen('agents/QA/CLAUDE.md', 'a').write('x')\nEOF"),
                  bash("cp /tmp/neuf ../../CLAUDE.md"), bash("tee -a CLAUDE.md < x"),
                  bash("ln -sf /tmp/x CLAUDE.md"), bash('echo x > "/a b/CLAUDE.md"')):
            self.assertIsNotNone(consignes.juge(d), d)

    def test_le_cto_et_harness_ecrivent(self):
        for nom in consignes.GARDIENS:
            self.en(nom)
            self.assertIsNone(consignes.juge(edit("/x/Alpha/CLAUDE.md")), nom)
            self.assertIsNone(consignes.juge(bash("echo x >> /x/CLAUDE.md")), nom)

    def test_un_nom_proche_ne_passe_pas(self):
        self.en("CTO-bis")
        self.assertIsNotNone(consignes.juge(edit("/x/CLAUDE.md")))

    def test_par_le_lanceur(self):
        """Le hook tel qu'il part : le refus sort en JSON de décision."""
        d = os.path.join(tempfile.mkdtemp(prefix="consignes-"), "Alpha")
        os.makedirs(d)
        o = subprocess.run(["sh", LANCEUR, "consignes"], input=json.dumps(edit("/x/CLAUDE.md")).encode(),
                           stdout=subprocess.PIPE, env=dict(os.environ, CLAUDE_PROJECT_DIR=d))
        self.assertEqual(o.returncode, 0)
        self.assertEqual(json.loads(o.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        o = subprocess.run(["sh", LANCEUR, "consignes"], input=json.dumps(edit("/x/todo.md")).encode(),
                           stdout=subprocess.PIPE, env=dict(os.environ, CLAUDE_PROJECT_DIR=d))
        self.assertEqual((o.returncode, o.stdout), (0, b""))


if __name__ == "__main__":
    unittest.main()
