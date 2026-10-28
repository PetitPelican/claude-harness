"""CONTRÔLE SUR TÉMOIN — le résolveur de mémoire.

Il lisait LES ARBRES RÉELS de l'atelier. C'était son intérêt — les worktrees d'un
projet réel n'existent nulle part ailleurs, et c'est là qu'était le défaut du 08/09
(`--show-toplevel` au lieu de `--git-common-dir`). C'est aussi sa faiblesse, et
elle devient rédhibitoire au moment de figer :

- **un différentiel sur l'état vivant ne prouve que les chemins que le jour
  emprunte** — le 10/09, sept projets sur douze étaient passés à `brain/`, donc
  la forme ancienne n'était plus jouée que par hasard ;
- un témoin figé sur l'état vivant périmerait à la première migration, en
  silence, et il porterait les chemins d'agents qui ne sont pas à moi.

LE CORPUS EST DONC FABRIQUÉ, une forme par cas, et il porte NOMMÉMENT le cas
qui a produit le défaut : un arbre de travail git, dont la racine ne se lit
correctement qu'avec `--git-common-dir`.

CE QUE CE TÉMOIN NE COUVRE PAS, ET IL FAUT LE DIRE. Le résolveur Python ne
connaît QUE la forme déportée : sur un projet en place ou en `brain/`, il rend
`(None, None)` — mesuré le 10/09/2026. Neuf des dix cas ne prouvent donc que la
racine, l'arbre et le lot ; la mémoire elle-même n'est prouvée que sur la forme
déportée. Les formes `brain/` et en place sont couvertes ailleurs — par les
essais Rust et par le témoin du briefing —, jamais ici. Un témoin qui laisserait
croire le contraire serait pire qu'absent.

FIGÉ LE 10/09/2026 (lot 0) dans `temoins/memoire.json`. `--gel` le reproduit.
"""
import json, os, pathlib, shutil, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import temoins

S   = pathlib.Path(sys.argv[1])/"memoire"
RS  = os.environ.get("HARNAIS_BIN") or str(pathlib.Path.home()/"Agentic/claude-harnais/bin/harnais")
# Le programme comparé doit avoir DÉMARRÉ avant qu'on juge quoi que ce soit :
# un lanceur mort rend une sortie qu'on confondrait avec un verdict (23/09/2026).
temoins.exige_que_ca_demarre([RS])
PYH = pathlib.Path.home()/".claude/hooks/memoire.py"
GEL = temoins.gel_demande()

BASE  = "---\ncap: aller là-bas\n---\n\n## Nature\n"
ETAT  = "---\nmaj: 2026-09-10\nsante: verte\njalon: J\n---\n"
TODO  = "- [ ] une tâche\n"

def ecrire(p, t):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t)

def git(d, *a):
    return subprocess.run(["git", "-C", str(d)] + list(a), capture_output=True, text=True)

def depot(nom, avec_git=True):
    d = S/nom
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    if avec_git:
        git(d, "init", "-q", "-b", "main")
        git(d, "config", "user.name", "M"); git(d, "config", "user.email", "m@x")
    return d

def commit(d):
    ecrire(d/"README.md", "x\n"); git(d, "add", "-A"); git(d, "commit", "-q", "-m", "socle")

# ── LE CORPUS : une forme par cas, et rien qui vienne de l'atelier vivant ──
def monte():
    cas = {}

    d = depot("en-place")
    ecrire(d/".fact/base.md", BASE); ecrire(d/".mind/state.md", ETAT)
    ecrire(d/".mind/todo.md", TODO); commit(d)
    cas["en-place"] = d

    d = depot("brain")
    ecrire(d/"brain/fact/base.md", BASE); ecrire(d/"brain/mind/state.md", ETAT)
    ecrire(d/"brain/mind/todo.md", TODO); commit(d)
    cas["brain"] = d

    d = depot("deportee")
    ecrire(d/"memoire/.fact/base.md", BASE); ecrire(d/"memoire/.mind/state.md", ETAT)
    commit(d)
    cas["deportee"] = d

    d = depot("multi-agents")
    ecrire(d/".fact/base.md", BASE)
    for a in ("ios", "web"):
        ecrire(d/"agents"/a/".mind"/"state.md", ETAT)
        ecrire(d/"agents"/a/".mind"/"todo.md", TODO)
    commit(d)
    cas["multi-agents"] = d
    cas["multi-agents · dans un lot"] = d/"agents"/"ios"

    # LE CAS DU DÉFAUT DU 08/09 : un arbre de travail. Sa racine ne se lit
    # correctement qu'avec `--git-common-dir` ; `--show-toplevel` rend l'arbre
    # lui-même, et la mémoire part se chercher au mauvais endroit.
    d = depot("worktree-source")
    ecrire(d/".fact/base.md", BASE); ecrire(d/".mind/state.md", ETAT); commit(d)
    wt = S/"worktree-arbre"
    shutil.rmtree(wt, ignore_errors=True)
    git(d, "worktree", "add", "-q", "-b", "essai", str(wt))
    cas["arbre de travail"] = wt

    d = depot("ambigue")
    ecrire(d/".fact/base.md", BASE); ecrire(d/"brain/fact/base.md", BASE); commit(d)
    cas["ambiguë — les deux arbres"] = d

    d = depot("sans-faits")
    commit(d)
    cas["dépôt sans mémoire"] = d

    d = depot("hors-depot", avec_git=False)
    ecrire(d/".fact/base.md", BASE)
    cas["hors dépôt"] = d

    cas["chemin inexistant"] = S/"jamais-cree"
    return cas

