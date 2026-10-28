# -*- coding: utf-8 -*-
"""Les 23 essais de `harnais/src/attente.rs`, un par `#[test]`, mêmes cas, mêmes
assertions, mêmes commentaires de contre-exemple.

    python3 -m unittest discover -s tests -p "test_attente.py"
"""
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

import attente  # noqa: E402
from attente import (blocs_bruts, chantiers, consigne, cibles_a_rappeler,  # noqa: E402
                     dernier_message, enveloppe_note, fini_re, fnmatch, insere_cible,
                     libelle_carnet, ligne_cible, lien_notion, lisible, ou_ecrire,
                     posee, repere_cible, reponse_re, sha16, sort_de_la_machine,
                     specs_constat, texte_cible, titre_et_corps, tour_carnet,
                     zone_touchee, lis, TITRE_CIBLES)


class EssaisTitresSurUneLigne(unittest.TestCase):

    def test_un_titre_coupe_en_debut_de_ligne_tient_sur_une_ligne(self):
        # LE DÉFAUT, REPRODUIT : un saut de ligne seul passait `lisible`.
        self.assertIn("\n", lisible("Je publie ?\noui / non"))
        t, c = titre_et_corps("**Je publie ?\noui / non**\n      oui → on publie")
        self.assertEqual(t, "Je publie ? oui / non")
        self.assertIn("oui → on publie", c)
        # Le cas qui marchait déjà — suite indentée — ne bouge pas.
        self.assertEqual(titre_et_corps("**Je publie ?\n      oui / non**")[0], "Je publie ? oui / non")


