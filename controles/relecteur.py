#!/usr/bin/env python3
"""LA BOUCLE DU RELECTEUR, de bout en bout.

Ce n'est plus un contrôle différentiel : le relecteur n'existe QUE dans la
version Rust. C'est donc un contrôle de comportement, et chaque assertion porte
son contraire — un dispositif qui ne se déclenche jamais passerait sinon pour
un dispositif qui n'a rien trouvé.

AUCUN VRAI JUGE N'EST LANCÉ ICI. Sans cet interrupteur, chaque passage
consommerait une douzaine d'appels réels et le plafond journalier.
"""
import json, os, pathlib, shutil, subprocess, sys, time, datetime

S = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/relecteur")/"relec"
shutil.rmtree(S, ignore_errors=True); S.mkdir(parents=True)
ICI = pathlib.Path(__file__).resolve().parent
RS = os.environ.get("HARNAIS_BIN") or str(ICI.parent/"bin"/"harnais")
FAUX = str(ICI/"faux-bin")
AUJ = datetime.date.today().isoformat()
T0 = 1700000000

TODO_SIMPLE = ("- [ ] !haut @user **J'autorise le paiement ? oui / non**\n"
               "      oui → on encaisse.\n      non → on attend.\n"
               "      fini quand → tu vois un paiement d'essai passer.\n")
TODO_CONSTAT = ("- [ ] !haut @user ?constat **La page de contact manque ? oui / non**\n"
                "      oui → je la crée.\n      non → on ferme le sujet.\n"
                "      fini quand → tu ouvres la page.\n"
                "      ↻ machine :: echo ABSENTE :: ^ABSENTE$\n")

def bac(nom, todo):
    d = S/nom/"projet"; d.mkdir(parents=True)
    data = S/nom/"data"; (data/"attente").mkdir(parents=True)
    (data/"rechutes.md").write_text("# x\n\n- **une ligne**\n")
    g = lambda *a: subprocess.run(["git","-C",str(d)]+list(a), capture_output=True, text=True)
    g("init","-q","-b","main"); g("config","user.name","M"); g("config","user.email","m@x")
    for p, t in ((d/".fact/base.md", "---\ncap: c\n---\n"),
                 (d/".mind/state.md", "---\nmaj: %s\nsante: v\njalon: J\n---\n" % AUJ),
                 (d/".mind/todo.md", todo)):
        p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t)
    g("add","-A"); g("commit","-q","-m","socle")
    os.utime(d/".mind/todo.md", (T0, T0))
    return d, data

juge_mode = ["aucun"]

def tour(d, data, n=0):
    e = dict(os.environ)
    e["PATH"] = FAUX + ":" + e["PATH"]
    e["CLAUDE_PLUGIN_DATA"] = str(data); e["CLAUDE_PROJECT_DIR"] = str(d)
    fx = data/"rappels.json"; fx.write_text("{}")
    e["FAUX_RAPPELS"] = str(fx); e["FAUX_JOURNAL"] = "/dev/null"
    e["HARNAIS_RELECTURE_SIMULEE"] = juge_mode[0]
    if n:
        t = d/".mind"/"todo.md"; t.write_text(t.read_text()); os.utime(t, (T0+n, T0+n))
    r = subprocess.run([RS, "attente"], cwd=str(d), input=json.dumps({"session_id":"s"}),
                       capture_output=True, text=True, env=e)
    return r.returncode, r.stderr

def demandes(data):
    p = data/"relecture"
    return sorted(x.name for x in p.glob("*.demande")) if p.is_dir() else []

echecs = []
def veut(cond, quoi):
    if not cond: echecs.append(quoi)
    print("  %-64s %s" % (quoi, "oui" if cond else "NON  ← attendu"))

print("① une question ordinaire n'a rien à faire juger")
d, data = bac("simple", TODO_SIMPLE)
tour(d, data)
veut(demandes(data) == [], "aucune demande déposée pour une question sans affirmation")

