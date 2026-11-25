# -*- coding: utf-8 -*-
"""`harnais aligne` (0.19.19) : les agents d'un même dépôt que le CLI laisse sur
l'ancienne version reçoivent, dans le registre, la version du plus récent."""
import glob
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import aligne  # noqa: E402

LANCEUR = os.path.join(os.path.dirname(__file__), "..", "bin", "harnais")


class Atelier(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.t = t.name
        self.equipe = os.path.join(self.t, "Equipe")
        self.seul = os.path.join(self.t, "Seul")
        for d in ("agents/OPS", "agents/PO", "agents/QA"):
            os.makedirs(os.path.join(self.equipe, d))
        os.makedirs(self.seul)
        for r in (self.equipe, self.seul):
            subprocess.run(["git", "init", "-q", r], check=True)
        self.neuf = os.path.join(self.t, "cache", "0.2.0")
        os.makedirs(self.neuf)

        def e(p, v, scope="project"):
            d = {"scope": scope, "version": v, "gitCommitSha": "sha-" + v,
                 "installPath": os.path.join(self.t, "cache", v)}
            if p:
                d["projectPath"] = p
            return d
        self.reg = os.path.join(self.t, "installed_plugins.json")
        with open(self.reg, "w", encoding="utf-8") as h:
            json.dump({"version": 2, "plugins": {"harnais@atelier": [
                e(None, "0.1.0", "user"),
                e(os.path.join(self.equipe, "agents", "OPS"), "0.2.0"),
                e(os.path.join(self.equipe, "agents", "PO"), "0.1.0"),
                e(os.path.join(self.equipe, "agents", "QA"), "0.1.0"),
                e(self.seul, "0.1.0"),
            ], "autre@x": [{"scope": "project", "projectPath": self.seul}]}}, h)
        p = mock.patch.dict(os.environ, {"HARNAIS_INSCRIPTIONS": self.reg})
        p.start()
        self.addCleanup(p.stop)

    def lance(self, *args):
        o = io.StringIO()
        with redirect_stdout(o):
            code = aligne.main(list(args))
        return code, o.getvalue()

    def versions(self):
        with open(self.reg, encoding="utf-8") as h:
            v = json.load(h)["plugins"]["harnais@atelier"]
        return {os.path.basename(e.get("projectPath", "user")): e["version"] for e in v}


class Aligne(Atelier):
    def test_a_blanc_rien_n_est_ecrit(self):
        avant = open(self.reg, encoding="utf-8").read()
        code, sortie = self.lance()
        self.assertEqual(code, 0)
        self.assertIn("PO", sortie)
        self.assertIn("QA", sortie)
        self.assertNotIn("Seul", sortie)        # seul dans son dépôt : rien à quoi l'aligner
        self.assertEqual(open(self.reg, encoding="utf-8").read(), avant)

    def test_go_aligne_le_depot_et_garde_une_copie(self):
        code, _ = self.lance("--go")
        self.assertEqual(code, 0)
        self.assertEqual(self.versions(), {"user": "0.1.0", "OPS": "0.2.0", "PO": "0.2.0",
                                           "QA": "0.2.0", "Seul": "0.1.0"})
        with open(self.reg, encoding="utf-8") as h:
            po = json.load(h)["plugins"]["harnais@atelier"][2]
        self.assertEqual((po["installPath"], po["gitCommitSha"]), (self.neuf, "sha-0.2.0"))
        self.assertEqual(len(glob.glob(self.reg + ".avant-aligne-*")), 1)

    def test_seulement_les_dossiers_nommes(self):
        self.lance(os.path.join(self.equipe, "agents", "PO"), "--go")
        self.assertEqual(self.versions()["PO"], "0.2.0")
        self.assertEqual(self.versions()["QA"], "0.1.0")

    def test_code_absent_du_cache(self):
        os.rmdir(self.neuf)
        code, sortie = self.lance("--go")
        self.assertIn("pas en cache", sortie)
        self.assertEqual(self.versions()["PO"], "0.1.0")

    def test_dossier_sans_inscription(self):
        code, sortie = self.lance(os.path.join(self.t, "Ailleurs"))
        self.assertIn("aucune inscription", sortie)

    def test_rien_a_aligner(self):
        self.lance("--go")
        code, sortie = self.lance("--go")
        self.assertEqual((code, "rien à aligner" in sortie), (0, True))

    def test_versions_comparees_en_nombres(self):
        self.assertGreater(aligne._cle("0.19.10"), aligne._cle("0.19.9"))


class Lanceur(Atelier):
    def test_par_le_lanceur(self):
        o = subprocess.run(["sh", LANCEUR, "aligne"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           env=dict(os.environ, HARNAIS_INSCRIPTIONS=self.reg), timeout=60)
        self.assertEqual(o.returncode, 0, o.stderr)
        self.assertIn("à blanc", o.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