CAS = monte()

def cote_python(d):
    sys.path.insert(0, str(pathlib.Path.home()/".claude/hooks"))
    import memoire as PY
    def s(p): return str(p) if p else None
    mind, fact = PY.pour_agent(d)
    pf, pe = PY.pour_projet(d)
    return {"racine_depot": s(PY.racine_depot(d)), "base": s(PY.base(d)),
            "base_projet": s(PY.base_projet(d)), "arbre": s(PY.arbre_courant(d)),
            "lot": PY._lot(d), "mind": s(mind), "fact": s(fact),
            "projet_fact": s(pf),
            "projet_etats": None if pe is None else [[n, str(m)] for n, m in pe]}

def cote_rust(d):
    e = dict(os.environ); e.pop("CLAUDE_PROJECT_DIR", None)
    r = subprocess.run([RS, "memoire", str(d)], capture_output=True, text=True, env=e)
    return json.loads(r.stdout) if r.returncode == 0 else {"ERREUR": r.stderr[:200]}

produit = {nom: (cote_python(d) if GEL else cote_rust(d)) for nom, d in CAS.items()}

# LE BAC EST CANONISÉ D'UN CÔTÉ ET PAS DE L'AUTRE : `/tmp` contre `/private/tmp`.
MASQUE = [("/private" + str(S), "<bac>"), (str(S), "<bac>")]

# TÉMOIN : au moins un cas doit rendre une résolution NON NULLE, sinon deux
# résolveurs qui rendent `null` partout se comparent égaux.
non_nuls = sum(1 for v in produit.values() if v.get("base") or v.get("mind"))
alertes = []
if not non_nuls:
    alertes.append("TÉMOIN RATÉ — aucune résolution non nulle : ce contrôle ne prouve rien")
if produit["chemin inexistant"].get("base"):
    alertes.append("TÉMOIN RATÉ — un chemin inexistant a rendu une mémoire")
# LE CAS DU DÉFAUT DU 08/09 DOIT SÉPARER LES DEUX REPÈRES. S'il ne les sépare
# plus, l'arbre de travail n'a pas été monté et ce contrôle a cessé de couvrir
# la seule chose qu'il couvrait de plus que les autres.
w = produit["arbre de travail"]
if w.get("racine_depot") == w.get("arbre"):
    alertes.append("TÉMOIN RATÉ — l'arbre de travail rend la même racine que son "
                   "arbre : le cas qui a produit le défaut du 08/09 n'est plus joué")

if GEL:
    if alertes:
        raise SystemExit("GEL REFUSÉ :\n  " + "\n  ".join(alertes))
    cas = [(n, "forme fabriquée", produit[n]) for n in produit]
    f = temoins.fige("memoire", cas, ("en-place", "chemin inexistant"), [PYH], MASQUE)
    print("témoin figé :", f)
    sys.exit(0)

ecarts, ligne = temoins.compare("memoire", produit, MASQUE)
ecarts = alertes + ecarts
print("%s · %d formes, %d résolutions non nulles" % (ligne, len(CAS), non_nuls))
print()
print("\n\n".join(ecarts) or "ÉCARTS : AUCUN — le résolveur rend le témoin sur les %d formes" % len(CAS))
sys.exit(1 if ecarts else 0)
