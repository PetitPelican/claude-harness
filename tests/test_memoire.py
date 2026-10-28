# -*- coding: utf-8 -*-
"""Essais de `py/memoire.py` — port de `mod essais` de `harnais/src/memoire.rs`.

Un test Python par `#[test]` du Rust (18), mêmes cas, mêmes assertions.
Lancer : python3 -m unittest discover -s tests -p "test_memoire.py"
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import memoire  # noqa: E402
from memoire import (Forme, resous, racine_depot, base, base_projet, pour_agent,  # noqa: E402
                     pour_projet, lot, NOM, BRAIN)


def mkdirs(*morceaux):
    os.makedirs(os.path.join(*morceaux), exist_ok=True)


class Essais(unittest.TestCase):

    def bac(self, n):
        d = tempfile.mkdtemp(prefix="harnais-memoire-%s-" % n)
        self.addCleanup(shutil.rmtree, d, True)
        return os.path.realpath(d)

    def depot(self, n):
        d = self.bac(n)
        subprocess.run(["git", "init", "-q"], cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return d

    # LE PRÉFIXE DE L'ESPRIT SUIT LA FORME, dans les trois formes.
    #
    # `mind_guard` composait ce chemin à la main. Sur un arbre migré le nom
    # composé ne désignait plus rien, et le contrôle de lisibilité laissait
    # passer un `state.md` sans en-tête. Ce test épingle les trois formes
    # ensemble : c'est leur DIVERGENCE qui est le sujet, pas l'une d'elles.
    def test_le_prefixe_de_l_esprit_suit_la_forme(self):
        d = self.bac("pfx-mind")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # v1 · en place
        mkdirs(d, ".fact")
        mkdirs(d, ".mind")
        self.assertEqual(resous(d).prefixe_mind, ".mind/")

        # v2 · LE CERVEAU, ET L'ANCIEN A DISPARU. Les laisser cohabiter rend
        # `Ambigue` — c'est le but de cette forme, et la migration retire
        # l'ancien dans le même geste. Une première version de ce test créait
        # les deux et attendait `Brain` : elle épinglait un arbre qui ne peut
        # pas exister après migration.
        shutil.rmtree(os.path.join(d, ".fact"))
        shutil.rmtree(os.path.join(d, ".mind"))
        mkdirs(d, "brain/fact")
        mkdirs(d, "brain/mind")
        r = resous(d)
        self.assertEqual(r.prefixe_mind, "brain/mind/")
        self.assertEqual(r.prefixe_fact, "brain/fact/")

        # v2 · le cerveau, à plusieurs — l'esprit porte le nom de l'agent
        a = os.path.join(d, "agents/ios")
        mkdirs(a, ".claude")
        mkdirs(d, "brain/mind/ios")
        r = resous(a)
        self.assertEqual(r.prefixe_mind, "brain/mind/ios/")
        # ET LE COMMUN RESTE COMMUN : les faits ne prennent pas le nom.
        self.assertEqual(r.prefixe_fact, "brain/fact/")

    def test_hors_depot_tout_rend_none(self):
        d = self.bac("hors")
        # TÉMOIN NÉGATIF : sans dépôt, aucune résolution ne doit inventer un chemin.
        self.assertIsNone(racine_depot(d))
        self.assertIsNone(base(d))
        self.assertEqual(pour_agent(d), (None, None))
        self.assertEqual(lot(d), "")

    def test_un_projet_sans_dossier_memoire_ne_bouge_pas(self):
        d = self.bac("enplace")
        mkdirs(d, ".fact")
        # Pas de `memoire/` : la réponse est « résous comme avant », pas une erreur.
        self.assertIsNone(base_projet(d))
        self.assertEqual(pour_projet(d), (None, None))

    def test_un_projet_deporte_rend_ses_deux_maisons(self):
        d = self.bac("deporte")
        for s in [".fact", ".mind", "agents/Team PO/.mind", "agents/QA/.mind"]:
            mkdirs(d, NOM, s)
        fact, etats = pour_projet(d)
        self.assertEqual(fact, os.path.join(d, NOM, ".fact"))
        e = etats
        # Deux agents, classés — et le `.mind` racine EST ignoré quand des
        # agents existent : c'est la règle de la version Python.
        self.assertEqual(len(e), 2)
        self.assertEqual(e[0][0], "QA")
        self.assertEqual(e[1][0], "Team PO")

    def test_mono_agent_retombe_sur_le_mind_racine(self):
        d = self.bac("mono")
        mkdirs(d, NOM, ".mind")
        _, etats = pour_projet(d)
        e = etats
        self.assertEqual(len(e), 1)
        self.assertIsNone(e[0][0], "aucun nom : c'est le projet lui-même")

    # ── `resous()` : la forme est une VALEUR ──────────────────────────────
    #
    # Chaque cas porte son contraire. Un contrôle qui ne rend jamais `Ambigue`
    # ne prouve pas qu'il sait la reconnaître.

    def test_resous_hors_depot_ne_devine_rien(self):
        r = resous(self.bac("r-hors"))
        self.assertEqual(r.forme, Forme.HorsDepot)
        self.assertIsNone(r.racine)
        self.assertIsNone(r.fact)
        # TÉMOIN : hors dépôt, `mind` aussi reste vide — sinon on inventerait
        # un chemin dans un dossier qui n'appartient à personne.
        self.assertIsNone(r.mind)
        self.assertFalse(memoire.a_des_faits(r.forme))

    def test_un_depot_sans_memoire_ne_se_dit_plus_hors_depot(self):
        # Audit § 6 ③ : ce cas se nommait « hors-depot » et la ligne suivante
        # du diagnostic donnait la racine du dépôt.
        d = self.depot("r-sansmem")
        r = resous(d)
        self.assertEqual(r.forme, Forme.SansMemoire)
        self.assertEqual(memoire.forme_mot(r.forme), "sans-memoire")
        self.assertIsNotNone(r.racine)
        self.assertIsNone(r.base_des_prefixes())
        # TÉMOIN : le même dossier avec des faits change de forme, et sa base
        # des préfixes est l'arbre — pas `None` pour tout le monde.
        mkdirs(d, ".fact")
        r = resous(d)
        self.assertEqual(r.forme, Forme.EnPlace)
        self.assertEqual(r.base_des_prefixes(), r.arbre)
        self.assertIsNotNone(r.base_des_prefixes())

    def test_resous_en_place_rend_des_chemins_et_un_prefixe(self):
        d = self.depot("r-enplace")
        mkdirs(d, ".fact")
        r = resous(d)
        self.assertEqual(r.forme, Forme.EnPlace)
        self.assertEqual(r.fact, os.path.join(d, ".fact"))
        self.assertEqual(r.mind, os.path.join(d, ".mind"))
        # Le préfixe est ce que `git diff --cached` rend, barre finale comprise.
        self.assertEqual(r.prefixe_fact, ".fact/")
        self.assertTrue(memoire.a_des_faits(r.forme))

    def test_resous_en_place_depuis_un_agent_porte_le_lot(self):
        d = self.depot("r-agent")
        mkdirs(d, ".fact")
        a = os.path.join(d, "agents", "QA")
        mkdirs(a)
        r = resous(a)
        self.assertEqual(r.forme, Forme.EnPlace)
        self.assertEqual(r.lot, "agents/QA")
        # Les faits sont au PROJET, l'état est à l'AGENT — c'est toute la règle.
        self.assertEqual(r.fact, os.path.join(d, ".fact"))
        self.assertEqual(os.path.normpath(r.mind), os.path.normpath(os.path.join(d, "agents/QA/.mind")))
        self.assertEqual(r.prefixe_fact, ".fact/")

    def test_resous_deportee_vise_le_depot_de_memoire(self):
        d = self.depot("r-deporte")
        mkdirs(d, NOM, ".fact")
        r = resous(d)
        self.assertEqual(r.forme, Forme.Deportee)
        self.assertEqual(r.fact, os.path.join(d, NOM, ".fact"))
        # DÉPORTÉE : le préfixe est NU. Les chemins que la garde compare
        # viennent du dépôt de mémoire, où le lot n'existe pas.
        self.assertEqual(r.prefixe_fact, ".fact/")
        self.assertEqual(r.prefixe_projet, "")
        self.assertTrue(memoire.a_des_faits(r.forme))

    def test_dans_la_v1_le_deporte_gagne_et_ce_n_est_pas_une_ambiguite(self):
        d = self.depot("r-v1-deux")
        mkdirs(d, ".fact")
        mkdirs(d, NOM, ".fact")
        r = resous(d)
        # LE DÉPORT NE SUPPRIME PAS L'ANCIEN DOSSIER : les deux cohabitent
        # légitimement, et la règle « le déporté gagne » est établie depuis le
        # 08/09. J'ai élargi l'ambiguïté à ce cas, et le contrôle différentiel
        # l'a dit dans la minute — deux briefings ont cessé de trouver leurs
        # faits. Un garde trop large casse ce qu'il devait protéger.
        self.assertEqual(r.forme, Forme.Deportee)
        self.assertEqual(r.fact, os.path.join(d, NOM, ".fact"))

    def test_resous_sans_faits_ne_pretend_pas_en_avoir(self):
        d = self.depot("r-avant")
        # Ni `.fact/` ni `memoire/` : la forme d'AVANT la migration.
        r = resous(d)
        self.assertIsNone(r.fact)
        # TÉMOIN : c'est ici que se jouait le piège du `cap:`. Un projet sans
        # faits ne doit pas être annoncé comme en ayant, sinon la garde de
        # commit lui réclame le mauvais contrat d'en-tête.
        self.assertFalse(memoire.a_des_faits(r.forme))
        # Mais le chemin de l'état est rendu quand même : l'appelant doit
        # pouvoir dire « cherché ici, absent », jamais rester muet.
        self.assertEqual(r.mind, os.path.join(d, ".mind"))

    # ── v2 · le cerveau ──────────────────────────────────────────────────

    def test_resous_v2_mono_un_seul_esprit(self):
        d = self.depot("r-brain-mono")
        for s in ["fact", "mind"]:
            mkdirs(d, BRAIN, s)
        r = resous(d)
        self.assertEqual(r.forme, Forme.Brain)
        self.assertEqual(r.fact, os.path.join(d, BRAIN, "fact"))
        # MONO : pas de niveau `<nom>`. Il n'y a qu'un esprit, le nommer serait
        # inventer une équipe qui n'existe pas.
        self.assertEqual(r.mind, os.path.join(d, BRAIN, "mind"))
        # Pas de carnet non plus : personne à qui écrire, et un dossier vide
        # se lirait comme un carnet muet.
        self.assertIsNone(r.workspace)
        self.assertFalse(r.brain_autonome)
        self.assertTrue(memoire.a_des_faits(r.forme))

    # LE CARNET NAÎT LÀ OÙ ON LE CHERCHE, dans chaque forme.
    #
    # Défaut mesuré le 10/09/2026 : la règle existait en double, et la copie de
    # `carnet` ne connaissait pas le cerveau. Sur un projet en `brain/`, le
    # carnet était créé à la racine et cherché dans le cerveau — il naissait
    # invisible, sans un mot.
    #
    # Le témoin porte les deux sens : chaque forme rend SON emplacement, et
    # aucune ne rend celui d'une autre. Une fonction qui répondrait `equipe`
    # à tout passerait le seul cas `en-place`.
    def test_le_carnet_nait_la_ou_on_le_cherche(self):
        d = self.depot("r-ws")
        # en place : le carnet est à la racine du dépôt de code
        mkdirs(d, ".fact")
        self.assertEqual(resous(d).workspace_prevu(), os.path.join(d, "equipe"))

        # cerveau : le carnet est DANS le cerveau, pas à côté
        b = self.depot("r-ws-brain")
        mkdirs(b, BRAIN, "fact")
        vu = resous(b).workspace_prevu()
        self.assertTrue(os.path.normpath(vu).endswith(os.path.normpath("brain/workspace")),
                        "cerveau : rendu %r" % (vu,))
        self.assertFalse(vu.endswith("equipe"), "cerveau : rend l'emplacement d'en-place")

        # AMBIGUË : deux arbres, aucun choix. Créer ici, c'est créer un carnet
        # que l'autre arbre ne verra jamais.
        a = self.depot("r-ws-ambigu")
        mkdirs(a, BRAIN, "fact")
        mkdirs(a, ".fact")
        self.assertEqual(resous(a).forme, Forme.Ambigue)
        self.assertIsNone(resous(a).workspace_prevu())

    # UNE SEULE ORTHOGRAPHE PAR DOSSIER, dans toute la résolution.
    #
    # Hors worktree, `racine` et `arbre` désignent le même dossier. S'ils ne
    # s'écrivent pas pareil, tout ce qui mélange les deux — `strip_prefix`,
    # `==`, la composition du carnet — cesse de mordre sans rien dire.
    #
    # TÉMOIN NÉGATIF : la course 34496105644 du 10/09/2026, sur le runner
    # Windows, avec la racine non canonicalisée. `racine` valait `C:/…` et
    # `arbre` `\\?\C:\…` ; le témoin du carnet est tombé là-dessus. Sur macOS
    # les deux orthographes coïncident : ce test y passe dans les deux sens, et
    # c'est exactement pourquoi le défaut a vécu jusqu'au premier franchissement
    # de la chaîne sous Windows.
    def test_la_racine_et_l_arbre_s_ecrivent_pareil(self):
        d = self.depot("r-orthographe")
        mkdirs(d, ".fact")
        r = resous(d)
        self.assertEqual(r.racine, r.arbre, "deux orthographes du même dossier")
        # Et le carnet se compose sur cette orthographe-là, pas sur une autre.
        self.assertEqual(r.workspace_prevu(), os.path.join(d, "equipe"))

    def test_resous_v2_multi_un_esprit_par_agent(self):
        d = self.depot("r-brain-multi")
        for s in ["fact", "mind/Projet QA", "workspace"]:
            mkdirs(d, BRAIN, s)
        mkdirs(d, "agents", "Projet QA")
        r = resous(os.path.join(d, "agents", "Projet QA"))
        self.assertEqual(r.forme, Forme.Brain)
        self.assertEqual(r.lot, "agents/Projet QA")
        # `agents/` n'existe PAS dans le cerveau : il ne désigne que le dossier
        # de lancement, dans le code. Le cerveau range par NOM.
        self.assertEqual(r.nom_agent, "Projet QA")
        self.assertEqual(r.mind, os.path.join(d, BRAIN, "mind", "Projet QA"))
        self.assertEqual(r.fact, os.path.join(d, BRAIN, "fact"))
        self.assertEqual(r.workspace, os.path.join(d, BRAIN, "workspace"))

    def test_resous_refuse_de_choisir_entre_les_trois_arbres(self):
        # TROIS combinaisons, et aucune ne doit rendre un arbre. C'est l'état
        # qu'une migration interrompue laisse : servir l'un des deux servirait
        # l'état d'hier, sans un mot.
        # L'ANCIEN CONTRE LE NEUF, et seulement ça. `.fact` + `memoire` est
        # une cohabitation de v1, pas une migration à moitié faite.
        for (a, b) in [(".fact", BRAIN), (NOM, BRAIN)]:
            d = self.depot("r-3arbres-%s-%s" % (a.lstrip("."), b))
            mkdirs(d, a)
            mkdirs(d, b)
            r = resous(d)
            self.assertEqual(r.forme, Forme.Ambigue, "%s + %s devait être ambigu" % (a, b))
            # ET RIEN N'EST RENDU. Un chemin rendu serait lu.
            self.assertIsNone(r.fact)
            self.assertIsNone(r.mind)

    def test_resous_v2_sait_si_le_cerveau_a_son_depot(self):
        d = self.depot("r-brain-autonome")
        mkdirs(d, BRAIN, "fact")
        self.assertFalse(resous(d).brain_autonome)
        # Ce qui reste de « déportée » une fois que ce n'est plus une forme :
        # une propriété, qui ne décide que d'une chose — où l'on commite.
        subprocess.run(["git", "init", "-q"], cwd=os.path.join(d, BRAIN),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertTrue(resous(d).brain_autonome)


class Equipe(unittest.TestCase):
    """v3 · « UN DOSSIER PAR AGENT » (décision du 14/10/2026)."""

    def setUp(self):
        sys.path.insert(0, os.path.dirname(__file__))
        import banc_equipe
        d = tempfile.mkdtemp(prefix="harnais-equipe-")
        self.addCleanup(shutil.rmtree, d, True)
        self.x = banc_equipe.construis(os.path.realpath(d))

    def j(self, *p):
        return os.path.join(self.x, *p)

    def test_depuis_le_dossier_de_l_agent(self):
        r = resous(self.j("agents", "PO"))
        self.assertEqual(r.forme, Forme.Equipe)
        self.assertEqual(r.projet, self.x)
        self.assertEqual(r.fact, self.j("fact"))
        self.assertEqual(r.mind, self.j("agents", "PO"))
        self.assertEqual(r.workspace, self.j("shared"))
        self.assertEqual((r.lot, r.prefixe_lot, r.nom_agent), ("agents/PO", "agents/PO/", "PO"))
        self.assertEqual((r.prefixe_fact, r.prefixe_mind), ("fact/", "agents/PO/"))
        self.assertTrue(r.brain_autonome)
        self.assertEqual(r.base_des_prefixes(), self.x)
        self.assertEqual(r.workspace_prevu(), self.j("shared"))
        # git tourne DANS la mémoire : c'est à l'appelant de le voir.
        self.assertEqual(r.racine, self.x)

    def test_depuis_le_fond_de_sa_copie_du_code(self):
        """Démarrer n'importe où sous `agents/<nom>/` rend l'équipe — aucun outil ne
        peut alors recréer un `brain/` dans le code. Et git y parle du CODE."""
        for a in ("OPS", "PO"):
            r = resous(self.j("agents", a, "code", "apps"))
            self.assertEqual((r.forme, r.mind, r.nom_agent), (Forme.Equipe, self.j("agents", a), a))
            self.assertNotEqual(r.racine, self.x, "git devait parler du dépôt du code")
        self.assertEqual(resous(self.j("agents", "PO", "code")).racine, self.j("agents", "OPS", "code"),
                         "la racine d'une copie est le checkout principal du code")

    def test_git_dans_le_code_position_dans_l_agent(self):
        r = memoire.resous_depuis(self.j("agents", "PO", "code"), self.j("agents", "PO"))
        self.assertEqual((r.forme, r.nom_agent), (Forme.Equipe, "PO"))
        self.assertEqual(r.arbre, self.j("agents", "PO", "code"))

    def test_depuis_la_racine_de_l_equipe(self):
        r = resous(self.x)
        self.assertEqual((r.forme, r.nom_agent, r.lot), (Forme.Equipe, "", ""))
        self.assertEqual(r.mind, self.j("agents"))

    def test_temoins_negatifs(self):
        """Sans `fact/`, ou avec un `brain/` à côté, ce n'est PAS une équipe : un
        projet `brain/` multi a aussi des `agents/<nom>/`."""
        shutil.rmtree(self.j("fact"))
        self.assertNotEqual(resous(self.j("agents", "PO")).forme, Forme.Equipe)
        mkdirs(self.x, "fact")
        mkdirs(self.x, BRAIN, "fact")
        self.assertNotEqual(resous(self.j("agents", "PO")).forme, Forme.Equipe)
        self.assertEqual(memoire.forme_mot(Forme.Equipe), "equipe")
        self.assertTrue(memoire.a_des_faits(Forme.Equipe))


if __name__ == "__main__":
    unittest.main()
