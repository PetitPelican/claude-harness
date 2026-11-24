# -*- coding: utf-8 -*-
"""LE GARDE DES ENVOIS — hook PreToolUse (Bash, PowerShell).

Décision du commanditaire du 24/11/2026 : un agent commite en local sans lui
demander ; ce qui quitte la copie de travail ou entre dans la branche principale
attend son clic. Mesuré sur huit jours (17 agents) : environ 1 800 commits, tous
libres, ce qui est voulu ; mais les push ne lui revenaient que là où un réglage
`ask` existait (six agents sans, et aucun réglage ne voyait PowerShell ni un
`git -C <ailleurs> push`), et environ 120 merges sont passés sans lui.

CE QUI ATTEND LE CLIC DE L'HUMAIN (décision `ask`, jamais un refus) :
  · tout `git push`, sous toutes ses formes (`git -C x push`, derrière `cd`,
    `env`, `Set-Location`, au milieu d'une ligne) — sauf `--dry-run` / `-n` ;
  · un `git merge` dont la branche qui reçoit est une branche principale
    (`main`, `master`) : la branche courante du dossier visé, ou celle qu'un
    `git checkout` / `git switch` plus tôt sur la même ligne vient de prendre ;
  · `gh pr merge`, et l'API GitHub en écriture vers une fusion.

CE QUI PASSE : les commits ; les merges entre branches de travail ;
`git merge --abort` ; tout le reste.

Le garde de la Production juge en plus, et lui REFUSE sans laissez-passer :
un refus l'emporte sur une demande.

**fail-open** sur une entrée illisible : la commande suit ses réglages, comme avant.
"""
import os
import re
import sys

import production as P

PRINCIPALES = {"main", "master"}
CD = {"cd", "pushd", "set-location", "sl", "push-location"}
FUSION_API = re.compile(r"/merges\b|/pulls/\d+/merge\b")


def _verbe(jetons, k, fin, dossier):
    """(dossier, indice du verbe, verbe) après `git` et ses options globales."""
    while k < fin:
        u = jetons[k]
        if u == "-C" and k + 1 < fin:
            dossier = P._resoudre(dossier, jetons[k + 1])
            k += 2
            continue
        if u.startswith("-"):
            k += 2 if u in P.PORTEUSES else 1
            continue
        return dossier, k, u
    return dossier, k, None


def _branche_prise(args):
    """La branche où mène `git checkout|switch <args>`, ou None (fichiers, détaché)."""
    if "--" in args:
        return None
    j = 0
    while j < len(args):
        a = args[j]
        if a in ("-b", "-B", "-c", "-C", "--orphan") and j + 1 < len(args):
            return args[j + 1]
        if a.startswith("-"):
            j += 1
            continue
        return a
    return None


def _courante(dossier):
    """La branche du dossier, même sans commit encore (`symbolic-ref`, pas `rev-parse`)."""
    import subprocess
    try:
        o = subprocess.run(["git", "-C", dossier, "symbolic-ref", "--short", "-q", "HEAD"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return o.stdout.decode("utf-8", "replace").strip() if o.returncode == 0 else ""


def a_envoyer(cmd, base, courante=_courante):
    """La raison si la ligne pousse ou fusionne vers une branche principale, sinon None."""
    jetons = P._jetons(cmd)
    cwd, prises, i = base, {}, 0
    while i < len(jetons):
        t = jetons[i]
        if t.lower() in CD and i + 1 < len(jetons) and not jetons[i + 1].startswith("-"):
            cwd = P._resoudre(cwd, jetons[i + 1])
            i += 2
            continue
        fin = i + 1
        while fin < len(jetons) and jetons[fin] not in P.FINS:
            fin += 1
        tete = i
        while tete < fin and P._programme(jetons[tete]) not in ("git", "gh"):
            tete += 1
        prog = P._programme(jetons[tete]) if tete < fin else ""
        if prog == "git":
            dossier, k, verbe = _verbe(jetons, tete + 1, fin, cwd)
            args = jetons[k + 1:fin]
            if verbe == "push":
                if not ({"--dry-run", "-n"} & set(args)):
                    return "`git push` envoie des commits hors de la copie de travail"
            elif verbe in ("checkout", "switch"):
                b = _branche_prise(args)
                if b:
                    prises[os.path.normcase(dossier)] = b
            elif verbe == "merge":
                if not ({"--abort", "--quit"} & set(args)):
                    cle = os.path.normcase(dossier)
                    recoit = prises[cle] if cle in prises else courante(dossier)
                    if recoit in PRINCIPALES:
                        return "`git merge` vers `%s`, la branche principale" % recoit
        elif prog == "gh":
            mots = jetons[tete + 1:fin]
            if mots[:2] == ["pr", "merge"]:
                return "`gh pr merge` fusionne une demande de fusion"
            reste = " ".join(mots)
            if mots[:1] == ["api"] and FUSION_API.search(reste) and P.ECRIT_GITHUB.search(" " + reste + " "):
                return "`gh api` demande une fusion sur GitHub"
        i = fin + 1 if fin < len(jetons) else fin
    if "api.github.com" in cmd and FUSION_API.search(cmd) and P.ECRIT_GITHUB.search(" " + cmd + " "):
        return "l'API GitHub demande une fusion"
    return None


def juge(d):
    """La raison de demander le clic (`str`), ou None pour laisser la commande à ses réglages."""
    if not isinstance(d, dict) or d.get("tool_name") not in ("Bash", "PowerShell"):
        return None
    ti = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
    cmd = ti.get("command")
    if not isinstance(cmd, str):
        return None
    if d.get("tool_name") == "PowerShell":
        cmd = cmd.replace("\\", "/")
    base = d.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    raison = a_envoyer(cmd, base)
    if raison is None:
        return None
    return ("envoi : %s. Décision du 24/11/2026 : l'agent commite en local librement ; "
            "un push, ou un merge vers la branche principale, attend le clic de l'humain."
            % raison)


def main(entree):
    bas = entree.lower()
    if "push" not in bas and "merge" not in bas:
        return
    import json
    try:
        d = json.loads(entree)
    except (ValueError, RecursionError):
        return
    raison = juge(d)
    if raison is not None:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": raison,
        }}, ensure_ascii=False) + "\n")
