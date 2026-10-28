#!/usr/bin/env python3
"""carnet - l'espace commun d'un projet multi-agents.

POURQUOI CE MODULE EXISTE. Mesuré le 08/09/2026 sur un projet : trois agents, trois
copies physiques du dépôt (des worktrees), et tout ce qu'un agent écrit sur son
travail ne voyage que dans SA copie. un agent QA avait 187 enregistrements de
retard, ne voyait AUCUN journal de ses deux coéquipiers pour les 07 et 08/09, et
lisait une liste de tâches d'OPS de 1 202 lignes là où la vraie en fait 2 810.
Rien, nulle part, ne le lui disait.

Le mur n'est donc pas entre les agents : il est entre leurs copies. Ce module
ouvre un endroit qui n'existe QU'UNE FOIS sur le disque, que les trois voient
identiquement — `<projet>/equipe/`.

CE QUI EN DÉCIDE LA FORME, ET QU'ON NE PEUT PAS CHANGER SANS TOUT CASSER :

  1. HORS SUIVI DE VERSION. Un dossier suivi par git serait recopié dans les
     trois copies à chaque fusion, et QA en aurait une version vieille de deux
     jours : on aurait reconstruit le défaut qu'on répare. Une ligne dans les
     exclusions du dépôt le tient dehors.

  2. UN SEUL ÉCRIVAIN PAR FICHIER. Le découpage `<mois>-<agent>.md` n'existe que
     pour ça — pas pour cloisonner ce que chacun voit. La LECTURE est toujours
     la fusion des trois. C'est la propriété que nos dossiers séparés donnent
     gratuitement et que le harnais de référence, avec son espace unique, doit racheter en
     rôles, droits et relecture avant fusion.

  3. ON AJOUTE, ON NE SUPPRIME JAMAIS. Le copy-on-write du harnais de référence. D'où le
     point suivant, qui n'est pas un détail d'implémentation.

  4. LE CHIFFRE DE CONFIANCE NE VIT PAS DANS LE CARNET. Une entrée est immuable
     et un chiffre bouge : les deux ne peuvent pas cohabiter dans le même
     fichier. Le chiffre est une SURCOUCHE, dans `.etat/confiance.json`, indexée
     par l'empreinte de l'entrée.

FAIL-OPEN PARTOUT. Ce module est appelé par deux hooks qui ne doivent jamais
empêcher de travailler. Toute erreur rend une valeur vide, jamais une exception.
"""
import os, re, json, hashlib, datetime, subprocess, pathlib

# Le départ, fixé par le NIVEAU. C'est le `provenance_tier` du harnais de référence ramené à
# trois crans, et c'est la moitié qui vaut d'être copiée : un niveau dit QUOI
# FAIRE pour vérifier, là où un nombre saisi à la main ne dit rien.
DEPART = {"mesure": 80, "observe": 60, "suppose": 40}
NIVEAUX = ("mesuré", "observé", "supposé")
ISSUES = ("abouti", "échoué", "en cours")

REUSSITE, ECHEC, OUBLI, EFFONDRE = 1.03, 0.85, 0.97, 0.5
PLANCHER, PLAFOND = 5, 99
# Le chiffre n'est AFFICHÉ qu'après avoir bougé deux fois. Avant ça, c'est le
# niveau de départ déguisé en mesure — exactement le défaut qu'on reprochait au
# chiffre saisi à la main du harnais de référence. Ne pas retirer cette borne.
MOUVEMENTS_AVANT_AFFICHAGE = 2

ENTETE = re.compile(
    r"^##\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s*·\s*(.+?)\s*·\s*(.+?)"
    r"(?:\s*·\s*(.+?))?\s*$")
POUR = re.compile(r"^\s*↗\s*(.+?)\s*:\s*(.+?)\s*$", re.M)
# Même syntaxe que les constats de `attente.py` — on ne crée pas un second
# dialecte de réouverture, il divergerait au premier changement.
REJEU = re.compile(r"^\s*↻\s*(machine|service)\s*::\s*(.+?)\s*::\s*(.+?)\s*$",
                   re.I | re.M)


def _sansaccents(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower())
                   if not unicodedata.combining(c))


