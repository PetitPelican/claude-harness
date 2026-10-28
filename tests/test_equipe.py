# -*- coding: utf-8 -*-
"""Port des `#[test]` de `harnais/src/equipe.rs` (1 test Rust, 1 test ici)."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import equipe  # noqa: E402
from equipe import slug  # noqa: E402


class Essais(unittest.TestCase):
    def test_slug_comme_claude(self):
        self.assertEqual(slug("/Users/u/Alpha Annexe"), "-Users-u-Alpha-Annexe")
        # Chaque caractère, pas chaque suite (mesuré le 14/10/2026).
        self.assertEqual(slug("/Users/u/Agentic/.worktrees/a b"), "-Users-u-Agentic--worktrees-a-b")
        self.assertEqual(slug("Q A"), slug("Q-A"),
                         "deux noms, une adresse : la collision que le refus attrape")


class CasLimites(unittest.TestCase):
    """Sorties de `harnais equipe`, comparées au Rust 0.12.8 (codes 2 et 101, même rapport)."""

    def projet(self):
        p = os.path.realpath(tempfile.mkdtemp(prefix="equipe-"))
        self.addCleanup(shutil.rmtree, p, True)
        for d in ("brain/fact", "brain/mind"):
            os.makedirs(os.path.join(p, d))
        with open(os.path.join(p, "brain/fact/base.md"), "w", encoding="utf-8") as h:
            h.write("cap: x\n")
        return p

    def lance(self, args):
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = equipe.main(args)
        return code, sortie.getvalue(), erreur.getvalue()

    def test_l_extension_d_un_nom_de_fichier(self):
        """`Path::extension` : le texte après le DERNIER point ; rien pour `..`, un nom sans
        point ou un nom qui ne commence que par son point."""
        self.assertEqual(equipe.extension("fil.jsonl"), "jsonl")
        self.assertEqual(equipe.extension("note.md"), "md")
        self.assertEqual(equipe.extension("a.b.md"), "md")
        self.assertEqual(equipe.extension("fin."), "")
        self.assertIsNone(equipe.extension(".md"))
        self.assertIsNone(equipe.extension("sans"))
        self.assertIsNone(equipe.extension(".."))

    def test_sans_agents_la_commande_refuse_en_code_2(self):
        p = self.projet()
        code, sortie, erreur = self.lance(["--project-root", p])
        self.assertEqual(code, 2)
        self.assertIn("--agents est requis", erreur)

    def test_une_liste_d_agents_vide_sort_en_101_comme_le_rust(self):
        """`--agents ,` : aucun nom, le Rust indexe un vecteur vide et panique (101)."""
        p = self.projet()
        erreur = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(erreur):
            with self.assertRaises(SystemExit) as c:
                equipe.main(["--agents", ",", "--project-root", p])
        self.assertEqual(c.exception.code, 101)
        self.assertIn("index out of bounds", erreur.getvalue())

    def test_le_rapport_compte_les_fils_et_les_memoires_de_l_ancienne_adresse(self):
        """Hors dépôt, la mémoire auto change d'adresse : le rapport dit combien de fils
        `.jsonl` et de notes `.md` suivent (Rust : « 2 fils, 2 mémoires »)."""
        h = os.path.realpath(tempfile.mkdtemp(prefix="equipe-maison-"))
        self.addCleanup(shutil.rmtree, h, True)
        p = self.projet()
        src = os.path.join(h, ".claude", "projects", equipe.slug(p))
        os.makedirs(os.path.join(src, "memory"))
        for f in ("a.jsonl", "b.jsonl", "c.txt", "memory/n1.md", "memory/n2.md", "memory/n3.txt"):
            with open(os.path.join(src, f), "w", encoding="utf-8") as fh:
                fh.write("x\n")
        with mock.patch.dict(os.environ, {"HOME": h, "USERPROFILE": h}):
            code, sortie, _ = self.lance(["--agents", "A,B", "--project-root", p])
        self.assertEqual(code, 0)
        self.assertIn("(2 fils, 2 mémoires)", sortie)



class UnDossierParAgent(unittest.TestCase):
    """v3 (14/10/2026) : ajouter ou retirer un agent en une commande."""

    def setUp(self):
        import contextlib
        import io
        import json
        import shutil
        import subprocess
        import tempfile
        from unittest import mock
        sys.path.insert(0, os.path.dirname(__file__))
        import banc_equipe
        d = os.path.realpath(tempfile.mkdtemp(prefix="equipe-v3-"))
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "X"))
        self.x = banc_equipe.construis(os.path.join(d, "X"))
        for a in ("OPS", "PO"):
            p = os.path.join(self.x, "agents", a, ".claude", "settings.json")
            os.makedirs(os.path.dirname(p))
            with open(p, "w") as h:
                h.write('{"permissions": {"deny": ["Bash(x*)"]}}')
        env = mock.patch.dict(os.environ, {"HOME": d})
        env.start()
        self.addCleanup(env.stop)
        self.json, self.sp = json, subprocess
        self.io, self.cl = io, contextlib

    def lis_json(self, f):
        with open(f, encoding="utf-8") as h:
            return self.json.load(h)

    def lance(self, *a):
        out = self.io.StringIO()
        with self.cl.redirect_stdout(out):
            code = equipe.main(["--project-root", self.x] + list(a))
        return code, out.getvalue()

    def test_ajouter_un_agent_en_une_commande(self):
        j = os.path.join
        code, out = self.lance("--agents", "QA")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(j(self.x, "agents", "QA")), "à blanc : rien n'est écrit")
        code, out = self.lance("--agents", "QA", "--apply")
        self.assertEqual(code, 0, out)
        qa = j(self.x, "agents", "QA")
        for f in ("CLAUDE.md", "state.md", "todo.md", ".claude/settings.json"):
            self.assertTrue(os.path.isfile(j(qa, f)), f)
        s = self.lis_json(j(qa, ".claude", "settings.json"))
        self.assertTrue(s["enabledPlugins"]["harnais@atelier"])
        self.assertIn("Edit(~/X/agents/OPS/**)", s["permissions"]["deny"])
        self.assertIn("Agent(isolation:worktree)", s["permissions"]["deny"])
        # Le périmètre type d'un agent DEV (27/10) : il lit tout, agit sans demander.
        self.assertEqual(s["permissions"]["defaultMode"], "bypassPermissions")
        self.assertEqual(s["permissions"]["allow"], ["Bash(*)", "Read(*)"])
        self.assertEqual(s["permissions"]["additionalDirectories"], [self.x],
                         "la maison entière n'est pas posée : chemin propre à la machine, inutile (mesuré)")
        self.assertNotIn("Edit(~/X/agents/QA/code/**)", s["permissions"]["deny"],
                         "sans rôle type QA, sa copie du code lui reste ouverte")
        ops = self.lis_json(j(self.x, "agents", "OPS", ".claude", "settings.json"))
        self.assertEqual(ops["permissions"], {"deny": ["Bash(x*)", "Edit(~/X/agents/QA/**)"]},
                         "une ligne ajoutée, le reste intact : le badge d'un autre ne change pas de mode")
        self.assertEqual(self.sp.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=j(qa, "code"),
                                     stdout=self.sp.PIPE).stdout.decode().strip(), "qa")
        self.assertIn("claude plugin install", out)

    def test_retirer_refuse_s_il_reste_du_travail(self):
        j = os.path.join
        with open(j(self.x, "agents", "PO", "code", "apps", "app.ts"), "a") as h:
            h.write("// en cours\n")
        code, out = self.lance("--retire", "PO", "--apply")
        self.assertEqual(code, 1, out)
        self.assertIn("travail non enregistré", out)
        self.assertTrue(os.path.isdir(j(self.x, "agents", "PO", "code")))
        # TÉMOIN : propre, il part.
        self.sp.run(["git", "checkout", "--", "."], cwd=j(self.x, "agents", "PO", "code"))
        code, out = self.lance("--retire", "PO", "--apply")
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(j(self.x, "agents", "PO")))
        self.assertNotIn("agents/PO", self.sp.run(["git", "worktree", "list"], cwd=j(self.x, "agents", "OPS", "code"),
                                                  stdout=self.sp.PIPE).stdout.decode())

    def test_des_roles_types_d_une_organisation_eprouvee(self):
        """Décision du 14/10 : redéployer une autre équipe avec l'organisation éprouvée."""
        j = os.path.join
        racine = j(self.x, "CLAUDE.md")
        avait = os.path.exists(racine)
        code, out = self.lance("--agents", "QA,NXT", "--modeles", "qa,nxt", "--apply")
        self.assertEqual(code, 0, out)
        with open(j(self.x, "agents", "QA", "CLAUDE.md"), encoding="utf-8") as h:
            qa = h.read()
        with open(j(self.x, "agents", "NXT", "CLAUDE.md"), encoding="utf-8") as h:
            nxt = h.read()
        self.assertIn("guichet des questions", qa)
        self.assertIn("# QA — rôle", qa)
        self.assertIn("demande une passe à QA", nxt, "le guichet est NOMMÉ d'après l'équipe")
        for t in (qa, nxt):
            self.assertNotRegex(t, r"\{[A-Z]+\}", "aucun champ laissé à remplir par la machine")
        self.assertIn("rôle type QA", out)
        # QA à l'envers : il prescrit, sa copie du code lui est fermée ; son dossier non.
        qa_deny = self.lis_json(j(self.x, "agents", "QA", ".claude", "settings.json"))["permissions"]["deny"]
        self.assertIn("Edit(~/X/agents/QA/code/**)", qa_deny)
        self.assertNotIn("Edit(~/X/agents/QA/**)", qa_deny)
        # TÉMOIN : NXT, d'un autre type, garde sa copie du code ouverte.
        nxt_deny = self.lis_json(j(self.x, "agents", "NXT", ".claude", "settings.json"))["permissions"]["deny"]
        self.assertNotIn("Edit(~/X/agents/NXT/code/**)", nxt_deny)
        if avait:
            self.assertIn("equipe-CLAUDE.md", out, "un CLAUDE.md existant n'est jamais écrasé")
        else:
            with open(racine, encoding="utf-8") as h:
                self.assertIn("guichet unique des questions", h.read())
        # TÉMOIN : sans modèle, le rôle reste à remplir.
        code, out = self.lance("--agents", "Annexe", "--apply")
        self.assertEqual(code, 0, out)
        with open(j(self.x, "agents", "Annexe", "CLAUDE.md"), encoding="utf-8") as h:
            self.assertNotIn("guichet", h.read())

    def test_chaque_role_type_nomme_son_metier_en_tete(self):
        """Métiers nommés par l'humain le 27/10 : OPS = DevOps ; PO = développeur ET
        Product Owner ; QA = qualité, plans, pilotage. Lus sur un autre poste, les
        rôles d'avant ne l'avaient pas fait comprendre."""
        attendus = {"ops": ("DevOps",), "po": ("Product Owner", "tu écris le code"),
                    "qa": ("pilotage de l'équipe", "La liste de travail est à toi")}
        for m, mots in attendus.items():
            equipe._TYPES.clear()
            equipe._TYPES["A"] = m
            texte = equipe.role("A", "P")
            tete = texte.split("\n\n", 2)[:2]
            self.assertIn(mots[0], "\n".join(tete), "%s : le métier dans le titre ou la première phrase" % m)
            for mot in mots:
                self.assertIn(mot, texte, m)
        self.assertNotIn("ne leur fixes pas de priorité", texte, "QA pilote : il ordonne le travail")
        equipe._TYPES.clear()

    def test_un_modele_inconnu_ou_mal_aligne_refuse(self):
        code, _ = self.lance("--agents", "QA", "--modeles", "qa,po")
        self.assertEqual(code, 2)
        code, _ = self.lance("--agents", "QA", "--modeles", "chef")
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(os.path.join(self.x, "agents", "QA")))



class Windows(unittest.TestCase):
    def test_le_perimetre_s_ancre_sur_le_dossier_personnel_sous_windows(self):
        """Sous Windows, `C:\\Users\\…` se coupe sur `\\` : le périmètre d'un agent s'ancre
        sur `~/`. TÉMOIN : lu comme un chemin POSIX, le même texte ne s'ancre pas."""
        x, h = "C:\\Users\\u\\Agentic\\Equipe", "C:\\Users\\u"
        with mock.patch.dict(os.environ, {"HOME": h}):
            with mock.patch.object(equipe.os, "name", "nt"):
                self.assertEqual(equipe._perimetre(x, "PO"), "Edit(~/Agentic/Equipe/agents/PO/**)")
            with mock.patch.object(equipe.os, "name", "posix"):
                self.assertNotIn("~/", equipe._perimetre(x, "PO"))


if __name__ == "__main__":
    unittest.main()
