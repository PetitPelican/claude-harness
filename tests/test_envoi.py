# -*- coding: utf-8 -*-
"""Le garde des envois (0.19.18) : un commit passe ; un push, ou un merge vers la
branche principale, attend le clic de l'humain (`ask`, jamais un refus)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import envoi  # noqa: E402

LANCEUR = os.path.join(os.path.dirname(__file__), "..", "bin", "harnais")


def sur(branche):
    return lambda dossier: branche


class Push(unittest.TestCase):
    def test_toutes_les_formes(self):
        for cmd in ("git push", "git push origin feat", "git -C code push origin HEAD",
                    "cd code && git push -u origin x", "echo ok; git push",
                    "env GIT_TRACE=1 git push", "/usr/bin/git push --tags"):
            self.assertIsNotNone(envoi.a_envoyer(cmd, "/p", sur("feat")), cmd)

    def test_a_blanc_passe(self):
        for cmd in ("git push --dry-run origin main", "git push -n"):
            self.assertIsNone(envoi.a_envoyer(cmd, "/p", sur("main")), cmd)

    def test_le_commit_passe(self):
        for cmd in ("git commit -m 'push it'", "git add -A && git commit -m x",
                    "git log --grep=push", "git fetch && git status"):
            self.assertIsNone(envoi.a_envoyer(cmd, "/p", sur("main")), cmd)


class Merge(unittest.TestCase):
    def test_vers_main_attend(self):
        self.assertIsNotNone(envoi.a_envoyer("git merge feat", "/p", sur("main")))
        self.assertIsNotNone(envoi.a_envoyer("git merge --no-ff feat", "/p", sur("master")))

    def test_entre_branches_de_travail_passe(self):
        self.assertIsNone(envoi.a_envoyer("git merge main", "/p", sur("feat")))

    def test_checkout_main_puis_merge_sur_la_meme_ligne(self):
        self.assertIsNotNone(envoi.a_envoyer("git checkout main && git merge feat", "/p", sur("feat")))
        self.assertIsNotNone(envoi.a_envoyer("git switch main; git merge feat", "/p", sur("feat")))
        self.assertIsNone(envoi.a_envoyer("git switch -c essai && git merge feat", "/p", sur("main")))

    def test_le_dossier_vise_compte(self):
        vus = []

        def courante(d):
            vus.append(d)
            return "main" if d.endswith("code") else "feat"
        self.assertIsNotNone(envoi.a_envoyer("git -C code merge feat", "/p", courante))
        self.assertTrue(vus[-1].endswith("code"))

    def test_abandon_passe(self):
        self.assertIsNone(envoi.a_envoyer("git merge --abort", "/p", sur("main")))

    def test_merge_base_n_est_pas_un_merge(self):
        self.assertIsNone(envoi.a_envoyer("git merge-base main feat", "/p", sur("main")))


class GitHub(unittest.TestCase):
    def test_gh(self):
        self.assertIsNotNone(envoi.a_envoyer("gh pr merge 12 --squash", "/p", sur("feat")))
        self.assertIsNotNone(envoi.a_envoyer("gh api -X PUT repos/o/r/pulls/3/merge", "/p", sur("feat")))
        self.assertIsNone(envoi.a_envoyer("gh pr view 12", "/p", sur("main")))
        self.assertIsNone(envoi.a_envoyer("gh api repos/o/r/pulls/3/merge", "/p", sur("main")))


class Hook(unittest.TestCase):
    def test_powershell(self):
        d = {"tool_name": "PowerShell", "cwd": "C:\\p",
             "tool_input": {"command": "Set-Location C:\\p\\code; git push origin feat"}}
        self.assertIsNotNone(envoi.juge(d))

    def test_autre_outil(self):
        self.assertIsNone(envoi.juge({"tool_name": "Read", "tool_input": {"file_path": "push"}}))


class Lanceur(unittest.TestCase):
    def lance(self, cmd, cwd):
        entree = {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": cmd}}
        return subprocess.run(["sh", LANCEUR, "envoi"], input=json.dumps(entree).encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

    def test_par_le_lanceur(self):
        with tempfile.TemporaryDirectory() as t:
            subprocess.run(["git", "init", "-q", "-b", "main", t], check=True)
            o = self.lance("git merge feat", t)
            self.assertEqual(o.returncode, 0, o.stderr)
            sortie = json.loads(o.stdout.decode("utf-8"))["hookSpecificOutput"]
            self.assertEqual(sortie["permissionDecision"], "ask")
            o = self.lance("git commit -m push", t)
            self.assertEqual((o.returncode, o.stdout), (0, b""), o.stderr)


if __name__ == "__main__":
    unittest.main()
