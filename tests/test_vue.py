# -*- coding: utf-8 -*-
"""Les essais de `vue.rs` (module `essais`), un test Python par `#[test]` Rust.

    python3 -m unittest discover -s tests -p "test_vue.py"
"""
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))

import socle  # noqa: E402
import vue  # noqa: E402
from vue import (MIND_ATTENDU, Chemins, Illisibles, Toutes, harnais, jauge,  # noqa: E402
                 numeros, symbole, verdict)

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DECLARE = '{"enabledPlugins":{"harnais@atelier":true},"permissions":{"deny":["Bash(x*)"]}}'
HOOKS = '{"hooks":{"PreToolUse":[{"hooks":[{"command":"python3 hooks/mind-guard.py"}]}]},"permissions":{"deny":["Bash(x*)"]}}'


def dossier(nom, git):
    d = tempfile.mkdtemp(prefix="harnais-vue-%s-" % nom)
    if git:
        subprocess.check_call(["git", "init", "-q"], cwd=d)
    return os.path.realpath(d)


def ecris(d, f, t):
    p = os.path.join(d, f)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(t)


def retire(d):
    shutil.rmtree(d, ignore_errors=True)


def courante():
    """La version de ce programme, sans son suffixe de construction locale."""
    a, b, c = numeros(vue.version_annoncee())
    return "%d.%d.%d" % (a, b, c)


def trace(d, v):
    """`""` : une trace d'avant la 0.10.0, sans version."""
    v = ', "version": "%s"' % v if v else ""
    ecris(d, ".claude/.briefing.json",
          '{"derniere": %s, "evenement": "SessionStart"%s}' % (vue.maintenant_s(), v))


def brain_mono(nom):
    """Un projet `brain/` à un agent, complet, déclaré, avec ses `deny`."""
    d = dossier(nom, True)
    for f in socle.FAITS_MONO:
        ecris(d, "brain/fact/%s" % f, "x\n")
    for f in MIND_ATTENDU:
        ecris(d, "brain/mind/%s" % f, "x\n")
    ecris(d, ".claude/settings.json", DECLARE)
    return d


def inscrit(ds, v):
    return Chemins([(d, v) for d in ds])


def juge(d, ins):
    return verdict(harnais(d, ins))


def commandes_mortes(texte):
    """Ce qui fait qu'un conseil ne cite rien de mort. Une commande se cite
    entre accents graves : « le harnais refuse » est de la prose."""
    with open(os.path.join(RACINE, "py", "main.py"), encoding="utf-8") as f:
        main = f.read()
    skills = os.path.join(RACINE, "skills")
    mortes = []
    for c in re.finditer(r"`harnais ([a-z][a-z-]*)", texte):
        if '"%s":' % c.group(1) not in main:
            mortes.append("harnais %s" % c.group(1))
    for c in re.finditer(r"(?:^|[\s`(])/([a-z][a-z0-9-]*)", texte):
        if not os.path.isfile(os.path.join(skills, c.group(1), "SKILL.md")):
            mortes.append("/%s" % c.group(1))
    for c in re.finditer(r"`claude plugin ([a-z]+)", texte):
        if c.group(1) not in ("install", "update"):
            mortes.append("claude plugin %s" % c.group(1))
    return mortes


