"""LA RÉTRO-PROPAGATION, qu'aucun des dix-neuf cas ne touchait.

`resultat()` ne fait quelque chose que si `~/.claude/projects/<chemin
slugifié>/memory/.usage.json` existe ET porte un registre de lecture pour la
session. La clé est le CHEMIN : un bac à sable n'en a pas, donc le mécanisme
restait éteint des deux côtés — et une comparaison qui ne traverse jamais un
chemin de code ne dit rien de ce chemin.

Trois verdicts à couvrir, et ce sont trois multiplicateurs différents :
  · une garde qui mord      → échec MINEUR (0,92)
  · un constat qui TIENT    → succès (1,03)
  · deux TOMBÉ consécutifs  → échec (0,90)

FIGÉ LE 10/09/2026 (lot 0) dans `temoins/attente-mem.json`. `--gel` le
reproduit.

On fabrique donc la mémoire à l'adresse du bac, on lance, on compare le fichier
à l'octet, et on retire tout à la fin.
"""
import json, os, re, shutil, subprocess, pathlib, sys, datetime, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import temoins

S = pathlib.Path(sys.argv[1])/"attmem"
shutil.rmtree(S, ignore_errors=True); S.mkdir(parents=True)
FAUX = str(pathlib.Path(__file__).resolve().parent/"faux-bin")
PY = str(pathlib.Path.home()/".claude/hooks/attente.py")
RS = os.environ.get("HARNAIS_BIN") or str(pathlib.Path.home()/"Agentic/claude-harnais/bin/harnais")
AUJ = datetime.date.today().isoformat()
T0 = 1700000000
cree = []

def bac(cote, nom, todo, niveaux, code=False):
    base = S/(cote+"_"+nom); base.mkdir(parents=True)
    d = base/"projet"; d.mkdir()
    data = base/"data"; (data/"attente").mkdir(parents=True)
    (data/"rechutes.md").write_text("# x\n\n- **une ligne**\n")
    g = lambda *a: subprocess.run(["git","-C",str(d)]+list(a), capture_output=True, text=True)
    g("init","-q","-b","main"); g("config","user.name","M"); g("config","user.email","m@x")
    for p, t in ((d/".fact/base.md", "---\ncap: c\n---\n"),
                 (d/".mind/state.md", "---\nmaj: %s\nsante: v\njalon: J\n---\n" % AUJ),
                 (d/".mind/todo.md", todo), (d/"src/a.ts", "const a = 1\n")):
        p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t)
    g("add","-A"); g("commit","-q","-m","socle")
    if code:
        (d/"src/a.ts").write_text("const a = 2\n")
        os.utime(d/"src/a.ts", (T0+10, T0+10))
    os.utime(d/".mind/todo.md", (T0, T0))
    # la mémoire auto, à l'ADRESSE du bac
    # LA CLÉ EST CELLE QUE CLAUDE CODE ÉCRIT : un tiret par caractère non
    # alphanumérique, jamais fondus. Elle effondrait les séparateurs consécutifs
    # jusqu'au 10/09/2026, pour rester identique au repli Python — repli supprimé
    # depuis. Un bac à sable sous un dossier jetable profond porte des tirets
    # consécutifs : ce contrôle fabriquait donc sa mémoire à une adresse où le
    # programme corrigé ne regarde plus.
    slug = "".join(c if c.isalnum() and c.isascii() else "-"
                   for c in str(d.resolve()))
    mem = pathlib.Path.home()/".claude/projects"/slug/"memory"
    mem.mkdir(parents=True); cree.append(mem.parent)
    u = {"_depuis": AUJ, "_encours": {"sess-1": list(niveaux)}}
    for n, niv in niveaux.items() if isinstance(niveaux, dict) else []:
        pass
    for n in niveaux:
        (mem/(n+".md")).write_text("# %s\n\n> **%s** · 09/09/2026 — parce que\n" % (n, niveaux[n]))
        u[n] = {"vu": AUJ, "n": 2}
    (mem/".usage.json").write_text(json.dumps(u, ensure_ascii=False, indent=1, sort_keys=True))
    return d, data, mem

