# -*- coding: utf-8 -*-
"""La garde des tâches Notion (0.19.2) : la ligne « Tâche: » au commit, et la page
lue en fin de tour — contre un faux Notion local. Chaque refus a sa jumelle qui
passe : une garde qui refuse tout et une garde qui laisse tout passer ne rendent
pas le même verdict sur une paire."""
import datetime
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env_windows  # noqa: E402
import banc_equipe  # noqa: E402

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAIN = os.path.join(RACINE, "py", "main.py")

BASE = "11111111111111111111111111111111"
AUTRE_BASE = "22222222222222222222222222222222"
T_FAITE = "a" * 32
T_A_FAIRE = "b" * 32
T_FRAICHE = "c" * 32
T_VIEILLE = "d" * 32
T_AILLEURS = "e" * 32
T_SANS_PREUVE = "f" * 32
INCONNUE = "0123456789abcdef0123456789abcdef"
INTERDITE = "9" * 32
JETON = "jeton-factice-ne-doit-jamais-sortir"
REGLAGE = {"base": BASE, "secret": "NOTION_LECTURE_TOKEN",
           "fait": {"Statut": ["🟢 Fait", "🟢 Vérifié"],
                    "Niveau d'avancement": "Terminé"},     # apostrophe droite, exprès
           "preuve": "Description"}


