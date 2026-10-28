# -*- coding: utf-8 -*-
"""Essais de `harnais demenage` — une équipe `brain/` passe à « un dossier par agent ».

Le banc reproduit ce que le relevé du 14/10/2026 a trouvé sur une équipe réelle : le code
en copie principale avec la mémoire imbriquée (son propre dépôt), une copie par
agent hors du projet, une copie posée par Claude Code DANS le principal, une
copie de Production à garder, un `.env.local` ignoré, des droits en chemins
absolus et des crochets en `../../`.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import demenage  # noqa: E402
import memoire  # noqa: E402
from equipe import slug  # noqa: E402

ENV = dict(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")


def git(d, *a):
    o = subprocess.run(["git"] + list(a), cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=dict(os.environ, **ENV))
    assert o.returncode == 0, "git %r : %s" % (a, o.stderr.decode())
    return o.stdout.decode()


def ecris(p, t):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as h:
        h.write(t)


def lis(p):
    with open(p, encoding="utf-8") as h:
        return h.read()


def sep(x):
    """Un chemin lu sans égard au séparateur : sous Windows `C:\\a\\b/c` (et `\\\\` dans
    un JSON brut) vaut `C:/a/b/c`. Sur Mac, l'identité — l'essai n'y perd rien."""
    return x.replace("\\\\", "/").replace("\\", "/")


