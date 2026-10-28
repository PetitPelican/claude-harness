#!/usr/bin/env python3
"""LE GARDE DU COFFRE, JOUÉ POUR DE VRAI — sur un faux coffre, avec le vrai Doppler.

Le test unitaire dit ce que le garde DÉCIDE. Ce contrôle dit si sa décision est
JUSTE : chaque commande Doppler est jugée par le lanceur du paquet (le hook tel
qu'il part), PUIS jouée contre un faux coffre local, et on compte les valeurs
factices qui arrivent à l'écran.

  · la forme refusée doit AFFICHER au moins une valeur (sinon le refus est un
    faux positif, et la paire ne prouve rien) ;
  · sa jumelle qui passe ne doit en afficher AUCUNE (sinon le garde laisse fuir).

Puis le témoin d'après : une fausse clé `sbp_` affichée exprès doit déclencher
l'alerte, et une sortie sans clé doit le laisser muet.

Rien ne sort de la machine : le faux coffre écoute sur 127.0.0.1, le jeton est
factice, la configuration de Doppler vit dans un dossier jetable. Sans Doppler
installé, le contrôle se déclare AVEUGLE (code 1) : ne rien jouer n'est pas passer.

    python3 controles/coffre-factice.py [dossier de travail]
"""
import http.server
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading

ICI = pathlib.Path(__file__).resolve().parent
BIN = os.environ.get("HARNAIS_BIN") or str(ICI.parent / "bin" / "harnais")
MARQUE = "VALEUR-FACTICE"

# (refusée, jumelle qui passe) — jouées toutes les deux contre le faux coffre.
PAIRES = [
    ("doppler secrets set CLE_A=x", "doppler secrets set CLE_A=x --silent"),
    ("doppler secrets set CLE_A=x", "doppler secrets set CLE_A=x > /dev/null"),
    ("doppler secrets delete CLE_A --yes", "doppler secrets delete CLE_A --yes --silent"),
    ("doppler secrets upload u.env", "doppler secrets upload u.env --silent"),
    ("doppler secrets", "doppler secrets --only-names"),
    ("doppler secrets --json | jq .", "doppler secrets --json | jq keys"),
    ("doppler secrets get CLE_A --plain", "X=$(doppler secrets get CLE_A --plain)"),
    ("doppler secrets download --no-file", "doppler secrets download --no-file > .env.sortie.local"),
    ("doppler run -- env", "doppler run -- env | grep -oE '^[A-Z_][A-Z0-9_]*='"),
    ("doppler run -- printenv CLE_A", "doppler run -- printenv CLE_A > /dev/null"),
    # un lanceur de coffre (`~/.secrets/coffre <config> …`, `exec doppler "$@"`)
    ("./coffre prd secrets", "./coffre prd secrets --only-names"),
    ("./coffre prd run -- env", "./coffre prd run -- env > /dev/null"),
    ("cat .env.local", "grep -oE '^[A-Z_][A-Z0-9_]*=' .env.local"),
    # la clé sur plusieurs lignes : `cut` la laisse passer, le garde doit le refuser
    ("cut -d= -f1 .env.local", "grep -c = .env.local"),
]


