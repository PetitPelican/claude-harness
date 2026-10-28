#!/usr/bin/env python3
"""REFAIT LES NEUF TÉMOINS FIGÉS — le seul geste qui appelle encore `python3`.

    python3 controles/geler-les-temoins.py [<dossier de travail>]

C'EST UN GESTE QU'ON NE POURRA PLUS FAIRE — mais il faut pouvoir le faire
ENCORE UNE FOIS. Il lance les hooks Python dans `~/.claude/hooks/` et garde
leurs sorties dans `controles/temoins/`.

Le lot 1 a supprimé ces fichiers. Le programme les REMET donc lui-même, depuis
le commit qui les a effacés, le temps du gel, et les retire ensuite — le poste
retrouve l'état où plus aucun Python n'existe.

C'est la leçon du 11/09 : un témoin s'est révélé fragile à l'heure de la
journée, et le seul geste capable de le refaire ne démarrait plus. Un témoin
irremplaçable et un moyen de le refaire qui a cessé de marcher, c'est la même
chose qu'aucun témoin. La restauration échoue bruyamment si l'historique ne
porte plus les fichiers : il ne doit pas y avoir de façon discrète de perdre la
référence.

Chaque témoin refuse de se figer si le côté Python ne tient pas ses propres
témoins positifs et négatifs. Un témoin produit par un programme qui ne fait
rien vaut moins que pas de témoin du tout : il rassure.
"""
import pathlib, shutil, subprocess, sys

ICI = pathlib.Path(__file__).resolve().parent
DEPOT = ICI.parent
HOOKS = pathlib.Path.home() / ".claude" / "hooks"
EFFACEMENT = "9011282"   # « Lot 1 : le repli Python part, et son absence se DIT »

S = sys.argv[1] if len(sys.argv) > 1 else "/tmp/gel-temoins"
pathlib.Path(S).mkdir(parents=True, exist_ok=True)


def _git(*a):
    return subprocess.run(["git", *a], cwd=str(DEPOT), capture_output=True, text=True)


def restaure_les_hooks():
    """Repose les hooks Python là où les différentiels les cherchent.

    Rend True si c'est nous qui les avons posés — donc à nous de les retirer.
    Si le dossier existait déjà, on n'y touche pas et on ne l'efface pas : un
    geste de mesure ne détruit pas ce qu'il n'a pas créé.
    """
    if HOOKS.exists():
        print("hooks déjà en place — laissés tels quels")
        return False
    r = _git("show", "%s^:hooks" % EFFACEMENT)
    if r.returncode != 0:
        raise SystemExit("HISTORIQUE MUET — `hooks/` introuvable avant %s. "
                         "La référence ne peut plus être refaite : ne rien "
                         "figer, et le dire." % EFFACEMENT)
    noms = [l.strip() for l in r.stdout.splitlines() if l.strip().endswith(".py")]
    if not noms:
        raise SystemExit("HISTORIQUE VIDE — aucun .py avant %s." % EFFACEMENT)
    HOOKS.mkdir(parents=True)
    for n in noms:
        c = _git("show", "%s^:hooks/%s" % (EFFACEMENT, n))
        if c.returncode != 0:
            raise SystemExit("HOOK ILLISIBLE — %s" % n)
        (HOOKS / n).write_text(c.stdout)
    print("%d hook(s) Python reposé(s) depuis %s^ — temporairement"
          % (len(noms), EFFACEMENT))
    return True


A_RETIRER = restaure_les_hooks()

T = ["diff-usage.py", "diff-journal.py", "diff-memoire.py", "diff-mindguard.py",
     "diff-carnet.py", "diff-briefing.py", "diff-briefing-mem.py",
     "diff-attente.py", "diff-attente-memoire.py"]

rates = []
for f in T:
    r = subprocess.run([sys.executable, str(ICI/f), S, "--gel"],
                       capture_output=True, text=True)
    ok = r.returncode == 0
    print("%-26s %s" % (f, "figé" if ok else "REFUSÉ"))
    if not ok:
        rates.append(f)
        print("   " + (r.stdout + r.stderr).strip().replace("\n", "\n   ")[:900])

if A_RETIRER:
    shutil.rmtree(HOOKS, ignore_errors=True)
    print("hooks Python retirés — le poste n'en porte plus aucun")

print()
if rates:
    print("%d témoin(s) NON figé(s) : %s" % (len(rates), ", ".join(rates)))
    sys.exit(1)
n = len(list((ICI/"temoins").glob("*.json")))
print("%d témoins dans %s" % (n, ICI/"temoins"))
