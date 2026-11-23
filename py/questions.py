# -*- coding: utf-8 -*-
"""LE GARDE DES QUESTIONS AUX BOUTONS — hook PreToolUse (AskUserQuestion).

Décision du commanditaire du 28/10/2026 : une question ne lui parvient que si
elle dit pourquoi elle lui revient, par un motif pris dans une liste fermée —
irréversible, production, argent, données, hors du poste, cap, périmètre. Sans
motif, l'agent décide seul. Le garde B8-motif de la fin de tour ne lisait que les
lignes du todo ; depuis que les questions se posent aux boutons (05/11), presque
toutes y échappaient. Mesuré sur une semaine (16-23/11, 17 agents) : 273
questions aux boutons, une vingtaine avec un motif.

CE QUI EST REFUSÉ : un appel dont une question ne porte pas `Motif → <mot de la
liste>`, n'importe où dans son texte. Le refus nomme les questions en cause et
dit les deux voies : ajouter le motif si elle lui revient vraiment, sinon
décider, le dire en une ligne, et continuer.

CE QUI PASSE : un appel dont chaque question porte son motif ; et tout appel
d'un agent dont le métier est de questionner l'humain (un mentor, un
entretien) — réglage `HARNAIS_QUESTIONS=libres` dans l'`env` de ses réglages.

**fail-open** sur une entrée illisible : la question part, comme avant.
"""
import json
import os
import re
import sys

MOTIF = re.compile(r"\bmotif\s*(?:→|->|:)\s*(?:irr[ée]versible|production|argent|donn[ée]es"
                   r"|hors du poste|cap|p[ée]rim[èe]tre)\b", re.I)


def libres():
    return os.environ.get("HARNAIS_QUESTIONS", "").strip().lower() == "libres"


def sans_motif(d):
    """Les questions (en-tête, texte) sans motif, ou [] pour laisser passer."""
    if not isinstance(d, dict) or d.get("tool_name") != "AskUserQuestion":
        return []
    ti = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
    qs = ti.get("questions")
    if not isinstance(qs, list):
        return []
    out = []
    for q in qs:
        if not isinstance(q, dict):
            continue
        texte = q.get("question") if isinstance(q.get("question"), str) else ""
        if not MOTIF.search(texte):
            out.append((q.get("header") or "", texte))
    return out


def juge(d):
    """Le motif du refus (`str`), ou None pour laisser passer."""
    if libres():
        return None
    manquent = sans_motif(d)
    if not manquent:
        return None
    liste = "\n".join("- [%s] %s" % (h, " ".join(t.split())[:140]) for h, t in manquent)
    return (
        "questions : %d question(s) ne disent pas pourquoi elles reviennent à l'humain :\n%s\n\n"
        "Décision du 28/10/2026 : une question ne lui parvient que si elle porte "
        "`Motif → <un mot>` pris dans cette liste : irréversible, production, argent, "
        "données, hors du poste, cap, périmètre. Sans motif, c'est à toi de décider.\n\n"
        "Pour chacune, une des deux voies :\n"
        "1. Elle lui revient vraiment → ajoute `Motif → …` dans le texte de la question, "
        "puis repose l'appel.\n"
        "2. Aucun motif ne tient → décide toi-même (la voie que tu recommandais), dis-le en "
        "une ligne avec comment le défaire, et continue.\n\n"
        "Si la réponse est un fait que tu peux mesurer, ce n'est pas une question : mesure-le."
        % (len(manquent), liste))


def main(entree):
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
