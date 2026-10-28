# -*- coding: utf-8 -*-
"""Le garde du coffre (0.19.1) : chaque forme qui affiche est refusée, et la même
forme jetée, capturée ou réduite aux noms passe — l'une est le témoin de l'autre."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import coffre  # noqa: E402

# (refusée, la même qui passe)
PAIRES = [
    # Doppler — mesuré sur 3.77.0 contre un faux coffre
    ("doppler secrets set CLE=x", "doppler secrets set CLE=x --silent"),
    ("doppler secrets set CLE=x", "doppler secrets set CLE=x > /dev/null"),
    ("doppler secrets set CLE=x --json", "doppler secrets set CLE=x --json >/dev/null 2>&1"),
    ("doppler secrets delete CLE --yes", "doppler secrets delete CLE --yes --silent"),
    ("doppler secrets upload .env.local", "doppler secrets upload .env.local --silent"),
    ("doppler secrets", "doppler secrets --only-names"),
    ("doppler secrets -p projet -c prd", "doppler secrets -p projet -c prd --only-names"),
    ("doppler secrets --json | jq .", "doppler secrets --json | jq keys"),
    ("doppler secrets get CLE --plain", "X=$(doppler secrets get CLE --plain)"),
    ("doppler secrets get CLE --plain", 'export X="$(doppler secrets get CLE --plain)"'),
    ("doppler secrets get CLE --silent", "doppler secrets get CLE --plain > .env.local"),
    ("doppler secrets download --no-file", "doppler secrets download --no-file > .env.local"),
    ("doppler secrets substitute gabarit", "doppler secrets substitute gabarit --output f"),
    ("doppler run -- env", "doppler run -- env | grep -oE '^[A-Z_][A-Z0-9_]*='"),
    ("doppler run -- printenv CLE", "doppler run -- printenv CLE > /dev/null"),
    ("doppler run --command env", "doppler run --command 'npm test'"),
    # les formes détournées
    ("cd x && doppler secrets set A=1", "cd x && doppler secrets set A=1 --silent"),
    ("echo ok; doppler secrets", "echo ok; doppler secrets --only-names"),
    ("env DOPPLER_TOKEN=t doppler secrets", "env DOPPLER_TOKEN=t doppler secrets --only-names"),
    ("/opt/homebrew/bin/doppler secrets", "/opt/homebrew/bin/doppler secrets --only-names"),
    ("bash -c 'doppler secrets'", "bash -c 'doppler secrets --only-names'"),
    ("sh -c \"doppler secrets set A=1\"", "sh -c \"doppler secrets set A=1\" > /dev/null"),
    ("doppler secrets set A=1 | tail -1", "doppler secrets set A=1 | wc -l"),
    ("doppler secrets set A=1 > /dev/stdout", "doppler secrets set A=1 > /tmp/x"),
    ("doppler secrets set A=1 2>/dev/null", "doppler secrets set A=1 &>/dev/null"),
    ("doppler \\\n  secrets", "doppler \\\n  secrets --only-names"),
    ("ls\ndoppler secrets", "ls\ndoppler secrets --only-names"),
    # fichiers de secrets
    ("cat .env.local", "grep -oE '^[A-Z_][A-Z0-9_]*=' .env.local"),
    ("cat apps/web/.env.local", "cat apps/web/.env.local | grep -oE '^[A-Z_][A-Z0-9_]*='"),
    ("head -5 .env", "wc -l .env"),
    ("cat .envrc", "grep -c export .envrc"),
    ("grep STRIPE .env.local", "grep -c STRIPE .env.local"),
    ("cat ~/.secrets/coffre-lecture", "ls -la ~/.secrets/"),
    ("cat .mcp.json", "jq '.mcpServers | keys' .mcp.json"),
    ("sed -n 1,5p .env.production", "grep -q STRIPE .env.production"),
    # les autres outils
    ("supabase status", "supabase status -o json | jq keys"),
    # une valeur sur plusieurs lignes traverse `cut` et `sed` : ils ne réduisent pas
    ("cut -d= -f1 .env.local", "grep -c = .env.local"),
    ("cat .env.local | sed 's/=.*//'", "cat .env.local | wc -l"),
    ("npx supabase status", "npx supabase status > /dev/null"),
    ("supabase projects api-keys --project-ref x", "supabase projects api-keys --project-ref x | wc -l"),
    ("gh auth token", "GH_TOKEN=$(gh auth token) gh api user"),
    ("gh auth status --show-token", "gh auth status"),
    ("security find-generic-password -s x -w", "P=$(security find-generic-password -s x -w)"),
    ("security find-generic-password -s x -g", "security find-generic-password -s x -g 2>/dev/null"),
    ("stripe config --list", "stripe config --list | grep -c _key"),
    ("vercel env pull /dev/stdout", "vercel env pull .env.local"),
]

# Ce qui ne doit jamais être refusé : le garde qui refuse tout rendrait le même verdict.
LIBRES = [
    "git status", "ls -la", "cat README.md", "cat .env.example", "grep -rn doppler docs/",
    "echo 'doppler secrets'", "git commit -m 'garde doppler secrets set'",
    "cat <<EOF > doc.md\ndoppler secrets set CLE=x\nEOF", "doppler setup --no-interactive",
    "doppler secrets --only-names --json", "gh pr list", "supabase db push --dry-run",
    "stripe listen", "source .env.local", "cp .env.local /tmp/sauve", "printenv PATH",
    "test -f .env.local && echo present", "doppler run -- npm test",
]


class Avant(unittest.TestCase):
    def test_chaque_forme_qui_affiche_est_refusee_et_sa_jumelle_passe(self):
        for mauvaise, bonne in PAIRES:
            with self.subTest(mauvaise=mauvaise):
                self.assertIsNotNone(coffre.affiche_un_secret(mauvaise), mauvaise)
            with self.subTest(bonne=bonne):
                self.assertIsNone(coffre.affiche_un_secret(bonne), bonne)

    def test_le_travail_ordinaire_passe(self):
        for c in LIBRES:
            with self.subTest(c=c):
                self.assertIsNone(coffre.affiche_un_secret(c), c)

    def test_une_ligne_illisible_ne_bloque_pas(self):
        self.assertIsNone(coffre.affiche_un_secret("echo 'non fermé"))

    def test_le_hook_refuse_avec_sa_raison(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            coffre.main(json.dumps({"tool_name": "Bash",
                                    "tool_input": {"command": "doppler secrets set A=1"}}))
        d = json.loads(sortie.getvalue())["hookSpecificOutput"]
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("--silent", d["permissionDecisionReason"])
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            coffre.main(json.dumps({"tool_name": "Bash",
                                    "tool_input": {"command": "doppler secrets set A=1 --silent"}}))
        self.assertEqual(sortie.getvalue(), "")

    def test_ouvrir_un_fichier_de_secrets(self):
        lire = lambda f: coffre.juge({"tool_name": "Read", "tool_input": {"file_path": f}})
        self.assertIsNotNone(lire("/p/apps/web/.env.local"))
        self.assertIsNotNone(lire("/p/.mcp.json"))
        self.assertIsNotNone(lire(os.path.expanduser("~/.secrets/coffre-lecture")))
        self.assertIsNone(lire("/p/.env.example"))
        self.assertIsNone(lire("/p/README.md"))

    def test_chercher_dans_un_fichier_de_secrets(self):
        g = lambda **ti: coffre.juge({"tool_name": "Grep", "tool_input": ti})
        self.assertIsNotNone(g(pattern="KEY", path=".env.local", output_mode="content"))
        self.assertIsNotNone(g(pattern="KEY", glob=".env*", output_mode="content"))
        self.assertIsNone(g(pattern="KEY", path=".env.local", output_mode="count"))
        self.assertIsNone(g(pattern="KEY", path=".env.local"))
        self.assertIsNone(g(pattern="KEY", glob="*.ts", output_mode="content"))


def _fausse(prefixe, n=40):
    # Fabriquée à l'exécution : ce fichier ne porte aucune clé que le témoin verrait.
    return prefixe + "A1b2C3d4E5f6G7h8" * (n // 16 + 1)


def _jwt(role):
    import base64
    b = lambda o: base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")
    return "%s.%s.%s" % (b({"alg": "HS256", "typ": "JWT"}), b({"role": role, "iss": "x"}),
                         "s1gnatureS1gnatureS1gnature")


class Lanceur(unittest.TestCase):
    """`~/.secrets/coffre prd secrets` : un script qui relaie à Doppler (QA, 17/10)."""
    def setUp(self):
        self.h = tempfile.mkdtemp(prefix="lanceur-")
        self.addCleanup(shutil.rmtree, self.h, True)
        self.coffre = os.path.join(self.h, "coffre")
        with open(self.coffre, "w") as f:
            f.write('#!/bin/sh\nc="$1"; shift\nexec doppler --config "$c" "$@"\n')
        self.autre = os.path.join(self.h, "autre")
        with open(self.autre, "w") as f:
            f.write('#!/bin/sh\necho "$@"\n')

    def test_le_lanceur_est_juge_comme_doppler(self):
        # Une ligne de Bash porte des `/` : sous Git Bash, `C:\Users\…` nu y serait déjà
        # mangé par le shell lui-même (la CI Windows l'a montré, 17/10/2026).
        c = self.coffre.replace("\\", "/")
        for mauvaise, bonne in [(c + " prd secrets", c + " prd secrets --only-names"),
                                (c + " prd run -- env", c + " prd run -- npm test"),
                                (c + " dev secrets set A=1", c + " dev secrets set A=1 --silent"),
                                ("./coffre prd secrets", "./coffre prd secrets > /dev/null")]:
            with self.subTest(mauvaise=mauvaise):
                self.assertIsNotNone(coffre.affiche_un_secret(mauvaise, self.h))
            with self.subTest(bonne=bonne):
                self.assertIsNone(coffre.affiche_un_secret(bonne, self.h))

    def test_un_script_qui_ne_relaie_pas_a_doppler_passe(self):
        self.assertIsNone(coffre.affiche_un_secret(self.autre.replace("\\", "/") + " prd secrets",
                                                   self.h))
        self.assertIsNone(coffre.affiche_un_secret("/nexiste/pas prd secrets", self.h))


class Apres(unittest.TestCase):
    def setUp(self):
        self.h = tempfile.mkdtemp(prefix="coffre-")
        self.addCleanup(shutil.rmtree, self.h, True)
        env = mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_DATA": os.path.join(self.h, "data"),
                                           "CLAUDE_PROJECT_DIR": "/p"})
        env.start()
        self.addCleanup(env.stop)

    def temoin(self, sortie, cmd="cat x"):
        o = io.StringIO()
        with contextlib.redirect_stdout(o):
            coffre.temoin(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd},
                                      "tool_response": {"stdout": sortie, "stderr": ""}}))
        return o.getvalue()

    def test_une_fausse_cle_affichee_declenche_l_alerte(self):
        cle = _fausse("sbp_")
        o = self.temoin("SUPABASE_ACCESS_TOKEN=" + cle)
        d = json.loads(o)
        self.assertIn("Supabase, jeton personnel", d["systemMessage"])
        self.assertNotIn(cle, o)
        with open(os.path.join(self.h, "data", "coffre", "fuites.log"), encoding="utf-8") as f:
            journal = f.read()
        self.assertIn("Supabase, jeton personnel", journal)
        self.assertNotIn(cle, journal)

    def test_chaque_forme_connue(self):
        for p in ("sbp_", "sb_secret_", "sk_live_", "rk_live_", "sk_test_", "rk_test_", "ghp_",
                  "dp.st.", "sk-ant-", "sk-proj-", "AIza", "xoxb-", "glpat-", "npm_"):
            with self.subTest(p=p):
                self.assertTrue(self.temoin("x=" + _fausse(p)), p)
        self.assertTrue(self.temoin("x=AKIA" + "A1B2C3D4E5F6G7H8"), "AWS : majuscules et chiffres")
        self.assertTrue(self.temoin(_jwt("service_role")))
        self.assertTrue(self.temoin("", cmd="doppler secrets set A=" + _fausse("sk_live_")))

    def test_une_cle_anthropic_n_est_pas_comptee_deux_fois(self):
        """`sk-ant-…` commence comme une clé OpenAI : une seule sorte, la bonne."""
        cles = coffre.cles("x=" + _fausse("sk-ant-"))
        self.assertEqual([c[0] for c in cles], ["Anthropic, clé"])

    def test_ce_qui_n_est_pas_une_cle_se_tait(self):
        for s in ("tout va bien", "sbp_court", "le préfixe sk_live_ dans une doc",
                  "pk_live_" + "A1b2C3d4E5f6G7h8" * 2, _jwt("anon"), "AKIA court", "npm_court"):
            with self.subTest(s=s):
                self.assertEqual(self.temoin(s), "")


if __name__ == "__main__":
    unittest.main()
