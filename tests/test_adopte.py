# -*- coding: utf-8 -*-
"""Port des `#[test]` de `harnais/src/adopte.rs` (5 tests Rust, 5 tests ici)."""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import adopte  # noqa: E402


def lance(args):
    """`main(args)` sans polluer la sortie du banc d'essai."""
    with contextlib.redirect_stdout(io.StringIO()):
        return adopte.main(args)


class Essais(unittest.TestCase):
    def bac(self, nom):
        d = tempfile.mkdtemp(prefix="adopte-%s-" % nom)
        self.addCleanup(shutil.rmtree, d, True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return os.path.realpath(d)

    def lis(self, d, f):
        with open(os.path.join(d, f), encoding="utf-8") as h:
            return h.read()

    def test_le_blanc_n_ecrit_rien(self):
        """LE BLANC N'ÉCRIT RIEN — et c'est le contrat, pas un détail. Un passage à
        blanc qui pose un fichier rend le geste irréversible avant d'avoir été
        décidé."""
        d = self.bac("blanc")
        self.assertEqual(lance([d]), 0)
        self.assertFalse(os.path.exists(os.path.join(d, "brain/fact/base.md")), "le blanc a écrit")
        self.assertFalse(os.path.exists(os.path.join(d, ".claude/settings.json")),
                         "le blanc a écrit les réglages")

    def test_go_pose_le_cerveau_et_branche_le_paquet(self):
        """ET `--go` ÉCRIT VRAIMENT. Le témoin négatif du précédent : sans lui,
        une commande qui n'écrit JAMAIS passerait le premier essai."""
        d = self.bac("go")
        self.assertEqual(lance([d, "--go"]), 0)
        for f in ["brain/fact/base.md", "brain/mind/state.md", "brain/mind/todo.md"]:
            self.assertTrue(os.path.exists(os.path.join(d, f)), "%s manque" % f)
        t = self.lis(d, ".claude/settings.json")
        self.assertIn(adopte.PAQUET, t, "le paquet n'est pas activé")
        self.assertIn(adopte.DEPOT, t, "le marché n'est pas déclaré")

    def test_le_workflow_de_depart_est_pose_marque_a_remplir_et_jamais_ecrase(self):
        """`workflow.md` COMMUN À TOUS (12/10/2026) : posé avec la marque « À REMPLIR »
        qui fait dire « À RENSEIGNER » au briefing ; en équipe aussi ; et un
        workflow.md déjà écrit n'est jamais touché."""
        d = self.bac("wf")
        lance([d, "--go"])
        t = self.lis(d, "brain/fact/workflow.md")
        self.assertIn("À REMPLIR", t)
        self.assertIn("## Les gestes qu'on ne redécouvre pas", t)
        e = self.bac("wfeq")
        lance([e, "--go", "--equipe", "A,B"])
        self.assertIn("À REMPLIR", self.lis(e, "fact/workflow.md"))
        with open(os.path.join(d, "brain/fact/workflow.md"), "w", encoding="utf-8") as h:
            h.write("MES GESTES\n")
        lance([d, "--go"])
        self.assertEqual(self.lis(d, "brain/fact/workflow.md"), "MES GESTES\n")
        b = self.bac("wfblanc")
        lance([b])
        self.assertFalse(os.path.exists(os.path.join(b, "brain/fact/workflow.md")), "le blanc a écrit")

    def test_les_quatre_faits_sont_poses_a_remplir(self):
        """0.17.0 — la vue d'équipe disait « adopte le pose » pour stack,
        architecture et rules ; adopte ne les posait pas (14/10/2026 :
        1 fait sur 4). Le compte qu'elle lit doit être plein après adoption."""
        import briefing
        d = self.bac("quatre")
        lance([d, "--go"])
        for f in ["stack.md", "architecture.md", "rules.md"]:
            p = os.path.join(d, "brain/fact", f)
            self.assertTrue(os.path.isfile(p), "%s manque" % f)
            self.assertTrue(briefing.a_renseigner(p), "%s n'est pas lu « À RENSEIGNER »" % f)

    def test_en_equipe_aucun_reglage_a_la_racine(self):
        """0.17.0 — en équipe, la racine ne porte pas de réglages : Claude Code ne lit
        que ceux du dossier de lancement. Témoin : en mono, ils y sont."""
        e = self.bac("racine")
        lance([e, "--go", "--equipe", "A,B"])
        self.assertFalse(os.path.exists(os.path.join(e, ".claude/settings.json")),
                         "réglages inertes posés à la racine d'une équipe")
        for a in ("A", "B"):
            self.assertIn(adopte.PAQUET, self.lis(e, "agents/%s/.claude/settings.json" % a))
        m = self.bac("racinemono")
        lance([m, "--go"])
        self.assertTrue(os.path.isfile(os.path.join(m, ".claude/settings.json")))

    def test_relancer_ne_change_rien(self):
        """DEUX PASSAGES RENDENT LE MÊME ARBRE. Un outil d'installation qu'on
        n'ose pas relancer n'est pas un outil, c'est un pari."""
        d = self.bac("idem")
        lance([d, "--go"])
        with open(os.path.join(d, "brain/fact/base.md"), "w", encoding="utf-8") as h:
            h.write("MON TEXTE À MOI\n")
        lance([d, "--go"])
        self.assertEqual(self.lis(d, "brain/fact/base.md"), "MON TEXTE À MOI\n",
                         "le second passage a écrasé un fichier du projet")

    def test_les_reglages_existants_survivent(self):
        """LES RÉGLAGES SE FUSIONNENT. Un projet qui a déjà ses permissions doit les
        garder — les écraser couperait ses droits sans le dire."""
        d = self.bac("fusion")
        os.makedirs(os.path.join(d, ".claude"))
        with open(os.path.join(d, ".claude/settings.json"), "w", encoding="utf-8") as h:
            h.write('{"permissions":{"deny":["Bash(rm*)"]}}')
        lance([d, "--go"])
        t = self.lis(d, ".claude/settings.json")
        self.assertIn("Bash(rm*)", t, "les permissions du projet ont été perdues")
        self.assertIn(adopte.PAQUET, t, "le paquet n'a pas été ajouté")

    def test_en_equipe_chacun_a_le_sien(self):
        """UNE ÉQUIPE NAÎT « UN DOSSIER PAR AGENT » (0.19, 16/10/2026) : chacun son état,
        son rôle, ses droits et SA copie du code ; la racine est le dépôt de la mémoire.
        TÉMOIN : l'ancienne forme (`brain/mind/<nom>/`) n'est plus posée."""
        import json
        import memoire
        d = self.bac("equipe")
        lance([d, "--equipe", "PO,QA", "--go"])
        for a in ["PO", "QA"]:
            for f in ("state.md", "todo.md", "CLAUDE.md", ".claude/settings.json"):
                self.assertTrue(os.path.isfile(os.path.join(d, "agents", a, f)), "%s sans %s" % (a, f))
            self.assertTrue(os.path.exists(os.path.join(d, "agents", a, "code", ".git")), "%s sans code" % a)
            v = json.loads(self.lis(d, "agents/%s/.claude/settings.json" % a))
            self.assertTrue(v["enabledPlugins"][adopte.PAQUET])
            self.assertIn(d, v["permissions"]["additionalDirectories"], "la mémoire hors de portée")
        for f in ("CLAUDE.md", ".gitignore", "fact/base.md", "fact/roles.md", "docs/decisions.md",
                  "shared/LISEZMOI.md", "assets/LISEZMOI.md"):
            self.assertTrue(os.path.isfile(os.path.join(d, f)), "%s manque" % f)
        self.assertFalse(os.path.exists(os.path.join(d, "brain")), "l'ancienne forme est revenue")
        self.assertFalse(os.path.exists(os.path.join(d, ".claude")), "réglages à la racine : inertes")
        # La copie de QA est une copie git du dépôt de PO, sur sa propre branche.
        o = subprocess.run(["git", "worktree", "list"], cwd=os.path.join(d, "agents/PO/code"),
                           stdout=subprocess.PIPE).stdout.decode()
        self.assertIn(os.path.join(d, "agents", "QA", "code").replace("\\", "/").lower(),
                      o.replace("\\", "/").lower(), "git écrit `C:/…` sous Windows")
        # Le résolveur y voit une équipe, depuis le fond de la copie du code.
        r = memoire.resous(os.path.join(d, "agents", "QA", "code"))
        self.assertEqual((r.forme, r.projet), (memoire.Forme.Equipe, d))

    def test_une_equipe_ne_nait_pas_sur_un_code(self):
        """Un dossier qui porte déjà quelque chose est refusé, rien n'est écrit.
        TÉMOIN : le même geste dans un dossier vide pose l'équipe (test précédent)."""
        d = self.bac("surcode")
        with open(os.path.join(d, "app.ts"), "w", encoding="utf-8") as h:
            h.write("x\n")
        self.assertEqual(lance([d, "--equipe", "A,B", "--go"]), 1)
        self.assertEqual(sorted(os.listdir(d)), [".git", "app.ts"])

    def test_a_blanc_l_equipe_n_ecrit_rien(self):
        d = self.bac("eqblanc")
        lance([d, "--equipe", "A,B"])
        self.assertEqual(os.listdir(d), [".git"])

    def test_en_mono_le_projet_recoit_son_claude_md_et_ses_decisions(self):
        d = self.bac("etage3")
        lance([d, "--go"])
        self.assertIn("À REMPLIR", self.lis(d, "CLAUDE.md"))
        self.assertTrue(os.path.isfile(os.path.join(d, "docs", "decisions.md")))
        with open(os.path.join(d, "CLAUDE.md"), "w", encoding="utf-8") as h:
            h.write("LE MIEN\n")
        lance([d, "--go"])
        self.assertEqual(self.lis(d, "CLAUDE.md"), "LE MIEN\n", "un CLAUDE.md existant a été écrasé")

    def test_une_equipe_demenagee_ne_s_adopte_pas(self):
        """0.18.0 : sur la forme « un dossier par agent », adopte ne pose rien — un
        `brain/` posé là recréerait la dispersion (KeyError avant le 14/10/2026)."""
        sys.path.insert(0, os.path.dirname(__file__))
        import banc_equipe
        d = tempfile.mkdtemp(prefix="adopte-v3-")
        self.addCleanup(shutil.rmtree, d, True)
        x = banc_equipe.construis(os.path.realpath(d))
        self.assertEqual(lance([x, "--go"]), 0)
        self.assertFalse(os.path.exists(os.path.join(x, "brain")))


class CasLimites(unittest.TestCase):
    """Cas limites que la mutation d'un octet a laissés vivants."""

    def bac(self, nom):
        d = tempfile.mkdtemp(prefix="adopte-%s-" % nom)
        self.addCleanup(shutil.rmtree, d, True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return os.path.realpath(d)

    def test_le_reste_d_un_chemin_se_prend_par_composants(self):
        """`Path::strip_prefix` : le reste sous la base, rien si le chemin est ailleurs
        ou si l'un est relatif et l'autre absolu."""
        self.assertEqual(adopte.strip_prefix("/a/b/c/d", "/a/b"), "c/d")
        self.assertEqual(adopte.strip_prefix("/a/b", "/a/b"), "")
        self.assertEqual(adopte.strip_prefix("/a/./b//c", "/a/b"), "c")
        self.assertIsNone(adopte.strip_prefix("/a/x/c", "/a/b"), "un chemin voisin n'est pas dessous")
        self.assertIsNone(adopte.strip_prefix("/a/bc", "/a/b"), "la comparaison se fait par composants, pas par texte")
        self.assertIsNone(adopte.strip_prefix("a/b/c", "/a/b"), "relatif contre absolu : pas de reste")
        self.assertIsNone(adopte.strip_prefix("/a/b/c", "a/b"), "absolu contre relatif : pas de reste")
        self.assertEqual(adopte.strip_prefix("a/b/c", "a/b"), "c")

    def test_les_fichiers_a_poser_s_affichent_relatifs_au_projet(self):
        """Le rapport nomme `brain/fact/base.md`, pas le chemin absolu : c'est ce que
        lit celui qui adopte (même sortie que le Rust 0.12.8)."""
        d = self.bac("court")
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            self.assertEqual(adopte.main([d]), 0)
        sortie = tampon.getvalue()
        self.assertIn("    brain/fact/base.md ", sortie)
        self.assertNotIn(d + "/brain/fact/base.md", sortie, "le chemin absolu a été affiché")

    def test_une_memoire_a_cheval_arrete_l_adoption_en_code_2(self):
        """Les DEUX arbres de mémoire : « Je m'arrête ici », code 2, et rien n'est posé
        (Rust 0.12.8 : code 2, même texte)."""
        d = self.bac("cheval")
        for sous in [".fact", "brain/fact"]:
            os.makedirs(os.path.join(d, sous))
            with open(os.path.join(d, sous, "base.md"), "w", encoding="utf-8") as h:
                h.write("cap: x\n")
        tampon = io.StringIO()
        with contextlib.redirect_stdout(tampon):
            code = adopte.main([d, "--go"])
        self.assertEqual(code, 2)
        self.assertIn("Je m'arrête ici", tampon.getvalue())
        self.assertFalse(os.path.exists(os.path.join(d, ".claude/settings.json")),
                         "une migration interrompue a été complétée à l'aveugle")

    def test_des_reglages_qui_ne_sont_pas_un_objet_sortent_en_101(self):
        """Là où le Rust panique, le Python sort en 101 de même (Rust 0.12.8 : 101)."""
        d = self.bac("panique")
        os.makedirs(os.path.join(d, ".claude"))
        with open(os.path.join(d, ".claude/settings.json"), "w", encoding="utf-8") as h:
            h.write("[1]")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as c:
                adopte.main([d, "--go"])
        self.assertEqual(c.exception.code, 101)
        self.assertIn("panicked", err.getvalue())


if __name__ == "__main__":
    unittest.main()
