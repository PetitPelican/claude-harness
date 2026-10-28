# -*- coding: utf-8 -*-
"""Port des `#[test]` de `harnais/src/mind_guard.rs` (5 tests)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_windows  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))

import mind_guard
from mind_guard import (CHAMPS_REQUIS_FACT, NOMS_MIND, aujourd_hui, autorise, champ,
                        entete, est_du_code, noms_fact, verifie_state)


class Essais(unittest.TestCase):

    def test_le_plafond_porte_sur_les_noms(self):
        """LE PLAFOND PORTE SUR LES NOMS, et il a deux mots distincts.

        La règle « jamais un 5ᵉ fichier de faits, jamais un 3ᵉ d'esprit, sans le
        demander » vivait dans le socle depuis toujours et n'était vérifiée
        NULLE PART : un `fact/extra.md` indexé passait sans un mot, le 10/09/2026.
        """
        for n in ["base.md", "architecture.md", "stack.md", "rules.md", "roles.md"]:
            self.assertIn(n, noms_fact(), "%s devrait être admis" % n)
        # CE QUE LE PLAFOND REFUSE — sinon on épingle une liste qui dit oui à tout.
        for n in ["extra.md", "notes.md", "base.txt", "Base.md"]:
            self.assertNotIn(n, noms_fact(), "%s devrait être refusé" % n)
        self.assertEqual(NOMS_MIND, ["state.md", "todo.md"])
        self.assertNotIn("belief.md", NOMS_MIND)

        # `fact-neuf` VAUT `fact-ok` — la hiérarchie, pas une clé partagée.
        # Sans elle la serrure ne s'ouvrirait jamais : `autorise()` ancre le mot
        # en FIN de commande, deux mots ne peuvent donc pas cohabiter.
        self.assertTrue(autorise("git commit -m x # fact-neuf", "fact-neuf"))
        self.assertFalse(autorise("git commit -m x # fact-ok", "fact-neuf"))
        # ET L'INVERSE RESTE FAUX : `fact-ok` n'autorise pas un 5ᵉ nom.
        self.assertFalse(autorise("git commit -m x # fact-neuf", "mind-neuf"))

    def test_l_echappatoire_se_lit_en_FIN_de_commande(self):
        self.assertTrue(autorise("git commit -m x # mind-ok", "mind-ok"))
        self.assertTrue(autorise("git commit -m x #fact-ok  ", "fact-ok"))
        self.assertTrue(autorise("git commit -m x # fact-ok\n", "fact-ok"))
        # LE DÉFAUT RÉPARÉ : une sous-chaîne n'importe où désarmait le garde.
        self.assertFalse(autorise("git checkout -b essai-fact-ok && git commit -m x", "fact-ok"))
        self.assertFalse(autorise("git commit -m 'répare fact-ok un jour'", "fact-ok"))
        self.assertFalse(autorise("git commit -m x", "mind-ok"))
        # UNE CLÉ, UNE SERRURE : `mind-ok` n'ouvre pas la serrure de `.fact/`.
        self.assertFalse(autorise("git commit -m x # mind-ok", "fact-ok"))

    def test_l_entete_se_lit_comme_le_tableau_de_bord(self):
        e = entete("---\nmaj: 2026-09-09\ncap: aller là   # un commentaire\n---\n\ntexte")
        self.assertEqual(champ(e, "maj"), "2026-09-09")
        self.assertEqual(champ(e, "cap"), "aller là")
        # TÉMOINS NÉGATIFS : pas d'en-tête, en-tête non fermé, texte nu.
        self.assertEqual(entete("texte sans en-tête"), [])
        self.assertEqual(entete("---\nmaj: x\n"), [])
        self.assertEqual(entete(""), [])

    def test_le_state_est_juge_sur_sa_structure_puis_sa_fraicheur(self):
        ok = "---\nmaj: %s\nsante: verte\njalon: x\n---\n" % aujourd_hui()
        self.assertEqual(verifie_state(ok, CHAMPS_REQUIS_FACT), [])
        # structure : sans en-tête, le projet DISPARAÎT du tableau de bord
        m = verifie_state("rien", CHAMPS_REQUIS_FACT)
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0][0], "structure")
        # structure : champ manquant
        m = verifie_state("---\nmaj: %s\n---\n" % aujourd_hui(), CHAMPS_REQUIS_FACT)
        self.assertTrue(any(k == "structure" and "`sante:`" in v for k, v in m))
        # structure : date qui n'est pas une date
        m = verifie_state("---\nmaj: hier\nsante: v\njalon: x\n---\n", CHAMPS_REQUIS_FACT)
        self.assertTrue(any(k == "structure" and "« hier »" in v for k, v in m))
        # fraîcheur : date valide mais pas celle du jour
        m = verifie_state("---\nmaj: 2020-01-01\nsante: v\njalon: x\n---\n", CHAMPS_REQUIS_FACT)
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0][0], "fraicheur")

    def test_le_harnais_de_l_agent_n_est_pas_du_code_projet(self):
        self.assertTrue(est_du_code("src/a.ts", "", ""))
        self.assertTrue(est_du_code("truc.py", "", ""))
        self.assertTrue(est_du_code("agents/ios/src/a.ts", "agents/ios/", ""))
        # LES DEUX JEUX DE PRÉFIXES, et c'est le défaut que ça répare :
        self.assertFalse(est_du_code("agents/ios/.claude/hooks/x.py", "agents/ios/", ""))
        self.assertFalse(est_du_code(".fact/base.md", "", ""))
        self.assertFalse(est_du_code("docs/decisions.md", "", ""))
        self.assertFalse(est_du_code(".logs/2026-09-09.md", "", ""))
        self.assertFalse(est_du_code("site/index.html", "", ""), "rendu généré")
        # L'espace des livrables (12/10/2026) : ce qu'un agent produit n'est pas du code.
        self.assertFalse(est_du_code("assets/requete.sql", "", ""))
        self.assertFalse(est_du_code("assets/OPS/analyse.ipynb", "", ""))
        self.assertFalse(est_du_code("agents/ops/assets/plan.py", "agents/ops/", "")
                         , "au pied d'un lot")
        self.assertFalse(est_du_code("assets/OPS/a.ts", "agents/ops/", ""), "à la racine du projet, vu d'un lot")
        # Témoins négatifs : seul le dossier de la RACINE est l'espace des livrables.
        self.assertTrue(est_du_code("src/assets/app.js", "", ""), "les assets d'un site restent du code")
        self.assertTrue(est_du_code("assets.py", "", ""), "un fichier n'est pas un dossier")
        self.assertTrue(est_du_code("agents/ops/src/assets/a.ts", "agents/ops/", ""))
        self.assertTrue(est_du_code("site/_content/a.py", "", ""), "mais son contenu, si")
        self.assertFalse(est_du_code("LISEZMOI.md", "", ""))


class Faits(unittest.TestCase):
    """Le garde des faits devant un vrai dépôt. Les attendus sont ceux du Rust 0.12.8, relevés en
    lançant `harnais mind-guard` sur le même dépôt (refus, et liste des fichiers citée)."""

    RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def depot(self):
        p = os.path.realpath(tempfile.mkdtemp(prefix="mind-guard-"))
        self.addCleanup(shutil.rmtree, p, True)
        self.git(p, "init", "-q", "-b", "main")
        os.makedirs(os.path.join(p, ".fact"))
        os.makedirs(os.path.join(p, ".mind"))
        os.makedirs(os.path.join(p, "agents/ios"))
        for n in ("base", "architecture", "stack", "rules"):
            self.ecris(p, ".fact/%s.md" % n, "---\ncap: x\n---\n")
        self.ecris(p, ".mind/state.md", "---\nmaj: 2026-10-12\nsante: vert\njalon: x\n---\n")
        self.git(p, "add", "-A")
        self.git(p, "commit", "-qm", "init")
        return p

    def git(self, d, *a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t"] + list(a), cwd=d,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    def ecris(self, d, f, t):
        with open(os.path.join(d, f), "a", encoding="utf-8") as h:
            h.write(t)

    def refus(self, cwd):
        """Le hook, lancé comme Claude Code le lance : (code, raison du refus ou None)."""
        maison = tempfile.mkdtemp(prefix="mind-guard-maison-")
        self.addCleanup(shutil.rmtree, maison, True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": maison,
               "CLAUDE_PLUGIN_DATA": os.path.join(maison, "donnees"), "LANG": "C.UTF-8"}
        env = dict(env_windows.essentiel(), **env)
        entree = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}})
        r = subprocess.run([sys.executable, os.path.join(self.RACINE, "py", "main.py"), "mind-guard"],
                           cwd=cwd, env=env, input=entree.encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        sortie = r.stdout.decode("utf-8", "replace").strip()
        if not sortie:
            return r.returncode, None
        return r.returncode, json.loads(sortie)["hookSpecificOutput"]["permissionDecisionReason"]

    def test_l_echantillon_garde_les_n_premiers_puis_des_points_de_suite(self):
        self.assertEqual(mind_guard.echantillon(["a", "b", "c", "d"], 4), "a, b, c, d")
        self.assertEqual(mind_guard.echantillon(["a", "b", "c", "d", "e"], 4), "a, b, c, d, …")
        self.assertEqual(mind_guard.echantillon([], 4), "")

    def test_le_refus_cite_quatre_fichiers_de_faits_puis_des_points_de_suite(self):
        """Cinq fichiers de faits indexés : quatre cités, puis « … » (Rust 0.12.8 : même liste)."""
        p = self.depot()
        for n in ("base", "architecture", "stack", "rules", "roles"):
            self.ecris(p, ".fact/%s.md" % n, "x\n")
        self.git(p, "add", "-A")
        code, raison = self.refus(p)
        self.assertIsNotNone(raison, "le commit des faits doit être refusé")
        self.assertIn("ce commit modifie `.fact/` "
                      "(.fact/architecture.md, .fact/base.md, .fact/roles.md, .fact/rules.md, …)", raison)
        self.assertNotIn("stack.md", raison.split("Ces fichiers")[0], "le cinquième n'est pas cité")

    def test_quatre_fichiers_de_faits_sont_cites_sans_points_de_suite(self):
        p = self.depot()
        for n in ("base", "architecture", "stack", "rules"):
            self.ecris(p, ".fact/%s.md" % n, "x\n")
        self.git(p, "add", "-A")
        code, raison = self.refus(p)
        self.assertIn("(.fact/architecture.md, .fact/base.md, .fact/rules.md, .fact/stack.md)", raison)

    def test_un_agent_de_lot_retrouve_les_faits_du_projet_au_dessus_de_lui(self):
        """Lancé depuis `agents/ios/`, toucher aux faits de la racine (`.fact/`) reste refusé
        (Rust 0.12.8 : refus, `.fact/base.md`)."""
        p = self.depot()
        self.ecris(p, ".fact/base.md", "x\n")
        self.git(p, "add", "-A")
        code, raison = self.refus(os.path.join(p, "agents", "ios"))
        self.assertIsNotNone(raison, "depuis un lot, les faits de la racine ne sont plus gardés")
        self.assertIn("(.fact/base.md)", raison)

    def test_le_contexte_d_un_lot_nomme_le_lot_le_projet_et_les_faits(self):
        p = self.depot()
        agent = os.path.join(p, "agents", "ios")
        self.assertEqual(mind_guard.contexte(mind_guard.Git(agent), agent), ("agents/ios/", "", ".fact/"))
        self.assertEqual(mind_guard.contexte(mind_guard.Git(p), p), ("", "", ".fact/"))

    def test_sans_dossier_de_faits_le_projet_est_le_lot(self):
        """Témoin négatif : aucun `.fact/` nulle part, `faits` est vide et le projet est le lot."""
        p = os.path.realpath(tempfile.mkdtemp(prefix="mind-guard-nu-"))
        self.addCleanup(shutil.rmtree, p, True)
        self.git(p, "init", "-q", "-b", "main")
        agent = os.path.join(p, "agents", "ios")
        os.makedirs(agent)
        self.assertEqual(mind_guard.contexte(mind_guard.Git(agent), agent), ("agents/ios/", "agents/ios/", None))

    def test_le_harnais_du_projet_modifie_depuis_un_lot_n_est_pas_du_code_pour_la_fin_de_tour(self):
        """Depuis `agents/ios/`, un `.claude/hooks/x.py` modifié à la RACINE est le harnais du projet,
        pas du code : la garde de fin de tour ne réclame pas de todo (Rust 0.12.8 : code 0). Si le
        projet était pris pour le lot, ce fichier compterait comme code et le tour serait renvoyé."""
        p = os.path.realpath(tempfile.mkdtemp(prefix="mind-guard-lot-"))
        self.addCleanup(shutil.rmtree, p, True)
        self.git(p, "init", "-q", "-b", "main")
        for n in ("base", "architecture", "stack", "rules"):
            os.makedirs(os.path.join(p, ".fact"), exist_ok=True)
            self.ecris(p, ".fact/%s.md" % n, "cap: x\n")
        os.makedirs(os.path.join(p, "agents/ios/.mind"))
        os.makedirs(os.path.join(p, ".claude/hooks"))
        self.ecris(p, "agents/ios/.mind/state.md", "---\nmaj: 2026-10-12\nsante: vert\njalon: x\n---\n")
        self.ecris(p, "agents/ios/.mind/todo.md", "# todo\n")
        self.ecris(p, ".claude/hooks/x.py", "print(0)\n")
        self.git(p, "add", "-A")
        self.git(p, "commit", "-qm", "init")
        self.ecris(p, ".claude/hooks/x.py", "print(1)\n")
        recent = os.path.getmtime(os.path.join(p, "agents/ios/.mind/todo.md")) + 10
        os.utime(os.path.join(p, ".claude/hooks/x.py"), (recent, recent))
        maison = tempfile.mkdtemp(prefix="mind-guard-maison-")
        self.addCleanup(shutil.rmtree, maison, True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": maison,
               "CLAUDE_PLUGIN_DATA": os.path.join(maison, "donnees"), "LANG": "C.UTF-8"}
        env = dict(env_windows.essentiel(), **env)
        r = subprocess.run([sys.executable, os.path.join(self.RACINE, "py", "main.py"), "attente"],
                           cwd=os.path.join(p, "agents", "ios"), env=env,
                           input=b'{"session_id":"s1"}', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))


class Equipe(unittest.TestCase):
    """v3 · « un dossier par agent » : l'agent se tient dans `agents/<nom>/`, qui est
    le dépôt de la MÉMOIRE, et enregistre son code dans `code/`."""

    RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def setUp(self):
        sys.path.insert(0, os.path.dirname(__file__))
        import banc_equipe
        d = os.path.realpath(tempfile.mkdtemp(prefix="mind-guard-equipe-"))
        self.addCleanup(shutil.rmtree, d, True)
        self.x = banc_equipe.construis(d)
        self.po = os.path.join(self.x, "agents", "PO")
        self.code = os.path.join(self.po, "code")

    def juge(self, commande):
        maison = tempfile.mkdtemp(prefix="mind-guard-maison-")
        self.addCleanup(shutil.rmtree, maison, True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": maison,
               "CLAUDE_PLUGIN_DATA": os.path.join(maison, "donnees"), "LANG": "C.UTF-8",
               "CLAUDE_PROJECT_DIR": self.po}
        env = dict(env_windows.essentiel(), **env)
        entree = json.dumps({"tool_name": "Bash", "tool_input": {"command": commande}})
        r = subprocess.run([sys.executable, os.path.join(self.RACINE, "py", "main.py"), "mind-guard"],
                           cwd=self.po, env=env, input=entree.encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        sortie = r.stdout.decode("utf-8", "replace").strip()
        return json.loads(sortie)["hookSpecificOutput"]["permissionDecisionReason"] if sortie else None

    def indexe_du_code(self, mtime_etat):
        with open(os.path.join(self.code, "apps", "app.ts"), "a", encoding="utf-8") as h:
            h.write("// x\n")
        subprocess.run(["git", "add", "apps/app.ts"], cwd=self.code, check=True)
        etat = os.path.join(self.po, "state.md")
        os.utime(etat, (mtime_etat, mtime_etat))

    def test_un_commit_tape_dans_le_dossier_de_l_agent_vise_la_memoire(self):
        with open(os.path.join(self.po, "todo.md"), "a", encoding="utf-8") as h:
            h.write("- [ ] x\n")
        subprocess.run(["git", "add", "todo.md"], cwd=self.po, check=True)
        m = self.juge("git commit -m x")
        self.assertIsNotNone(m)
        self.assertIn("MÉMOIRE", m)
        self.assertIn("git -C code commit", m)
        # TÉMOIN : l'échappatoire ouvre la serrure.
        self.assertIsNone(self.juge("git commit -m x # memoire-ok"))

    def test_git_dash_C_code_juge_le_code_contre_l_etat_de_l_agent(self):
        self.indexe_du_code(1000000000)          # état très ancien
        for cmd in ("git -C code commit -m x", "cd code && git commit -m x"):
            m = self.juge(cmd)
            self.assertIsNotNone(m, cmd)
            self.assertIn("du code projet est indexé", m)
            self.assertIn("Mets `state.md` à jour", m)
            self.assertNotIn("memoire/", m)
        # TÉMOIN : un état plus récent que le code laisse passer.
        os.utime(os.path.join(self.po, "state.md"), None)
        self.assertIsNone(self.juge("git -C code commit -m x"))

    def test_les_faits_s_ecrivent_dans_la_memoire_avec_fact_ok(self):
        with open(os.path.join(self.x, "fact", "base.md"), "a", encoding="utf-8") as h:
            h.write("ajout\n")
        subprocess.run(["git", "add", "fact/base.md"], cwd=self.x, check=True)
        self.assertIsNone(self.juge("git commit -m x # fact-ok"))
        # TÉMOIN : `memoire-ok` ouvre la mémoire, PAS les faits.
        m = self.juge("git commit -m x # memoire-ok")
        self.assertIsNotNone(m)
        self.assertIn("fact", m)

    def test_le_role_de_l_agent_n_est_pas_un_intrus(self):
        with open(os.path.join(self.po, "CLAUDE.md"), "a", encoding="utf-8") as h:
            h.write("ajout\n")
        subprocess.run(["git", "add", "CLAUDE.md"], cwd=self.po, check=True)
        self.assertIsNone(self.juge("git commit -m x # memoire-ok"))
        # TÉMOIN : un troisième nom dans l'esprit reste refusé.
        with open(os.path.join(self.po, "notes.md"), "w", encoding="utf-8") as h:
            h.write("x\n")
        subprocess.run(["git", "add", "notes.md"], cwd=self.po, check=True)
        m = self.juge("git commit -m x # memoire-ok")
        self.assertIsNotNone(m)
        self.assertIn("notes.md", m)

    def test_une_copie_du_code_ne_nait_que_dans_le_dossier_de_l_agent(self):
        dehors = ("git -C code worktree add ../../../ailleurs",
                  "git -C code worktree add -b essai /tmp/copie-sauvage",
                  "cd code && git worktree add ../../OPS/code-x")
        for cmd in dehors:
            m = self.juge(cmd)
            self.assertIsNotNone(m, cmd)
            self.assertIn("code-<sujet>", m)
        # TÉMOINS : dans son dossier, ou sur la demande du commanditaire.
        for cmd in ("git -C code worktree add ../code-essai",
                    "git -C code worktree add -b essai ../code-essai",
                    "git -C code worktree add /tmp/x # copie-ok",
                    "git -C code worktree list"):
            self.assertIsNone(self.juge(cmd), cmd)

    def test_le_dossier_du_commit(self):
        d = mind_guard.dossier_du_commit
        self.assertEqual(d("git -C code commit -m x", self.po), self.code)
        self.assertEqual(d("cd code && git commit", self.po), self.code)
        self.assertEqual(d('git -C "code" commit', self.po), self.code)
        self.assertEqual(d("git commit -m x", self.po), self.po)
        self.assertEqual(d("git -C inexistant commit", self.po), self.po)


if __name__ == "__main__":
    unittest.main()
