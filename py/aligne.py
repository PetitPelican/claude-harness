# -*- coding: utf-8 -*-
"""`harnais aligne` — les agents d'un même dépôt sur la version posée.

LE DÉFAUT QU'ELLE CONTOURNE (CLI de Claude Code, mesuré le 28/10/2026 et
retrouvé ailleurs le 24/11) : dans une équipe « un dossier par agent »
(`agents/OPS`, `agents/PO`, `agents/QA` dans un même dépôt),
`claude plugin update harnais@atelier --scope project` ne met à jour que le
premier dossier. Pour les suivants il répond « déjà à jour », sort sans erreur,
et le registre (`~/.claude/plugins/installed_plugins.json`) garde leur ancienne
version : il a lu l'entrée du premier.

CE QU'ELLE FAIT : dans le registre, chaque entrée de portée projet du paquet
qui partage son dépôt git avec une entrée plus récente reçoit la version de
celle-ci (`installPath`, `version`, `gitCommitSha`). Seulement si le code de
cette version est bien en cache sur la machine. À blanc par défaut ; `--go`
écrit, après une copie du registre à côté de lui.

    harnais aligne                 tout le registre, à blanc
    harnais aligne agents/PO --go  ces dossiers seulement, et écrire

À faire agents arrêtés : un agent prend la version à son message suivant.
`HARNAIS_INSCRIPTIONS` impose le registre (essais).
"""
import datetime
import json
import os
import shutil
import subprocess

import socle

PAQUET = "harnais@atelier"


def registre():
    return os.environ.get("HARNAIS_INSCRIPTIONS") or os.path.join(
        socle.maison(), ".claude", "plugins", "installed_plugins.json")


def _cle(v):
    out = []
    for x in str(v or "").split("."):
        try:
            out.append(int(x))
        except ValueError:
            out.append(-1)
    return tuple(out)


def _canon(p):
    return os.path.normcase(os.path.realpath(p))


def depot(dossier):
    """La racine du dépôt git qui porte `dossier`, ou le dossier lui-même."""
    try:
        o = subprocess.run(["git", "-C", dossier, "rev-parse", "--show-toplevel"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if o.returncode == 0 and o.stdout.strip():
            return _canon(o.stdout.decode("utf-8", "replace").strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return _canon(dossier)


def plan(entrees, cibles=None, depot_de=depot):
    """[(entrée, modèle)] à aligner, et [lignes à dire] pour ce qui ne peut pas l'être."""
    projets = [e for e in entrees if isinstance(e, dict) and e.get("scope") == "project"
               and isinstance(e.get("projectPath"), str)]
    groupes = {}
    for e in projets:
        groupes.setdefault(depot_de(e["projectPath"]), []).append(e)
    voulus = None if cibles is None else {_canon(c) for c in cibles}
    a_faire, dits = [], []
    for _, groupe in sorted(groupes.items()):
        modele = max(groupe, key=lambda e: _cle(e.get("version")))
        for e in groupe:
            if voulus is not None and _canon(e["projectPath"]) not in voulus:
                continue
            if _cle(e.get("version")) >= _cle(modele.get("version")):
                continue
            if not os.path.isdir(modele.get("installPath") or ""):
                dits.append("%s : %s, mais le code de la %s n'est pas en cache (%s) — non aligné"
                            % (e["projectPath"], e.get("version"), modele.get("version"),
                               modele.get("installPath")))
                continue
            a_faire.append((e, modele))
    if voulus is not None:
        connus = {_canon(e["projectPath"]) for e in projets}
        for c in sorted(voulus - connus):
            dits.append("%s : aucune inscription du paquet en portée projet — "
                        "lancer d'abord `claude plugin install harnais@atelier --scope project` ici" % c)
    return a_faire, dits


def main(args):
    go = "--go" in args
    cibles = [os.path.abspath(a) for a in args if a != "--go"] or None
    f = registre()
    try:
        with open(f, encoding="utf-8") as h:
            v = json.load(h)
        entrees = v["plugins"][PAQUET]
    except (OSError, ValueError, KeyError, TypeError):
        print("aligne : registre illisible ou sans %s (%s) — rien à faire" % (PAQUET, f))
        return 1
    a_faire, dits = plan(entrees, cibles)
    for e, m in a_faire:
        print("%-60s %s -> %s" % (e["projectPath"], e.get("version"), m.get("version")))
    for d in dits:
        print("⚠ " + d)
    if not a_faire:
        print("rien à aligner")
        return 0 if not dits else 1
    if not go:
        print("à blanc : rien d'écrit — `--go` pour écrire, agents arrêtés")
        return 0
    jour = datetime.datetime.now()
    sauve = f + ".avant-aligne-" + jour.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(f, sauve)
    tampon = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    for e, m in a_faire:
        for k in ("installPath", "version", "gitCommitSha"):
            if k in m:
                e[k] = m[k]
        e["lastUpdated"] = tampon
    with open(f, "w", encoding="utf-8") as h:
        json.dump(v, h, ensure_ascii=False, indent=2)
        h.write("\n")
    print("écrit (%d entrée(s)) ; copie : %s" % (len(a_faire), sauve))
    print("chaque agent prend la version à son message suivant")
    return 0
