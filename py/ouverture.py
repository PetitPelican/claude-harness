# -*- coding: utf-8 -*-
"""LE GARDE DE L'OUVERTURE DE SESSION — hook PreToolUse
(`mcp__ccd_session__start_session`, `mcp__ccd_session__hand_off_to_session`).

Décision de l'humain du 04/11/2026, à la demande du CTO : un agent qui veut
confier quelque chose à un autre agent lui ÉCRIT ; il n'ouvre pas une seconde
session à côté de la sienne. Mesuré dans les journaux de l'atelier, trois
ouvertures fautives en deux jours : deux sans `cwd`, le titre commençant par le
nom de l'agent visé (« Designer — … », « Éditeur : … » ; la session naissait
dans le dossier de l'appelant), une avec `cwd` vers le dossier d'un autre agent.

CE QUI EST REFUSÉ, quelle que soit l'`initiation` (une proposition `offer` ou
`own_initiative` est la même erreur, une carte en plus) :
  · un `cwd` dont le dossier d'agent a déjà une session ouverte dans l'app ;
  · sans `cwd`, un titre (ou un `name`) dont la tête — avant « — », « : »,
    « - » — est le nom d'un agent qui a déjà une session ailleurs.
Le refus nomme la session et dit quoi faire : SendMessage à son id.

CE QUI PASSE : un dossier sans session (l'humain reste libre de lancer un agent
sous un autre ; la règle `ask` de l'app montre sa carte), une session à côté
de soi dans son propre dossier, `proposal_id` seul (la proposition a déjà été
jugée), `preset` (le lieu qu'il désigne n'est pas lu).

D'OÙ VIENT « UNE SESSION OUVERTE » : les fiches que l'app tient par session
(`claude-code-sessions/<compte>/<org>/local_*.json` : `cwd`, `title`,
`isArchived`, `cliSessionId`), sous `%LOCALAPPDATA%\\Claude-Data\\*` (Windows,
mesuré le 04/11) ou `~/Library/Application Support/Claude*` (macOS, pas
mesuré). `HARNAIS_SESSIONS_APP` impose le dossier. Une fiche archivée ne compte
pas ; celle de l'appelant non plus (`session_id` = `cliSessionId`).

Le « dossier d'agent » est le plus proche parent qui porte `.claude/settings.json`.

**fail-open** : sans fiches lisibles, rien n'est refusé — la carte de l'humain
reste là.
"""
import glob
import json
import os
import re
import sys
import unicodedata

OUTILS = ("mcp__ccd_session__start_session", "mcp__ccd_session__hand_off_to_session")
TETE = re.compile(r"\s+[—–-]\s+|\s*:\s+|\s*:$")


def _dossiers_fiches():
    impose = os.environ.get("HARNAIS_SESSIONS_APP")
    if impose:
        return [impose]
    motifs = []
    loc = os.environ.get("LOCALAPPDATA")
    if loc:
        motifs.append(os.path.join(loc, "Claude-Data", "*", "claude-code-sessions"))
        motifs.append(os.path.join(loc, "Claude*", "claude-code-sessions"))
    app = os.environ.get("APPDATA")
    if app:
        motifs.append(os.path.join(app, "Claude*", "claude-code-sessions"))
    motifs.append(os.path.expanduser(os.path.join("~", "Library", "Application Support",
                                                  "Claude*", "claude-code-sessions")))
    vus = []
    for m in motifs:
        for d in glob.glob(m):
            if d not in vus:
                vus.append(d)
    return vus


def sessions_ouvertes():
    """[(id, titre, cwd, cliSessionId)] des sessions non archivées."""
    out = []
    for d in _dossiers_fiches():
        for f in glob.glob(os.path.join(d, "*", "*", "local_*.json")):
            try:
                with open(f, encoding="utf-8") as h:
                    s = json.load(h)
            except (OSError, ValueError):
                continue
            if not isinstance(s, dict) or s.get("isArchived") or not s.get("cwd"):
                continue
            out.append((s.get("sessionId") or os.path.basename(f)[:-5], s.get("title") or "",
                        s["cwd"], s.get("cliSessionId") or ""))
    return out


def _norme(chemin):
    return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(chemin))))


def racine_agent(chemin):
    """Le plus proche parent qui porte `.claude/settings.json`, sinon le chemin."""
    c = _norme(chemin)
    p = c
    while True:
        if os.path.isfile(os.path.join(p, ".claude", "settings.json")):
            return p
        haut = os.path.dirname(p)
        if haut == p:
            return c
        p = haut


def _nom(texte):
    t = unicodedata.normalize("NFKD", texte or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _noms(racine, titre):
    """Les noms sous lesquels on désigne l'agent d'un dossier. Le dossier d'un
    agent d'équipe (`agents/PO`) n'en est pas un : PO existe dans chaque équipe."""
    noms = {_nom(titre)} if titre else set()
    if os.path.basename(os.path.dirname(racine)).lower() != "agents":
        noms.add(_nom(os.path.basename(racine)))
    return noms - {""}


def _refus(cibles, comment):
    lignes = ["- « %s » (%s), id %s" % (t, c, i) for i, t, c in cibles]
    premier = cibles[0][0]
    return ("ouverture de session : %s a déjà une session ouverte :\n%s\n\nN'en ouvre pas une "
            "seconde, et ne propose pas d'en ouvrir une : ÉCRIS-LUI. `list_sessions` pour "
            "confirmer, puis `SendMessage` avec to = %s, et la demande en clair. S'il faut "
            "vraiment une autre session dans ce dossier, c'est l'humain qui l'ouvre depuis "
            "l'app." % (comment, "\n".join(lignes), premier))


def juge(d):
    """Le motif du refus (`str`), ou None pour laisser passer."""
    if not isinstance(d, dict) or d.get("tool_name") not in OUTILS:
        return None
    ti = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
    if ti.get("proposal_id") or ti.get("preset") or ti.get("target") in ("cloud", "ssh") \
            or ti.get("host"):
        return None
    ici = racine_agent(os.environ.get("CLAUDE_PROJECT_DIR") or d.get("cwd") or os.getcwd())
    moi = d.get("session_id") or ""
    autres = []
    for i, t, c, cli in sessions_ouvertes():
        if moi and cli == moi:
            continue
        r = racine_agent(c)
        if r != ici:
            autres.append((i, t, c, r))
    if not autres:
        return None
    cwd = ti.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        vise = racine_agent(cwd)
        if vise == ici:
            return None
        cibles = [(i, t, c) for i, t, c, r in autres if r == vise]
        return _refus(cibles, "le dossier `%s`" % cwd) if cibles else None
    tetes = set()
    titre = ti.get("title")
    if isinstance(titre, str) and titre.strip():
        tetes.add(_nom(TETE.split(titre.strip(), 1)[0]))
    if isinstance(ti.get("name"), str):
        tetes.add(_nom(ti["name"]))
    tetes.discard("")
    cibles = [(i, t, c) for i, t, c, r in autres if _noms(r, t) & tetes]
    return _refus(cibles, "l'agent que nomme ce titre") if cibles else None


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