def racine_commune(depart=None):
    """Le SEUL point délicat de ce fichier, et il décide de tout.

    `git rev-parse --show-toplevel` rend le worktree COURANT : appelé depuis les
    trois copies d'un projet il rend trois chemins différents, donc trois dossiers
    `equipe/` différents — le défaut qu'on répare, reconstruit par l'outil censé
    le réparer. Mesuré le 08/09/2026.

    `--git-common-dir` rend le `.git` du dépôt PRINCIPAL, identique depuis les
    trois. C'est une identité, pas un chemin d'emprunt : voilà pourquoi c'est
    lui. Vérifié : les trois copies rendent `/Users/u/Agentic/Alpha/.git`.
    """
    depart = str(depart or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=10, cwd=depart)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        g = pathlib.Path(r.stdout.strip())
        # `.git` peut être le dossier lui-même (dépôt normal ou worktree
        # principal). Son parent est la racine du dépôt principal.
        return g.parent if g.name == ".git" else None
    except Exception:
        return None


def espace(depart=None, creer=False):
    """`<racine>/memoire/equipe` si la mémoire est déportée, sinon
    `<racine>/equipe`. Les deux sont hors du suivi de version et n'existent
    qu'une fois — le carnet a été le premier à passer, le reste de la mémoire
    d'état l'a suivi le 08/09/2026 et l'a rejoint dans le même dossier."""
    r = racine_commune(depart)
    if r is None:
        return None
    e = (r / "memoire" / "equipe") if (r / "memoire").is_dir() else (r / "equipe")
    if creer:
        try:
            (e / ".etat").mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
    return e if e.is_dir() else None


def _slug(nom):
    return re.sub(r"[^A-Za-z0-9_-]", "-", nom or "agent")


def fichier(esp, agent, quand=None):
    quand = quand or datetime.date.today()
    return esp / ("%s-%s.md" % (quand.strftime("%Y-%m"), _slug(agent)))


def empreinte(e):
    """Date + auteur + première ligne. Uniques parce qu'on n'écrase jamais."""
    return hashlib.sha1(
        ("%s %s|%s|%s" % (e.get("date", ""), e.get("heure", ""),
                          e.get("auteur", ""), e.get("texte", "")[:120]))
        .encode("utf-8")).hexdigest()[:12]


# ── écrire ───────────────────────────────────────────────────────────────

def ecrire(esp, agent, texte, issue="abouti", niveau=None, pour=None,
           rejeu=None, quand=None, vus=None):
    """Une entrée, en AJOUT SEUL. Rend son empreinte, ou None."""
    if esp is None or not (texte or "").strip():
        return None
    quand = quand or datetime.datetime.now()
    if niveau is None:
        niveau = "mesuré" if rejeu else "observé"
    f = fichier(esp, agent, quand.date())
    bloc = []
    if not f.exists():
        bloc += ["# Carnet d'équipe — %s · %s" % (agent, quand.strftime("%B %Y")),
                 "",
                 "Écrit par le hook `attente` quand une tâche cochée porte `↗`.",
                 "**En ajout seul** : on n'y réécrit rien, on n'y supprime rien.",
                 ""]
    bloc.append("## %s %s · %s · %s · %s"
                % (quand.strftime("%Y-%m-%d"), quand.strftime("%H:%M"),
                   agent, issue, niveau))
    bloc.append(texte.strip())
    for qui, quoi in (pour or []):
        bloc.append("↗ %s : %s" % (qui, quoi))
    if rejeu:
        bloc.append("↻ %s" % rejeu.lstrip("↻ ").strip())
    # L'ACQUITTEMENT est le seul geste « social » du dispositif. Sans lui, une
    # demande adressée à un agent resterait en tête de son briefing pour
    # toujours — et il apprendrait à ne plus la lire, ce qui est pire que de ne
    # rien lui servir.
    for v in (vus or []):
        bloc.append("↩ %s" % v)
    bloc.append("")
    try:
        with f.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(bloc) + "\n")
    except OSError:
        return None
    e = {"date": quand.strftime("%Y-%m-%d"), "heure": quand.strftime("%H:%M"),
         "auteur": agent, "texte": texte.strip()}
    ident = empreinte(e)
    _naissance(esp, ident, niveau)
    return ident


# ── lire ─────────────────────────────────────────────────────────────────

