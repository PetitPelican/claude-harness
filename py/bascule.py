# -*- coding: utf-8 -*-
"""`harnais bascule` — BRANCHER UN AGENT SUR LE PAQUET, SANS LUI RETIRER SES GARDES.

Port de `harnais/src/bascule.rs` (Rust, 0.12.8).

POURQUOI CETTE SOUS-COMMANDE EXISTE, ET CE QU'ELLE RÉPARE. La recette d'avant
disait « retire tout le bloc `hooks`, déclare le paquet ». Elle était juste
pour six projets sur douze — ceux qui n'ont aucun garde propre — et FAUSSE
pour un projet dont deux hooks ne sont pas du harnais : `guard-branche.py`, qui
tient l'agent dans son arbre de travail, et `guard-base-prod.py`, le seul
qui empêche d'écrire dans la vraie base. Les trois agents de ce projet ont
refusé cette recette le 10/09/2026, et les trois avaient raison.

**La frontière n'est pas un langage, c'est une PROPRIÉTÉ** — tranchée par le
commanditaire le même jour : ce qui est partagé par tous les projets vit dans
le paquet ; ce qui protège UN projet vit dans ce projet, et son langage est le
sien. Cette sous-commande est l'exécution de cette phrase.

CE QU'ELLE RETIRE : les hooks du harnais, reconnus par le NOM EXACT de leur
fichier — jamais par une sous-chaîne. `journal.py` est du harnais ;
`journal-metier.py` ne l'est pas, et un test sur `"journal" in cmd` aurait
emporté le second avec le premier. Le doute se tranche toujours du même côté :
**ce qu'on ne reconnaît pas, on le GARDE**, et on le dit.

CE QU'ELLE NE TOUCHE PAS : `permissions` — périmètres, `deny`, dossiers
supplémentaires — et toute autre clé du fichier. L'ordre des clés est
préservé (dict Python), donc le diff ne montre que le geste.

Blanc par défaut. `--apply` pour écrire.
"""
import copy
import json
import os

V = "\x1b[32m"
R = "\x1b[31m"
J = "\x1b[33m"
D = "\x1b[2m"
X = "\x1b[0m"

# LES FICHIERS DU HARNAIS, PAR NOM EXACT. Cette liste est la définition de
# « partagé » : tout ce qui n'y est pas appartient au projet. L'allonger revient
# à retirer un garde à quelqu'un — ne le faire qu'en le sachant.
NOMS_HARNAIS = [
    "briefing.py", "attente.py", "journal.py", "usage.py",
    "mind-guard.py", "carnet.py", "memoire.py", "relecture.py",
]

MARCHE = "atelier"
PAQUET = "harnais@atelier"
DEPOT = "PetitPelican/claude-harness"


class Nature(object):
    """Les trois sortes de commande de hook. Chaque valeur est un couple
    `(sorte, détail)` : Harnais(fichier reconnu) · Paquet · Projet(ON GARDE)."""
    @staticmethod
    def Harnais(f):
        return ("Harnais", f)     # le fichier reconnu

    Paquet = ("Paquet", None)     # déjà servi par le paquet

    @staticmethod
    def Projet(f):
        return ("Projet", f)      # propre au projet — ON GARDE


def _alnum(c):
    # `char::is_alphanumeric` du Rust (Alphabetic ou Numeric).
    return c.isalnum()


def nature(cmd):
    """La nature d'une commande de hook. Le nom de fichier décide, pas le chemin."""
    if "CLAUDE_PLUGIN_ROOT" in cmd:
        return Nature.Paquet
    # Tous les `*.py` cités, comparés par NOM EXACT.
    vus = []
    o = list(cmd)
    i = 0
    n = len(o)
    while i < n:
        if o[i:i + 3] == [".", "p", "y"]:
            d = i
            while d > 0:
                c = o[d - 1]
                if _alnum(c) or c == "_" or c == "-":
                    d -= 1
                else:
                    break
            if d < i:
                vus.append("".join(o[d:i + 3]))
        i += 1
    for f in vus:
        if f in NOMS_HARNAIS:
            return Nature.Harnais(f)
    return Nature.Projet(vus[0] if vus else cmd[:30])


