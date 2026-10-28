# -*- coding: utf-8 -*-
"""QUELLE VERSION DU HARNAIS CHAQUE AGENT A-T-IL CHARGÉE ?

Une session garde, jusqu'à son arrêt, la version avec laquelle elle a démarré :
publier ne change rien aux agents déjà éveillés (mesuré le 14/10/2026 : à la
publication de la 0.18.1, AUCUNE session ne tournait dessus, le CTO était encore
sur une version du 12/10). Le commanditaire a décidé le même jour que le CTO endort chaque
nuit les agents au repos et réveille ceux qu'il veut éveillés — encore fallait-il
pouvoir le VÉRIFIER au lieu de le supposer.

À chaque ouverture de session, le briefing note ici la version qui tourne, par
dossier de lancement. `harnais versions` la relit et la compare à la dernière
version installée.
"""
import json
import os
import time

import socle


def dossier():
    return os.path.join(socle.socle(), "versions")


def _cle(lancement):
    return "".join(c if (c.isascii() and c.isalnum()) or c in "-_" else "-" for c in lancement).strip("-")[:120]


def identite():
    import main
    return main._identite()


def note(charge):
    """Appelé au SessionStart. Ne lève jamais : une trace ne coûte jamais un tour."""
    try:
        lancement = os.environ.get("CLAUDE_PROJECT_DIR") or charge.get("cwd") or os.getcwd()
        lancement = os.path.realpath(lancement)
        v = identite().split()
        d = dossier()
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, _cle(lancement) + ".json")
        tmp = f + ".tmp"
        with open(tmp, "w", encoding="utf-8") as h:
            json.dump({"dossier": lancement, "version": v[0], "empreinte": v[1] if len(v) > 1 else "",
                       "session": charge.get("session_id") or "",
                       "demarre": time.strftime("%Y-%m-%dT%H:%M:%S")}, h, ensure_ascii=False)
        os.replace(tmp, f)
    except Exception:
        pass


def _cle_version(v):
    out = []
    for x in v.split("."):
        out.append(int(x) if x.isdigit() else -1)
    return out


def derniere_installee():
    """La plus haute version présente dans le cache des paquets, ou None."""
    c = os.path.join(socle.maison(), ".claude", "plugins", "cache", "atelier", "harnais")
    try:
        vs = [x for x in os.listdir(c) if x[:1].isdigit()]
    except OSError:
        return None
    return max(vs, key=_cle_version) if vs else None


def releve():
    out = []
    try:
        noms = sorted(os.listdir(dossier()))
    except OSError:
        noms = []
    for n in noms:
        if not n.endswith(".json"):
            continue
        try:
            with open(os.path.join(dossier(), n), encoding="utf-8") as h:
                out.append(json.load(h))
        except (OSError, ValueError):
            continue
    return out


def main(args):
    """`harnais versions [--json]` — la version chargée par chaque dossier de lancement."""
    derniere = derniere_installee()
    lignes = releve()
    if "--json" in args:
        print(json.dumps({"derniere": derniere, "sessions": lignes}, ensure_ascii=False, indent=1))
        return 0
    print("dernière version installée : %s" % (derniere or "inconnue"))
    if not lignes:
        print("aucune session notée — la trace naît avec la 0.18.2, au prochain démarrage de chaque agent")
        return 0
    retard = 0
    for x in sorted(lignes, key=lambda x: x.get("dossier", "")):
        a_jour = derniere is not None and x.get("version") == derniere
        retard += 0 if a_jour else 1
        print("  %-8s %-8s démarré %s  %s" % ("à jour" if a_jour else "EN RETARD", x.get("version"),
                                               x.get("demarre", "?").replace("T", " ")[:16], x.get("dossier")))
    print("%d en retard sur %d noté(s) — ce relevé dit la version au DÉMARRAGE ; une session arrêtée depuis "
          "garde sa dernière ligne" % (retard, len(lignes)))
    return 1 if retard else 0