def entrees(esp, depuis=None):
    """Les carnets des TROIS agents, fusionnés et triés — du plus récent au plus
    ancien. C'est le point de tout le dispositif : l'écriture est séparée, la
    lecture ne l'est jamais."""
    if esp is None or not esp.is_dir():
        return []
    out = []
    try:
        fichiers = sorted(esp.glob("*.md"))
    except OSError:
        return []
    for f in fichiers:
        try:
            texte = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        bloc, courant = [], None
        for l in texte.splitlines():
            m = ENTETE.match(l)
            if m:
                courant = {"date": m.group(1), "heure": m.group(2),
                           "auteur": m.group(3).strip(),
                           "issue": (m.group(4) or "").strip(),
                           "niveau": (m.group(5) or "observé").strip(),
                           "corps": []}
                bloc.append(courant)
            elif courant is not None:
                courant["corps"].append(l)
        for e in bloc:
            corps = "\n".join(e.pop("corps")).strip()
            # LES TROIS MARQUEURS, PAS DEUX. L'empreinte est calculée sur ce
            # texte ; en oublier un ici et l'entrée relue n'a plus la même
            # empreinte que l'entrée écrite — sa confiance devient introuvable,
            # silencieusement. Mesuré sur le banc le 08/09/2026 avec `↩`.
            lignes = [x for x in corps.splitlines()
                      if not x.lstrip().startswith(("↗", "↻", "↩"))]
            e["texte"] = " ".join(x.strip() for x in lignes if x.strip())
            e["pour"] = [(a.strip(), b.strip()) for a, b in POUR.findall(corps)]
            mr = REJEU.search(corps)
            e["rejeu"] = ({"source": mr.group(1).lower(), "cmd": mr.group(2),
                           "motif": mr.group(3)} if mr else None)
            e["vus"] = ACQUIT.findall(corps)
            e["id"] = empreinte(e)
            e["quand"] = "%s %s" % (e["date"], e["heure"])
            out.append(e)
    out.sort(key=lambda e: e["quand"], reverse=True)
    if depuis:
        out = [e for e in out if e["quand"] >= depuis]
    return out


# ── la confiance : une surcouche, jamais le carnet ───────────────────────

def _etat(esp):
    return esp / ".etat" / "confiance.json"


