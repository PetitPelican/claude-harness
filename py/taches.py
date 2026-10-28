# -*- coding: utf-8 -*-
"""LES TÂCHES NOTION RESTENT À JOUR — demandé par QA (18/10/2026,
option retenue : « une garde qui lit Notion »). Un grand ménage avait remis la
base des tâches à jour ; deux jours après, elle avait décroché : les agents ne
touchaient Notion qu'aux revues.

DEUX TEMPS, ET AUCUN NE COMPTE SUR LA MÉMOIRE DE L'AGENT.
  1. Au commit (appelé par la garde de commit, dans la copie du code d'une
     équipe) : le message porte une ligne `Tâche: <id>`, `Tâche: <id> fait` ou
     `Tâche: aucune`. Sans elle, refus, avec la phrase à écrire.
  2. En fin de tour (`harnais taches`, déclencheur Stop à part) : chaque tâche
     citée par les commits DU TOUR est lue dans Notion (GET /v1/pages/<id>).
       · `fait` : les valeurs de « fini » réglées, et la preuve non vide ;
       · sinon : la page a été modifiée depuis le premier commit qui la cite ;
       · un identifiant inconnu, ou hors de la base des tâches : refus.
     Notion injoignable, délai dépassé, secret absent : un avertissement en
     clair pour le commanditaire, jamais un blocage (décision du commanditaire).

UN DÉCLENCHEUR À PART, PAS UNE GARDE DE PLUS DANS `attente`. Un appel réseau
lent ne doit pas retarder les autres gardes de fin de tour, et une panne de
Notion ne doit pas pouvoir les faire tomber.

RÉGLAGE PAR PROJET, éteint par défaut : la variable `HARNAIS_TACHES`, un objet
JSON posé dans les réglages des agents (comme `HARNAIS_CANAL`) :

    {"base": "<id de la base des tâches>",
     "secret": "NOTION_LECTURE_TOKEN", "coffre": "projet/dev",
     "fait": {"Statut": ["🟢 Fait", "🟢 Vérifié"],
              "Niveau d’avancement": "Terminé"},
     "preuve": "Description"}

LE SECRET n'est jamais affiché ni journalisé : lu dans l'environnement s'il y
est, sinon par `doppler secrets get --plain`, capturé, jamais recopié.

LES COMMITS DU TOUR se lisent dans le reflog de HEAD de chaque copie du code de
l'agent (`code`, `code-*`) : il est propre à la copie, donc les commits des
autres agents — même dépôt, autres copies — n'y sont pas. Le tour commence au
dernier message qui n'est pas de l'agent (un renvoi de fin de tour n'en ouvre
pas un nouveau).

CE QUI N'EST PAS VU : un commit fait hors de `git commit` (cherry-pick, rebase,
fusion) ne cite rien pour la fin de tour ; Notion arrondit l'heure de
modification à la minute — une page touchée dans la minute du commit, juste
avant lui, passe.
"""
import json
import os
import re
import sys

ID = r"[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
VALEUR = re.compile(r"^(?:(aucune)|(%s)(?:[ \t]+(fait))?)\.?$" % ID, re.I)
# Dans un message : en début de ligne. Dans une commande : aussi juste après un
# guillemet (`-m "Tâche: …"`), un `-m` ou un `\n` littéral de `$'…'`.
LIGNE_MESSAGE = re.compile(r"^[ \t]*T[âa]che[ \t]*:[ \t]*([^\n]*?)[ \t]*$", re.I | re.M)
LIGNE_COMMANDE = re.compile(
    r"(?:^|\n|[\"']|\\n|-m[ \t]*)[ \t]*T[âa]che[ \t]*:[ \t]*([^\n\"'\\]*)", re.I)
API = "https://api.notion.com"
VERSION_NOTION = "2022-06-28"
SECRET = "NOTION_LECTURE_TOKEN"
MAX_TACHES = 8           # lues par fin de tour ; au-delà, dit sans bloquer
DELAI = 6                # secondes par appel
BUDGET = 22              # secondes pour tout le tour (déclencheur à 30)
RENVOIS_MAX = 3          # renvois de suite, puis on laisse finir en le disant