def lance(argv, d, data):
    fx = data/"rappels.json"; fx.write_text(json.dumps({}))
    jl = data/"appels.log"; jl.write_text("")
    e = dict(os.environ); e["PATH"] = FAUX + ":" + e["PATH"]
    e["CLAUDE_PLUGIN_DATA"] = str(data); e["CLAUDE_PROJECT_DIR"] = str(d)
    e["FAUX_RAPPELS"] = str(fx); e["FAUX_JOURNAL"] = str(jl)
    # AUCUN VRAI JUGE PENDANT LES CONTRÔLES : sans ça chaque passage
    # lancerait une douzaine dappels reels, et consommerait le plafond
    # journalier du relecteur avec des bacs a sable.
    e["HARNAIS_RELECTURE_SIMULEE"] = "1"
    e.pop("CLAUDE_PLUGIN_ROOT", None)
    r = subprocess.run(argv, cwd=str(d), input=json.dumps({"session_id":"sess-1"}),
                       capture_output=True, text=True, env=e)
    return r.returncode, r.stderr

NIVEAUX = {"note-mesuree": "mesuré", "note-supposee": "supposé", "note-dite": "dit"}
TODO_OK = ("- [ ] !haut @user **Une question ? oui / non**\n      oui → ceci.\n"
           "      non → cela.\n      fini quand → tu vois.\n")
TODO_TIENT = ("- [ ] !haut @user ?constat **La page manque ? oui / non**\n      oui → ceci.\n"
              "      non → cela.\n      fini quand → tu vois.\n"
              "      ↻ machine :: echo ATTENDU :: ^ATTENDU$\n")

CAS = [("garde qui mord", dict(todo=TODO_OK, niveaux=NIVEAUX, code=True)),
       ("constat qui tient", dict(todo=TODO_TIENT, niveaux=NIVEAUX))]

GEL  = temoins.gel_demande()
# MÊME DÉFAUT QUE `diff-attente.py`, MÊME CORRECTION — 23/09/2026. Le repli
# Python a été retiré du poste le 10/09 ; le gel l'appelait encore, `python3
# <fichier absent>` sort en code 2, et un code 2 se lit ici comme un BLOCAGE.
# L'échec de l'instrument était le sosie de son succès. La référence est le
# PROGRAMME, et on exige qu'il réponde avant de juger.
ARGV = [RS, "attente"]
_v = subprocess.run([RS, "version"], capture_output=True, text=True)
if _v.returncode != 0 or not _v.stdout.strip():
    raise SystemExit("CONTRÔLE IMPOSSIBLE : le programme de référence ne répond "
                     "pas à `version` (%s). Rien n'a été jugé ni figé." % RS)
COTE = "py" if GEL else "rs"

produit, alertes, bouge = {}, [], 0
for nom, kw in CAS:
    d, data, mem = bac(COTE, re.sub(r"\W+", "_", nom), **kw)
    avant = (mem/".usage.json").read_text()
    code, _ = lance(ARGV, d, data)
    apres = (mem/".usage.json").read_text()
    if apres != avant:
        bouge += 1
    else:
        alertes.append("TÉMOIN RATÉ — [%s] la rétro-propagation n'a RIEN bougé : "
                       "ce contrôle ne dit rien d'elle." % nom)
    produit[nom] = {"code": code, "usage": apres}

MASQUE = [(str(S), "<bac>"), (AUJ, "<auj>")]
if GEL:
    if alertes:
        for m in cree: shutil.rmtree(m, ignore_errors=True)
        raise SystemExit("GEL REFUSÉ :\n  " + "\n  ".join(alertes))
    cas = [(n, {"todo": kw["todo"], "code_touche": bool(kw.get("code"))}, produit[n])
           for n, kw in CAS]
    f = temoins.fige("attente-mem", cas, ("garde qui mord", "constat qui tient"),
                     [RS], MASQUE, origine="rust")
    for m in cree: shutil.rmtree(m, ignore_errors=True)
    print("témoin figé :", f)
    sys.exit(0)

ecarts, ligne = temoins.compare("attente-mem", produit, MASQUE)
ecarts = alertes + ecarts
print("%s · %d/%d cas ont fait bouger la confiance" % (ligne, bouge, len(CAS)))
print()
print("\n\n".join(ecarts) or "ÉCARTS : AUCUN — mêmes chiffres, même fichier à l'octet")
for m in cree:
    shutil.rmtree(m, ignore_errors=True)
sys.exit(1 if ecarts else 0)