def confiances(esp):
    try:
        return json.loads(_etat(esp).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ecrire_etat(esp, d):
    try:
        (esp / ".etat").mkdir(parents=True, exist_ok=True)
        tmp = _etat(esp).with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(_etat(esp))
    except OSError:
        pass


def _naissance(esp, ident, niveau):
    d = confiances(esp)
    if ident in d:
        return
    d[ident] = {"n": DEPART.get(_sansaccents(niveau), 60), "m": 0,
                "niveau": niveau,
                "vu": datetime.date.today().isoformat()}
    _ecrire_etat(esp, d)


def bouge(esp, idents, facteur, marque=True):
    """Le mécanisme du harnais de référence : ce que l'agent avait LU bouge quand il déclare
    son issue. Faisable ici parce que c'est le briefing qui sert les entrées —
    il sait donc exactement ce qui a été lu, sans que l'agent désigne rien."""
    if esp is None or not idents:
        return
    d = confiances(esp)
    auj = datetime.date.today().isoformat()
    for i in idents:
        c = d.get(i)
        if not c:
            continue
        c["n"] = max(PLANCHER, min(PLAFOND, round(c["n"] * facteur, 1)))
        if marque:
            c["m"] = c.get("m", 0) + 1
        c["vu"] = auj
    _ecrire_etat(esp, d)


def replancher(esp, ident, verdict):
    """Un `↻` rejoué. TIENT rend son plancher de niveau — c'est ce qui fait que
    les deux étages se tiennent : une mesure refaite RESTAURE la confiance, là
    où l'accumulation seule ne fait que l'éroder."""
    d = confiances(esp)
    c = d.get(ident)
    if not c:
        return
    if verdict == "TIENT":
        c["n"] = DEPART.get(_sansaccents(c.get("niveau", "")), 60)
    elif verdict == "TOMBÉ":
        c["n"] = max(PLANCHER, round(c["n"] * EFFONDRE, 1))
    else:
        return                      # MUET ne conclut RIEN, jamais
    c["m"] = c.get("m", 0) + 1
    c["vu"] = datetime.date.today().isoformat()
    _ecrire_etat(esp, d)


def oubli(esp, jours=30):
    """Ce qui n'est jamais relu descend d'un cran, sans être détruit."""
    d = confiances(esp)
    if not d:
        return
    limite = (datetime.date.today() - datetime.timedelta(days=jours)).isoformat()
    change = False
    for c in d.values():
        if c.get("vu", "9999") < limite:
            c["n"] = max(PLANCHER, round(c["n"] * OUBLI, 1))
            c["vu"] = datetime.date.today().isoformat()
            change = True
    if change:
        _ecrire_etat(esp, d)


def chiffre(esp_ou_conf, ident):
    """Le chiffre, ou None tant qu'il n'a pas bougé deux fois."""
    d = esp_ou_conf if isinstance(esp_ou_conf, dict) else confiances(esp_ou_conf)
    c = d.get(ident) or {}
    if c.get("m", 0) < MOUVEMENTS_AVANT_AFFICHAGE:
        return None
    return int(round(c.get("n", 0)))


# ── ce que le briefing a servi ───────────────────────────────────────────

def sert(esp, agent, session, idents):
    if esp is None or not idents:
        return
    try:
        (esp / ".etat").mkdir(parents=True, exist_ok=True)
        f = esp / ".etat" / ("%s-%s.lu" % (_slug(agent), _slug(session)))
        deja = set(f.read_text(encoding="utf-8").split()) if f.exists() else set()
        f.write_text("\n".join(sorted(deja | set(idents))), encoding="utf-8")
    except OSError:
        pass


def lu(esp, agent, session):
    if esp is None:
        return []
    f = esp / ".etat" / ("%s-%s.lu" % (_slug(agent), _slug(session)))
    try:
        return f.read_text(encoding="utf-8").split()
    except OSError:
        return []


# ── le résumé servi au démarrage ─────────────────────────────────────────
# `↩ <empreinte>` : j'ai traité cette entrée. C'est le seul geste « social » du
# dispositif — sans lui, une demande adressée à un agent resterait en tête de
# son briefing pour toujours, et il apprendrait à ne plus la lire.
ACQUIT = re.compile(r"^\s*↩\s*([0-9a-f]{6,12})\s*$", re.M)


def vise(cible, agent):
    """`↗ PO :` doit atteindre « Alpha PO ». On compare sans accents, dans les
    deux sens : un agent écrit tantôt le nom court, tantôt le nom complet."""
    c, a = _sansaccents(cible).strip(), _sansaccents(agent).strip()
    if not c or not a:
        return False
    if c in ("tous", "all", "equipe", "*"):
        return True
    return c == a or c in a.split() or a.endswith(" " + c) or c.endswith(" " + a)


def acquits(esp, agent):
    """Les empreintes que CET agent a déclaré avoir traitées."""
    out = set()
    if esp is None or not esp.is_dir():
        return out
    for f in esp.glob("*-%s.md" % _slug(agent)):
        try:
            out |= set(ACQUIT.findall(f.read_text(encoding="utf-8",
                                                  errors="replace")))
        except OSError:
            pass
    return out


def resume(esp, agent, heures=48, maxi=8):
    """Rend `(lignes, empreintes_servies)`.

    L'ORDRE EST LA MOITIÉ DU DISPOSITIF, et il n'est pas chronologique :

      1. ce qui M'EST ADRESSÉ et que je n'ai pas acquitté — sans limite d'âge,
         parce qu'une demande ne cesse pas d'exister en vieillissant ;
      2. les ÉCHECS des autres, jamais masqués. Règle reprise telle quelle à
         Le harnais de référence : un échec sert d'examen, jamais d'exemple. Le cacher au
         démarrage est la façon la plus sûre de le refaire ;
      3. le reste, par date.
    """
    if esp is None:
        return [], []
    try:
        oubli(esp)
    except Exception:
        pass
    limite = (datetime.datetime.now() - datetime.timedelta(hours=heures)) \
        .strftime("%Y-%m-%d %H:%M")
    conf = confiances(esp)
    vus = acquits(esp, agent)
    pour_moi, echecs, reste = [], [], []
    for e in entrees(esp):
        if e["auteur"] == agent:
            continue                       # je ne me relis pas moi-même
        if any(vise(q, agent) for q, _ in e["pour"]) and e["id"] not in vus:
            e["_rang"] = "→ POUR TOI"
            pour_moi.append(e)
        elif _sansaccents(e["issue"]).startswith("echou"):
            if e["quand"] >= limite:
                e["_rang"] = "ÉCHEC"
                echecs.append(e)
        elif e["quand"] >= limite:
            e["_rang"] = e["issue"]
            reste.append(e)
    choix = (pour_moi + echecs + reste)[:maxi]
    if not choix:
        return [], []
    lignes = []
    for e in choix:
        n = chiffre(conf, e["id"])
        marque = e.get("_rang") or e["issue"]
        quoi = e["texte"]
        for q, p in e["pour"]:
            if vise(q, agent):
                quoi = p                   # ce qui me concerne, pas son résumé
                break
        lignes.append("  %s · %s · %s%s — %s"
                      % (e["date"][5:], e["auteur"], marque,
                         "" if n is None else " (%d)" % n, quoi[:110]))
    caches = len(pour_moi) + len(echecs) + len(reste) - len(choix)
    if caches > 0:
        lignes.append("  … et %d autre(s) dans `equipe/`" % caches)
    return lignes, [e["id"] for e in choix]
