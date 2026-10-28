"""CONTRÔLE DIFFÉRENTIEL — le garde de commit, Python contre Rust.

C'est le premier hook porté qui REFUSE. On ne compare donc pas seulement
« bloque / ne bloque pas » : on compare le MOTIF, au caractère près. Un garde
qui mord au bon moment avec la mauvaise phrase apprend le mauvais geste.

La sortie est un document JSON lu par un analyseur, pas un flux d'octets :
Python échappe les accents en \\uXXXX, Rust les écrit tels quels. On compare
donc les JSON ANALYSÉS — même document, deux encodages.

FIGÉ LE 10/09/2026 (lot 0) : `temoins/mind-guard.json` garde les verdicts que
Python rendait sur les dix-neuf cas fabriqués. `--gel` les reproduit.

TÉMOINS : il faut des refus ET des passages. Deux gardes qui laissent tout
passer se comparent égaux.
"""
import json, os, shutil, subprocess, pathlib, sys, datetime, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import temoins

BASE = pathlib.Path(sys.argv[1])/"mg"
PY = str(pathlib.Path.home()/".claude/hooks/mind-guard.py")
RS = os.environ.get("HARNAIS_BIN") or str(pathlib.Path.home()/"Agentic/claude-harnais/bin/harnais")
AUJ = datetime.date.today().isoformat()

ENTETE_OK   = f"---\nmaj: {AUJ}\ncap: aller là\nsante: verte\njalon: x\n---\n\ntexte\n"
ENTETE_VIEUX= "---\nmaj: 2020-01-01\ncap: c\nsante: verte\njalon: x\n---\n\ntexte\n"
ENTETE_NUL  = "pas d'en-tête du tout\n"
ENTETE_TROU = f"---\nmaj: {AUJ}\n---\n\ntexte\n"
BASE_MD     = "---\ncap: la destination du projet\n---\n\ntexte\n"
BASE_SANS   = "---\nautre: x\n---\n\ntexte\n"

def depot(nom, state, code=True, fact=None, lot=None, deporte=False, tard=False):
    d = BASE/nom
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    g = lambda *a: subprocess.run(["git","-C",str(d)]+list(a), capture_output=True, text=True)
    g("init","-q","-b","main"); g("config","user.name","M"); g("config","user.email","m@x")
    (d/"README.md").write_text("x\n"); g("add","-A"); g("commit","-q","-m","socle")
    racine_agent = d/lot if lot else d
    if deporte:
        m = d/"memoire"
        (m/".fact").mkdir(parents=True, exist_ok=True); (m/".mind").mkdir(parents=True, exist_ok=True)
        (m/".fact/base.md").write_text(fact if fact is not None else BASE_MD)
        (m/".mind/state.md").write_text(state)
    else:
        (racine_agent/".mind").mkdir(parents=True, exist_ok=True)
        (racine_agent/".mind/state.md").write_text(state)
        if fact is not None:
            (racine_agent/".fact").mkdir(parents=True, exist_ok=True)
            (racine_agent/".fact/base.md").write_text(fact)
    if code:
        (racine_agent/"src").mkdir(parents=True, exist_ok=True)
        (racine_agent/"src/a.ts").write_text("const a = 1\n")
    g("add","-A")
    if tard:  # le code touché APRÈS l'état : la règle du déporté
        time.sleep(1.1); (racine_agent/"src/a.ts").write_text("const a = 2\n"); g("add","-A")
    return d, racine_agent

def lance(argv, d, agent, cmd):
    e = dict(os.environ); e["CLAUDE_PROJECT_DIR"] = str(agent)
    entree = json.dumps({"tool_name":"Bash","tool_input":{"command":cmd},"session_id":"s"})
    r = subprocess.run(argv, cwd=str(d), input=entree, capture_output=True, text=True, env=e)
    s = r.stdout.strip()
    try:    return json.loads(s) if s else None
    except Exception: return {"BRUT": s}

CAS = [
 ("en-tête absent",        dict(state=ENTETE_NUL),                         "git commit -m x"),
 ("champ manquant",        dict(state=ENTETE_TROU),                        "git commit -m x"),
 ("date périmée",          dict(state=ENTETE_VIEUX),                       "git commit -m x"),
 ("état frais, code",      dict(state=ENTETE_OK),                          "git commit -m x"),
 ("code sans état",        dict(state=ENTETE_OK, code=True),               "git commit -m x"),
 (".fact touché",          dict(state=ENTETE_OK, fact=BASE_MD),            "git commit -m x"),
 (".fact autorisé",        dict(state=ENTETE_OK, fact=BASE_MD),            "git commit -m x # fact-ok"),
 ("fact-ok au milieu",     dict(state=ENTETE_OK, fact=BASE_MD),            "git commit -m 'fact-ok un jour'"),
 ("mind-ok n'ouvre pas .fact", dict(state=ENTETE_NUL, fact=BASE_MD),       "git commit -m x # mind-ok"),
 ("mind-ok, état cassé",   dict(state=ENTETE_NUL),                         "git commit -m x # mind-ok"),
 ("base.md sans cap",      dict(state=ENTETE_OK, fact=BASE_SANS),          "git commit -m x # fact-ok"),
 ("pas un commit",         dict(state=ENTETE_NUL),                         "git status"),
 ("sans code",             dict(state=ENTETE_OK, code=False),              "git commit -m x"),
 ("multi-agents",          dict(state=ENTETE_OK, lot="agents/ios"),        "git commit -m x"),
 ("multi-agents cassé",    dict(state=ENTETE_NUL, lot="agents/ios"),       "git commit -m x"),
 ("déporté, état frais",   dict(state=ENTETE_OK, deporte=True),            "git commit -m x"),
 ("déporté, code plus récent", dict(state=ENTETE_OK, deporte=True, tard=True), "git commit -m x"),
 ("déporté, état cassé",   dict(state=ENTETE_NUL, deporte=True),           "git commit -m x"),
]