class Essais(unittest.TestCase):
    def test_servi_seulement_si_declare_inscrit_et_trace_et_chaque_manque_seul_le_fait_tomber(self):
        """Chaque condition, retirée SEULE, fait tomber le « servi » — sinon un
        verdict qui dit toujours « ok » passerait les mêmes essais."""
        d = brain_mono("servi")
        v = courante()
        trace(d, v)
        ins = inscrit([d], v)
        self.assertEqual(juge(d, ins)[0], "ok")
        self.assertEqual(juge(d, Chemins([]))[0], "non-inscrit")
        self.assertEqual(juge(d, Illisibles())[0], "non-mesure", "illisible n'est pas « inscrit »")
        self.assertEqual(juge(d, Toutes(v))[0], "ok", "une inscription globale vaut pour tous")
        os.remove(os.path.join(d, ".claude/.briefing.json"))
        self.assertEqual(juge(d, ins)[0], "jamais-servi")
        trace(d, v)
        ecris(d, ".claude/settings.json", '{"permissions":{"deny":["Bash(x*)"]}}')
        self.assertEqual(juge(d, ins)[0], "non-branche")
        ecris(d, ".claude/settings.json", HOOKS)
        self.assertEqual(juge(d, ins)[0], "hooks-locaux")
        ecris(d, ".claude/settings.json", '{"enabledPlugins":{"harnais@atelier":true}}')
        self.assertEqual(juge(d, ins)[0], "sans-deny")
        ecris(d, ".claude/settings.json", DECLARE)
        ecris(d, "brain/fact/journal.md", "x\n")
        self.assertEqual(juge(d, ins)[0], "surplus")
        os.remove(os.path.join(d, "brain/fact/journal.md"))
        os.remove(os.path.join(d, "brain/mind/todo.md"))
        v2, c = juge(d, ins)
        self.assertEqual(v2, "incomplet")
        self.assertTrue("brain/mind/todo.md" in c and "harnais mise-a-niveau" in c, c)
        os.remove(os.path.join(d, "brain/mind/state.md"))
        self.assertEqual(juge(d, ins)[0], "sans-agent")
        retire(d)

    def test_le_retard_se_juge_contre_la_version_inscrite(self):
        """La référence est ce qui est INSCRIT : c'est ce que l'agent chargera."""
        d = brain_mono("retard")
        v = courante()
        trace(d, "0.0.1")
        self.assertEqual(juge(d, inscrit([d], v))[0], "en-retard")
        trace(d, "")
        x, c = juge(d, inscrit([d], v))
        self.assertEqual(x, "en-retard")
        self.assertIn("avant la 0.10.0", c)
        trace(d, v)
        self.assertEqual(juge(d, inscrit([d], v))[0], "ok")
        # Une trace PLUS RÉCENTE que l'inscrite n'est pas un retard.
        trace(d, "999.0.0")
        self.assertEqual(juge(d, inscrit([d], v))[0], "ok")
        trace(d, "0.0.1")
        x, c = juge(d, inscrit([d], "0.0.1"))
        self.assertEqual(x, "inscription-vieille", c)
        self.assertIn("claude plugin update harnais@atelier --scope project", c)
        retire(d)

    def test_toutes_les_formes_de_memoire_sont_vues(self):
        d = dossier("neuf", True)
        self.assertEqual(juge(d, Chemins([]))[0], "neuf")
        ecris(d, ".memory/business.md", "x\n")
        x, c = juge(d, Chemins([]))
        self.assertEqual(x, "ancien")
        self.assertIn("business.md", c)
        retire(d)

        d = dossier("mind-seul", True)
        ecris(d, ".mind/state.md", "x\n")
        self.assertEqual(juge(d, Chemins([]))[0], "ancien")
        retire(d)

        d = dossier("sans-git", False)
        for f in socle.FAITS_MONO:
            ecris(d, "brain/fact/%s" % f, "x\n")
        self.assertEqual(juge(d, Chemins([]))[0], "sans-git")
        retire(d)

        d = dossier("v1", True)
        for f in socle.FAITS_MONO:
            ecris(d, ".fact/%s" % f, "x\n")
        for f in MIND_ATTENDU:
            ecris(d, ".mind/%s" % f, "x\n")
        ecris(d, ".claude/settings.json", DECLARE)
        trace(d, courante())
        ins = inscrit([d], courante())
        self.assertEqual(juge(d, ins)[0], "v1")
        os.makedirs(os.path.join(d, "brain"), exist_ok=True)
        x, c = juge(d, ins)
        self.assertEqual(x, "ambigu")
        self.assertIn("harnais mise-a-niveau", c)
        retire(d)

    def test_le_renvoi_vers_la_memoire_peut_vivre_a_l_etage_du_dessus(self):
        """0.17.0 — consignes en quatre étages (14/10/2026) : le CLAUDE.md commun,
        au-dessus des projets, porte le renvoi vers `brain/` ; celui du projet ne le
        redit plus. Témoin : un commun qui ne le dit pas laisse « NON »."""
        haut = dossier("etage", False)
        self.addCleanup(retire, haut)
        p = os.path.join(haut, "projet")
        os.makedirs(p)
        subprocess.check_call(["git", "init", "-q"], cwd=p)
        ecris(p, "CLAUDE.md", "# Le projet\n\nSon rôle, rien d'autre.\n")
        ecris(haut, "CLAUDE.md", "# Le commun\n\nRien sur la mémoire.\n")
        self.assertFalse(harnais(p, Chemins([])).oriente)
        ecris(haut, "CLAUDE.md", "# Le commun\n\n`brain/fact/` porte les faits.\n")
        self.assertTrue(harnais(p, Chemins([])).oriente)

    def test_a_plusieurs_chaque_agent_est_lu_depuis_son_dossier(self):
        """À plusieurs, l'état de chaque agent vit dans `brain/mind/<nom>/`, et ses
        réglages dans `agents/<nom>/` — ceux de la racine sont inertes."""
        d = dossier("equipe", True)
        for f in socle.faits_tous():
            ecris(d, "brain/fact/%s" % f, "x\n")
        v = courante()
        ags = []
        for a in ["Alpha", "Beta"]:
            for f in MIND_ATTENDU:
                ecris(d, "brain/mind/%s/%s" % (a, f), "x\n")
            ag = os.path.join(d, "agents", a)
            ecris(ag, "CLAUDE.md", "x\n")
            ecris(ag, ".claude/settings.json", DECLARE)
            trace(ag, v)
            ags.append(ag)
        ins = inscrit([ags[0], ags[1]], v)
        h = harnais(d, ins)
        self.assertEqual(verdict(h)[0], "ok")
        self.assertTrue("faits 5/5" in jauge(h) and "état 4/4" in jauge(h), jauge(h))
        x, c = juge(d, inscrit([ags[0]], v))
        self.assertEqual(x, "non-inscrit")
        self.assertTrue(c.startswith("Beta : "), "l'agent en défaut est nommé : %s" % c)
        os.remove(os.path.join(d, "brain/mind/Beta/todo.md"))
        x, c = juge(d, ins)
        self.assertEqual(x, "incomplet")
        self.assertIn("brain/mind/Beta/todo.md", c)
        retire(d)

    def test_une_equipe_un_dossier_par_agent_et_ce_qui_s_eparpille(self):
        """v3 (14/10/2026) : la forme est nommée, le rôle de l'agent n'est pas un
        surplus, et ce qui s'éparpille à nouveau se voit."""
        sys.path.insert(0, os.path.dirname(__file__))
        import banc_equipe
        d = dossier("v3", False)
        self.addCleanup(retire, d)
        banc_equipe.construis(d)
        for f in socle.faits_tous():
            ecris(d, "fact/%s" % f, "x\n")
        v = courante()
        ags = [os.path.join(d, "agents", a) for a in ("OPS", "PO")]
        for ag in ags:
            ecris(ag, ".claude/settings.json", DECLARE)
            trace(ag, v)
        h = harnais(d, inscrit(ags, v))
        self.assertEqual(h.forme, "equipe")
        self.assertEqual(h.surplus, [])
        self.assertTrue(h.oriente)
        self.assertEqual(verdict(h)[0], "ok", verdict(h))
        # UNE COPIE POSÉE À LA MAIN HORS DES AGENTS — ce que la page doit montrer.
        dehors = dossier("v3-dehors", False)
        self.addCleanup(retire, dehors)
        os.rmdir(dehors)
        subprocess.check_call(["git", "worktree", "add", "-q", "-b", "sauvage", dehors],
                              cwd=os.path.join(d, "agents", "OPS", "code"))
        x, c = verdict(harnais(d, inscrit(ags, v)))
        self.assertEqual(x, "disperse")
        self.assertIn(dehors, c)
        self.assertEqual(commandes_mortes(c), [])
        # Et un ancien dossier réapparu dans une copie du code.
        subprocess.check_call(["git", "worktree", "remove", "--force", dehors],
                              cwd=os.path.join(d, "agents", "OPS", "code"))
        self.assertEqual(verdict(harnais(d, inscrit(ags, v)))[0], "ok", "TÉMOIN : la copie retirée")
        os.makedirs(os.path.join(d, "agents", "PO", "code", "brain"))
        x, c = verdict(harnais(d, inscrit(ags, v)))
        self.assertEqual(x, "disperse")
        self.assertIn("`brain/` réapparu", c)

    def test_une_trace_dans_une_copie_de_travail_compte(self):
        """Un agent qui se lance depuis une copie de travail n'a, dans l'arbre
        principal, qu'une trace ancienne — ou aucune."""
        d = brain_mono("copie")
        c = d + "-copie"
        retire(c)

        def git(a):
            return subprocess.run(["git", "-c", "user.email=e@e", "-c", "user.name=e"] + a, cwd=d,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(git(["commit", "-q", "--allow-empty", "-m", "x"]).returncode, 0)
        ajout = git(["worktree", "add", "-q", c])
        self.assertEqual(ajout.returncode, 0, ajout.stderr.decode("utf-8", "replace"))
        c = os.path.realpath(c)
        v = courante()
        ins = inscrit([c], v)
        self.assertEqual(juge(d, ins)[0], "jamais-servi", "témoin : sans la trace de la copie")
        trace(c, v)
        self.assertEqual(juge(d, ins)[0], "ok")
        retire(c)
        retire(d)

    def test_aucun_conseil_ne_renvoie_a_une_commande_qui_n_existe_pas(self):
        """Le défaut d'origine : deux conseils renvoyaient à des compétences
        supprimées. Tous les verdicts sont produits, et chacun est relu."""
        # témoins : la vérification mord sur les deux morts d'origine
        u, y = "/agentic-" + "upgrade", "/agentic-" + "sync"
        self.assertEqual(commandes_mortes("lancer `%s` puis %s" % (u, y)), [u, y])
        # Composée à l'exécution : écrite en clair, le contrôle de la
        # documentation la prendrait pour une vraie citation.
        self.assertEqual(commandes_mortes("`harnais %s`" % "inexistant"), ["harnais inexistant"])
        self.assertEqual(commandes_mortes("`harnais adopte --go` puis `/agentic-adopte`, dans brain/mind/"), [])
        self.assertEqual(commandes_mortes("le harnais refuse de choisir"), [])
        self.assertEqual(commandes_mortes("`claude plugin upgrade x`"), ["claude plugin upgrade"])

        vus = {}

        def note(d, ins):
            v, c = juge(d, ins)
            vus[v] = c
        v = courante()
        d = brain_mono("tous")
        ins = inscrit([d], v)
        note(d, Chemins([]))
        note(d, Illisibles())
        note(d, ins)
        trace(d, v)
        note(d, ins)
        trace(d, "0.0.1")
        note(d, ins)
        note(d, inscrit([d], "0.0.1"))
        trace(d, v)
        ecris(d, ".claude/settings.json", "{}")
        note(d, ins)
        ecris(d, ".claude/settings.json", HOOKS)
        note(d, ins)
        ecris(d, ".claude/settings.json", '{"enabledPlugins":{"harnais@atelier":true}}')
        note(d, ins)
        ecris(d, ".claude/settings.json", DECLARE)
        ecris(d, "brain/fact/journal.md", "x\n")
        note(d, ins)
        os.remove(os.path.join(d, "brain/fact/journal.md"))
        os.remove(os.path.join(d, "brain/mind/todo.md"))
        note(d, ins)
        os.remove(os.path.join(d, "brain/mind/state.md"))
        note(d, ins)
        retire(d)
        d = dossier("tous-v1", True)
        note(d, ins)
        ecris(d, ".mind/state.md", "x\n")
        note(d, ins)
        ecris(d, ".memory/business.md", "x\n")
        note(d, ins)
        for f in socle.FAITS_MONO:
            ecris(d, ".fact/%s" % f, "x\n")
        shutil.rmtree(os.path.join(d, ".memory"))
        ecris(d, ".mind/todo.md", "x\n")
        ecris(d, ".claude/settings.json", DECLARE)
        trace(d, v)
        note(d, inscrit([d], v))
        ecris(d, ".claude/settings.json", "{}")
        note(d, inscrit([d], v))
        ecris(d, ".claude/settings.json", HOOKS)
        note(d, inscrit([d], v))
        os.makedirs(os.path.join(d, "brain"), exist_ok=True)
        note(d, ins)
        retire(d)
        d = dossier("tous-sans-git", False)
        note(d, ins)
        retire(d)

        # Chaque verdict que le tableau sait afficher a été produit ici : un
        # verdict ajouté sans essai fait échouer celui-ci.
        tous = ["ok", "v1", "en-retard", "neuf", "ancien", "ambigu", "incomplet", "sans-agent",
                "non-branche", "non-inscrit", "non-mesure", "jamais-servi", "sans-git", "surplus",
                "sans-deny", "hooks-locaux", "inscription-vieille"]
        for t in tous:
            self.assertIn(t, vus, "verdict jamais produit par l'essai : %s" % t)
            self.assertNotEqual(symbole(t), "?   ", "%s sans symbole" % t)
        self.assertEqual(len(vus), len(tous), "verdicts produits : %s" % sorted(vus))
        for v, c in sorted(vus.items()):
            self.assertEqual(commandes_mortes(c), [], "%s cite une commande morte : %s" % (v, c))


class DatesDeMaj(unittest.TestCase):
    """`maj:` se lit comme chrono : `%Y-%m-%d` puis `%Y%m%d`, jour sur DEUX chiffres au plus
    (équivalents vérifiés contre le Rust 0.12.8 par `equipe-vue`)."""

    AUJOURDHUI = datetime.date(2026, 10, 12)

    def test_un_jour_a_trois_chiffres_rend_la_date_illisible(self):
        """« 2026-10-012 » : trois chiffres de jour, même nuls en tête, ne sont pas une date
        (Rust : ILLISIBLE). Un jour lu sur trois chiffres rendrait « à jour » un en-tête faux."""
        self.assertEqual(vue.fraicheur("2026-10-012", self.AUJOURDHUI), ("illisible", None))
        self.assertEqual(vue.fraicheur("2026-10-123", self.AUJOURDHUI), ("illisible", None))
        self.assertIsNone(vue._date("2026-10-012"))
        self.assertIsNone(vue._date("2026-01-001"))

    def test_les_formes_de_date_lisibles(self):
        """Témoins : les formes valides restent lues (Rust : à jour 0 j, à jour 0 j, tiède 11 j)."""
        self.assertEqual(vue.fraicheur("2026-10-12", self.AUJOURDHUI), ("frais", 0))
        self.assertEqual(vue.fraicheur("20261012", self.AUJOURDHUI), ("frais", 0))
        self.assertEqual(vue.fraicheur("2026-10-1", self.AUJOURDHUI), ("tiede", 11))
        self.assertEqual(vue.fraicheur("20261001", self.AUJOURDHUI), ("tiede", 11))


if __name__ == "__main__":
    unittest.main()