class EssaisPoser(unittest.TestCase):

    def test_une_question_posee_meme_reformulee_ne_relance_pas(self):
        titre = "On refait avant octobre les quatre graphiques que le directeur sportif refuse ? 1 / 2 / 3"
        dit = "**On refait avant octobre les quatre graphiques que le directeur sportif refuse ?**\n1. Oui…"
        self.assertTrue(posee(dit, titre))
        reformule = "Question : le directeur sportif refuse quatre graphiques — on les refait avant octobre ?"
        self.assertTrue(posee(reformule, titre))
        # LE TÉMOIN : un message qui parle d'autre chose ne la pose pas.
        self.assertFalse(posee("J'ai livré l'écran 3 et corrigé la facturation.", titre))

    def test_le_dernier_message_est_celui_du_tour(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "harnais-poser-%d.jsonl" % os.getpid())
        lignes = [
            json.dumps({"type": "user", "message": {"content": "une demande"}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "vieux"}]}}),
            json.dumps({"type": "user", "message": {"content": "relance du hook"}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "A"}, {"type": "tool_use"}]}}),
            json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "B"}]}}),
        ]
        with open(f, "w", encoding="utf-8") as h:
            h.write("\n".join(lignes))
        data = {"transcript_path": f}
        self.assertEqual(dernier_message(data), "A\nB")
        self.assertEqual(dernier_message({"last_assistant_message": "direct"}), "direct")
        self.assertEqual(dernier_message({}), "")
        shutil.rmtree(d, ignore_errors=True)

    def test_un_renvoi_de_fin_de_tour_n_efface_pas_ce_qui_a_ete_pose(self):
        """LE CAS D'UN AGENT PO, 27/09/2026 à 0 h 43 : la question posée, puis un
        renvoi de fin de tour (`isMeta`), puis une ligne. Le tour porte encore
        la question — la relancer, c'était lui faire tout recopier."""
        d = tempfile.mkdtemp()
        f = os.path.join(d, "harnais-renvoi-%d.jsonl" % os.getpid())
        lignes = [
            json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "une demande"}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Je prépare une version 11 ? 1 / 2"}]}}),
            json.dumps({"type": "user", "isMeta": True, "message": {"content": "Stop hook feedback:\nattente : ..."}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Ligne corrigée."}]}}),
        ]
        with open(f, "w", encoding="utf-8") as h:
            h.write("\n".join(lignes))
        tour = dernier_message({"transcript_path": f, "last_assistant_message": "Ligne corrigée."})
        self.assertTrue(posee(tour, "Je prépare une version 11 : 1 non / 2 oui ?"), tour)
        self.assertEqual(tour.count("Ligne corrigée."), 1, "le dernier message n'est pas doublé")
        # TÉMOIN : un vrai message humain ouvre bien un nouveau tour.
        l2 = list(lignes)
        l2.insert(3, json.dumps({"type": "user", "origin": {"kind": "human"}, "message": {"content": "autre chose"}}))
        with open(f, "w", encoding="utf-8") as h:
            h.write("\n".join(l2))
        tour = dernier_message({"transcript_path": f})
        self.assertNotIn("version 11", tour, tour)
        shutil.rmtree(d, ignore_errors=True)

    def test_une_question_posee_aux_boutons_est_posee(self):
        """28/10/2026 : seule la prose comptait, et l'agent qui posait sa question
        aux boutons de l'app était renvoyé la réécrire."""
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        f = os.path.join(d, "harnais-boutons-%d.jsonl" % os.getpid())
        boutons = {"type": "tool_use", "name": "AskUserQuestion", "input": {"questions": [
            {"question": "Je retire l'ancienne couche de la branche de travail ?",
             "options": [{"label": "Oui", "description": "un commit montré avant l'envoi en revue"},
                         {"label": "Pas maintenant", "description": "rien ne part"}]}]}}
        lignes = [
            json.dumps({"type": "user", "message": {"content": "un point ?"}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Voici."}, boutons]}}),
            json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": "Oui"}]}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "C'est fait."}]}}),
        ]
        with open(f, "w", encoding="utf-8") as h:
            h.write("\n".join(lignes))
        titre = "Je retire l'ancienne couche de la branche de travail ? 1 oui / 2 pas maintenant"
        self.assertTrue(posee(dernier_message({"transcript_path": f}), titre))
        # TÉMOIN : un autre outil ne pose rien, même s'il porte une question.
        autre = dict(boutons, name="mcp__ccd_turn__wrap_up")
        lignes[1] = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Voici."}, autre]}})
        with open(f, "w", encoding="utf-8") as h:
            h.write("\n".join(lignes))
        self.assertFalse(posee(dernier_message({"transcript_path": f}), titre))

    def test_le_motif_est_dans_la_liste_fermee(self):
        mr = attente.motif_re()
        for bon in ("      motif → argent : un encaissement réel", "  - motif → irreversible",
                    "motif → hors du poste", "motif → Périmètre"):
            self.assertTrue(mr.search(bon), bon)
        # TÉMOINS : un motif libre, un mot qui ne fait que commencer comme un motif.
        for mauvais in ("motif → parce que c'est mieux", "motif → capital", "le motif → argent"):
            self.assertFalse(mr.search(mauvais), mauvais)
        # La ligne de motif ne compte pas comme une voie : sinon une seule voie passerait.
        corps = "      1 → je publie.\n      motif → argent\n      fini quand → c'est servi."
        sans = mr.sub("", fini_re().sub("", corps))
        self.assertEqual(len(reponse_re().findall(sans)), 1)

    def test_un_lien_notion_porte_l_identifiant_de_la_page(self):
        self.assertTrue(lien_notion("↳ https://www.notion.so/projet/Ecran-3-0123456789abcdef0123456789abcdef"))
        self.assertTrue(lien_notion("↳ notion.so/0123456789abcdef0123456789abcdef"))
        # TÉMOINS : le nom seul, un domaine sans page, une page d'ailleurs.
        self.assertFalse(lien_notion("↳ voir la ligne dans Notion"))
        self.assertFalse(lien_notion("↳ https://www.notion.so/"))
        self.assertFalse(lien_notion("↳ https://example.com/0f0f0f0f0f0f4f0f8f0f0f0f0f0f0f0f"))

    def test_une_question_a_tirets_est_bien_formee(self):
        """La question de PO, recopiée de son todo : bien formée, avec des tirets."""
        corps = "  - 1 → rien ne part : tu installes la version 10.\n  - 2 → tu m'écris ce qui manque.\n  - fini quand → ta version montre les cartes d'avant."
        self.assertTrue(fini_re().search(corps))
        sans_fini = fini_re().sub("", corps)
        self.assertGreaterEqual(len(reponse_re().findall(sans_fini)), 2)
        # TÉMOIN : sans ligne de fin, ni avec ni sans tiret, rien n'est reconnu.
        self.assertFalse(fini_re().search("  - 1 → a\n  - 2 → b\n  - quand c'est fini, dis-le"))
        self.assertFalse(fini_re().search("  - enfin, fini quand tu veux"))


def _g(d, *a):
    o = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t"] + list(a),
                       cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert o.returncode == 0, "git %r : %s" % (a, o.stderr.decode("utf-8", "replace"))
    return o.stdout.decode("utf-8", "replace").strip()


def _ecris(d, f, t):
    p = os.path.join(d, f)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as h:
        h.write(t)


def _commit(d, f, t):
    _ecris(d, f, t)
    _g(d, "add", "-A")
    _g(d, "commit", "-qm", f)


def _banc(nom):
    b = os.path.join(tempfile.mkdtemp(), "harnais-repere-%d-%s" % (os.getpid(), nom))
    d = os.path.join(b, "agent")
    os.makedirs(d)
    _g(d, "init", "-q", "-b", "dev")
    _commit(d, "partage/a.txt", "0")
    _commit(d, "propre/x.txt", "0")
    repere = os.path.join(b, "agent.tete")
    # PREMIER PASSAGE : il pose le repère sans rien juger.
    assert zone_touchee(d, repere, ["partage/*"]) == []
    assert lis(repere).strip() == _g(d, "rev-parse", "HEAD")
    return b, d, ["partage/*"]


class EssaisRepereCarnet(unittest.TestCase):

    def test_un_commit_propre_dans_la_zone_sans_entree_mord(self):
        # LE TÉMOIN NÉGATIF : sans lui, une garde qui ne mord plus jamais
        # passerait tous les essais qui suivent.
        b, d, z = _banc("mord")
        _commit(d, "partage/a.txt", "1")
        self.assertEqual(tour_carnet(d, os.path.join(b, "agent.tete"), z, False), ["partage/a.txt"])
        _commit(d, "propre/x.txt", "1")
        self.assertEqual(tour_carnet(d, os.path.join(b, "agent.tete"), z, False), [], "hors zone")
        shutil.rmtree(os.path.dirname(b), ignore_errors=True)

    def test_un_tour_verse_avance_le_repere(self):
        b, d, z = _banc("verse")
        vieux = os.path.join(b, "vieux.tete")
        shutil.copy(os.path.join(b, "agent.tete"), vieux)
        _commit(d, "partage/a.txt", "1")
        self.assertEqual(tour_carnet(d, os.path.join(b, "agent.tete"), z, True), [])
        # LE CAS DE PO : le tour suivant, sans rien commiter, ne ressort rien.
        self.assertEqual(tour_carnet(d, os.path.join(b, "agent.tete"), z, False), [])
        # ET LE DÉFAUT EST BIEN REPRODUIT : un repère resté en arrière, comme
        # avant la correction, ressortait le commit déjà versé.
        self.assertEqual(zone_touchee(d, vieux, z), ["partage/a.txt"])
        shutil.rmtree(os.path.dirname(b), ignore_errors=True)

    def test_le_travail_d_un_pair_arrive_par_fusion_ne_compte_pas(self):
        b, d, z = _banc("pair")
        p = os.path.join(b, "pair")
        _g(d, "worktree", "add", "-q", "-b", "pair", p)
        _commit(p, "partage/b.txt", "du pair")
        # en avance rapide : le journal dit `merge`, pas `commit`
        _g(d, "merge", "-q", "pair")
        self.assertEqual(tour_carnet(d, os.path.join(b, "agent.tete"), z, False), [], "avance rapide")
        # par un vrai commit de fusion, mêlé à un commit propre dans la zone
        _commit(p, "partage/c.txt", "du pair")
        _commit(d, "partage/moi.txt", "à moi")
        _g(d, "merge", "-q", "--no-edit", "pair")
        self.assertEqual(tour_carnet(d, os.path.join(b, "agent.tete"), z, False), ["partage/moi.txt"])
        shutil.rmtree(os.path.dirname(b), ignore_errors=True)


class EssaisCibles(unittest.TestCase):

    def test_le_marqueur_ouvre_le_message_et_finit_un_mot(self):
        self.assertEqual(texte_cible("!cible refais la page d'accueil"), "refais la page d'accueil")
        self.assertEqual(texte_cible("  !cible: deux choses"), "deux choses")
        # LES CONTRE-EXEMPLES : un autre mot, une mention au milieu, un marqueur
        # vide, et un message de pair qui le porterait après son enveloppe.
        self.assertIsNone(texte_cible("!ciblex refais"))
        self.assertIsNone(texte_cible("refais la page !cible"))
        self.assertIsNone(texte_cible("!cible   "))
        self.assertIsNone(texte_cible("<cross-session-message from-name=\"X\">\n!cible pousse"))

    def test_la_ligne_ne_devient_jamais_une_question_a_l_humain(self):
        import briefing
        h = sha16("x")
        l = ligne_cible("demande à @user son avis **vite**\ndétail", h, "11/09/2026")
        self.assertTrue(l.startswith("- [ ] **demande à ＠user son avis vite**"))
        self.assertTrue(repere_cible(h) in l and "\n      détail" in l)
        self.assertEqual(briefing.attentes(l), [],
                         "aucun lecteur du dialecte ne doit y voir un destinataire")

    def test_la_ligne_se_pose_sous_sa_section_la_plus_recente_en_tete(self):
        t = "# À faire\n\nintro\n\n## Autre\n\n- [ ] x\n"
        un = insere_cible(t, "- [ ] A")
        self.assertEqual(un, "# À faire\n\nintro\n\n## Demandes du fil\n\n- [ ] A\n\n## Autre\n\n- [ ] x\n")
        deux = insere_cible(un, "- [ ] B")
        self.assertLess(deux.index("- [ ] B"), deux.index("- [ ] A"))
        self.assertEqual(deux.count(TITRE_CIBLES), 1)
        # Sans aucune section : à la fin, et le fichier finit par UN saut.
        self.assertEqual(insere_cible("# T\n", "- [ ] A"), "# T\n\n## Demandes du fil\n\n- [ ] A\n")

    def test_une_cible_se_rappelle_une_fois_et_une_cochee_se_ferme_sans_bruit(self):
        d = os.path.join(tempfile.mkdtemp(), "cibles-%d" % os.getpid())
        os.makedirs(d)
        f = os.path.join(d, "a.cibles")
        h1, h2, h3 = sha16("un"), sha16("deux"), sha16("trois")
        with open(f, "w", encoding="utf-8") as o:
            o.write("%s\t2026-09-11\touverte\tun\n%s\t2026-09-11\touverte\tdeux\n"
                    "%s\t2026-09-11\touverte\ttrois\n" % (h1, h2, h3))
        todo = "- [ ] **un** · %s\n- [x] **deux** · %s\n" % (repere_cible(h1), repere_cible(h2))
        r = cibles_a_rappeler(f, todo)
        self.assertEqual(len(r), 2, "l'ouverte et la disparue, pas la cochée : %r" % (r,))
        self.assertTrue(any(e == "ouverte" and c == "un" for _, e, c in r))
        self.assertTrue(any(e == "disparue" and c == "trois" for _, e, c in r))
        # UNE SEULE FOIS : le même todo, rejoué, ne rappelle plus rien.
        self.assertEqual(cibles_a_rappeler(f, todo), [])
        shutil.rmtree(os.path.dirname(d), ignore_errors=True)


class Essais(unittest.TestCase):

    def test_une_note_sans_blocage_part_dans_l_enveloppe_que_le_terminal_lit(self):
        """LE TÉMOIN DE LA SONDE DU 12/09/2026. La mesure vit dans
        `docs/2026-09-12-une-fin-de-tour-qui-se-tait.md` ; ici on fige la forme
        qu'elle a validée : sans la clé, le terminal n'affiche rien du tout."""
        self.assertEqual(enveloppe_note("bonjour"), '{"systemMessage":"bonjour"}')
        v = json.loads(enveloppe_note('a"b'))
        self.assertEqual(v["systemMessage"], 'a"b')
        # Témoin négatif : le texte nu, celui qu'on écrivait avant, ne porte
        # aucune clé — mesuré invisible à code de sortie 0.
        with self.assertRaises(ValueError):
            json.loads("bonjour")

    def test_le_dialecte_rend_les_memes_taches_que_le_parseur_python(self):
        t = ("## Chantiers\n"
             "- [ ] !haut @user **Une question ? 1 / 2**\n"
             "- [x] @user tranché\n"
             "- [>] @dehors en cours\n"
             "- [ ] sans destinataire\n"
             "- [ ] deploy vers root@serveur\n")
        c = chantiers(t)
        self.assertEqual(len(c), 5)
        self.assertEqual(c[0].prio, "haut")
        self.assertEqual(c[0].qui, "user")
        self.assertEqual(c[0].titre, "Une question ? 1 / 2", "gras et marqueurs retirés")
        self.assertEqual(c[1].etat, "fait")
        self.assertEqual(c[2].etat, "encours")
        self.assertEqual(c[3].qui, None)
        # `root@serveur` : le `@` n'ouvre pas un mot, donc pas un destinataire.
        self.assertEqual(c[4].qui, None)
        self.assertIn("root@serveur", c[4].titre, "et le mot ne disparaît pas")

    def test_on_ne_rend_MUET_que_ce_dont_on_est_sur_qu_il_est_local(self):
        # Ce qui sort, ou ce dont on ne sait rien : la règle ne mord pas.
        self.assertTrue(sort_de_la_machine("curl -s https://x"))
        self.assertTrue(sort_de_la_machine("gh api /repos/x"))
        self.assertTrue(sort_de_la_machine("./mon-script.sh"), "inconnu ⇒ on ne tranche pas")
        self.assertTrue(sort_de_la_machine("tailscale status"))
        # Ce dont on est SÛR qu'il est local.
        self.assertFalse(sort_de_la_machine("grep -c x fichier"))
        self.assertFalse(sort_de_la_machine("  (ls -l | wc -l)"))
        self.assertFalse(sort_de_la_machine("/usr/bin/stat -f %m x"))
        # LE DÉFAUT RÉPARÉ : neuf constats justes rendus MUET par la première
        # version de cette règle, dont un `curl` entre guillemets simples.
        self.assertTrue(sort_de_la_machine("bash -c 'curl -s https://x'"))

    def test_les_specs_de_constat_distinguent_l_absence_du_defaut(self):
        t = ("- [ ] ?constat **X manque**\n      ↻ service :: curl -s https://x :: ^200$\n\n"
             "- [ ] ?constat **Y manque**\n      pas de rejeu\n\n"
             "- [ ] une tâche ordinaire\n")
        s = specs_constat(t)
        self.assertEqual(len(s), 3)
        a = s[0]
        self.assertEqual(a.source, "service")
        self.assertEqual(a.motif, "^200$")
        self.assertFalse(a.sans)
        self.assertTrue(s[1].sans, "marqué mais sans moyen de rouvrir")
        self.assertIsNone(s[2], "sans `?constat` : rien à rejouer")

    def test_le_titre_se_separe_de_son_explication(self):
        t, c = titre_et_corps("**Une question ? oui / non**\noui → ceci\nnon → cela")
        self.assertEqual(t, "Une question ? oui / non")
        self.assertTrue(c.startswith("oui → ceci"))
        # Sans gras : on retombe sur la première phrase, jamais sur huit lignes.
        t, _ = titre_et_corps("Ceci est une phrase assez longue. Et voici la suite.")
        self.assertEqual(t, "Ceci est une phrase assez longue")

    def test_la_mecanique_ne_part_jamais_vers_le_telephone(self):
        # ATTENTION : en Rust, une continuation `\` mange l'indentation de la
        # ligne suivante — et l'indentation EST ce qui fait une ligne de
        # continuation du dialecte. Le premier essai de ce contrôle testait donc
        # un bloc d'une seule ligne, et passait pour la mauvaise raison. Ici les
        # chaînes sont écrites ligne à ligne, indentation comprise.
        t = ("- [ ] !haut @user ?constat **Une question ?**\n      oui → ceci\n"
             "      ↻ service :: curl -s https://x :: ^200$\n      non → cela\n")
        b = blocs_bruts(t)[0]
        self.assertNotIn("↻", b, "la ligne de rejeu porte une commande shell")
        self.assertTrue("!haut" not in b and "@user" not in b and "?constat" not in b)
        self.assertTrue("oui → ceci" in b and "non → cela" in b, "rendu : %r" % (b,))
        self.assertEqual(len(b.split("\n")), 3, "trois lignes, pas un pavé : %r" % (b,))

    def test_le_libelle_de_carnet_est_lisible_par_un_pair(self):
        b = "- [x] ~~!haut @user **Réparer l'inscription**~~\n      ↗ PO : c'est réparé."
        self.assertEqual(libelle_carnet(b), "Réparer l'inscription")
        # Un libellé barré qui se ferme à la ligne suivante se recolle.
        b = "- [x] ~~Un titre qui court\n      sur deux lignes~~\n      ↗ PO : voilà."
        self.assertEqual(libelle_carnet(b), "Un titre qui court sur deux lignes")

    def test_fnmatch_traverse_les_barres_comme_en_python(self):
        self.assertTrue(fnmatch("src/api/x.ts", "src/*"))
        self.assertTrue(fnmatch("src/api/x.ts", "*.ts"))
        self.assertTrue(fnmatch("a.py", "?.py"))
        self.assertFalse(fnmatch("src/api/x.ts", "lib/*"))
        self.assertFalse(fnmatch("x.rs", "*.ts"))

    def test_un_gabarit_de_consigne_ne_se_joue_pas(self):
        d = os.path.join(tempfile.mkdtemp(), "harnais-consigne-gabarit")
        os.makedirs(d)
        with open(os.path.join(d, "base.md"), "w", encoding="utf-8") as h:
            h.write("# Base\n\n## Consigne\n\nTenir la cible du projet.\n\n"
                    "    ↻ service :: <commande qui rend le nombre> :: <motif si la cible est tenue>\n")
        phrase, specs = consigne(d)
        self.assertIsNotNone(phrase)
        # LE CŒUR DU CAS : la ligne d'exemple a la forme exacte d'une
        # vérification. Retenue, elle échoue à chaque tour et se lit comme un
        # écart qui ne bouge pas — un acharnement sur une mesure inexistante.
        self.assertEqual(specs, [], "un gabarit a été retenu comme instrument")

        # TÉMOIN CONTRAIRE : une VRAIE ligne, elle, doit être retenue —
        # sinon on aurait éteint le dispositif au lieu de le corriger.
        with open(os.path.join(d, "base.md"), "w", encoding="utf-8") as h:
            h.write("# Base\n\n## Consigne\n\nTenir la cible du projet.\n\n"
                    "    ↻ service :: curl -s https://exemple/etat :: ^ok$\n")
        _, specs = consigne(d)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].cmd, "curl -s https://exemple/etat")
        shutil.rmtree(os.path.dirname(d), ignore_errors=True)

    def test_le_garde_nomme_le_fichier_qui_existe_dans_les_trois_formes(self):
        """LE GARDE NOMME LE FICHIER QUI EXISTE, dans les trois formes de mémoire.

        Défaut mesuré le 10/09/2026, et observé en session réelle : sur un projet
        en `brain/`, ce garde disait `.mind/todo.md`. L'agent a suivi, s'est
        heurté à un refus d'écriture, et a rendu la main sans rien noter — ce qui
        devait remonter au commanditaire perdu en silence.

        Le témoin porte les DEUX sens : le chemin juste est rendu pour chaque
        forme, ET aucune forme ne rend le chemin d'une autre. Sans le second, une
        fonction qui répondrait `.mind/todo.md` à tout passerait le premier cas."""
        r = "/d/projet"
        cas = [
            ("brain", r + "/brain/mind/todo.md", "brain/mind/todo.md"),
            ("en-place", r + "/.mind/todo.md", ".mind/todo.md"),
            ("déportée", r + "/memoire/.mind/todo.md", "memoire/.mind/todo.md"),
        ]
        for forme, todo, attendu in cas:
            rendu = ou_ecrire(r, todo)
            self.assertEqual(rendu, attendu, "forme %s : chemin mal nommé" % forme)
            # Le témoin négatif : ce que cette forme ne doit JAMAIS dire.
            for autre, _, chemin_autre in cas:
                if autre != forme:
                    self.assertNotEqual(rendu, chemin_autre,
                                        "forme %s : nomme le chemin de la forme %s" % (forme, autre))

        # Mémoire hors du dépôt : aucun chemin relatif ne serait ouvrable, on
        # rend donc l'absolu plutôt qu'un chemin joli et faux.
        dehors = "/ailleurs/memoire/.mind/todo.md"
        self.assertEqual(ou_ecrire(r, dehors), "/ailleurs/memoire/.mind/todo.md")


class EssaisCasLimites(unittest.TestCase):
    """Cas limites que la mutation d'un octet a laissés vivants. Les attendus du hook sont ceux
    du Rust 0.12.8, relevés en rejouant la même suite de tours sur les deux programmes."""

    RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def test_un_motif_garde_le_caractere_qui_suit_un_antislash(self):
        """`\\.` est recopié avec SON caractère, une seule fois : « ^a\\.b$ » ne devient pas « ^a\\.bb »."""
        self.assertEqual(attente._motif_rust(r"^a\.b$"), r"^a\.b\Z")
        self.assertEqual(attente._motif_rust(r"^a\\$"), r"^a\\\Z")
        self.assertEqual(attente._motif_rust(r"^\d\w$"), r"^\d\w\Z")
        self.assertEqual(attente._motif_rust(r"a\$"), r"a\$", "un `$` échappé reste un caractère")

    def test_un_constat_a_motif_echappe_tient_ou_tombe_comme_le_rust(self):
        """Rust 0.12.8 : `echo a.b` tient `^a\\.b$` ; `echo a.bb` et `echo a.b.` tombent."""
        motif = r"^a\.b$"
        self.assertEqual(attente.rejouer(attente.Spec("machine", "echo a.b", motif, False), 20)[0], attente.TIENT)
        self.assertEqual(attente.rejouer(attente.Spec("machine", "echo a.bb", motif, False), 20)[0], attente.TOMBE)
        self.assertEqual(attente.rejouer(attente.Spec("machine", "echo a.b.", motif, False), 20)[0], attente.TOMBE)

    def test_fnmatch_lit_les_jeux_de_caracteres_comme_python(self):
        """`[ab]` reconnaît a ou b ; `[!ab]` le reste ; `]` en tête de jeu est littéral ;
        un jeu jamais fermé est du texte. Même table que `fnmatch.fnmatchcase`."""
        import fnmatch as stdlib
        table = [("b", "[ab]", True), ("a", "[ab]", True), ("c", "[ab]", False),
                 ("ab", "[ab]", False), ("a]", "[ab]", False),
                 ("x", "[!ab]", True), ("a", "[!ab]", False),
                 ("]", "[]]", True), ("a", "[]a]", True), ("b", "[]a]", False),
                 ("a", "[a-c]", True), ("d", "[a-c]", False),
                 ("partage/b.txt", "partage/[ab].txt", True),
                 ("partage/c.txt", "partage/[ab].txt", False),
                 ("[ab", "[ab", True), ("x[]", "x[]", True), ("x]", "x[]", False)]
        for nom, motif, attendu in table:
            self.assertEqual(fnmatch(nom, motif), attendu, "%r contre %r" % (nom, motif))
            self.assertEqual(stdlib.fnmatchcase(nom, motif), attendu, "table fausse : %r %r" % (nom, motif))

    def test_une_zone_a_jeu_de_caracteres_mord_sur_le_commit_d_un_pair(self):
        """Une zone partagée écrite `partage/[ab].txt` voit un commit sur `b.txt`, pas sur `c.txt`."""
        b, d, _ = _banc("jeu")
        z = ["partage/[ab].txt"]
        _commit(d, "partage/b.txt", "1")
        self.assertEqual(tour_carnet(d, os.path.join(b, "agent.tete"), z, False), ["partage/b.txt"])
        _commit(d, "partage/c.txt", "1")
        self.assertEqual(tour_carnet(d, os.path.join(b, "agent.tete"), z, False), [], "hors du jeu")
        shutil.rmtree(os.path.dirname(b), ignore_errors=True)

    def lance_le_hook(self, projet, donnees, maison, session):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": maison,
               "CLAUDE_PLUGIN_DATA": donnees, "HARNAIS_RELECTURE_SIMULEE": "aucun",
               "LANG": "C.UTF-8"}
        env = dict(env_windows.essentiel(), **env)
        r = subprocess.run([sys.executable, os.path.join(self.RACINE, "py", "main.py"), "attente"],
                           cwd=projet, env=env, input=('{"session_id":"%s"}' % session).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return r.returncode, r.stderr.decode("utf-8", "replace")

    def monte_une_cible_tombee(self):
        """Un projet propre, d'une cible que sa mesure dément. Rend (projet, données, maison)."""
        base = tempfile.mkdtemp(prefix="harnais-b11-")
        self.addCleanup(shutil.rmtree, base, True)
        p = os.path.realpath(os.path.join(base, "projet"))
        maison, donnees = os.path.join(base, "maison"), os.path.join(base, "donnees")
        os.makedirs(os.path.join(p, "brain/fact"))
        os.makedirs(os.path.join(p, "brain/mind"))
        os.makedirs(maison)
        os.makedirs(donnees)
        _g(p, "init", "-q", "-b", "main")
        _ecris(p, "brain/fact/base.md",
               "cap: x\n\n## Consigne\nLe site répond 200.\n↻ machine :: echo NOPE :: ^200$\n")
        _ecris(p, "brain/mind/state.md", "---\nmaj: 2026-10-12\nsante: vert\njalon: x\n---\n")
        _ecris(p, "brain/mind/todo.md", "# todo\n\n- [ ] !moyen @dev  une tache\n")
        _g(p, "add", "-A")
        _g(p, "commit", "-qm", "init")
        self.tour_n = 0
        return p, donnees, maison

    def un_tour(self, p, donnees, maison):
        """Un tour de travail (le todo a bougé, à la seconde près) et le hook de fin de tour."""
        self.tour_n += 1
        todo = os.path.join(p, "brain/mind/todo.md")
        with open(todo, "a", encoding="utf-8") as h:
            h.write("- [ ] !bas @dev  t%d\n" % self.tour_n)
        os.utime(todo, (1800000000 + 10 * self.tour_n, 1800000000 + 10 * self.tour_n))
        return self.lance_le_hook(p, donnees, maison, "s%d" % self.tour_n)

    def fichier_cible(self, donnees):
        d = os.path.join(donnees, "attente")
        return os.path.join(d, [x for x in os.listdir(d) if x.endswith(".cible")][0])

    def test_la_cible_qui_ne_bouge_pas_est_denoncee_a_la_troisieme_mesure(self):
        """B11 : le compte des mesures sans progrès se relit dans le fichier d'état. Trois tours de
        travail avec une cible TOMBÉE : 1, 2, puis 3 et le renvoi (Rust 0.12.8 : rc 0, 0, 2 ;
        état `TOMBÉ · 12/10 · 3`)."""
        p, donnees, maison = self.monte_une_cible_tombee()
        codes = []
        for i in range(1, 4):
            rc, err = self.un_tour(p, donnees, maison)
            codes.append(rc)
            with open(self.fichier_cible(donnees), encoding="utf-8") as h:
                e = h.read().split("\t")
            self.assertEqual(e[0], "TOMBÉ")
            self.assertEqual(e[2], str(i), "mesure %d : le compte lu et réécrit" % i)
        self.assertEqual(codes, [0, 0, 2])
        self.assertIn("PAS BOUGÉ depuis 3 mesures", err)
        self.assertIn("Le site répond 200", err)

    def test_le_compte_se_lit_dans_le_troisieme_champ_meme_si_le_quatrieme_est_vide(self):
        """Un état « TOMBÉ · jour · 5 · (vide) · phrase » : le compte est celui du TROISIÈME champ
        (Rust 0.12.8 : on repart de 5, la mesure suivante est la sixième, rc 2). Lu dans le quatrième,
        le compte retomberait à 1 et la dénonciation ne viendrait jamais."""
        p, donnees, maison = self.monte_une_cible_tombee()
        rc, _ = self.un_tour(p, donnees, maison)
        self.assertEqual(rc, 0)
        f = self.fichier_cible(donnees)
        with open(f, "w", encoding="utf-8", newline="") as h:
            h.write("TOMBÉ\t12/10\t5\t\tLe site répond 200")
        rc, err = self.un_tour(p, donnees, maison)
        with open(f, encoding="utf-8") as h:
            e = h.read().split("\t")
        self.assertEqual(e[2], "6")
        self.assertEqual(rc, 2)
        self.assertIn("PAS BOUGÉ depuis 6 mesures", err)

    def test_un_compte_illisible_repart_de_un(self):
        """Témoins : un troisième champ qui n'est pas un nombre, ou un état sans phrase, ne
        prolongent rien (Rust 0.12.8 : compte 2 puis 1)."""
        p, donnees, maison = self.monte_une_cible_tombee()
        self.un_tour(p, donnees, maison)
        f = self.fichier_cible(donnees)
        for avant, attendu in (("TOMBÉ\t12/10\tx5\tLe site répond 200", "2"),
                               ("TOMBÉ\t12/10\t5\t", "1")):
            with open(f, "w", encoding="utf-8", newline="") as h:
                h.write(avant)
            rc, _ = self.un_tour(p, donnees, maison)
            with open(f, encoding="utf-8") as h:
                self.assertEqual(h.read().split("\t")[2], attendu, repr(avant))
            self.assertEqual(rc, 0)


class EssaisB17(unittest.TestCase):
    """B17 (12/10/2026) : le commanditaire n'a pas de terminal. Un message final qui lui demande de
    taper une commande (« ! … ») est refusé UNE fois ; un refus du mode auto est rappelé
    UNE fois en fin de tour, avec la consigne « passer du mode auto au mode edit »."""

    RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def setUp(self):
        base = tempfile.mkdtemp(prefix="harnais-b17-")
        self.addCleanup(shutil.rmtree, base, True)
        self.p = os.path.realpath(os.path.join(base, "projet"))
        self.maison, self.donnees = os.path.join(base, "maison"), os.path.join(base, "donnees")
        os.makedirs(os.path.join(self.p, "brain/fact"))
        os.makedirs(os.path.join(self.p, "brain/mind"))
        os.makedirs(self.maison)
        os.makedirs(self.donnees)
        _g(self.p, "init", "-q", "-b", "main")
        _ecris(self.p, "brain/fact/base.md", "---\ncap: x\n---\n\n## Nature\nx\n")
        _ecris(self.p, "brain/mind/state.md", "---\nmaj: 2026-10-12\nsante: vert\njalon: x\n---\n")
        _ecris(self.p, "brain/mind/todo.md", "# todo\n\n- [>] !moyen  en cours\n")
        _g(self.p, "add", "-A")
        _g(self.p, "commit", "-qm", "init")

    def appelle(self, sous, donnees):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": self.maison,
               "CLAUDE_PLUGIN_DATA": self.donnees, "HARNAIS_RELECTURE_SIMULEE": "aucun",
               "LANG": "C.UTF-8"}
        env = dict(env_windows.essentiel(), **env)
        r = subprocess.run([sys.executable, os.path.join(self.RACINE, "py", "main.py"), sous],
                           cwd=self.p, env=env, input=json.dumps(donnees).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return r.returncode, r.stderr.decode("utf-8", "replace")

    def fin_de_tour(self, message, session="b17", actif=False):
        return self.appelle("attente", {"session_id": session, "last_assistant_message": message,
                                        "stop_hook_active": actif})

    def test_une_commande_a_taper_est_refusee(self):
        rc, err = self.fin_de_tour("C'est fait. Pour finir, lance :\n\n```\n! python3 reglages.py\n```\n")
        self.assertEqual(rc, 2, err)
        self.assertIn("pas de terminal", err)
        self.assertIn("! python3 reglages.py", err)

    def test_le_meme_message_sans_la_ligne_passe(self):
        rc, err = self.fin_de_tour("C'est fait. Réponds « go » et je continue.")
        self.assertEqual((rc, err), (0, ""))
        rc, err = self.fin_de_tour("Ne jamais lui demander de taper une commande, `!` compris. Super ! Voilà.")
        self.assertEqual(rc, 0, "citer la règle n'est pas la violer : " + err)

    def test_un_code_en_ligne_commencant_par_un_point_d_exclamation_est_refuse(self):
        rc, err = self.fin_de_tour("Tape `! sh pose.sh` puis dis-moi.")
        self.assertEqual(rc, 2, err)

    def test_la_regle_tient_a_chaque_tour_meme_quand_le_todo_n_a_pas_bouge(self):
        """Trouvé par sabotage : à partir du 2e tour d'une session dont le todo n'a pas
        bougé, la fin de tour sortait tôt et ne lisait plus le message."""
        rc, err = self.fin_de_tour("Tout va bien.", session="b17t")
        self.assertEqual((rc, err), (0, ""))
        rc, err = self.fin_de_tour("Tape ceci :\n! python3 y.py", session="b17t")
        self.assertEqual(rc, 2, err)

    def test_un_refus_note_n_est_pas_rappele_au_tour_deja_renvoye(self):
        self.appelle("refus-auto", {"session_id": "b17d", "tool_name": "Bash", "reason": "x"})
        rc, _ = self.fin_de_tour("Autre chose.", session="b17d", actif=True)
        self.assertEqual(rc, 0, "pas de boucle")

    def test_la_garde_ne_redemande_pas_deux_fois(self):
        """Sans boucle : le tour déjà renvoyé (`stop_hook_active`) passe."""
        rc, _ = self.fin_de_tour("! python3 x.py", actif=True)
        self.assertEqual(rc, 0)

    def test_un_refus_du_mode_auto_est_rappele_une_fois(self):
        rc, _ = self.appelle("refus-auto", {"session_id": "b17r", "tool_name": "Edit",
                                           "reason": "[Self-Modification]"})
        self.assertEqual(rc, 0, "le hook de refus ne bloque jamais")
        rc, err = self.fin_de_tour("J'ai essayé, c'est refusé.", session="b17r")
        self.assertEqual(rc, 2, err)
        self.assertIn("mode edit", err)
        self.assertIn("Self-Modification", err)
        rc, err = self.fin_de_tour("J'ai essayé, c'est refusé.", session="b17r")
        self.assertEqual((rc, err), (0, ""), "le rappel est consommé : une seule fois")

    def test_un_message_qui_demande_deja_le_mode_edit_passe(self):
        self.appelle("refus-auto", {"session_id": "b17m", "tool_name": "Bash", "reason": "x"})
        rc, err = self.fin_de_tour("Peux-tu passer l'app du mode auto au mode edit ? Je réessaie ensuite.",
                                   session="b17m")
        self.assertEqual((rc, err), (0, ""))
        rc, _ = self.fin_de_tour("Autre tour.", session="b17m")
        self.assertEqual(rc, 0, "le refus a été consommé même quand le message était bon")

    def test_sans_refus_aucun_rappel(self):
        rc, err = self.fin_de_tour("Rien à signaler.", session="b17n")
        self.assertEqual((rc, err), (0, ""))

    def test_un_refus_est_propre_a_sa_session(self):
        self.appelle("refus-auto", {"session_id": "autre", "tool_name": "Bash", "reason": "x"})
        rc, _ = self.fin_de_tour("Rien.", session="b17p")
        self.assertEqual(rc, 0)



class Equipe(unittest.TestCase):
    """0.18.0 — l'agent se tient dans `agents/<nom>/` (la mémoire, qui ignore
    `code/`) : la fin de tour doit regarder SA copie du code."""

    def test_du_code_ecrit_sans_todo_mord_dans_la_copie_de_l_agent(self):
        import json
        import shutil
        import subprocess
        import tempfile
        sys.path.insert(0, os.path.dirname(__file__))
        import banc_equipe
        d = os.path.realpath(tempfile.mkdtemp(prefix="attente-v3-"))
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "x"))
        x = banc_equipe.construis(os.path.join(d, "x"))
        po = os.path.join(x, "agents", "PO")
        with open(os.path.join(po, "code", "apps", "neuf.ts"), "w") as h:
            h.write("export const a = 1\n")
        os.utime(os.path.join(po, "todo.md"), (1e9, 1e9))
        main = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "py", "main.py"))

        def fin_de_tour():
            e = dict(os.environ, CLAUDE_PROJECT_DIR=po, CLAUDE_PLUGIN_DATA=os.path.join(d, "data"),
                     HOME=d, HARNAIS_RELECTURE_SIMULEE="1")
            e.pop("CLAUDE_PLUGIN_ROOT", None)
            e.pop("CLAUDE_CODE_ENTRYPOINT", None)
            r = subprocess.run([sys.executable, main, "attente"], cwd=po, input=json.dumps({"session_id": "s"}).encode(),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e)
            return r.returncode, r.stderr.decode("utf-8", "replace")
        code, err = fin_de_tour()
        self.assertEqual(code, 2, err)
        self.assertIn("neuf.ts", err)
        self.assertIn("`todo.md`", err, "nommé depuis le dossier de l'agent")
        # TÉMOIN : le todo à jour, le tour finit.
        os.utime(os.path.join(po, "todo.md"), None)
        self.assertEqual(fin_de_tour()[0], 0)


