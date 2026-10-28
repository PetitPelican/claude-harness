# -*- coding: utf-8 -*-
"""La garde des sous-agents (0.19.3) : un sous-agent qui regarde du visuel ou
reçoit un lot de plus de 30 éléments ne part pas sans le oui de l'humain. Chaque
refus a son témoin muet."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "..", "py"))
import sous_agent  # noqa: E402

# Une consigne de rédaction de textes alternatifs, de la forme de celle du 18/10/2026 :
# fixture synthétique, sans sujet réel.
CONSIGNE_ALT = (
    "Tu rédiges des textes alternatifs (attribut alt, pour lecteurs d'écran) en français pour "
    "des diapositives de présentation.\n\n"
    "Méthode : pour chaque diapositive, convertis-la en PNG de 1000 px dans ton dossier de "
    "travail, puis regarde l'image avec l'outil Read et décris-la.")
# Un audit ordinaire, en lecture seule, qui PARLE d'images sans les regarder.
AUDIT = (
    "Tu fais un AUDIT D'ACCESSIBILITÉ EN LECTURE SEULE du site. Lis d'abord "
    "docs/guide.md.\n"
    "5. Images : alt manquant ou non pertinent (alt = nom de fichier), images décoratives ; "
    "iframes sans title.\n"
    "- Images : formats servis, images surdimensionnées, poids des 10 plus lourdes ressources.\n"
    "- public/images fait ~400 Mo et ~1000 fichiers : combien sont réellement référencées ?\n"
    "- Liens : 404 = vidéo retirée ?")


def muet(f, *a):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return f(*a)


class Base(unittest.TestCase):
    def setUp(self):
        self.h = os.path.realpath(tempfile.mkdtemp(prefix="sousag-"))
        self.addCleanup(shutil.rmtree, self.h, True)
        self.agent = os.path.join(self.h, "Projet", "agents", "PO")
        os.makedirs(self.agent)
        env = mock.patch.dict(os.environ, {"HOME": self.h, "USERPROFILE": self.h,
                                           "CLAUDE_PLUGIN_DATA": os.path.join(self.h, "data"),
                                           "CLAUDE_PROJECT_DIR": self.agent})
        env.start()
        self.addCleanup(env.stop)

    def juge(self, prompt, outil="Agent", description="tâche"):
        ti = {"script": prompt} if outil == "Workflow" else {"description": description,
                                                             "prompt": prompt}
        return sous_agent.juge({"tool_name": outil, "cwd": self.agent, "tool_input": ti})

    def passe(self, motif="l'humain : « oui, 3 lots de 30 »"):
        return muet(sous_agent.laissez_passer, [motif])


class Visuel(Base):
    def test_la_consigne_de_textes_alternatifs_est_refusee(self):
        r = self.juge(CONSIGNE_ALT)
        self.assertIsNotNone(r)
        self.assertIn("visuel", r)
        self.assertIn("laissez-passer-lot", r)
        self.assertIn("lot de 30", r)

    def test_regarder_l_image_mord_seul(self):
        # Sans la phrase des textes alternatifs, le verbe qui voit suffit.
        self.assertIsNotNone(self.juge("Pour chaque fichier, regarde l'image avec l'outil Read."))

    def test_l_audit_ordinaire_passe(self):
        self.assertIsNone(self.juge(AUDIT, description="Audit accessibilité"))

    def test_formes_qui_mordent(self):
        for p in ("Lis le contrat (PDF) et résume-le.",
                  "Ouvre docs/guide.pdf puis dis ce qu'il prévoit.",
                  "Look at each screenshot and describe the layout.",
                  "Décris les captures d'écran du dossier.",
                  "Fais un OCR des factures.",
                  "Write alt text for every picture on the page.",
                  "Ne lis pas le code, regarde les captures d'écran."):
            with self.subTest(p=p):
                self.assertIsNotNone(self.juge(p))

    def test_formes_qui_passent(self):
        for p in ("Ne lis aucune image : le code seul.",
                  "Lis le code qui génère les miniatures des images.",
                  "Do not open any screenshot; read src/ only.",
                  "Observations sur la capture d'écran réelle : la carte est trop large.",
                  'Le SVG a viewBox="0 0 120 60" ; porte-le dans l\'app.',
                  "Audite les gardes du dépôt et rends un rapport."):
            with self.subTest(p=p):
                self.assertIsNone(self.juge(p))

    def test_la_description_seule_suffit(self):
        self.assertIsNotNone(self.juge("Suis la méthode du fichier joint.",
                                       description="Décrire visuels lot 1"))

    def test_un_workflow_est_lu(self):
        script = "agent(`Regarde chaque capture d'écran et note les défauts`)"
        self.assertIsNotNone(self.juge(script, outil="Workflow"))
        self.assertIsNone(self.juge("agent(`Audite le dépôt`)", outil="Workflow"))

    def test_un_autre_outil_n_est_pas_juge(self):
        self.assertIsNone(sous_agent.juge({"tool_name": "Bash", "tool_input": {
            "command": "regarde l'image"}}))


class Lot(Base):
    def test_un_gros_lot_d_images_est_refuse_meme_muni(self):
        self.passe()
        r = self.juge("Décris les 2 273 images du dossier.")
        self.assertIsNotNone(r)
        self.assertIn("2273 médias", r)

    def test_un_lot_de_texte_passe(self):
        # CTO, 20/10 : le verrou est réservé aux médias ; un lot de texte n'a jamais
        # dépassé 6,7 M en un mois, et le coupe-circuit le couvre.
        for p in ("tests/ (38 fichiers, 7371 l.) : classe chaque fichier.",
                  "78 migration files were added. Read each file.",
                  "Il y a des centaines de pages à résumer."):
            with self.subTest(p=p):
                self.assertIsNone(self.juge(p))

    def test_une_masse_sans_chiffre(self):
        self.passe()
        self.assertIsNotNone(self.juge("Il y a des centaines de captures à trier."))
        self.assertIsNotNone(self.juge("Thousands of screenshots are in the folder."))

    def test_trente_passe_avec_le_laissez_passer(self):
        self.assertIsNotNone(self.juge("Décris ces 30 images."))
        self.passe()
        self.assertIsNone(self.juge("Décris ces 30 images."))
        self.assertIsNotNone(self.juge("Décris ces 31 images."))


class LaissezPasser(Base):
    def test_il_ouvre_le_visuel_et_journalise(self):
        self.assertIsNotNone(self.juge(CONSIGNE_ALT))
        self.assertEqual(self.passe(), 0)
        self.assertIsNone(self.juge(CONSIGNE_ALT))
        _, log = sous_agent._fichiers(self.agent)
        with open(log, encoding="utf-8") as h:
            lignes = h.read().splitlines()
        self.assertTrue(lignes[0].split("\t")[1] == "déposé")
        self.assertTrue(lignes[-1].split("\t")[1] == "usage")
        self.assertIn("3 lots de 30", lignes[-1])

    def test_il_expire(self):
        self.passe()
        f, _ = sous_agent._fichiers(self.agent)
        vieux = time.time() - (sous_agent.DUREE * 60 + 5)
        os.utime(f, (vieux, vieux))
        self.assertIsNotNone(self.juge(CONSIGNE_ALT))

    def test_il_ne_vaut_que_pour_son_agent(self):
        self.passe()
        autre = os.path.join(self.h, "Projet", "agents", "QA")
        os.makedirs(autre)
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": autre}):
            self.assertIsNotNone(self.juge(CONSIGNE_ALT))

    def test_sans_motif_il_refuse(self):
        self.assertEqual(muet(sous_agent.laissez_passer, []), 2)
        self.assertIsNotNone(self.juge(CONSIGNE_ALT))


class Lanceur(Base):
    def lance(self, sous, entree, *args):
        env = dict(os.environ)
        return subprocess.run([sys.executable, os.path.join(ICI, "..", "py", "main.py"), sous]
                              + list(args), input=entree.encode("utf-8"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=30)

    def test_le_refus_sort_en_decision_du_hook(self):
        o = self.lance("sous-agent", json.dumps({"tool_name": "Agent", "tool_input": {
            "description": "Décrire visuels", "prompt": CONSIGNE_ALT}}))
        self.assertEqual(o.returncode, 0)
        d = json.loads(o.stdout.decode("utf-8"))["hookSpecificOutput"]
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("l'humain", d["permissionDecisionReason"])

    def test_muet_sur_l_audit_et_sur_l_illisible(self):
        for entree in (json.dumps({"tool_name": "Agent", "tool_input": {"prompt": AUDIT}}),
                       "{pas du json"):
            o = self.lance("sous-agent", entree)
            self.assertEqual((o.returncode, o.stdout), (0, b""))

    def test_le_laissez_passer_par_le_lanceur(self):
        o = self.lance("laissez-passer-lot", "", "oui de l'humain")
        self.assertEqual(o.returncode, 0, o.stderr)
        self.assertIsNone(self.juge(CONSIGNE_ALT))


if __name__ == "__main__":
    unittest.main()
