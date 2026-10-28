# -*- coding: utf-8 -*-
"""La version chargée par chaque agent est notée à l'ouverture et se relit
(décision du 14/10/2026 : endormir chaque nuit pour prendre la dernière — vérifiable)."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import versions  # noqa: E402


class Versions(unittest.TestCase):

    def setUp(self):
        self.d = os.path.realpath(tempfile.mkdtemp(prefix="versions-"))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.maison = os.path.join(self.d, "maison")
        self.cache = os.path.join(self.maison, ".claude", "plugins", "cache", "atelier", "harnais")
        for v in ("0.9.0", "0.18.1", "0.18.10"):
            os.makedirs(os.path.join(self.cache, v))
        self.agent = os.path.join(self.d, "Projet PO")
        os.makedirs(self.agent)
        p = mock.patch.dict(os.environ, {"HOME": self.maison, "CLAUDE_PLUGIN_DATA": os.path.join(self.d, "data"),
                                         "CLAUDE_PROJECT_DIR": self.agent})
        p.start()
        self.addCleanup(p.stop)

    def lance(self, *a):
        out = io.StringIO()
        with redirect_stdout(out):
            code = versions.main(list(a))
        return code, out.getvalue()

    def test_derniere_compare_en_nombres(self):
        self.assertEqual(versions.derniere_installee(), "0.18.10")

    def test_note_puis_relit_et_juge(self):
        with mock.patch.object(versions, "identite", lambda: "0.18.1 abc"):
            versions.note({"session_id": "s1"})
        code, out = self.lance()
        self.assertEqual(code, 1, out)
        self.assertIn("EN RETARD", out)
        self.assertIn(self.agent, out)
        with mock.patch.object(versions, "identite", lambda: "0.18.10 abc"):
            versions.note({"session_id": "s2"})
        code, out = self.lance("--json")
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertEqual([x["version"] for x in d["sessions"]], ["0.18.10"], "une ligne par dossier, la dernière")

    def test_temoin_rien_note_ne_passe_pas_pour_a_jour(self):
        code, out = self.lance()
        self.assertIn("aucune session notée", out)

    def test_une_trace_ne_coute_jamais_un_tour(self):
        with mock.patch.object(versions, "identite", side_effect=RuntimeError("x")):
            versions.note({})   # ne lève pas

    def test_le_briefing_note_a_l_ouverture(self):
        import briefing
        appels = []
        with mock.patch.object(versions, "note", lambda c: appels.append(c)):
            briefing.main(json.dumps({"hook_event_name": "SessionStart", "session_id": "z"}))
            briefing.main(json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "z", "prompt": "x"}))
        self.assertEqual([c["session_id"] for c in appels], ["z"], "à l'ouverture seulement")


if __name__ == "__main__":
    unittest.main()