def _iso(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _page(base, titre, etape, avancement, description, edite):
    return {"object": "page", "parent": {"type": "database_id",
                                         "database_id": "%s-%s-%s-%s-%s" % (base[:8], base[8:12], base[12:16], base[16:20], base[20:])},
            "last_edited_time": edite,
            "properties": {
                "Nom de la tâche": {"type": "title", "title": [{"plain_text": titre}]},
                "Statut": {"type": "select", "select": {"name": etape}},
                "Niveau d’avancement": {"type": "status", "status": {"name": avancement}},
                "Description": {"type": "rich_text", "rich_text": ([{"plain_text": description}] if description else [])}}}


class FauxNotion(http.server.BaseHTTPRequestHandler):
    pages = {}
    appels = []

    def do_GET(self):
        FauxNotion.appels.append((self.path, self.headers.get("Authorization")))
        ident = self.path.rsplit("/", 1)[-1].replace("-", "")
        p = FauxNotion.pages.get(ident)
        statut = 403 if ident == INTERDITE else (200 if p else 404)
        b = json.dumps(p if p else {"object": "error", "status": statut}).encode()
        self.send_response(statut)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


class Commit(unittest.TestCase):
    """1. La ligne « Tâche: » — par la garde de commit, dans `code/` d'une équipe."""

    def setUp(self):
        d = os.path.realpath(tempfile.mkdtemp(prefix="taches-commit-"))
        self.addCleanup(shutil.rmtree, d, True)
        self.x = banc_equipe.construis(d)
        self.po = os.path.join(self.x, "agents", "PO")
        self.code = os.path.join(self.po, "code")
        with open(os.path.join(self.code, "apps", "app.ts"), "a", encoding="utf-8") as h:
            h.write("// x\n")
        subprocess.run(["git", "add", "apps/app.ts"], cwd=self.code, check=True)
        os.utime(os.path.join(self.po, "state.md"), None)     # état plus récent que le code

    def juge(self, commande, reglage=REGLAGE):
        maison = tempfile.mkdtemp(prefix="taches-maison-")
        self.addCleanup(shutil.rmtree, maison, True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": maison,
               "CLAUDE_PLUGIN_DATA": os.path.join(maison, "donnees"), "LANG": "C.UTF-8",
               "CLAUDE_PROJECT_DIR": self.po}
        if reglage is not None:
            env["HARNAIS_TACHES"] = json.dumps(reglage, ensure_ascii=False)
        env = dict(env_windows.essentiel(), **env)
        entree = json.dumps({"tool_name": "Bash", "tool_input": {"command": commande}})
        r = subprocess.run([sys.executable, MAIN, "mind-guard"], cwd=self.po, env=env,
                           input=entree.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        s = r.stdout.decode("utf-8", "replace").strip()
        return json.loads(s)["hookSpecificOutput"]["permissionDecisionReason"] if s else None

    def test_a_un_commit_sans_ligne_tache_est_refuse(self):
        m = self.juge("git -C code commit -m x")
        self.assertIsNotNone(m)
        self.assertIn("ne cite pas sa tâche Notion", m)
        self.assertIn("Tâche: aucune", m)
        # TÉMOINS : la même commande passe sans réglage, et avec la ligne.
        self.assertIsNone(self.juge("git -C code commit -m x", reglage=None))
        self.assertIsNone(self.juge("git -C code commit -m x -m 'Tâche: %s'" % T_A_FAIRE))

    def test_les_trois_formes_passent(self):
        for ligne in ("Tâche: aucune", "Tâche: %s" % T_A_FAIRE, "Tâche: %s fait" % T_FAITE,
                      "Tache: 8f2a1c3e-0b4d-4e6f-8a9b-0c1d2e3f4a5b", "TÂCHE : aucune"):
            self.assertIsNone(self.juge('git -C code commit -m "x\n\n%s"' % ligne), ligne)

    def test_le_message_par_heredoc_et_par_fichier(self):
        self.assertIsNone(self.juge(
            "cd code && git commit -m \"$(cat <<'EOF'\nx\n\nTâche: %s\nEOF\n)\"" % T_A_FAIRE))
        self.assertIsNotNone(self.juge("cd code && git commit -m \"$(cat <<'EOF'\nx\nEOF\n)\""))
        with open(os.path.join(self.code, "msg.txt"), "w", encoding="utf-8") as h:
            h.write("x\n\nTâche: aucune\n")
        self.assertIsNone(self.juge("git -C code commit -F msg.txt"))
        with open(os.path.join(self.code, "msg.txt"), "w", encoding="utf-8") as h:
            h.write("x\n")
        self.assertIsNotNone(self.juge("git -C code commit -F msg.txt"))

    def test_une_ligne_illisible_est_refusee_avec_la_phrase(self):
        m = self.juge("git -C code commit -m x -m 'Tâche: la page du paiement'")
        self.assertIsNotNone(m)
        self.assertIn("n'est pas lisible", m)
        self.assertIsNotNone(self.juge("git -C code commit -m x -m 'Tâche: %s'" % T_A_FAIRE[:31]))

    def test_sans_message_l_editeur_est_refuse(self):
        m = self.juge("git -C code commit")
        self.assertIsNotNone(m)
        self.assertIn("éditeur", m)

    def test_un_message_repris_passe(self):
        for c in ("git -C code commit --amend --no-edit", "git -C code commit -C HEAD",
                  "git -C code commit --fixup HEAD"):
            self.assertIsNone(self.juge(c), c)

    def test_la_memoire_n_est_pas_concernee(self):
        with open(os.path.join(self.po, "todo.md"), "a", encoding="utf-8") as h:
            h.write("- [ ] x\n")
        subprocess.run(["git", "add", "todo.md"], cwd=self.po, check=True)
        self.assertIsNone(self.juge("git commit -m x # memoire-ok"))


class FinDeTour(unittest.TestCase):
    """2. La fin de tour lit les tâches citées par les commits du tour."""

    @classmethod
    def setUpClass(cls):
        cls.serveur = http.server.HTTPServer(("127.0.0.1", 0), FauxNotion)
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()
        cls.api = "http://127.0.0.1:%d" % cls.serveur.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def setUp(self):
        d = os.path.realpath(tempfile.mkdtemp(prefix="taches-tour-"))
        self.addCleanup(shutil.rmtree, d, True)
        self.x = banc_equipe.construis(d)
        self.po = os.path.join(self.x, "agents", "PO")
        self.code = os.path.join(self.po, "code")
        self.maison = os.path.join(d, "maison")
        os.makedirs(self.maison)
        self.transcript = os.path.join(d, "session.jsonl")
        self.debut(time.time() - 120)
        maintenant = time.time()
        recent, vieux = _iso(maintenant + 120), "2020-01-01T00:00:00.000Z"
        FauxNotion.pages = {
            T_FAITE: _page(BASE, "Paiement", "🟢 Fait", "Terminé", "preuve : run 42", vieux),
            T_A_FAIRE: _page(BASE, "Panier", "🟠 À faire", "En cours", "", recent),
            T_FRAICHE: _page(BASE, "Profil", "🟠 À faire", "En cours", "", recent),
            T_VIEILLE: _page(BASE, "Recherche", "🟠 À faire", "En cours", "", vieux),
            T_AILLEURS: _page(AUTRE_BASE, "Une décision", "", "", "", recent),
            T_SANS_PREUVE: _page(BASE, "Export", "🟢 Fait", "Terminé", "", vieux),
        }
        FauxNotion.appels = []

    def debut(self, t):
        with open(self.transcript, "w", encoding="utf-8") as h:
            h.write(json.dumps({"type": "user", "timestamp": _iso(t),
                                "message": {"role": "user", "content": "au travail"}}) + "\n")

    def commit(self, ligne):
        with open(os.path.join(self.code, "apps", "app.ts"), "a", encoding="utf-8") as h:
            h.write("// %s\n" % ligne)
        banc_equipe._git(self.code, "commit", "-q", "-am", "x\n\n" + ligne)

    def tour(self, reglage=None, jeton=JETON, session="s1"):
        r = dict(REGLAGE, api=self.api)
        r.update(reglage or {})
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": self.maison,
               "CLAUDE_PLUGIN_DATA": os.path.join(self.maison, "donnees"), "LANG": "C.UTF-8",
               "CLAUDE_PROJECT_DIR": self.po, "HARNAIS_TACHES": json.dumps(r, ensure_ascii=False)}
        if jeton:
            env["NOTION_LECTURE_TOKEN"] = jeton
        env = dict(env_windows.essentiel(), **env)
        entree = json.dumps({"session_id": session, "transcript_path": self.transcript, "cwd": self.po})
        o = subprocess.run([sys.executable, MAIN, "taches"], cwd=self.po, env=env,
                           input=entree.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=60)
        sortie = o.stdout.decode("utf-8", "replace") + o.stderr.decode("utf-8", "replace")
        self.assertNotIn(JETON, sortie)
        return o.returncode, sortie

    def test_b_fait_avec_la_tache_restee_a_faire_est_refuse(self):
        self.commit("Tâche: %s fait" % T_A_FAIRE)
        code, s = self.tour()
        self.assertEqual(code, 2, s)
        self.assertIn("« Panier »", s)
        self.assertIn("Statut vaut « 🟠 À faire »", s)
        self.assertIn("Description est vide", s)
        # TÉMOIN : posée Fait + Terminé + preuve → acceptée.
        self.commit("Tâche: %s fait" % T_FAITE)
        FauxNotion.pages[T_A_FAIRE] = FauxNotion.pages[T_FAITE]
        code, s = self.tour()
        self.assertEqual(code, 0, s)
        self.assertEqual(s.strip(), "")

    def test_b_fait_sans_preuve_est_refuse(self):
        self.commit("Tâche: %s fait" % T_SANS_PREUVE)
        code, s = self.tour()
        self.assertEqual(code, 2, s)
        self.assertIn("écris-y la preuve", s)

    def test_c_sans_fait_la_page_doit_avoir_bouge(self):
        self.commit("Tâche: %s" % T_VIEILLE)
        code, s = self.tour()
        self.assertEqual(code, 2, s)
        self.assertIn("mets à jour la tâche « Recherche »", s)
        # TÉMOIN : la page modifiée après le commit → acceptée.
        FauxNotion.pages[T_VIEILLE]["last_edited_time"] = _iso(time.time() + 60)
        code, s = self.tour()
        self.assertEqual(code, 0, s)

    def test_d_un_identifiant_invente_ou_hors_base_est_refuse(self):
        self.commit("Tâche: %s" % INCONNUE)
        code, s = self.tour()
        self.assertEqual(code, 2, s)
        self.assertIn("n'existe pas dans Notion", s)
        self.debut(time.time() + 1)
        time.sleep(1.1)
        self.commit("Tâche: %s" % T_AILLEURS)
        code, s = self.tour(session="s2")
        self.assertEqual(code, 2, s)
        self.assertIn("n'est pas une tâche", s)
        self.assertNotIn(INCONNUE, s)          # le commit d'avant le tour n'est pas relu

    def test_d_une_page_interdite_a_son_propre_refus(self):
        self.commit("Tâche: %s" % INTERDITE)
        code, s = self.tour()
        self.assertEqual(code, 2, s)
        self.assertIn("(403)", s)
        self.assertNotIn("n'existe pas", s)

    def test_un_jeton_refuse_avertit_sans_bloquer(self):
        """401 : le jeton, pas la tâche — un avertissement, pas un refus."""
        class Refuse(FauxNotion):
            def do_GET(self):
                self.send_response(401)
                self.send_header("Content-Length", "0")
                self.end_headers()
        s401 = http.server.HTTPServer(("127.0.0.1", 0), Refuse)
        threading.Thread(target=s401.serve_forever, daemon=True).start()
        self.addCleanup(s401.server_close)
        self.addCleanup(s401.shutdown)
        self.commit("Tâche: %s" % T_VIEILLE)
        code, s = self.tour({"api": "http://127.0.0.1:%d" % s401.server_address[1]})
        self.assertEqual(code, 0, s)
        self.assertIn("Notion répond 401", s)

    def test_e_api_injoignable_avertit_sans_bloquer(self):
        self.commit("Tâche: %s" % T_VIEILLE)
        code, s = self.tour({"api": "http://127.0.0.1:9"})
        self.assertEqual(code, 0, s)
        self.assertIn("systemMessage", s)
        self.assertIn("Notion injoignable", s)
        # TÉMOIN : la bonne adresse, et la même tâche refuse.
        self.assertEqual(self.tour()[0], 2)

    def test_f_aucune_passe_sans_appel_reseau(self):
        self.commit("Tâche: aucune")
        code, s = self.tour()
        self.assertEqual((code, s.strip()), (0, ""))
        self.assertEqual(FauxNotion.appels, [])
        # TÉMOIN : une tâche citée appelle bien Notion, avec le jeton.
        self.commit("Tâche: %s" % T_FRAICHE)
        self.assertEqual(self.tour()[0], 0)
        self.assertEqual(len(FauxNotion.appels), 1)
        self.assertEqual(FauxNotion.appels[0][1], "Bearer " + JETON)

    def test_un_secret_absent_se_dit_une_fois_par_tour(self):
        self.commit("Tâche: %s" % T_VIEILLE)
        code, s = self.tour({"secret": "SECRET_QUI_N_EXISTE_PAS"}, jeton=None)
        self.assertEqual(code, 0)
        self.assertIn("introuvable", s)
        self.assertEqual(self.tour({"secret": "SECRET_QUI_N_EXISTE_PAS"}, jeton=None)[1].strip(), "")
        self.assertEqual(FauxNotion.appels, [])

    def test_les_commits_d_avant_le_tour_ne_comptent_pas(self):
        self.commit("Tâche: %s" % T_VIEILLE)
        self.debut(time.time() + 5)
        self.assertEqual(self.tour(), (0, ""))
        self.assertEqual(FauxNotion.appels, [])

    def test_au_bout_de_trois_renvois_on_laisse_finir_en_le_disant(self):
        self.commit("Tâche: %s" % T_VIEILLE)
        for _ in range(3):
            self.assertEqual(self.tour()[0], 2)
        code, s = self.tour()
        self.assertEqual(code, 0)
        self.assertIn("après 3 renvois", s)

    def test_eteinte_sans_reglage(self):
        self.commit("Tâche: %s" % INCONNUE)
        env = dict(env_windows.essentiel(), PATH=os.environ.get("PATH", "/usr/bin:/bin"),
                   HOME=self.maison, CLAUDE_PROJECT_DIR=self.po)
        o = subprocess.run([sys.executable, MAIN, "taches"], cwd=self.po, env=env,
                           input=json.dumps({"transcript_path": self.transcript}).encode(),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual((o.returncode, o.stdout, o.stderr), (0, b"", b""))


if __name__ == "__main__":
    unittest.main()
