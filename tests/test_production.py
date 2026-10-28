# -*- coding: utf-8 -*-
"""Le garde de la Production (0.19) : une équipe typée naît fermée, seul l'agent
nommé pousse, et seulement muni d'un laissez-passer daté. Chaque refus a son témoin."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import adopte  # noqa: E402
import production  # noqa: E402


def muet(f, *a):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return f(*a)


class Base(unittest.TestCase):
    def setUp(self):
        self.h = os.path.realpath(tempfile.mkdtemp(prefix="prod-"))
        self.addCleanup(shutil.rmtree, self.h, True)
        env = mock.patch.dict(os.environ, {"HOME": self.h, "USERPROFILE": self.h,
                                           "CLAUDE_PLUGIN_DATA": os.path.join(self.h, "data")})
        env.start()
        self.addCleanup(env.stop)

    def equipe(self, *extra):
        x = os.path.join(self.h, "Equipe")
        os.makedirs(x)
        self.assertEqual(muet(adopte.main, [x, "--equipe", "OPS,PO", "--go"] + list(extra)), 0)
        return x

    def juge(self, agent_dir, cmd, cwd=None):
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": agent_dir}):
            return production.juge({"tool_name": "Bash", "cwd": cwd or agent_dir,
                                    "tool_input": {"command": cmd}})

    def passe(self, agent_dir, motif="oui de l'humain"):
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": agent_dir}):
            return muet(production.laissez_passer, [motif])


class Equipe(Base):
    def setUp(self):
        super().setUp()
        self.x = self.equipe("--modeles", "ops,po")
        self.ops = os.path.join(self.x, "agents", "OPS")
        self.po = os.path.join(self.x, "agents", "PO")

    def test_une_equipe_typee_nait_fermee(self):
        e = production._entete(os.path.join(self.x, "fact", "rules.md"))
        self.assertEqual(e["production-agent"], "OPS")
        self.assertIn("main", e["production"])

    def test_po_ne_pousse_jamais_sur_main_meme_muni(self):
        for cmd in ("git push origin main", "git push origin HEAD:main", "git push origin +main",
                    "git push origin refs/heads/main", "git push --all", "git push origin 'refs/heads/*'",
                    "env X=1 git push origin main", "echo ok && git push origin main",
                    "cd code && git push origin main", "git -C code push origin main",
                    "gh pr merge 12 --merge"):
            m = self.juge(self.po, cmd)
            self.assertIsNotNone(m, cmd)
            self.assertIn("OPS", m, cmd)
        self.assertEqual(self.passe(self.po), 1, "PO ne s'accorde pas de laissez-passer")
        self.assertIsNotNone(self.juge(self.po, "git push origin main"))
        # TÉMOIN : sa branche de travail passe.
        self.assertIsNone(self.juge(self.po, "git push origin po"))
        self.assertIsNone(self.juge(self.po, "git -C code push origin dev"))

    def test_un_push_nu_depuis_main_est_vu(self):
        code_ops = os.path.join(self.ops, "code")      # le dépôt principal, sur `main`
        self.assertIsNotNone(self.juge(self.po, "git push", cwd=code_ops))
        # TÉMOIN : depuis la copie de PO, sur sa branche `po`.
        self.assertIsNone(self.juge(self.po, "git push", cwd=os.path.join(self.po, "code")))

    def test_ops_pousse_avec_un_laissez_passer_et_seulement_avec(self):
        m = self.juge(self.ops, "git push origin main")
        self.assertIsNotNone(m)
        self.assertIn("laissez-passer", m)
        self.assertEqual(self.passe(self.ops, "l'humain : « oui, mets en ligne »"), 0)
        self.assertIsNone(self.juge(self.ops, "git push origin main"))
        projet = self.x
        _, log = production._fichiers(projet)
        with open(log, encoding="utf-8") as h:
            j = h.read()
        self.assertIn("déposé", j)
        self.assertIn("usage", j)
        # TÉMOIN : périmé, il ne sert plus.
        f, _ = production._fichiers(projet)
        vieux = time.time() - 16 * 60
        os.utime(f, (vieux, vieux))
        self.assertIsNotNone(self.juge(self.ops, "git push origin main"))

    def test_le_hook_rend_un_refus_lisible_par_claude_code(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.po}), contextlib.redirect_stdout(out):
            production.main(json.dumps({"tool_name": "Bash", "cwd": self.po,
                                        "tool_input": {"command": "git push origin main"}}))
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "deny")


class SansReglage(Base):
    def test_rien_n_est_ferme_sans_reglage(self):
        """TÉMOIN de tout le reste : une équipe sans agent OPS ne ferme rien."""
        x = self.equipe()
        self.assertIsNone(self.juge(os.path.join(x, "agents", "PO"), "git push origin main"))


class Seul(Base):
    def test_un_projet_seul_se_ferme_par_ses_regles(self):
        p = os.path.join(self.h, "Mono")
        os.makedirs(p)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=p, check=True)
        muet(adopte.main, [p, "--go"])
        self.assertIsNone(self.juge(p, "git push origin main"), "pas de réglage : ouvert")
        f = os.path.join(p, "brain", "fact", "rules.md")
        with open(f, encoding="utf-8") as h:
            t = h.read()
        with open(f, "w", encoding="utf-8") as h:
            h.write("---\nproduction: main\n---\n" + t)
        self.assertIsNotNone(self.juge(p, "git push origin main"))
        self.assertEqual(self.passe(p), 0)
        self.assertIsNone(self.juge(p, "git push origin main"))


if __name__ == "__main__":
    unittest.main()
