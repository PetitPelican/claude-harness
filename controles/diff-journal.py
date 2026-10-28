"""CONTRÔLE SUR TÉMOIN — le hook journal.

Il était différentiel : Python et Rust jouaient les mêmes cas côte à côte. Le
10/09/2026 (lot 0) sa moitié Python a été FIGÉE dans `temoins/journal.json` —
le jour où l'interpréteur part, elle ne se régénère plus. `--gel` la reproduit,
et c'est le seul mode qui appelle encore `python3`.

TÉMOIN POSITIF, conservé et déplacé : on exige que le programme écrive VRAIMENT
dans les trois cas qui doivent écrire, et rien dans le quatrième. Sans lui,
deux programmes qui ne font rien se comparent égaux — c'est le faux succès
qu'on a eu sur le premier hook porté.

LE JOUR ET L'HEURE SONT MASQUÉS. Le journal nomme son fichier d'après la date :
sans masque, ce témoin cesserait de valoir à minuit.
"""
import json, os, re, shutil, subprocess, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import temoins

BASE = pathlib.Path(sys.argv[1])/"journal"
PY   = pathlib.Path.home()/".claude/hooks/journal.py"
RS   = pathlib.Path(os.environ.get("HARNAIS_BIN") or str(pathlib.Path.home()/"Agentic/claude-harnais/bin/harnais"))
GEL  = temoins.gel_demande()
ARGV = ["python3", str(PY)] if GEL else [str(RS), "journal"]
# Le programme comparé doit avoir DÉMARRÉ avant qu'on juge quoi que ce soit :
# un lanceur mort rend une sortie qu'on confondrait avec un verdict (23/09/2026).
temoins.exige_que_ca_demarre(ARGV)
COTE = "py" if GEL else "rs"

def depot(nom, sous=None):
    d = BASE/nom
    shutil.rmtree(d, ignore_errors=True)
    (d/"src").mkdir(parents=True)
    if sous: (d/sous).mkdir(parents=True, exist_ok=True)
    g = lambda *a: subprocess.run(["git","-C",str(d)]+list(a), capture_output=True, text=True)
    g("init","-q","-b","main")
    g("config","user.name","Alex Martin"); g("config","user.email","m@x")
    (d/"src/a.rs").write_text("un\n"); (d/"src/b.rs").write_text("deux\n")
    (d/".logs").mkdir(exist_ok=True); (d/".logs/vieux.md").write_text("x\n")
    g("add","-A"); g("commit","-q","-m","Un sujet de commit")
    return d

def lance(d, cmd, env_sup):
    e = dict(os.environ); e.pop("CLAUDE_PROJECT_DIR", None); e.update(env_sup)
    entree = json.dumps({"tool_name":"Bash","tool_input":{"command":cmd},"session_id":"s1"})
    return subprocess.run(ARGV, cwd=str(d), input=entree, capture_output=True, text=True, env=e)

def logs(d):
    return {p.name: p.read_text() for p in sorted((d/".logs").glob("*.md")) if p.name != "vieux.md"}

def normalise(t):
    """L'heure, l'empreinte du commit et LE JOUR ne se figent pas."""
    t = re.sub(r"## \d\d:\d\d · `[0-9a-f]+`", "## HH:MM · `HASH`", t)
    t = re.sub(r"\d{4}-\d\d-\d\d", "<jour>", t)
    return t

CAS = [
  ("commit-simple",  "git commit -m 'x'",          {}),
  ("reecriture",     "git commit --amend -m 'x'",  {}),
  ("hors-commit",    "git status",                 {}),
  ("multi-agents",   "git commit -m 'x'",          {"__AGENT": "agents/Alpha PO"}),
]

produit, alertes = {}, []
for nom, cmd, sup in CAS:
    sous = dict(sup).pop("__AGENT", None)
    d = depot(COTE + "_" + nom, sous)
    env = {k: v for k, v in sup.items() if k != "__AGENT"}
    if sous:
        env["CLAUDE_PROJECT_DIR"] = str(d/sous)
    r = lance(d, cmd, env)
    l = {normalise(k): normalise(v) for k, v in logs(d).items()}
    produit[nom] = {"journal": l, "code": r.returncode}
    doit_ecrire = (nom != "hors-commit")
    if doit_ecrire and not any(l.values()):
        alertes.append("TÉMOIN POSITIF RATÉ — %s : rien écrit (rc=%d %s)"
                       % (nom, r.returncode, r.stderr[:120]))
    if not doit_ecrire and l:
        alertes.append("TÉMOIN NÉGATIF RATÉ — %s : a écrit alors qu'il ne devait pas" % nom)

# DOUBLON : rejouer le même hook deux fois ne doit produire qu'une entrée.
d = depot(COTE + "_doublon")
lance(d, "git commit -m x", {}); un = logs(d)
lance(d, "git commit -m x", {}); deux = logs(d)
produit["doublon"] = {"une-fois": {normalise(k): normalise(v) for k, v in un.items()},
                      "deux-fois-identique": un == deux}
if not any(un.values()):
    alertes.append("TÉMOIN POSITIF RATÉ — doublon : rien écrit au premier appel")
if un != deux:
    alertes.append("DOUBLON — le second appel a écrit une seconde entrée")

MASQUE = [(str(BASE), "<bac>")]
if GEL:
    if alertes:
        raise SystemExit("GEL REFUSÉ — le côté Python ne tient pas ses propres "
                         "témoins :\n  " + "\n  ".join(alertes))
    cas = [(n, {"commande": c, "agent": bool(s.get("__AGENT"))}, produit[n]) for n, c, s in CAS]
    cas.append(("doublon", "deux appels identiques", produit["doublon"]))
    f = temoins.fige("journal", cas, ("commit-simple", "hors-commit"), [PY], MASQUE)
    print("témoin figé :", f)
    sys.exit(0)

ecarts, ligne = temoins.compare("journal", produit, MASQUE)
ecarts = alertes + ecarts
print(ligne)
print()
print("\n\n".join(ecarts) or "ÉCARTS : AUCUN — le Rust rend le témoin à l'octet")
sys.exit(1 if ecarts else 0)