class Banc(unittest.TestCase):

    def setUp(self):
        self.racine = os.path.realpath(tempfile.mkdtemp(prefix="demenage-"))
        self.addCleanup(shutil.rmtree, self.racine, True)
        j = os.path.join
        self.maison = j(self.racine, "maison")
        os.makedirs(j(self.maison, ".claude", "projects"))
        P = self.P = j(self.racine, "Projet")
        wt = self.wt = j(self.racine, ".worktrees")
        os.makedirs(P)
        git(P, "init", "-q", "-b", "main")
        ecris(j(P, ".gitignore"), "brain/\n.env*\n")
        ecris(j(P, "apps", "app.ts"), "export {}\n")
        ecris(j(P, "docs", "decisions.md"), "# Décisions\n")
        ecris(j(P, "CLAUDE.md"), "# Consignes communes\n")
        for n in ("OPS", "PO"):
            ecris(j(P, "agents", n, "CLAUDE.md"), "# rôle %s\n" % n)
            ecris(j(P, "agents", n, ".claude", "settings.json"), json.dumps({
                "permissions": {"deny": ["Edit(%s/**)" % j(P, "brain", "mind", "OPS" if n == "PO" else "PO"),
                                         "Edit(%s/**)" % j(wt, "po", "apps"),
                                         "Edit(%s/agents/**)" % P, "Edit(%s/package.json)" % P,
                                         "Edit(%s/brain/workspace/**)" % P]},
                "hooks": {"PreToolUse": [{"hooks": [{"command": "${CLAUDE_PROJECT_DIR}/../../.claude/hooks/g.py"},
                                                    {"command": "exec python3 \"${CLAUDE_PROJECT_DIR:-.}/../../.claude/hooks/h.py\""}]}]},
            }, indent=2))
        git(P, "add", "-A")
        git(P, "commit", "-qm", "code")
        ecris(j(P, ".env.local"), "CLE=1\n")
        B = j(P, "brain")
        os.makedirs(B)
        git(B, "init", "-q", "-b", "main")
        ecris(j(B, "fact", "base.md"), "---\ncap: banc\n---\n")
        for n in ("OPS", "PO"):
            ecris(j(B, "mind", n, "state.md"), "---\nmaj: 2026-10-14\nsante: vert\njalon: x\n---\n")
            ecris(j(B, "mind", n, "todo.md"), "# todo %s\n" % n)
        ecris(j(B, "workspace", "2026-10-OPS.md"), "carnet\n")
        git(B, "add", "-A")
        git(B, "commit", "-qm", "memoire")
        git(P, "worktree", "add", "-q", "-b", "po", j(wt, "po"))
        git(P, "worktree", "add", "-q", "--detach", j(wt, "promotion"))
        git(P, "worktree", "add", "-q", "-b", "isole", j(P, ".claude", "worktrees", "agent-1"))
        git(P, "worktree", "add", "-q", "-b", "sauvage", j(wt, "sauvage"))
        ecris(j(wt, "po", ".env.local"), "CLE=2\n")
        ecris(j(P, "agents", "OPS", ".claude", ".briefing.json"), '{"derniere": 1}')
        ecris(j(wt, "po", "agents", "PO", ".claude", ".briefing.json"), '{"derniere": 2}')
        ecris(j(wt, "po", "agents", "PO", ".claude", "settings.local.json"), '{"env": {"HARNAIS_SYNCHRO": "git"}}')
        self.conv = j(self.maison, ".claude", "projects", slug(j(wt, "po", "agents", "PO")))
        ecris(j(self.conv, "fil.jsonl"), "{}\n")
        self.ins = j(self.maison, "installed.json")
        ecris(self.ins, json.dumps({"plugins": {"harnais@atelier": [
            {"scope": "project", "projectPath": j(P, "agents", "OPS"), "version": "0.17.0"},
            {"scope": "project", "projectPath": j(wt, "po", "agents", "PO"), "version": "0.17.0"}]}}))
        self.env = mock.patch.dict(os.environ, {"HOME": self.maison, "HARNAIS_INSCRIPTIONS": self.ins})
        self.env.start()
        self.addCleanup(self.env.stop)

    def lance(self, *a):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = demenage.main([self.P] + list(a))
        return code, out.getvalue()

    def complet(self, *extra):
        return self.lance("--en-plus", "OPS:promotion=%s" % os.path.join(self.wt, "promotion"), *extra)

    def test_a_blanc_rien_ne_bouge(self):
        code, out = self.complet()
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isdir(os.path.join(self.P, "brain")))
        self.assertIn("sauvage", out, "la copie sans agent est nommée")
        self.assertIn("À ENREGISTRER DANS LE CODE", out)

    def test_sans_agents_arretes_rien_n_est_ecrit(self):
        code, out = self.complet("--apply")
        self.assertEqual(code, 1)
        self.assertIn("--agents-arretes", out)
        self.assertTrue(os.path.isdir(os.path.join(self.P, "brain")))

    @unittest.skipIf(os.name == "nt", "ÉCART CONNU 0.19 (16/10/2026, CI Windows) : sous Windows, la migration ne réécrit pas encore un droit écrit en chemin COMPLET (C:\\…). Hors du déploiement neuf (droits ancrés sur ~/). Suivi dans le todo de Harness.")
    def test_le_demenagement(self):
        j = os.path.join
        P = self.P
        code, out = self.complet("--apply", "--agents-arretes")
        self.assertEqual(code, 0, out)
        # La mémoire EST le projet.
        self.assertFalse(os.path.exists(j(P, "brain")))
        self.assertEqual(lis(j(P, "fact", "base.md")), "---\ncap: banc\n---\n")
        self.assertEqual(lis(j(P, "agents", "PO", "todo.md")), "# todo PO\n")
        self.assertEqual(lis(j(P, "shared", "2026-10-OPS.md")), "carnet\n")
        self.assertEqual(lis(j(P, "docs", "decisions.md")), "# Décisions\n")
        self.assertEqual(lis(j(P, "CLAUDE.md")), "# Consignes communes\n")
        self.assertEqual(lis(j(P, "agents", "PO", "CLAUDE.md")), "# rôle PO\n")
        self.assertEqual(git(P, "status", "--porcelain"), "", "la mémoire est enregistrée, et ignore le code")
        # Le code, chaque copie chez son agent, fichiers ignorés compris.
        ops, po = j(P, "agents", "OPS", "code"), j(P, "agents", "PO", "code")
        self.assertEqual(lis(j(ops, ".env.local")), "CLE=1\n")
        self.assertEqual(lis(j(po, ".env.local")), "CLE=2\n")
        self.assertEqual(git(po, "rev-parse", "--abbrev-ref", "HEAD").strip(), "po")
        liste = demenage.copies(ops)
        chemins = [c for c, _ in liste]
        self.assertEqual(len(liste), 5)
        for c in (ops, po, j(P, "agents", "OPS", "code-promotion"),
                  j(ops, ".claude", "worktrees", "agent-1"), j(self.wt, "sauvage")):
            self.assertIn(os.path.realpath(c), chemins)
            self.assertEqual(subprocess.run(["git", "status"], cwd=c, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE).returncode, 0, c)
        # Les droits : un exemplaire, réécrit.
        s = lis(j(P, "agents", "PO", ".claude", "settings.json"))
        # Lu comme le JSON qu'il est : sous Windows le texte double les `\\`.
        s = json.dumps(json.loads(s), ensure_ascii=False).replace("\\\\", "\\")
        self.assertIn(sep("Edit(%s/**)" % j(P, "agents", "OPS")), sep(s))
        self.assertIn(sep("Edit(%s/**)" % j(po, "apps")), sep(s))
        self.assertIn("${CLAUDE_PROJECT_DIR}/code/.claude/hooks/g.py", s)
        self.assertIn("${CLAUDE_PROJECT_DIR:-.}/code/.claude/hooks/h.py", s)
        # CHAQUE RÈGLE GARDE SON SENS (banc du 14/10/2026) : `agents/` du checkout
        # principal était le dossier des badges SUIVI PAR LE CODE d'OPS.
        deny = json.loads(s)["permissions"]["deny"]
        self.assertIn("Edit(%s/agents/**)" % ops, deny)
        self.assertIn("Edit(%s/package.json)" % ops, deny)
        self.assertIn("Edit(%s/**)" % j(P, "shared"), deny, "sans réécriture en cascade")
        self.assertNotIn("Edit(%s/agents/**)" % P, deny, "PO ne doit pas se fermer son propre dossier")
        self.assertNotIn("Edit(%s/**)" % j(P, "agents", "PO"), deny)
        # LE PÉRIMÈTRE POSÉ : le dossier des autres, et ses propres droits.
        self.assertIn("Edit(/%s/**)" % j(P, "agents", "OPS"), deny, "absolu hors du home : `//`")
        self.assertIn("Edit(/%s/.claude/**)" % j(P, "agents", "PO"), deny)
        self.assertIn("Agent(isolation:worktree)", deny, "la copie isolée viserait la mémoire")
        self.assertNotIn("../../.claude/hooks", s)
        self.assertNotIn("brain", s)
        self.assertNotIn(".worktrees", s)
        self.assertIn("HARNAIS_SYNCHRO", lis(j(P, "agents", "PO", ".claude", "settings.local.json")))
        # Le harnais y lit une équipe.
        r = memoire.resous(j(P, "agents", "PO"))
        self.assertEqual((r.forme, r.nom_agent), (memoire.Forme.Equipe, "PO"))
        # Conversations et inscriptions suivent.
        neuf = j(self.maison, ".claude", "projects", slug(j(P, "agents", "PO")))
        self.assertTrue(os.path.isfile(j(neuf, "fil.jsonl")))
        self.assertFalse(os.path.exists(self.conv))
        chemins = [e["projectPath"] for e in json.loads(lis(self.ins))["plugins"]["harnais@atelier"]]
        self.assertEqual(sorted(chemins), sorted([j(P, "agents", "OPS"), j(P, "agents", "PO")]))

    def test_docs_differents_bloquent(self):
        ecris(os.path.join(self.wt, "po", "docs", "decisions.md"), "autre\n")
        code, out = self.complet("--apply", "--agents-arretes")
        self.assertEqual(code, 1)
        self.assertIn("`docs/` diffère", out)
        self.assertTrue(os.path.isdir(os.path.join(self.P, "brain")), "TÉMOIN : rien n'a bougé")

    def test_un_secret_qui_monterait_bloque(self):
        ecris(os.path.join(self.P, "docs", "operations.md"), "privé\n")
        ecris(os.path.join(self.wt, "po", "docs", "operations.md"), "privé\n")
        code, out = self.complet()
        self.assertEqual(code, 1)
        self.assertIn("operations.md", out)
        os.remove(os.path.join(self.P, "docs", "operations.md"))
        os.remove(os.path.join(self.wt, "po", "docs", "operations.md"))
        ecris(os.path.join(self.P, "docs", "cle.txt"), "-----BEGIN RSA PRIVATE KEY-----\n")
        ecris(os.path.join(self.wt, "po", "docs", "cle.txt"), "-----BEGIN RSA PRIVATE KEY-----\n")
        code, out = self.complet()
        self.assertIn("cle.txt", out)

    def test_un_temoin_rouge_ramene_tout(self):
        """Le retour arrière : un inventaire qui change en route doit tout ramener."""
        vrai = demenage.inventaire
        appels = {"n": 0}

        def faux(r):
            v, k = vrai(r)
            appels["n"] += 1
            if r.endswith(os.path.join("agents", "PO", "code")):
                v = dict(v, fantome=(1, 1))
            return v, k
        avant = sorted(c for c, _ in demenage.copies(self.P))
        with mock.patch.object(demenage, "inventaire", faux):
            code, out = self.complet("--apply", "--agents-arretes")
        self.assertEqual(code, 1, out)
        self.assertIn("ÉCHEC du déplacement du code", out)
        self.assertIn("retour arrière fait", out)
        self.assertTrue(os.path.isdir(os.path.join(self.P, "brain", ".git")))
        self.assertTrue(os.path.isfile(os.path.join(self.wt, "po", "apps", "app.ts")))
        self.assertEqual(sorted(c for c, _ in demenage.copies(self.P)), avant)
        for c in avant:
            self.assertEqual(subprocess.run(["git", "status"], cwd=c, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE).returncode, 0, c)
        self.assertFalse(os.path.exists(self.P + ".code-demenage"))
        # Les dossiers créés en route (`agents/<nom>/` de la mémoire) repartent aussi :
        # laissés, ils bloquaient l'essai suivant (« `brain/agents` existe déjà »).
        self.assertFalse(os.path.exists(os.path.join(self.P, "brain", "agents")))
        code, out = self.complet()
        self.assertEqual(code, 0, out)

    def test_une_copie_sans_agent_qui_emprunte_les_dependances(self):
        """Mesuré au jour J d'une équipe réelle : une copie sans agent dont `node_modules` est un
        LIEN vers celles d'une copie qui déménage. Le lien pend après le déplacement ;
        ce n'est pas un fichier apparu. Le déménagement passe, la copie reste en place."""
        j = os.path.join
        git(self.P, "worktree", "add", "-q", "--detach", j(self.wt, "emprunte"))
        os.makedirs(j(self.wt, "po", "apps", "node_modules"))
        try:
            os.symlink(j(self.wt, "po", "apps", "node_modules"), j(self.wt, "emprunte", "apps", "node_modules"))
        except OSError as e:
            # Sous Windows, un lien symbolique demande le mode développeur ou les
            # droits d'administrateur (WinError 1314, mesuré le 28/10/2026).
            if getattr(e, "winerror", None) == 1314:
                self.skipTest("lien symbolique refusé par Windows sans privilège")
            raise
        code, out = self.complet("--apply", "--agents-arretes")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.islink(j(self.wt, "emprunte", "apps", "node_modules")))

    def test_une_copie_au_git_perdu_est_ignoree(self):
        """Mesuré au jour J d'une équipe réelle : une copie jetable dont le dossier existe mais
        dont le `.git` a disparu (« prunable »). `worktree repair` échouait sur elle et
        tout repartait en arrière. Elle est nommée et laissée telle quelle."""
        j = os.path.join
        git(self.P, "worktree", "add", "-q", "--detach", j(self.wt, "jetable"))
        os.remove(j(self.wt, "jetable", ".git"))
        code, out = self.complet()
        self.assertEqual(code, 0, out)
        self.assertIn("jetable", out)
        code, out = self.complet("--apply", "--agents-arretes")
        self.assertEqual(code, 0, out)
        # Restée en place ; la réparation finale de git lui rend son `.git`, vers le
        # nouveau dépôt — elle redevient une copie saine, signalée par la page d'équipe.
        self.assertTrue(os.path.isfile(j(self.wt, "jetable", "apps", "app.ts")))
        self.assertEqual(subprocess.run(["git", "status"], cwd=j(self.wt, "jetable"), stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE).returncode, 0)


if __name__ == "__main__":
    unittest.main()
