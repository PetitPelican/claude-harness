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


if __name__ == "__main__":
    unittest.main()
