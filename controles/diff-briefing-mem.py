"""La branche que les douze cas précédents ne touchaient PAS : la ligne
« mémoire à ranger ».

Elle ne s'allume que si `~/.claude/projects/<chemin slugifié>/memory/` existe —
la clé est le CHEMIN, donc un projet copié dans le scratchpad n'a pas de
mémoire, et la branche restait éteinte des deux côtés. Une comparaison qui ne
touche jamais un chemin de code ne dit rien de ce chemin.

FIGÉ LE 10/09/2026 (lot 0) : le côté Python vit dans `temoins/briefing-mem.json`,
`--gel` le reproduit. Les dates sont masquées une par une — `<auj>`, `<auj-40>` —
pour qu'un témoin daté ne cesse pas de valoir à minuit sans qu'un chiffre faux
puisse s'y cacher.

On fabrique donc la mémoire À L'ADRESSE du bac à sable, avec un ménage vieux de
40 jours et des notes jamais servies. Elle est retirée à la fin.
"""
import json, os, re, shutil, subprocess, pathlib, sys, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import temoins

S = pathlib.Path(sys.argv[1])/"bfmem"
shutil.rmtree(S, ignore_errors=True); S.mkdir(parents=True)
PY = str(pathlib.Path.home()/".claude/hooks/briefing.py")
RS = os.environ.get("HARNAIS_BIN") or str(pathlib.Path.home()/"Agentic/claude-harnais/bin/harnais")
AUJ = datetime.date.today()

d = S/"projet"; d.mkdir()
g = lambda *a: subprocess.run(["git","-C",str(d)]+list(a), capture_output=True, text=True)
g("init","-q","-b","main"); g("config","user.name","M"); g("config","user.email","m@x")
(d/".fact").mkdir(); (d/".mind").mkdir()
(d/".fact/base.md").write_text("---\ncap: un cap\n---\n\n## Nature\n")
(d/".mind/state.md").write_text(f"---\nmaj: {AUJ.isoformat()}\nsante: verte\njalon: J\n---\n")
(d/".mind/todo.md").write_text("- [ ] @user **Une question ? 1 / 2**\n")
g("add","-A"); g("commit","-q","-m","socle")

# LA CLÉ EST CELLE QUE CLAUDE CODE ÉCRIT : un tiret par caractère non
# alphanumérique, jamais fondus. Elle effondrait les séparateurs consécutifs
# jusqu'au 10/09/2026, pour rester identique au repli Python — repli supprimé
# depuis. Un bac à sable sous un dossier jetable profond porte des tirets
# consécutifs : ce contrôle fabriquait donc sa mémoire à une adresse où le
# programme corrigé ne regarde plus.
slug = "".join(c if c.isalnum() and c.isascii() else "-"
               for c in str(d.resolve()))
mem = pathlib.Path.home()/".claude/projects"/slug/"memory"
shutil.rmtree(mem.parent, ignore_errors=True); mem.mkdir(parents=True)
for i in range(5):
    (mem/f"note-{i}.md").write_text(f"# note {i}\n")
(mem/"MEMORY.md").write_text("- index\n")
vieux = (AUJ - datetime.timedelta(days=40)).isoformat()
usage = {"_depuis": vieux, "_menage": vieux,
         "note-0": {"vu": AUJ.isoformat(), "n": 3},
         "note-1": {"vu": vieux, "n": 1},
         "note-2": {"epingle": True, "vu": vieux, "n": 1}}
ref = json.dumps(usage, ensure_ascii=False, indent=1, sort_keys=True)
(mem/".usage.json").write_text(ref)

def lance(argv):
    e = dict(os.environ); e["CLAUDE_PROJECT_DIR"] = str(d)
    e.pop("CLAUDE_PLUGIN_DATA", None)
    entree = json.dumps({"hook_event_name": "SessionStart", "cwd": str(d),
                         "session_id": "s"})
    r = subprocess.run(argv, cwd=str(d), input=entree, capture_output=True, text=True, env=e)
    try:    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    except Exception: return None