PHRASE = ("ajoute au message une ligne « Tâche: <identifiant Notion à 32 caractères> » "
          "(la tâche avance), « Tâche: <identifiant> fait » (ce commit la termine) ou "
          "« Tâche: aucune ».")


def reglage():
    """Le réglage du projet, ou `None` (garde éteinte). Illisible = éteinte, mais
    dit : une garde qu'on croit posée et qui ne lit pas son réglage est pire
    qu'une garde absente."""
    brut = os.environ.get("HARNAIS_TACHES", "").strip()
    if not brut:
        return None
    try:
        r = json.loads(brut)
    except ValueError:
        return {"erreur": "HARNAIS_TACHES n'est pas du JSON lisible"}
    if not isinstance(r, dict) or not r.get("base"):
        return {"erreur": "HARNAIS_TACHES n'a pas de « base » (l'identifiant de la base des tâches)"}
    bases = r["base"] if isinstance(r["base"], list) else [r["base"]]
    fait = r.get("fait") if isinstance(r.get("fait"), dict) else {}
    return {
        "bases": set(_id(b) for b in bases if isinstance(b, str)),
        "secret": r.get("secret") or SECRET,
        "coffre": r.get("coffre") or "",
        "api": (r.get("api") or API).rstrip("/"),
        "fait": sorted((k, v if isinstance(v, list) else [v]) for k, v in fait.items()),
        "preuve": r["preuve"] if isinstance(r.get("preuve"), str) else None,
    }


def _id(s):
    return s.replace("-", "").strip().lower()


def _nom(s):
    """« Niveau d’avancement » et « Niveau d'avancement » sont le même nom : Notion
    écrit l'apostrophe typographique, un réglage tapé à la main la droite."""
    return s.replace("’", "'").strip().lower()


def lis_valeur(v):
    """`(\"aucune\" | id, fait)` — ou `None` si la valeur n'est pas reconnue."""
    m = VALEUR.match(v.strip())
    if not m:
        return None
    if m.group(1):
        return ("aucune", False)
    return (_id(m.group(2)), bool(m.group(3)))


# --- 1. AU COMMIT ------------------------------------------------------------

def _message_de_fichier(cmd, dossier):
    m = re.search(r"(?:^|\s)(?:-F|--file)(?:[ \t]+|=)([\"']?)([^\s\"']+)\1", cmd)
    if not m:
        return None
    p = m.group(2)
    if p == "-":
        return None
    p = p if os.path.isabs(p) else os.path.join(dossier, p)
    try:
        with open(p, encoding="utf-8", errors="replace") as h:
            return h.read()
    except OSError:
        return ""


def juge_commit(cmd, dossier):
    """Le motif d'un refus, ou `None`. Appelé par la garde de commit pour un
    commit dans la copie du code d'une équipe."""
    r = reglage()
    if r is None or "erreur" in r:
        return None
    # Les options se lisent APRÈS `commit` : `git -C code commit` porte un `-C`
    # qui est celui de git, pas « reprends le message de ce commit ».
    m = re.search(r"\bcommit\b", cmd)
    apres = cmd[m.end():] if m else cmd
    # Message repris tel quel : il a été jugé à son premier passage.
    if re.search(r"(?:^|\s)(?:-C|-c|--reuse-message|--reedit-message|--fixup|--squash)\b", apres) or \
            ("--amend" in apres and "--no-edit" in apres):
        return None
    texte = _message_de_fichier(apres, dossier)
    if texte is not None:
        valeurs = [m.group(1) for m in LIGNE_MESSAGE.finditer(texte)]
    elif re.search(r"(?:^|\s)(?:-[a-zA-Z]*m|--message)", apres):
        valeurs = [m.group(1) for m in LIGNE_COMMANDE.finditer(apres)]
    else:
        return ("mind-guard : ce commit ouvrirait un éditeur, et sur ce projet son message doit "
                "citer sa tâche Notion. Passe le message par -m, et " + PHRASE)
    if not valeurs:
        return "mind-guard : ce commit ne cite pas sa tâche Notion. Sur ce projet, " + PHRASE
    if any(lis_valeur(v) is not None for v in valeurs):
        return None
    return ("mind-guard : la ligne « Tâche: %s » n'est pas lisible. %s"
            % (valeurs[0].strip()[:60], PHRASE[0].upper() + PHRASE[1:]))


