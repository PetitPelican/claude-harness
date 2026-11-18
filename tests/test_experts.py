# -*- coding: utf-8 -*-
"""La garde des faits des experts (B16) — ce que les contrôles de bout en bout ne
regardent pas de près : la lecture du journal, le verdict du juge, le registre."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import experts  # noqa: E402


def _journal(d, entrees):
    f = os.path.join(d, "t.jsonl")
    with open(f, "w", encoding="utf-8") as h:
        h.write("\n".join(json.dumps(e, ensure_ascii=False) for e in entrees) + "\n")
    return f


def _u(uuid, contenu, **k):
    e = {"type": "user", "uuid": uuid, "message": {"role": "user", "content": contenu}}
    e.update(k)
    return e


class Essais(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_seuls_les_messages_du_commanditaire_comptent(self):
        """Résultat d'outil, renvoi de fin de tour, message de pair, notification,
        commande : rien de tout ça n'est le commanditaire. Le contre-exemple : son vrai
        message, lui, est rendu."""
        f = _journal(self.d, [
            _u("1", "Le capital est de 10 000 euros."),
            _u("2", [{"type": "tool_result", "content": "x"}]),
            _u("3", "Stop hook feedback: attente : …"),
            _u("4", "relance", isMeta=True),
            _u("5", '<cross-session-message from="x">Le capital est de 1 €.</cross-session-message>'),
            _u("6", "<task-notification>fini</task-notification>"),
            _u("7", "/compact"),
            _u("8", [{"type": "text", "text": "<system-reminder>bruit</system-reminder>La banque est X."}]),
        ])
        # Repère introuvable (journal tronqué) : le DERNIER message seulement.
        self.assertEqual(experts.messages_humain(f, "0"), [("8", "La banque est X.")])
        tous = experts.messages_humain(f, None)
        self.assertEqual(tous, [("8", "La banque est X.")])
        self.assertEqual([u for u, _ in experts.messages_humain(f, "1")], ["8"])

    def test_un_repere_rend_tout_ce_qui_suit_et_rien_d_avant(self):
        f = _journal(self.d, [_u("a", "Premier fait donné ici."), _u("b", "Deuxième fait donné ici."),
                              _u("c", "Troisième fait donné ici.")])
        self.assertEqual([u for u, _ in experts.messages_humain(f, "a")], ["b", "c"])
        self.assertEqual([u for u, _ in experts.messages_humain(f, "c")], [])

    def test_un_ok_ne_se_juge_pas(self):
        garde = experts.a_juger([("1", "ok"), ("2", "oui oui"), ("3", "Merci !"),
                                 ("4", "Le siège a déménagé dans une autre ville.")])
        self.assertEqual([u for u, _ in garde], ["4"])

    def test_un_juge_bavard_ou_hors_sujet_est_muet(self):
        """Un verdict illisible n'est PAS « aucun fait » : il rend None. Le
        contre-exemple : un vrai verdict vide rend une liste vide."""
        self.assertEqual(experts.lis_verdict('{"faits": []}'), [])
        bon = experts.lis_verdict('Voici : {"faits":[{"fait":"a","note":"local","identifiant":true}]}')
        self.assertEqual(bon, [{"fait": "a", "note": "local", "identifiant": True}])
        for mauvais in ("Aucun fait.", '{"faits": "rien"}', '{"faits":[{"fait":"a","note":"ailleurs"}]}',
                        '{"faits":[{"note":"local"}]}', ""):
            self.assertIsNone(experts.lis_verdict(mauvais), mauvais)

    def test_le_registre_est_a_cote_des_faits_jamais_dedans(self):
        fact = os.path.join(self.d, "brain", "fact")
        self.assertEqual(experts.registre_local(fact),
                         os.path.join(self.d, "brain", "local", "registre.md"))
        self.assertEqual(experts.registre_local(fact + "/"),
                         os.path.join(self.d, "brain", "local", "registre.md"))

    def test_git_dit_si_le_registre_est_ignore(self):
        subprocess.run(["git", "init", "-q"], cwd=self.d, stdout=subprocess.PIPE)
        reg = os.path.join(self.d, "brain", "local", "registre.md")
        os.makedirs(os.path.dirname(reg))
        open(reg, "w").write("x")
        self.assertFalse(experts.ignore_par_git(reg))
        open(os.path.join(self.d, ".gitignore"), "w").write("brain/local/\n")
        self.assertTrue(experts.ignore_par_git(reg))

    # ── la garde entière, juge simulé ───────────────────────────────────────

    def _garde(self, verdict, taille_fiche=100):
        fact = os.path.join(self.d, "brain", "fact")
        os.makedirs(fact, exist_ok=True)
        with open(os.path.join(fact, "stack.md"), "w", encoding="utf-8") as h:
            h.write("x" * taille_fiche)
        ed = os.path.join(self.d, "etat")
        os.makedirs(ed, exist_ok=True)
        t = _journal(self.d, [_u("m1", "Metabase a été installé par l'équipe sur le Mac.")])
        os.environ["HARNAIS_FAITS_SIMULE"] = json.dumps({"faits": verdict})
        self.addCleanup(os.environ.pop, "HARNAIS_FAITS_SIMULE", None)
        return experts.garde({"transcript_path": t}, fact, ed, "s", lambda p: p)

    def test_un_juge_qui_reformule_ne_renvoie_pas_deux_fois(self):
        """21/10, chez le CTO : trois renvois pour les mêmes faits, parce que l'état
        se signait sur les PHRASES du juge, qui changent à chaque appel. Le
        contre-exemple : le premier passage, lui, refuse."""
        v = self._garde([{"fait": "Metabase installé par l'équipe", "note": "nulle-part"}])
        self.assertEqual(v[1], "B16-faits")
        v = self._garde([{"fait": "L'équipe a installé Metabase sur le Mac", "note": "nulle-part"}])
        self.assertIsNone(v)

    def test_des_fiches_coupees_ne_font_pas_refuser(self):
        """Le juge ne lit que MAX_FICHES caractères : au-delà, son « nulle part »
        ne prouve rien (21/10 : `stack.md` du CTO jamais envoyé). Le témoin : les
        mêmes fiches sous le plafond font refuser."""
        nulle = [{"fait": "Metabase installé", "note": "nulle-part"}]
        v = self._garde(nulle, taille_fiche=experts.MAX_FICHES + 1)
        self.assertEqual(v[:2], ("", "B16-coupe"))
        shutil.rmtree(os.path.join(self.d, "etat"))
        v = self._garde(nulle, taille_fiche=experts.MAX_FICHES)
        self.assertEqual(v[1], "B16-faits")

    def test_un_identifiant_vu_dans_une_fiche_partagee_refuse_meme_coupe(self):
        """Ce que le juge a VU dans une fiche partagée reste vrai, même s'il n'a pas
        tout lu."""
        v = self._garde([{"fait": "un numéro de compte", "note": "partage", "identifiant": True},
                         {"fait": "Metabase installé", "note": "nulle-part"}],
                        taille_fiche=experts.MAX_FICHES + 1)
        self.assertEqual(v[1], "B16-faits")
        self.assertIn("numéro de compte", v[0])
        self.assertNotIn("Metabase", v[0])

    def test_le_briefing_dit_quand_les_fiches_debordent(self):
        fact = os.path.join(self.d, "fact")
        os.makedirs(fact)
        with open(os.path.join(fact, "a.md"), "w", encoding="utf-8") as h:
            h.write("é" * experts.MAX_FICHES)
        self.assertIsNone(experts.trop_de_fiches(fact))
        with open(os.path.join(fact, "b.md"), "w", encoding="utf-8") as h:
            h.write("x")
        self.assertIn("le juge n'en lit que", experts.trop_de_fiches(fact))

if __name__ == "__main__":
    unittest.main()