GEL  = temoins.gel_demande()
ARGV = ["python3", PY] if GEL else [RS, "briefing"]
# Le programme comparé doit avoir DÉMARRÉ avant qu'on juge quoi que ce soit :
# un lanceur mort rend une sortie qu'on confondrait avec un verdict (23/09/2026).
temoins.exige_que_ca_demarre(ARGV)

a = lance(ARGV)
apres = (mem/".usage.json").read_bytes().decode("utf-8")

MASQUE = [(str(S), "<bac>"), (slug, "<slug>"), (vieux, "<auj-40>"),
          (AUJ.isoformat(), "<auj>")]
ligne_mem = [x for x in (a or "").splitlines() if x.startswith("mémoire:")]
alertes = []
if not ligne_mem:
    alertes.append("TÉMOIN RATÉ — la branche « mémoire à ranger » ne s'est PAS "
                   "allumée : ce contrôle ne dit rien d'elle.")

produit = {"briefing-servi": a or "(aucun)", "usage-reecrit": apres}

if GEL:
    if alertes:
        shutil.rmtree(mem.parent, ignore_errors=True)
        raise SystemExit("GEL REFUSÉ :\n  " + "\n  ".join(alertes))
    cas = [("briefing-servi", "mémoire fabriquée : 5 notes, ménage vieux de 40 j",
            produit["briefing-servi"]),
           ("usage-reecrit", "le registre après passage du hook",
            produit["usage-reecrit"])]
    f = temoins.fige("briefing-mem", cas, ("briefing-servi", "usage-reecrit"),
                     [PY], MASQUE)
    shutil.rmtree(mem.parent, ignore_errors=True)
    print("témoin figé :", f)
    sys.exit(0)

# ── LE NOM DU CURATEUR A CHANGÉ, ET C'EST UNE DIVERGENCE DATÉE ──────────────
# Le 11/09/2026 le curateur entre dans le paquet (décision du commanditaire, après un
# audit) : le briefing cite `harnais curateur`, qui existe partout, au lieu de
# `claude-memoire`, qui n'existait que sur ce Mac. Le témoin porte l'ancien
# nom : on le remplace de SON côté seulement, et on exige que le remplacement
# ait eu lieu — un témoin qui ne porterait plus l'ancien nom voudrait dire
# qu'on a refigé sans retirer ceci.
ANCIEN, NOUVEAU = "`claude-memoire` pour voir", "`harnais curateur` pour voir"
_renomme = [0]
# LA DIVERGENCE VOULUE DU 12/10/2026 — `workflow.md` pour tous (décision du commanditaire : « on
# doit intégrer un fichier workflow.md dans le folder fact aussi, pour tous les
# agents »). Le briefing l'annonce partout, ABSENT quand il manque, ce que le
# témoin figé ne faisait pas. Retirée du RENDU seulement, comme dans
# `diff-briefing.py` ; et elle doit l'avoir été au moins une fois.
WORKFLOW = re.compile(r"^ {2,}\S*workflow\.md .*\n(?: {6}\S.*\n)?", re.M)
_workflow = [0]
def renomme(x, cote):
    if cote == "temoin" and ANCIEN in x:
        _renomme[0] += 1
        return x.replace(ANCIEN, NOUVEAU)
    if cote != "temoin" and isinstance(x, str):
        x, n = WORKFLOW.subn("", x)
        _workflow[0] += n
    return x

ecarts, ligne = temoins.compare("briefing-mem", produit, MASQUE, renomme)
if not _renomme[0]:
    ecarts.append("DIVERGENCE DÉCLARÉE SANS OBJET — le témoin ne cite plus "
                  "`claude-memoire` : retirer le renommage de ce contrôle.")
if not _workflow[0]:
    ecarts.append("DIVERGENCE DÉCLARÉE SANS OBJET — le rendu n'annonce plus "
                  "`workflow.md` : retirer cette exception.")
ecarts = alertes + ecarts
print("%s · %s" % (ligne, ligne_mem[0] if ligne_mem else "AUCUNE ligne mémoire"))
print()
print("\n\n".join(ecarts) or "ÉCARTS : AUCUN — même ligne servie, même registre réécrit")
shutil.rmtree(mem.parent, ignore_errors=True)
sys.exit(1 if ecarts else 0)
