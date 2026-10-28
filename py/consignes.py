# -*- coding: utf-8 -*-
"""LE VERROU DES CONSIGNES — hook PreToolUse (Edit, Write, MultiEdit, NotebookEdit, Bash).

Décision du 14/10/2026 : les agents ne touchent pas à leur `CLAUDE.md`, sauf le CTO
et Harness. Les `CLAUDE.md` —
ceux du Mac, de l'atelier, de chaque projet, du rôle de chaque agent — sont lus
à chaque démarrage : ils disent à l'agent qui il est. Jusqu'ici la règle n'était
qu'écrite ; elle est désormais tenue.

Seuls les agents nommés dans `GARDIENS` (lancés depuis un dossier de ce nom)
écrivent un `CLAUDE.md`. Les autres lisent librement — `cat`, `grep`, `git
diff` passent — mais toute ÉCRITURE est refusée, avec la raison et à qui
s'adresser. Pas d'échappatoire : la décision est celle du commanditaire.

Le verrou porte sur le NOM `CLAUDE.md`, pas sur un chemin : il tient dans tous
les projets, présents et à venir, sans liste à entretenir. La mémoire de travail
(état, tâches, faits) n'est pas concernée.

**fail-open** sur une entrée illisible : un garde qui bloque ce qu'il ne
comprend pas se fait désactiver.
"""
import os
import re

GARDIENS = ("CTO", "Harness")

NOM = re.compile(r"CLAUDE\.md", re.I)

# Une commande qui NOMME un CLAUDE.md n'est pas une commande qui l'ÉCRIT : QA,
# 14/10/2026, s'est vu refuser l'ajout d'une ligne à son todo parce que la ligne
# citait le fichier. On juge donc la CIBLE de chaque écriture, jamais le texte.
INTERPRETES = re.compile(r"\b(python3?|node|perl|ruby|sh|bash|zsh)\b")
ECRIT_SCRIPT = re.compile(r"\.write|write_text|\bopen\([^)]*['\"][wax+]|\bunlink\b|\bshutil\.|"
                          r"\bos\.(remove|rename|replace)\b|writeFile|appendFile|\brm\b|\bmv\b|>")
TOUT_ARG = {"rm", "unlink", "truncate", "touch", "mv", "shred", "chmod"}
DERNIER_ARG = {"cp", "ln", "install", "rsync", "ditto"}
GIT_ECRIT = {"rm", "mv", "checkout", "restore", "apply", "am", "stash", "reset"}


def _nomme(tok):
    tok = tok.strip("'\"")
    return os.path.basename(tok.rstrip("/")).lower() == "claude.md"


def _decoupe(cmd):
    """(texte sans les corps de heredoc, [(ligne qui ouvre, corps)])."""
    lignes = cmd.split("\n")
    out, corps, i = [], [], 0
    while i < len(lignes):
        l = lignes[i]
        out.append(l)
        fins = re.findall(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", l)
        i += 1
        for fin in fins:
            b = []
            while i < len(lignes) and lignes[i].strip() != fin:
                b.append(lignes[i])
                i += 1
            i += 1
            corps.append((l, "\n".join(b)))
    return "\n".join(out), corps


def _jetons(segment):
    import shlex
    try:
        return shlex.split(segment, comments=False)
    except ValueError:
        return segment.split()


def ecrit_un_claude_md(cmd):
    if not NOM.search(cmd):
        return False
    texte, corps = _decoupe(cmd)
    # 1. Les redirections : seule leur CIBLE compte.
    for m in re.finditer(r"(?<![0-9<])>>?\|?\s*(\"[^\"]*\"|'[^']*'|[^\s;&|<>]+)", texte):
        if _nomme(m.group(1)):
            return True
    # 2. Les commandes, segment par segment.
    for seg in re.split(r"&&|\|\||[;|\n]", texte):
        tok = _jetons(seg)
        if not tok:
            continue
        k = 0
        while k < len(tok) and ("=" in tok[k] and not tok[k].startswith("-")):
            k += 1                                     # VAR=x devant la commande
        if k >= len(tok):
            continue
        prog, args = os.path.basename(tok[k]), [a for a in tok[k + 1:] if not a.startswith(">")]
        noms = [a for a in args if not a.startswith("-")]
        if prog in TOUT_ARG and any(_nomme(a) for a in noms):
            return True
        if prog in DERNIER_ARG and noms and _nomme(noms[-1]):
            return True
        if prog == "tee" and any(_nomme(a) for a in noms):
            return True
        if prog in ("sed", "perl") and any(a.startswith("-i") or (a.startswith("-") and "i" in a[1:] and prog == "perl")
                                           for a in args) and any(_nomme(a) for a in noms):
            return True
        if prog == "git":
            verbes = [a for a in noms if a in GIT_ECRIT]
            if verbes and any(_nomme(a) for a in noms):
                return True
        if INTERPRETES.fullmatch(prog or "") and ("-c" in args or "-e" in args):
            s = " ".join(args)
            if NOM.search(s) and ECRIT_SCRIPT.search(s):
                return True
    # 3. Un script passé en heredoc à un interprète : son texte EST le geste.
    for ouvre, b in corps:
        if INTERPRETES.search(ouvre.split("<<")[0]) and NOM.search(b) and ECRIT_SCRIPT.search(b):
            return True
    return False


def agent():
    d = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.basename(os.path.realpath(d).rstrip(os.sep))


def vise(chemin):
    return isinstance(chemin, str) and os.path.basename(chemin).lower() == "claude.md"


def juge(d):
    """Rend le motif (`str`) pour refuser, `None` pour laisser passer."""
    if not isinstance(d, dict):
        return None
    outil = d.get("tool_name")
    ti = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
    if outil in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        cible = ti.get("file_path") or ti.get("notebook_path")
        if not vise(cible):
            return None
    elif outil == "Bash":
        cmd = ti.get("command")
        if not isinstance(cmd, str) or not ecrit_un_claude_md(cmd):
            return None
        cible = "un CLAUDE.md"
    else:
        return None
    if agent() in GARDIENS:
        return None
    return (
        "consignes : les CLAUDE.md ne se modifient que par %s (décision du "
        "14/10/2026 : seuls le CTO et Harness y touchent).\n\n"
        "  visé : %s\n\n"
        "Ce fichier dit à chaque agent qui il est ; il ne bouge que sur l'ordre de l'humain. "
        "Si une consigne te semble fausse ou manquante, écris-le dans ton todo, adressé à "
        "l'humain, avec la phrase que tu proposes — le CTO la posera s'il dit oui. Ta "
        "mémoire de travail (état, tâches, faits) n'est pas concernée."
        % (" et ".join(GARDIENS), cible))


def main(entree):
    if "claude.md" not in entree.lower():
        return
    import json
    import sys
    try:
        d = json.loads(entree)
    except (ValueError, RecursionError):
        return
    motif = juge(d)
    if motif is not None:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motif,
        }}, ensure_ascii=False) + "\n")
