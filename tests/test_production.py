# -*- coding: utf-8 -*-
"""Le garde de la Production (0.19) : une équipe typée naît fermée, seul l'agent
nommé pousse, et seulement muni d'un laissez-passer daté. Chaque refus a son témoin."""
import contextlib
import io
import json
import os
import re
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

    def test_l_outil_powershell_pousse_aussi(self):
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.po}):
            m = production.juge({"tool_name": "PowerShell", "cwd": self.po,
                                 "tool_input": {"command": "git push origin main"}})
        self.assertIsNotNone(m)

    def test_le_hook_rend_un_refus_lisible_par_claude_code(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.po}), contextlib.redirect_stdout(out):
            production.main(json.dumps({"tool_name": "Bash", "cwd": self.po,
                                        "tool_input": {"command": "git push origin main"}}))
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "deny")


class Vercel(Base):
    """0.19.7 : la publication Vercel se ferme comme une branche de production."""
    PROD = ("vercel --prod", "vercel deploy --prod", "vercel deploy --prebuilt --prod",
            "npx vercel --prod", "npx --yes vercel@latest deploy --prod", "pnpm dlx vercel --prod",
            "env VERCEL_ORG_ID=x /usr/local/bin/vercel --prod", r'"C:\outils\vercel.cmd" --prod',
            "vercel --scope equipe --prod", "vercel -p site --prod", "vc --prod",
            "vercel --environment production", "vercel deploy --environment=production",
            "vercel --target production", "vercel promote dpl_123", "vercel rollback",
            "vercel redeploy site.vercel.app", "vercel redeploy site.vercel.app -e production",
            "echo ok && vercel --prod", "cd web && npx vercel deploy --prod")
    TEMOINS = ("vercel", "vercel deploy", "vercel -p site", "vercel --project site",
               "npx vercel deploy --yes", "vercel --environment preview", "vercel build --prod",
               "vercel pull --environment=production", "vercel promote status",
               "vercel redeploy site.vercel.app --environment preview", "vercel ls",
               "git push origin main", "grep -r 'vercel --prod' .")

    def setUp(self):
        super().setUp()
        x = self.equipe("--modeles", "ops,po")
        self.ops = os.path.join(x, "agents", "OPS")
        self.po = os.path.join(x, "agents", "PO")
        f = os.path.join(x, "fact", "rules.md")
        with open(f, encoding="utf-8") as h:
            t = h.read()
        # Un projet Vercel seul : pas de branche fermée, seule la publication l'est.
        t = re.sub(r"(?m)^production:.*\n", "production-commandes: vercel\n", t, count=1)
        with open(f, "w", encoding="utf-8") as h:
            h.write(t)

    def test_le_garde_mord_sans_laissez_passer_et_s_ouvre_avec(self):
        for cmd in self.PROD:
            m = self.juge(self.ops, cmd)
            self.assertIsNotNone(m, cmd)
            self.assertIn("laissez-passer", m, cmd)
        for cmd in self.TEMOINS:
            self.assertIsNone(self.juge(self.ops, cmd), cmd)
        self.assertEqual(self.passe(self.ops, "l'humain : « oui, publie »"), 0)
        for cmd in self.PROD:
            self.assertIsNone(self.juge(self.ops, cmd), cmd)

    def test_seul_l_agent_nomme_publie(self):
        self.assertEqual(self.passe(self.po), 1)
        for cmd in self.PROD:
            m = self.juge(self.po, cmd)
            self.assertIsNotNone(m, cmd)
            self.assertIn("OPS", m, cmd)
        self.assertIsNone(self.juge(self.po, "vercel deploy"))

    def test_rien_sans_la_cle(self):
        """TÉMOIN : une équipe qui ferme ses branches sans déclarer vercel le laisse ouvert."""
        x = os.path.join(self.h, "Autre")
        os.makedirs(x)
        muet(adopte.main, [x, "--equipe", "OPS,PO", "--modeles", "ops,po", "--go"])
        self.assertIsNone(self.juge(os.path.join(x, "agents", "OPS"), "vercel --prod"))
        self.assertIsNotNone(self.juge(os.path.join(x, "agents", "OPS"), "git push origin main"))

    def test_le_garde_voit_le_laissez_passer_pose_depuis_le_shell(self):
        """0.19.9 (relevé par un agent seul le 04/11) : le crochet tourne avec
        CLAUDE_PLUGIN_DATA, le shell de l'agent sans. Le laissez-passer posé à la
        main finissait dans `~/.claude`, le garde le cherchait ailleurs."""
        sans = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"}
        with mock.patch.dict(os.environ, sans, clear=True):
            self.assertEqual(self.passe(self.ops, "l'humain : « oui »"), 0)
        self.assertIn("CLAUDE_PLUGIN_DATA", os.environ)
        self.assertIsNone(self.juge(self.ops, "vercel --prod"))

    def test_l_outil_powershell_ne_contourne_pas(self):
        def ps(agent, cmd):
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": agent}):
                return production.juge({"tool_name": "PowerShell", "cwd": agent,
                                        "tool_input": {"command": cmd}})
        for cmd in (r'& "C:\Program Files\nodejs\vercel.cmd" --prod', r"C:\outils\vercel.exe deploy --prod",
                    "npx vercel --prod; Write-Output fini", "vercel promote dpl_1"):
            self.assertIsNotNone(ps(self.ops, cmd), cmd)
        self.assertIsNone(ps(self.ops, r"C:\outils\vercel.exe -p site"))
        self.assertEqual(self.passe(self.ops), 0)
        self.assertIsNone(ps(self.ops, "npx vercel --prod"))

    def test_le_hook_refuse_vercel(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.ops}), contextlib.redirect_stdout(out):
            production.main(json.dumps({"tool_name": "Bash", "cwd": self.ops,
                                        "tool_input": {"command": "npx vercel deploy --prod"}}))
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

    def test_un_projet_seul_qui_se_nomme_obtient_son_laissez_passer(self):
        """0.19.8 (relevé par un agent seul le 04/11) : `production-agent:` au nom du
        projet refusait tout le monde, l'agent seul compris (« tu es « ? » »)."""
        p = os.path.join(self.h, "Solo")
        os.makedirs(p)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=p, check=True)
        muet(adopte.main, [p, "--go"])
        f = os.path.join(p, "brain", "fact", "rules.md")
        with open(f, encoding="utf-8") as h:
            t = h.read()
        with open(f, "w", encoding="utf-8") as h:
            h.write("---\nproduction-commandes: vercel\nproduction-agent: Solo\n---\n" + t)
        self.assertEqual(production.agent_appelant(p), "Solo")
        self.assertEqual(production.agent_appelant(os.path.join(p, "brain")), "Solo")
        self.assertIsNotNone(self.juge(p, "vercel --prod"))
        self.assertEqual(self.passe(p), 0)
        self.assertIsNone(self.juge(p, "vercel --prod"))
        # TÉMOIN : un autre nom reste refusé, même dans un projet seul.
        with open(f, "w", encoding="utf-8") as h:
            h.write("---\nproduction-commandes: vercel\nproduction-agent: OPS\n---\n" + t)
        self.assertEqual(self.passe(p), 1)
        self.assertIn("OPS", self.juge(p, "vercel --prod"))


if __name__ == "__main__":
    unittest.main()