# LE CAS QUI SÉPARE `cwd` DE `CLAUDE_PROJECT_DIR` : deux DÉPÔTS différents.
# Aucun des dix-huit cas ci-dessus ne le distingue — ils sont tous dans le même
# dépôt, donc `rev-parse` rend la même racine des deux côtés. Sans ce cas, une
# implémentation qui lance git depuis le mauvais dossier passe tous les
# contrôles et juge l'index d'un dépôt étranger.
def cas_deux_depots():
    a1, aa1 = depot("py_x1", state=ENTETE_NUL)
    a2, _   = depot("py_x2", state=ENTETE_OK)
    b1, bb1 = depot("rs_x1", state=ENTETE_NUL)
    b2, _   = depot("rs_x2", state=ENTETE_OK)
    # on LANCE depuis a2 (dépôt sain) en déclarant l'agent de a1 (état cassé)
    ra = lance(["python3", PY], a2, aa1, "git commit -m x")
    rb = lance([RS, "mind-guard"], b2, bb1, "git commit -m x")
    na = json.loads(json.dumps(ra).replace(str(a1), "<1>").replace(str(a2), "<2>")) if ra else ra
    nb = json.loads(json.dumps(rb).replace(str(b1), "<1>").replace(str(b2), "<2>")) if rb else rb
    return na, nb

GEL  = temoins.gel_demande()
ARGV = ["python3", PY] if GEL else [RS, "mind-guard"]
# Le programme comparé doit avoir DÉMARRÉ avant qu'on juge quoi que ce soit :
# un lanceur mort rend une sortie qu'on confondrait avec un verdict (23/09/2026).
temoins.exige_que_ca_demarre(ARGV)
COTE = "py" if GEL else "rs"

def cas_deux_depots():
    """Réécrit pour un seul côté — voir le commentaire ci-dessus."""
    d1, a1 = depot(COTE + "_x1", state=ENTETE_NUL)
    d2, _  = depot(COTE + "_x2", state=ENTETE_OK)
    r = lance(ARGV, d2, a1, "git commit -m x")
    return json.loads(json.dumps(r).replace(str(d1), "<1>").replace(str(d2), "<2>")) if r else r

produit, refus, passages = {}, 0, 0
for nom, kw, cmd in CAS:
    d, agent = depot(COTE + "_" + nom.replace(" ", "_").replace("'", "").replace(".", ""), **kw)
    r = lance(ARGV, d, agent, cmd)
    if r is None: passages += 1
    else: refus += 1
    produit[nom] = json.loads(json.dumps(r).replace(str(d), "<RACINE>")) if r else None

produit["deux-depots"] = cas_deux_depots()

alertes = []
if not refus:
    alertes.append("TÉMOIN RATÉ — aucun refus : un garde qui laisse tout passer "
                   "se compare égal à un garde absent")
if not passages:
    alertes.append("TÉMOIN RATÉ — aucun passage : un garde qui refuse tout non plus")

MASQUE = [(str(BASE), "<bac>")]
if GEL:
    if alertes:
        raise SystemExit("GEL REFUSÉ :\n  " + "\n  ".join(alertes))
    cas = [(n, {"commande": c, "montage": {k: str(v) for k, v in kw.items()}}, produit[n])
           for n, kw, c in CAS]
    cas.append(("deux-depots", "lancé depuis un dépôt sain, agent déclaré dans un autre",
                produit["deux-depots"]))
    f = temoins.fige("mind-guard", cas, ("en-tête absent", "pas un commit"), [PY], MASQUE)
    print("témoin figé :", f)
    sys.exit(0)

ecarts, ligne = temoins.compare("mind-guard", produit, MASQUE)
ecarts = alertes + ecarts
print("%s · %d refus, %d passages" % (ligne, refus, passages))
print()
print("\n\n".join(ecarts) or "ÉCARTS : AUCUN sur %d cas + les deux dépôts — même verdict, même motif" % len(CAS))
sys.exit(1 if ecarts else 0)