class Coffre(http.server.BaseHTTPRequestHandler):
    def _r(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        s = {k: {"raw": "%s-%s" % (MARQUE, k), "computed": "%s-%s" % (MARQUE, k), "note": "",
                 "rawVisibility": "masked", "computedVisibility": "masked",
                 "rawValueType": {"type": "string"}, "computedValueType": {"type": "string"}}
             for k in ("CLE_A", "CLE_B")}
        if "/secrets/download" in self.path:      # `doppler run` : la forme à plat
            s = {k: v["computed"] for k, v in s.items()}
            b = json.dumps(s).encode()
        else:
            b = json.dumps({"success": True, "secrets": s}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    do_GET = do_POST = do_PUT = _r

    def log_message(self, *a):
        pass


TRAVAIL = [None]


def hook(sous, charge):
    o = subprocess.run(["sh", BIN, sous], input=json.dumps(charge).encode(),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    return o.returncode, o.stdout.decode("utf-8", "replace")


def refuse(cmd):
    code, sortie = hook("coffre", {"tool_name": "Bash", "cwd": str(TRAVAIL[0]),
                                   "tool_input": {"command": cmd}})
    if code != 0:
        raise SystemExit("le lanceur rend %d sur « %s » : le garde n'a pas jugé" % (code, cmd))
    return '"deny"' in sortie


def main():
    vrai = shutil.which("doppler")
    if not vrai:
        print("AVEUGLE : Doppler n'est pas installé — aucune commande n'a été jouée.")
        return 1
    travail = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="coffre-"))
    travail.mkdir(parents=True, exist_ok=True)
    TRAVAIL[0] = travail
    serveur = http.server.HTTPServer(("127.0.0.1", 0), Coffre)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    port = serveur.server_address[1]
    outils = travail / "bin"
    outils.mkdir(exist_ok=True)
    (outils / "doppler").write_text(
        "#!/bin/sh\nexec '%s' --api-host http://127.0.0.1:%d --token dp.st.factice "
        "--project p --config c --no-check-version --config-dir '%s' \"$@\"\n"
        % (vrai, port, travail / "cfg"))
    (outils / "doppler").chmod(0o755)
    (travail / "u.env").write_text("CLE_A=x\n")
    (travail / "coffre").write_text('#!/bin/sh\nc="$1"; shift\nexec doppler "$@"\n')
    (travail / "coffre").chmod(0o755)
    (travail / ".env.local").write_text(
        "CLE_A=%s-CLE_A\nCLE_PEM=\"-----BEGIN PRIVATE KEY-----\n%s-SUR-PLUSIEURS-LIGNES==\n"
        "-----END PRIVATE KEY-----\"\n" % (MARQUE, MARQUE))
    env = dict(os.environ, PATH="%s%s%s" % (outils, os.pathsep, os.environ.get("PATH", "")))

    def affiche(cmd):
        o = subprocess.run(["sh", "-c", cmd], cwd=travail, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=60)
        return o.stdout.decode("utf-8", "replace").count(MARQUE)

    echecs = 0
    for mauvaise, bonne in PAIRES:
        r_m, n_m = refuse(mauvaise), affiche(mauvaise)
        r_b, n_b = refuse(bonne), affiche(bonne)
        ok = r_m and n_m > 0 and not r_b and n_b == 0
        echecs += not ok
        print("%s  %-40s refusée=%s affiche %d  ·  %-48s passe=%s affiche %d"
              % ("ok  " if ok else "ÉCHEC", mauvaise, r_m, n_m, bonne, not r_b, n_b))
    serveur.shutdown()

    # Le témoin d'après : une fausse clé, fabriquée ici, jamais écrite dans un fichier suivi.
    fausse = "sbp_" + "A1b2C3d4E5f6G7h8" * 3
    charge = lambda s: {"tool_name": "Bash", "tool_input": {"command": "echo"},
                        "tool_response": {"stdout": s, "stderr": ""}}
    data = travail / "data"
    os.environ["CLAUDE_PLUGIN_DATA"] = str(data)
    _, alerte = hook("coffre-temoin", charge("SUPABASE_ACCESS_TOKEN=" + fausse))
    _, muet = hook("coffre-temoin", charge("tout va bien"))
    ok = "systemMessage" in alerte and fausse not in alerte and muet.strip() == ""
    echecs += not ok
    print("%s  témoin : fausse clé sbp_ → alerte=%s, valeur recopiée=%s ; sortie propre → muet=%s"
          % ("ok  " if ok else "ÉCHEC", "systemMessage" in alerte, fausse in alerte,
             muet.strip() == ""))
    print("\n%d paire(s) jouée(s) sur un faux coffre + le témoin, %d en échec" % (len(PAIRES), echecs))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
