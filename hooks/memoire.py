#!/usr/bin/env python3
"""memoire - où vit la mémoire d'un projet. Une seule autorité, pour tous.

POURQUOI CE MODULE EXISTE. Compté le 08/09/2026 : **huit programmes** résolvaient
chacun de leur côté l'emplacement de `.mind/` et `.fact/` — quatre hooks et
quatre outils de poste. Tant qu'ils sont d'accord ça ne se voit pas ; le jour où
l'emplacement change, il faut les changer ensemble ou pas du tout, et un oublié
ne proteste pas : il lit l'ancien endroit, le trouve vide, et se tait.

CE QU'IL RÉSOUT, ET POURQUOI ÇA COMPTE. Mesuré le même jour sur un projet, dont les
trois agents travaillent sur trois copies physiques du dépôt : sur 137 fichiers
de mémoire, **67 étaient recopiés à l'identique pour rien, 15 existaient en trois
versions différentes, et 55 étaient absents d'au moins une copie** — dont la
fiche qui dit qui tient quoi, introuvable précisément chez l'agent chargé de
surveiller les deux autres.

    La mémoire était rangée DANS le code, donc recopiée par branche.

D'où la règle, et c'est celle que le commanditaire avait déjà écrite pour lui-même :

    ce qui décrit l'ÉTAT PRÉSENT doit être unique   → `.fact/`, `.mind/`
    ce qui est DATÉ ne périme pas, il s'accumule    → `docs/`, `.logs/`

Seul le premier groupe se déporte. `docs/` et `.logs/` restent dans le dépôt,
avec le code qu'ils racontent : les y arracher couperait chaque trace du commit
qui l'explique, pour corriger un défaut qu'ils n'ont pas.

DEUX FORMES COEXISTENT, ET C'EST VOULU.

    en place   `<projet>/.fact/` et `<projet>/agents/<nom>/.mind/`
    déportée   `<racine du dépôt>/memoire/` porte les deux

Un projet est déporté si — et seulement si — ce dossier existe. Les neuf autres
projets de l'atelier n'en ont pas et ne changent pas d'un octet : c'est ce qui
rend la bascule réversible, et vérifiable projet par projet.

LE REPÈRE EST `--git-common-dir`, JAMAIS `--show-toplevel`. Le second rend
l'arbre de travail COURANT : appelé depuis les trois copies d'un projet il rend
trois chemins, donc trois dossiers `memoire/`, et on aurait reconstruit le
défaut avec l'outil censé le réparer. Le premier rend le `.git` du dépôt
principal, identique depuis les trois — une identité, pas un chemin d'emprunt.

FAIL-OPEN. Toute erreur rend None, et l'appelant retombe sur la forme en place.
"""
import os, pathlib, subprocess

NOM = "memoire"


def racine_depot(depart=None):
    """La racine du dépôt PRINCIPAL — la même depuis tous ses arbres de travail."""
    depart = str(depart or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=10, cwd=depart)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        g = pathlib.Path(r.stdout.strip())
        return g.parent if g.name == ".git" else None
    except Exception:
        return None


def base(depart=None):
    """`<racine>/memoire`, ou None si ce projet n'est pas déporté."""
    r = racine_depot(depart)
    if r is None:
        return None
    b = r / NOM
    return b if b.is_dir() else None


def base_projet(projet):
    """Même chose quand on tient déjà la racine du projet — sans appeler git.

    `forme()` de `claude-projets` est dans ce cas, et il est appelé pour chaque
    projet de l'atelier : lui faire payer un `git` par projet serait gratuit en
    exactitude et cher en temps."""
    try:
        b = pathlib.Path(projet) / NOM
        return b if b.is_dir() else None
    except (OSError, ValueError):
        return None


def arbre_courant(depart):
    """L'arbre de travail COURANT — celui d'où l'on parle."""
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10,
                           cwd=str(depart))
        return pathlib.Path(r.stdout.strip()) if r.returncode == 0 else None
    except Exception:
        return None


def _lot(depart):
    """`agents/<nom>` si l'agent en est un, sinon ''.

    LES DEUX REPÈRES NE SONT PAS INTERCHANGEABLES, et les confondre était le
    défaut trouvé au banc le 08/09/2026 : la POSITION d'un agent se mesure dans
    SON arbre de travail (`--show-toplevel`), l'IDENTITÉ du dépôt se lit sur le
    dépôt principal (`--git-common-dir`). Mesurer la position depuis l'identité
    échoue en silence hors de l'arbre principal — `relative_to` lève, on rend
    '', et l'agent se voit servir la mémoire d'un projet mono qui n'existe pas.
    """
    a = arbre_courant(depart)
    if a is None:
        return ""
    try:
        rel = pathlib.Path(depart).resolve().relative_to(a.resolve())
    except (OSError, ValueError):
        return ""
    parts = rel.parts
    return "/".join(parts[:2]) if len(parts) >= 2 and parts[0] == "agents" else ""


def pour_agent(depart=None):
    """`(mind, fact)` pour l'agent qui parle — ou `(None, None)` si en place.

    Rendre None n'est PAS une erreur : c'est la réponse « ce projet n'est pas
    déporté, résous comme avant ». Un appelant qui confondrait les deux
    briefrait un agent sur une mémoire vide, et se tairait."""
    depart = str(depart or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    b = base(depart)
    if b is None:
        return None, None
    lot = _lot(depart)
    mind = (b / lot / ".mind") if lot else (b / ".mind")
    return mind, (b / ".fact")


def pour_projet(projet):
    """`(fact, [(nom, mind)])` — la vue de tout le projet, pour les tableaux."""
    b = base_projet(projet)
    if b is None:
        return None, None
    fact = b / ".fact"
    etats = []
    ag = b / "agents"
    if ag.is_dir():
        try:
            etats = [(d.name, d / ".mind") for d in sorted(ag.iterdir())
                     if (d / ".mind").is_dir()]
        except OSError:
            etats = []
    if not etats and (b / ".mind").is_dir():
        etats = [(None, b / ".mind")]
    return (fact if fact.is_dir() else None), (etats or None)
