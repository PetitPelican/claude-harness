# -*- coding: utf-8 -*-
"""Port des `#[test]` de `harnais/src/usage.rs` (5 tests)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))

import usage
from usage import REGISTRE_MAX, chemin_lu, est_une_note, note_l_usage


def _lire(f):
    with open(f, encoding="utf-8") as h:
        return json.loads(h.read())


class Essais(unittest.TestCase):

    def test_reconnait_une_note_et_rien_d_autre(self):
        base = "/Users/u/.claude/projects/-a-b/memory/"
        self.assertTrue(est_une_note(base + "une-note.md"))
        # L'INDEX N'EST PAS UNE NOTE : le lire ne prouve rien sur les notes.
        self.assertFalse(est_une_note(base + "MEMORY.md"))
        self.assertFalse(est_une_note(base + "memory.md"))
        # Hors mémoire, ou pas du markdown : le hook ne doit pas s'y intéresser.
        self.assertFalse(est_une_note("/Users/u/Agentic/CTO/README.md"))
        self.assertFalse(est_une_note(base + "note.txt"))
        self.assertFalse(est_une_note("/Users/u/.claude/projects/-a-b/notes/x.md"))

    def test_lit_le_chemin_des_deux_cotes(self):
        self.assertEqual(chemin_lu({"tool_input": {"file_path": "/a"}}), "/a")
        self.assertEqual(chemin_lu({"tool_response": {"filePath": "/b"}}), "/b")
        # tool_response gagne : c'est l'ordre de la version Python.
        self.assertEqual(chemin_lu({"tool_input": {"file_path": "/a"},
                                    "tool_response": {"file_path": "/b"}}), "/b")
        self.assertIsNone(chemin_lu({}))

    def test_compte_et_registre(self):
        d = tempfile.mkdtemp(prefix="essai-usage-")
        try:
            f = os.path.join(d, ".usage.json")
            self.assertTrue(note_l_usage(f, "une-note", "S1", "2026-09-09"))
            self.assertTrue(note_l_usage(f, "une-note", "S1", "2026-09-09"))
            self.assertTrue(note_l_usage(f, "autre", "S1", "2026-09-09"))
            v = _lire(f)
            self.assertEqual(v["une-note"]["n"], 2, "le compte doit s'incrémenter")
            self.assertEqual(v["une-note"]["vu"], "2026-09-09")
            enc = v["_encours"]["S1"]
            self.assertEqual(len(enc), 2, "sans doublon, deux notes distinctes")

            # TÉMOIN NÉGATIF : sans session, pas de registre — mais le compte, si.
            f2 = os.path.join(d, ".usage2.json")
            self.assertTrue(note_l_usage(f2, "x", "", "2026-09-09"))
            v2 = _lire(f2)
            self.assertEqual(v2["x"]["n"], 1)
            self.assertNotIn("_encours", v2, "aucun registre sans session")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_le_registre_est_plafonne(self):
        d = tempfile.mkdtemp(prefix="essai-plafond-")
        try:
            f = os.path.join(d, ".usage.json")
            for i in range(REGISTRE_MAX + 10):
                note_l_usage(f, "n%d" % i, "S", "2026-09-09")
            v = _lire(f)
            self.assertEqual(len(v["_encours"]["S"]), REGISTRE_MAX)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_entree_illisible_ne_leve_rien(self):
        usage.main("pas du json du tout")
        usage.main("")
        usage.main("{}")


class CasLimites(unittest.TestCase):
    """Cas limites vérifiés contre le Rust 0.12.8 (même `.usage.json` octet pour octet)."""

    def test_le_compte_boucle_au_plus_grand_i64(self):
        """`i64::MAX + 1` rend `i64::MIN` (mode release) ; un cran avant, le compte monte
        normalement."""
        self.assertEqual(usage._plus_un(2 ** 63 - 2), 2 ** 63 - 1)
        self.assertEqual(usage._plus_un(2 ** 63 - 1), -(2 ** 63))
        d = tempfile.mkdtemp(prefix="essai-usage-borne-")
        self.addCleanup(shutil.rmtree, d, True)
        f = os.path.join(d, ".usage.json")
        with open(f, "w", encoding="utf-8") as h:
            h.write('{"note":{"n":9223372036854775807,"vu":"2020-01-01"},'
                    '"autre":{"n":9223372036854775806}}')
        self.assertTrue(note_l_usage(f, "note", "", "2026-10-12"))
        self.assertTrue(note_l_usage(f, "autre", "", "2026-10-12"))
        v = _lire(f)
        self.assertEqual(v["note"]["n"], -9223372036854775808)
        self.assertEqual(v["autre"]["n"], 9223372036854775807)

    def test_le_tilde_se_deplie_vers_le_dossier_personnel(self):
        """`~/x` devient `<maison>/x` : tous les caractères après « ~/ » sont gardés."""
        h = tempfile.mkdtemp(prefix="essai-maison-")
        self.addCleanup(shutil.rmtree, h, True)
        avec = mock.patch.dict(os.environ, {"HOME": h})
        with avec:
            self.assertEqual(usage.deplie("~/.claude/a.md"), os.path.join(h, ".claude/a.md"))
            self.assertEqual(usage.deplie("~/x"), os.path.join(h, "x"))
            self.assertEqual(usage.deplie("$HOME/.claude/a.md"), h + "/.claude/a.md")
            self.assertEqual(usage.deplie("~autre/x"), "~autre/x", "seul `~/` est déplié")

    def test_une_note_citee_par_un_tilde_est_comptee_dans_son_dossier(self):
        """`cat ~/.claude/projects/-x/memory/note.md` : le compte est écrit à côté de la
        note, dans le dossier retrouvé à travers le `~`."""
        h = tempfile.mkdtemp(prefix="essai-maison-")
        self.addCleanup(shutil.rmtree, h, True)
        m = os.path.join(h, ".claude", "projects", "-x", "memory")
        os.makedirs(m)
        with open(os.path.join(m, "note.md"), "w", encoding="utf-8") as fh:
            fh.write("hi\n")
        entree = json.dumps({"tool_name": "Bash", "session_id": "",
                             "tool_input": {"command": "cat ~/.claude/projects/-x/memory/note.md"}})
        with mock.patch.dict(os.environ, {"HOME": h}):
            usage.main(entree)
        f = os.path.join(m, ".usage.json")
        self.assertTrue(os.path.exists(f), "le compte n'a pas été écrit")
        self.assertEqual(_lire(f)["note"]["n"], 1)


if __name__ == "__main__":
    unittest.main()