class Bilan(object):
    def __init__(self):
        self.retires = []
        self.gardes = []
        self.deja = False


def _get(v, cle):
    """`Value::get(&str)` de serde_json : None sur tout ce qui n'est pas un objet."""
    return v.get(cle) if isinstance(v, dict) else None


def _swap_remove(d, cle):
    """`Map::remove` de serde_json avec `preserve_order` est un `swap_remove` :
    la DERNIÈRE clé prend la place de celle qu'on retire (mesuré sur le Rust
    0.12.8 : `permissions`, dernière, remonte en tête quand `hooks` disparaît).
    Un `dict.pop` ordinaire décalerait tout le reste, et le fichier écrit ne
    serait plus le même octet."""
    if cle not in d:
        return
    ordre = list(d)
    i = ordre.index(cle)
    dernier = ordre.pop()
    if i < len(ordre):
        ordre[i] = dernier
    valeurs = dict(d)
    d.clear()
    for k in ordre:
        d[k] = valeurs[k]


def trie(d):
    """Réécrit le bloc `hooks` en ne gardant que ce qui appartient au projet."""
    b = Bilan()
    anciens = d.get("hooks")
    if not isinstance(anciens, dict):
        b.deja = True
        return b
    neufs = {}
    for ev, blocs in list(anciens.items()):
        if not isinstance(blocs, list):
            continue
        gardes_ev = []
        for bloc in blocs:
            hs = _get(bloc, "hooks")
            if not isinstance(hs, list):
                hs = []
            gardes_bloc = []
            for h in hs:
                cmd = _get(h, "command")
                if not isinstance(cmd, str):
                    cmd = ""
                nat = nature(cmd)
                if nat[0] == "Harnais":
                    b.retires.append("%s:%s" % (ev, nat[1]))
                elif nat[0] == "Paquet":
                    b.retires.append("%s:(déjà le paquet)" % ev)
                else:
                    b.gardes.append("%s:%s" % (ev, nat[1]))
                    gardes_bloc.append(h)
            # UN BLOC VIDÉ DISPARAÎT, il ne reste pas en coquille : un `matcher`
            # sans hook se lit comme un dispositif en place.
            if gardes_bloc:
                nb = dict(bloc) if isinstance(bloc, dict) else {}
                nb["hooks"] = gardes_bloc
                gardes_ev.append(nb)
        if gardes_ev:
            neufs[ev] = gardes_ev
    if not neufs:
        _swap_remove(d, "hooks")
    else:
        d["hooks"] = neufs
    return b


def declare(d):
    """Déclare le marché et le paquet, sans écraser ce qui est déjà là."""
    if "extraKnownMarketplaces" not in d:
        d["extraKnownMarketplaces"] = {}
    m = d["extraKnownMarketplaces"]
    if isinstance(m, dict):
        if MARCHE not in m:
            m[MARCHE] = {"source": {"source": "github", "repo": DEPOT}}
    if "enabledPlugins" not in d:
        d["enabledPlugins"] = {}
    p = d["enabledPlugins"]
    if isinstance(p, dict):
        p[PAQUET] = True


def reglage(agent):
    return os.path.join(agent, ".claude", "settings.json")


def _file_name(p):
    """`Path::file_name` : le dernier composant, ou None (`..`, `.`, `/`, vide)."""
    comps = [c for c in p.replace("\\", "/").split("/") if c not in ("", ".")]
    if not comps or comps[-1] == "..":
        return None
    return comps[-1]


def _erreur_io(e):
    # Le texte de `io::Error` du Rust : « Permission denied (os error 13) ».
    if isinstance(e, UnicodeDecodeError):
        return "stream did not contain valid UTF-8"
    return "%s (os error %s)" % (e.strerror or "erreur", e.errno)


