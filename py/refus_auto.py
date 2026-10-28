# -*- coding: utf-8 -*-
"""LE CONTRÔLEUR DU MODE AUTO A REFUSÉ UN GESTE — on le note, la fin de tour le dit.

Né le 12/10/2026 d'une demande du CTO, relayant le commanditaire : quand le contrôleur du
mode auto refuse un geste approuvé, on lui demande de passer du mode auto
au mode edit, puis on réessaie — jamais de commande à taper. Une ligne dans le
socle ne suffit pas (elle n'est suivie qu'une partie du temps) : la règle se tient
au moment du geste.

CE QUE L'ÉVÉNEMENT PERMET, ET C'EST MAIGRE. `PermissionDenied` ne tire que dans le
mode auto, et son seul retour utile est `retry` : la documentation n'y prévoit AUCUN
champ pour ajouter du contexte à l'agent (lue le 12/10/2026, Claude Code 2.1.89+).
On ne peut donc pas lui parler à l'instant du refus. Ce hook se contente de NOTER le
refus, par session ; la garde de fin de tour (`attente`, B17) le lit avant que
l'agent rende la main, et lui rappelle la consigne — une seule fois.

CE HOOK NE DÉCIDE RIEN ET NE BLOQUE RIEN : le code de sortie est ignoré par Claude
Code pour cet événement. Fail-open, toujours.
"""


def main(entree):
    import json
    import os
    try:
        d = json.loads(entree)
    except (ValueError, RecursionError):
        return
    if not isinstance(d, dict):
        return
    import socle
    sid = d.get("session_id")
    session = "".join(c for c in (sid if isinstance(sid, str) else "x")
                      if (c.isascii() and c.isalnum()) or c == "_" or c == "-")[:64]
    outil = d.get("tool_name")
    raison = d.get("reason")
    ligne = {"outil": outil if isinstance(outil, str) else "?",
             "raison": (raison if isinstance(raison, str) else "")[:120]}
    dossier = os.path.join(socle.socle(), "attente")
    try:
        os.makedirs(dossier, exist_ok=True)
        with open(os.path.join(dossier, session + ".refus-auto"), "w", encoding="utf-8") as h:
            h.write(json.dumps(ligne, ensure_ascii=False))
    except OSError:
        return


def lis_et_consomme(dossier, session):
    """Le refus noté dans cette session, ou None. Le fichier est SUPPRIMÉ à la lecture :
    un refus ne rappelle sa consigne qu'une fois."""
    import json
    import os
    f = os.path.join(dossier, session + ".refus-auto")
    try:
        with open(f, encoding="utf-8") as h:
            brut = h.read()
    except OSError:
        return None
    try:
        os.remove(f)
    except OSError:
        pass
    try:
        d = json.loads(brut)
    except ValueError:
        return {"outil": "?", "raison": ""}
    return d if isinstance(d, dict) else {"outil": "?", "raison": ""}