print("② un constat, lui, est déposé — et seulement l'artefact")
d, data = bac("constat", TODO_CONSTAT)
tour(d, data)                                  # 1er tour : amnisties des témoins
tour(d, data, 100)
dem = demandes(data)
veut(len(dem) == 1, "une demande déposée pour la ligne qui affirme")
if dem:
    t = (data/"relecture"/dem[0]).read_text()
    veut("La page de contact manque" in t, "elle porte l'affirmation")
    veut("echo ABSENTE" in t, "elle porte la vérification")
    veut("oui → je la crée" in t, "elle porte ce que chaque réponse déclenche")
    veut("session" not in t.lower() and "raisonn" not in t.lower(),
         "elle ne porte RIEN du raisonnement ni de la conversation")

print("③ un verdict qui CONTREDIT renvoie l'agent au travail")
v = data/"relecture"/(dem[0].replace(".demande", ".verdict"))
(data/"relecture"/dem[0]).unlink()
v.write_text("verdict_relecteur: CONTREDIT la vérification cherche l'absence, la ligne "
             "affirme l'absence : elle rendra vrai quoi qu'il arrive\nrendu_le: 1\nsur: %s\n"
             % dem[0].replace(".demande",""))
rc, err = tour(d, data, 200)
veut(rc == 2, "le tour est bloqué")
veut("relecteur qui n'a PAS écrit ces lignes" in err, "le motif du relecteur est servi")
veut("il n'a pas raison d'office" in err.lower(), "et il est présenté comme faillible")
veut(not v.exists() and v.with_suffix(".traite").exists(), "le verdict est marqué traité")

print("④ le même verdict ne bloque JAMAIS deux fois")
rc2, _ = tour(d, data, 300)
veut(rc2 != 2, "le tour suivant passe — aucun agent coincé")

print("⑤ un verdict qui CONFIRME ne bloque pas")
d2, data2 = bac("confirme", TODO_CONSTAT)
tour(d2, data2); tour(d2, data2, 100)
dm = demandes(data2)
(data2/"relecture"/dm[0]).unlink()
(data2/"relecture"/(dm[0].replace(".demande",".verdict"))).write_text(
    "verdict_relecteur: CONFIRME\nrendu_le: 1\nsur: %s\n" % dm[0].replace(".demande",""))
rc3, _ = tour(d2, data2, 200)
veut(rc3 != 2, "un CONFIRME laisse passer")
veut((data2/"attente"/"relectures.log").exists(), "et le passage laisse une trace")

print("⑥ les gardes du juge lui-même")
sec = S/"juge"; (sec/"relecture").mkdir(parents=True)
(sec/"relecture"/"a.demande").write_text("id: a\n--- affirmation ---\nx\n")
e = dict(os.environ); e["CLAUDE_PLUGIN_DATA"] = str(sec)
r = subprocess.run([RS, "relecture", "--sec"], capture_output=True, text=True, env=e)
veut("CONFIRME" in r.stdout, "il rend un verdict")
(sec/"relecture"/"b.demande").write_text("id: b\nverdict_relecteur: CONFIRME\n")
r = subprocess.run([RS, "relecture", "--sec"], capture_output=True, text=True, env=e)
veut("→" not in r.stdout, "il ne relit JAMAIS une relecture")
(sec/"relecture"/"c.demande").write_text("id: c\n--- affirmation ---\nx\n")
(sec/"relecture"/".verrou").write_text(str(int(time.time())))
r = subprocess.run([RS, "relecture", "--sec"], capture_output=True, text=True, env=e)
veut("tourne déjà" in r.stdout, "un seul ouvrier à la fois")
(sec/"relecture"/".verrou").unlink()
(sec/"relecture"/".compteur").write_text("%d 12" % (int(time.time())//86400))
r = subprocess.run([RS, "relecture", "--sec"], capture_output=True, text=True, env=e)
veut("plafond" in r.stdout, "le plafond journalier mord")

print()
if echecs:
    print("ÉCHECS : " + " · ".join(echecs))
else:
    print("LA BOUCLE TIENT — dépôt, verdict, blocage, et aucun agent coincé")
sys.exit(1 if echecs else 0)