class EssaisMotif(unittest.TestCase):
    """28/10/2026 : le commanditaire répondait « 1 » à presque tout. Une question
    qui ne nomme pas son motif, dans une liste fermée, lui est refusée."""

    # Le décor de B17, sans rejouer ses essais.
    RACINE = EssaisB17.RACINE
    setUp, appelle, fin_de_tour = EssaisB17.setUp, EssaisB17.appelle, EssaisB17.fin_de_tour

    QUESTION = ("- [ ] !haut @user **Je range les restes de l'ancien outil aux archives ? 1 oui / 2 non**\n"
                "      1 → je déplace, rien n'est supprimé.\n"
                "      2 → rien ne bouge.\n")
    FIN = "      fini quand → le dossier de l'ancien outil est vide.\n"

    def tour_avec(self, corps_question, message):
        # Première rencontre : l'arriéré est amnistié, rien ne mord.
        rc, err = self.fin_de_tour("Rien.", session="m0")
        self.assertEqual(rc, 0, err)
        todo = os.path.join(self.p, "brain/mind/todo.md")
        _ecris(self.p, "brain/mind/todo.md", "# todo\n\n- [>] !moyen  en cours\n" + corps_question)
        # La garde ne relit le todo que si sa date a bougé, à la seconde près.
        t = os.path.getmtime(todo) + 5
        os.utime(todo, (t, t))
        return self.fin_de_tour(message, session="m1")

    def test_sans_motif_la_question_est_refusee(self):
        rc, err = self.tour_avec(self.QUESTION + self.FIN, "Je range les restes de l'ancien outil aux archives ? 1 oui / 2 non")
        self.assertEqual(rc, 2, err)
        self.assertIn("ne disent pas pourquoi", err)
        self.assertIn("Décide toi-même", err)

    def test_avec_motif_elle_passe(self):
        """TÉMOIN : la même question, motif compris, posée dans le message."""
        rc, err = self.tour_avec(self.QUESTION + "      motif → périmètre\n" + self.FIN,
                                 "Je range les restes de l'ancien outil aux archives ? 1 oui / 2 non")
        self.assertEqual((rc, err), (0, ""))

    def test_un_constat_reste_un_defaut_de_forme(self):
        rc, err = self.tour_avec("- [ ] !haut @user Les restes de l'ancien outil sont toujours là.\n", "Point fait.")
        self.assertEqual(rc, 2, err)
        self.assertIn("CONSTATS", err)


if __name__ == "__main__":
    unittest.main()