def _refuse_constante(nom):
    raise ValueError(nom)


def _entier(s):
    # serde_json lit `-0` comme le flottant -0.0 (et l'écrit « -0.0 »).
    return -0.0 if s == "-0" else int(s)


def _lire_json(texte):
    return json.loads(texte, parse_constant=_refuse_constante, parse_int=_entier)


def main(args):
    appliquer = "--apply" in args
    cibles = [a for a in args if not a.startswith("--")]
    if not cibles:
        cibles = [os.getcwd()]

    print("\n  %sBASCULE VERS LE PAQUET%s   %s%d agent(s)%s"
          % ("\x1b[1m", X, D, len(cibles), X))

    faits = sautes = rates = 0
    total_gardes = 0
    for c in cibles:
        f = reglage(c)
        nom = _file_name(c) or c
        if not os.path.isfile(f):
            print("  %s·%s %-30s aucun settings.json" % (D, X, nom))
            sautes += 1
            continue
        try:
            with open(f, "rb") as h:
                brut = h.read().decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print("  %s✗%s %-30s illisible : %s" % (R, X, nom, _erreur_io(e)))
            rates += 1
            continue
        try:
            d = _lire_json(brut)
        except ValueError:
            d = None
        if not isinstance(d, dict):
            print("  %s✗%s %-30s JSON illisible" % (R, X, nom))
            rates += 1
            continue

        t = copy.deepcopy(d)
        avant_gardes = len(trie(t).gardes)
        b = trie(d)
        p = _get(d, "enabledPlugins")
        deja_paquet = isinstance(p, dict) and PAQUET in p
        declare(d)

        if not b.retires and deja_paquet:
            print("  %s·%s %-30s déjà sur le paquet · %d garde(s) propre(s) intact(s)"
                  % (D, X, nom, len(b.gardes)))
            total_gardes += len(b.gardes)
            sautes += 1
            continue

        # LE TÉMOIN QUI COMPTE, et c'est celui que la recette d'avant n'avait
        # pas : le nombre de gardes PROPRES doit être le même après qu'avant.
        # Une bascule qui en perd un ne se voit nulle part — le réglage a l'air
        # plus propre, et la barrière qui protège la Production a disparu.
        if len(b.gardes) != avant_gardes:
            print("  %s✗%s %-30s %d garde(s) propre(s) avant, %d après — RIEN ÉCRIT"
                  % (R, X, nom, avant_gardes, len(b.gardes)))
            rates += 1
            continue

        sortie = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
        try:
            _lire_json(sortie)
        except ValueError:
            print("  %s✗%s %-30s le résultat ne se relit pas — RIEN ÉCRIT" % (R, X, nom))
            rates += 1
            continue

        print("  %s%s%s %-30s −%d du harnais · %s%d gardé(s) : %s%s"
              % (V if appliquer else J, "→" if appliquer else "?", X,
                 nom, len(b.retires), V, len(b.gardes),
                 ", ".join(b.gardes) if b.gardes else "—", X))
        total_gardes += len(b.gardes)

        if appliquer:
            try:
                with open(f, "w", encoding="utf-8", newline="") as h:
                    h.write(sortie)
            except OSError as e:
                print("      %s✗ écriture refusée : %s%s" % (R, _erreur_io(e), X))
                rates += 1
                continue
        faits += 1

    print("")
    if appliquer:
        print("  %s✓%s %d bascule(s) appliquée(s) · %d sautée(s) · %d en échec"
              % (V if rates == 0 else R, X, faits, sautes, rates))
    else:
        print("  %d bascule(s) À FAIRE %s(--apply pour agir)%s · %d sautée(s) · %d en échec"
              % (faits, D, X, sautes, rates))
    print("  %s%d garde(s) propre(s) au projet, tous conservés%s" % (D, total_gardes, X))

    # UN OUTIL QUI NE TROUVE RIEN N'EST PAS UN OUTIL QUI A RÉUSSI.
    if rates > 0:
        return 1
    return 0
