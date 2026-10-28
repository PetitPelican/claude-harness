# -*- coding: utf-8 -*-
"""Port des `#[test]` de `harnais/src/bascule.rs` (3 tests, mêmes cas, mêmes assertions)."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))

import bascule  # noqa: E402
from bascule import nature, trie, declare, Nature, PAQUET  # noqa: E402


class Bascule(unittest.TestCase):
    def test_la_nature_se_lit_sur_le_nom_exact(self):
        self.assertEqual(nature('exec python3 "$HOME/.claude/hooks/briefing.py"'),
                         Nature.Harnais("briefing.py"))
        self.assertEqual(nature("… ${CLAUDE_PLUGIN_ROOT}/bin/harnais … briefing"), Nature.Paquet)
        # CE QUE LA SOUS-CHAÎNE AURAIT EMPORTÉ. `journal-metier.py` contient
        # « journal » ; un test sur `contains` l'aurait retiré au projet.
        self.assertEqual(nature('exec python3 "…/hooks/journal-metier.py"'),
                         Nature.Projet("journal-metier.py"))
        self.assertEqual(nature('exec python3 "…/hooks/guard-base-prod.py"'),
                         Nature.Projet("guard-base-prod.py"))
        # ET L'INCONNU RESTE AU PROJET — le doute se tranche du côté qui garde.
        self.assertEqual(nature("node ./scripts/verifie.js"),
                         Nature.Projet("node ./scripts/verifie.js"))

    def test_le_tri_garde_les_gardes_et_vide_les_coquilles(self):
        d = json.loads("""{
          "hooks": {
            "PreToolUse": [
              {"matcher":"Bash","hooks":[{"command":"exec python3 x/mind-guard.py"}]},
              {"matcher":"Bash","hooks":[{"command":"exec python3 x/guard-base-prod.py"}]}
            ],
            "Stop": [{"hooks":[{"command":"exec python3 x/attente.py"}]}]
          }
        }""")
        b = trie(d)
        self.assertEqual(len(b.gardes), 1, "le garde du projet doit survivre")
        self.assertEqual(len(b.retires), 2, "les deux du harnais doivent partir")
        # `Stop` n'avait que du harnais : l'événement disparaît, pas de coquille.
        h = d["hooks"]
        self.assertNotIn("Stop", h)
        self.assertEqual(len(h["PreToolUse"]), 1)

    def test_un_agent_sans_garde_propre_perd_son_bloc_entier(self):
        d = json.loads("""{
          "permissions": {"defaultMode":"bypassPermissions"},
          "hooks": {"Stop":[{"hooks":[{"command":"exec python3 x/attente.py"}]}]}
        }""")
        b = trie(d)
        self.assertEqual(b.gardes, [])
        self.assertNotIn("hooks", d, "plus rien à garder : la clé disparaît")
        # ET `permissions` N'A PAS BOUGÉ — c'est la moitié du contrat.
        self.assertIn("permissions", d)
        declare(d)
        self.assertIs(d["enabledPlugins"][PAQUET], True)


class Ecriture(unittest.TestCase):
    """Ce que `--apply` écrit sur le disque, octet pour octet (comparé au Rust 0.12.8)."""

    def applique(self, brut):
        d = tempfile.mkdtemp(prefix="bascule-")
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, ".claude"))
        f = os.path.join(d, ".claude", "settings.json")
        with open(f, "w", encoding="utf-8") as h:
            h.write(brut)
        with contextlib.redirect_stdout(io.StringIO()):
            bascule.main([d, "--apply"])
        with open(f, encoding="utf-8") as h:
            return h.read()

    def test_le_reglage_reecrit_s_indente_de_deux_espaces(self):
        """Le fichier réécrit est indenté de DEUX espaces et finit par un saut de ligne."""
        t = self.applique('{"permissions":{"deny":["Bash(rm*)"]},"hooks":'
                          '{"Stop":[{"hooks":[{"command":"exec python3 x/attente.py"}]}]}}')
        self.assertEqual(t, '{\n  "permissions": {\n    "deny": [\n      "Bash(rm*)"\n    ]\n  },\n'
                            '  "extraKnownMarketplaces": {\n    "atelier": {\n      "source": {\n'
                            '        "source": "github",\n        "repo": "PetitPelican/claude-harness"\n'
                            '      }\n    }\n  },\n  "enabledPlugins": {\n    "harnais@atelier": true\n  }\n}\n')

    def test_moins_zero_reste_un_flottant_et_les_autres_entiers_restent_entiers(self):
        """serde_json lit `-0` comme -0.0 et l'écrit « -0.0 » ; un entier ordinaire reste entier
        (Rust 0.12.8 : `"n": -0.0`, `"k": 5`, `[0, -0.0, 12]`)."""
        t = self.applique('{"n": -0, "k": 5, "z": [0, -0, 12], "hooks":'
                          '{"Stop":[{"hooks":[{"command":"exec python3 x/attente.py"}]}]}}')
        r = json.loads(t)
        self.assertIn('"n": -0.0,', t)
        self.assertIn('"k": 5,', t)
        self.assertIn("    0,\n    -0.0,\n    12\n", t)
        self.assertEqual(r["k"], 5)
        self.assertIsInstance(r["k"], int)


if __name__ == "__main__":
    unittest.main()