# --- 2. EN FIN DE TOUR -------------------------------------------------------

def _git(d, *a):
    import subprocess
    try:
        o = subprocess.run(["git", "-C", d] + list(a), stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return o.stdout.decode("utf-8", "replace") if o.returncode == 0 else None


def copies(racine):
    """Les copies du code de l'agent : `code` et `code-*`, qui portent un `.git`."""
    try:
        noms = sorted(os.listdir(racine))
    except OSError:
        return []
    return [os.path.join(racine, n) for n in noms
            if (n == "code" or n.startswith("code-")) and os.path.exists(os.path.join(racine, n, ".git"))]


def debut_du_tour(chemin):
    """L'heure (secondes) du dernier message qui n'est pas de l'agent, ni un
    résultat d'outil, ni un renvoi de fin de tour. `None` si illisible."""
    import datetime
    if not isinstance(chemin, str) or not chemin:
        return None
    try:
        with open(chemin, "rb") as f:
            taille = os.fstat(f.fileno()).st_size
            f.seek(max(0, taille - 3000000))
            brut = f.read().decode("utf-8", "replace")
    except (OSError, ValueError):
        return None
    debut = None
    for l in brut.split("\n"):
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if not isinstance(e, dict) or e.get("type") != "user" or e.get("isMeta") is True:
            continue
        m = e.get("message")
        c = m.get("content") if isinstance(m, dict) else None
        if isinstance(c, list) and c and all(isinstance(x, dict) and x.get("type") == "tool_result" for x in c):
            continue
        t = e.get("timestamp")
        if isinstance(t, str):
            try:
                d = datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
            except ValueError:
                continue
            debut = d.timestamp()
    return debut


def commits_du_tour(copie, debut):
    """`[(sha, heure)]` des commits faits par `git commit` dans cette copie depuis
    `debut`, du plus ancien au plus récent."""
    out = _git(copie, "log", "-g", "--date=unix", "--format=%H%x09%gd%x09%gs", "HEAD")
    if out is None:
        return []
    vus, res = set(), []
    for l in out.splitlines():
        p = l.split("\t", 2)
        if len(p) < 3:
            continue
        m = re.search(r"@\{(\d+)\}", p[1])
        if not m:
            continue
        t = int(m.group(1))
        # Le reflog compte en secondes entières : un commit fait dans la seconde
        # où le tour commence porte la seconde ARRONDIE, donc « avant » lui.
        if t < int(debut):
            break
        if p[2].startswith("commit") and p[0] not in vus:
            vus.add(p[0])
            res.append((p[0], t))
    return list(reversed(res))


def taches_citees(racine, debut):
    """`{id: {"fait": bool, "premier": heure}}` pour le tour."""
    res = {}
    for c in copies(racine):
        for sha, t in commits_du_tour(c, debut):
            msg = _git(c, "log", "-1", "--format=%B", sha) or ""
            for m in LIGNE_MESSAGE.finditer(msg):
                v = lis_valeur(m.group(1))
                if v is None or v[0] == "aucune":
                    continue
                e = res.setdefault(v[0], {"fait": False, "premier": t})
                e["fait"] = e["fait"] or v[1]
                e["premier"] = min(e["premier"], t)
    return res


def secret(r, racine):
    """La valeur du secret, ou `None`. Jamais affichée, jamais écrite."""
    v = os.environ.get(r["secret"], "").strip()
    if v:
        return v
    import shutil
    import subprocess
    d = shutil.which("doppler")
    if not d:
        return None
    a = [d, "secrets", "get", r["secret"], "--plain"]
    if "/" in r["coffre"]:
        projet, config = r["coffre"].split("/", 1)
        a += ["--project", projet, "--config", config]
    try:
        o = subprocess.run(a, cwd=racine, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return None
    v = o.stdout.decode("utf-8", "replace").strip()
    return v if o.returncode == 0 and v else None


class Injoignable(Exception):
    pass


INTROUVABLE, INTERDITE = "introuvable", "interdite"


def lis_page(r, jeton, ident):
    """La page en JSON ; `INTROUVABLE` (400, 404 : l'identifiant n'existe pas) ;
    `INTERDITE` (403 : la page existe peut-être, l'accès en lecture n'y a pas
    droit — mesuré par QA le 18/10, deux refus distincts). Lève `Injoignable`
    pour tout le reste : réseau, délai, jeton refusé (401)."""
    import urllib.error
    import urllib.request
    q = urllib.request.Request("%s/v1/pages/%s" % (r["api"], ident), headers={
        "Authorization": "Bearer " + jeton, "Notion-Version": VERSION_NOTION})
    try:
        with urllib.request.urlopen(q, timeout=DELAI) as h:
            return json.loads(h.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            return INTROUVABLE
        if e.code == 403:
            return INTERDITE
        raise Injoignable("Notion répond %d" % e.code)
    except Exception as e:  # réseau, délai, réponse illisible
        raise Injoignable(type(e).__name__)


def texte_propriete(p):
    """La valeur lisible d'une propriété Notion, quel que soit son type."""
    if not isinstance(p, dict):
        return ""
    t = p.get("type")
    v = p.get(t)
    if t in ("select", "status"):
        return (v or {}).get("name", "") if isinstance(v, dict) or v is None else ""
    if t in ("rich_text", "title"):
        return "".join(x.get("plain_text", "") for x in (v or []) if isinstance(x, dict))
    if t == "multi_select":
        return ", ".join(x.get("name", "") for x in (v or []) if isinstance(x, dict))
    if t in ("number", "checkbox", "url", "email", "phone_number"):
        return "" if v is None or v is False else str(v)
    if t == "date":
        return (v or {}).get("start", "") if isinstance(v, dict) else ""
    return ""


def _heure(iso):
    import datetime
    try:
        return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def juge_page(r, ident, citee, page):
    """Le motif d'un refus pour cette tâche, ou `None`."""
    if page == INTERDITE:
        return ("la page %s existe peut-être, mais l'accès en lecture de la garde n'y a pas droit "
                "(403) : cite une tâche de la base des tâches." % ident)
    if page == INTROUVABLE or not isinstance(page, dict):
        return ("la tâche %s n'existe pas dans Notion : corrige l'identifiant dans un nouveau "
                "commit, ou cite « Tâche: aucune »." % ident)
    parent = page.get("parent") or {}
    ids = set(_id(parent.get(k, "")) for k in ("database_id", "data_source_id") if parent.get(k))
    if not ids & r["bases"]:
        return "la page %s n'est pas une tâche (elle n'est pas dans la base des tâches)." % ident
    props = dict((_nom(k), v) for k, v in (page.get("properties") or {}).items())
    titre = ""
    for v in props.values():
        if isinstance(v, dict) and v.get("type") == "title":
            titre = texte_propriete(v)
    nom = "« %s »" % titre if titre else ident
    if citee["fait"]:
        manque = []
        for k, attendus in r["fait"]:
            vu = texte_propriete(props.get(_nom(k)))
            if vu not in attendus:
                manque.append("%s vaut « %s », attendu « %s »" % (k, vu or "vide", " » ou « ".join(attendus)))
        if r["preuve"] and not texte_propriete(props.get(_nom(r["preuve"]))).strip():
            manque.append("%s est vide : écris-y la preuve" % r["preuve"])
        if manque:
            return "la tâche %s est citée « fait », mais %s." % (nom, " ; ".join(manque))
        return None
    vu = _heure(page.get("last_edited_time", ""))
    # Notion arrondit à la minute : on compare à la minute du premier commit.
    if vu is None or vu < citee["premier"] - citee["premier"] % 60:
        return ("mets à jour la tâche %s : où elle en est (elle n'a pas bougé depuis le commit "
                "qui la cite)." % nom)
    return None


def _etat(nom):
    import socle
    d = os.path.join(socle.socle(), "taches")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return os.path.join(d, nom)


def _lis(p):
    try:
        with open(p, encoding="utf-8") as h:
            return h.read().strip()
    except OSError:
        return ""


def _ecris(p, t):
    try:
        with open(p, "w", encoding="utf-8") as h:
            h.write(t)
    except OSError:
        pass


def _note(texte):
    """Un avertissement pour le commanditaire, sans bloquer (voir
    `attente.enveloppe_note` : à code 0, seul `systemMessage` arrive)."""
    sys.stdout.write(json.dumps({"systemMessage": texte}, ensure_ascii=False) + "\n")


def fin_de_tour(data):
    """Rend `(code, texte)` : 2 et le renvoi ; 0 et une note (ou rien)."""
    import time
    r = reglage()
    if r is None:
        return 0, None
    if "erreur" in r:
        return 0, "taches : garde éteinte — %s." % r["erreur"]
    racine = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    debut = debut_du_tour(data.get("transcript_path"))
    if debut is None:
        return 0, None
    citees = taches_citees(racine, debut)
    if not citees:
        return 0, None
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("session_id") or "x"))[:64] or "x"
    jeton = secret(r, racine)
    if not jeton:
        f = _etat(sid + ".secret")
        if _lis(f) == str(int(debut)):
            return 0, None
        _ecris(f, str(int(debut)))
        return 0, ("taches : le secret %s est introuvable (environnement, puis coffre) — les %d "
                   "tâche(s) citée(s) ce tour n'ont pas été vérifiées dans Notion."
                   % (r["secret"], len(citees)))
    t0 = time.time()
    refus, notes = [], []
    ids = sorted(citees, key=lambda i: citees[i]["premier"])
    for i in ids[:MAX_TACHES]:
        if time.time() - t0 > BUDGET:
            notes.append("délai épuisé avant la tâche %s" % i)
            break
        try:
            page = lis_page(r, jeton, i)
        except Injoignable as e:
            notes.append("Notion injoignable (%s) : tâches non vérifiées ce tour" % e)
            break
        m = juge_page(r, i, citees[i], page)
        if m:
            refus.append(m)
    if len(ids) > MAX_TACHES:
        notes.append("%d tâche(s) au-delà des %d lues ce tour" % (len(ids) - MAX_TACHES, MAX_TACHES))
    f = _etat(sid + ".renvois")
    if refus:
        n = int(_lis(f) or 0)
        if n < RENVOIS_MAX:
            _ecris(f, str(n + 1))
            return 2, ("taches : les tâches Notion citées par tes commits de ce tour ne sont pas à jour.\n"
                       + "".join("  · %s\n" % m for m in refus)
                       + "Mets-les à jour dans Notion, puis termine. Si Notion ne te laisse pas "
                         "écrire, dis-le dans ton message : au bout de %d renvois, je laisse finir "
                         "et je le signale au commanditaire." % RENVOIS_MAX)
        notes.append("%d tâche(s) restée(s) pas à jour après %d renvois" % (len(refus), RENVOIS_MAX))
    try:
        os.remove(f)
    except OSError:
        pass
    if notes:
        return 0, "taches : " + " ; ".join(notes) + "."
    return 0, None


def main(entree):
    # Éteinte : rien n'est importé, rien n'est lu.
    if not os.environ.get("HARNAIS_TACHES", "").strip():
        return
    try:
        data = json.loads(entree)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    code, texte = fin_de_tour(data)
    if code == 2:
        sys.stderr.write(texte + "\n")
        sys.stderr.flush()
        sys.exit(2)
    if texte:
        _note(texte)
