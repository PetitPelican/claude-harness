# -*- coding: utf-8 -*-
"""`harnais demenage` — UNE ÉQUIPE `brain/` PASSE À « UN DOSSIER PAR AGENT ».

POURQUOI (décision du 14/10/2026 : il n'est pas logique d'avoir plusieurs
dossiers avec les mêmes agents dans des dossiers différents). Mesuré le même
jour sur une équipe réelle : le badge de chaque agent en 9 exemplaires, ce qui concerne
un agent dans 3 endroits, 12 copies du code dont 5 posées à la main dans un
dossier caché hors du projet. Plan approuvé par le commanditaire après l'avis de QA.

    AVANT                                   APRÈS
    P/            le code (copie princ.)    P/                 la MÉMOIRE (son dépôt)
    P/brain/      la mémoire (son dépôt)      fact/ shared/ docs/ assets/ CLAUDE.md
    P/agents/<n>/ badges, ×1 par copie        agents/<n>/       badge ×1, state, todo
    ../.worktrees/<copie>/  les copies          agents/<n>/code/  sa copie du code

LA SÉQUENCE DU CODE EST CELLE DE QA, REJOUÉE PAR LUI SUR UN DÉPÔT JETABLE. Le
checkout principal ne se déplace pas par `git worktree move` (« '.' is a main
working tree ») ; et après les `mv`, chaque copie pointe vers `P/.git`, devenu
le `.git` de la MÉMOIRE — un `move` est alors refusé. D'où :

    1. relevé          copies, branches, inventaire (fichiers ignorés compris)
    2. mv P -> P.code-demenage ; mv P.code-demenage/brain -> P
    3. mv P.code-demenage -> P/agents/<premier>/code
    4. git worktree repair <chemins ACTUELS des copies>, depuis le nouveau principal
    5. git worktree move <copie> P/agents/<n>/code[-<sujet>]
    6. repair final, puis le TÉMOIN : même nombre de copies, mêmes branches,
       aucune ne pointe vers un `.git` absent, inventaire identique
    — sinon RETOUR ARRIÈRE par les mêmes gestes, en sens inverse.

Puis, dans la mémoire seulement : `mind/<n>` -> `agents/<n>`, `workspace` ->
`shared` (git mv), badges posés en UN exemplaire (droits réécrits), `docs/` et
les livrables copiés et vérifiés à l'octet, consignes communes remontées, un
seul enregistrement. Enfin les conversations et les inscriptions au paquet.

**CE QU'IL NE FAIT PAS, ET LE DIT** : enregistrer quoi que ce soit dans le
dépôt du CODE (retirer `agents/`, `CLAUDE.md`, `docs/`) — c'est sur demande de
l'humain ; trier les copies qu'aucun agent ne lance ; relire la prose.

**À BLANC PAR DÉFAUT.** `--apply --agents-arretes` écrit, et seulement si rien
ne bloque : agents arrêtés, synchronisation coupée, mémoire propre, `docs/`
identique dans toutes les copies, aucun secret dans ce qui monte (la mémoire
part sur GitHub).
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import memoire
import niveau
import socle
from memoire import Forme

V, R, J, B, D, X = "\x1b[32m", "\x1b[31m", "\x1b[33m", "\x1b[1m", "\x1b[2m", "\x1b[0m"

# Ce qui ne monte JAMAIS dans la mémoire, qui part sur GitHub (QA, 14/10/2026).
SECRETS_NOMS = re.compile(r"(^|/)(\.env(\..*)?|operations\.md|id_rsa.*|.*\.pem|.*\.p12|.*\.key)$")
SECRETS_TEXTE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk_live_[0-9A-Za-z]{8,}|\bAKIA[0-9A-Z]{16}\b")
# Le code ne garde plus ces dossiers : ils vivent dans la mémoire.
QUITTENT_LE_CODE = ("agents", "brain", "docs", "assets", "CLAUDE.md")
INVENTAIRE_SAUF = ("node_modules", ".git")


def _p(s=""):
    sys.stdout.write(s + "\n")


def _lis(f):
    with open(f, encoding="utf-8") as h:
        return h.read()


def _git(ou, args):
    o = subprocess.run(["git"] + list(args), cwd=ou, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return o.returncode, o.stdout.decode("utf-8", "replace"), o.stderr.decode("utf-8", "replace")


def _ok(ou, args):
    c, out, err = _git(ou, args)
    if c != 0:
        raise RuntimeError("git %s (dans %s) : %s" % (" ".join(args), ou, (err or out).strip()[:300]))
    return out


def vivante(c):
    """Une copie qu'on peut réparer et déplacer : son dossier ET son `.git`. Les
    autres (« prunable ») restent telles quelles, nommées."""
    return os.path.isdir(c) and os.path.exists(os.path.join(c, ".git"))


def copies(principal):
    """`[(chemin, branche ou None)]`, le principal en premier — `git worktree list`."""
    out = _ok(principal, ["worktree", "list", "--porcelain"])
    v, cur = [], None
    for l in out.split("\n"):
        if l.startswith("worktree "):
            cur = [l[len("worktree "):], None]
            v.append(cur)
        elif l.startswith("branch ") and cur is not None:
            cur[1] = l[len("branch refs/heads/"):] if l.startswith("branch refs/heads/") else l[7:]
    return [(os.path.realpath(p), b) for p, b in v]


def inventaire(racine):
    """`{chemin relatif: (taille, mtime_ns)}` — fichiers ignorés compris, sans
    `node_modules` ni `.git` (comptés à part). Un `mv` garde les deux : c'est le
    témoin qu'aucun fichier n'est resté en route, `.env*` compris."""
    v, lourds = {}, 0
    for d, dirs, fs in os.walk(racine):
        garde = []
        for x in dirs:
            if x in INVENTAIRE_SAUF:
                lourds += 1
            else:
                garde.append(x)
        dirs[:] = garde
        for f in fs:
            # Le `.git` d'une copie est un FICHIER que git réécrit en la réparant :
            # son changement est le geste, pas une perte.
            if f == ".git":
                continue
            # Un `node_modules` qui est un LIEN vers une autre copie pend quand celle-ci
            # déménage : os.walk le range alors parmi les fichiers. Il reste hors compte.
            if f in INVENTAIRE_SAUF:
                continue
            p = os.path.join(d, f)
            try:
                s = os.lstat(p)
            except OSError:
                continue
            v[os.path.relpath(p, racine)] = (s.st_size, s.st_mtime_ns)
    return v, lourds


def empreinte(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def arbre_empreintes(racine):
    v = {}
    for d, dirs, fs in os.walk(racine):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in fs:
            if f == ".DS_Store":
                continue
            p = os.path.join(d, f)
            if os.path.isfile(p) and not os.path.islink(p):
                v[os.path.relpath(p, racine)] = empreinte(p)
    return v


def secrets(racine, rel_base=""):
    """Les fichiers qui ne doivent JAMAIS monter dans la mémoire : par nom, puis par
    contenu (les fichiers de moins de 2 Mo)."""
    out = []
    if not os.path.exists(racine):
        return out
    fichiers = [racine] if os.path.isfile(racine) else [
        os.path.join(d, f) for d, dirs, fs in os.walk(racine) for f in fs]
    for p in fichiers:
        rel = os.path.join(rel_base, os.path.relpath(p, os.path.dirname(racine)))
        if SECRETS_NOMS.search(rel.replace(os.sep, "/")):
            out.append(rel)
            continue
        try:
            if os.path.getsize(p) > 2 * 1024 * 1024:
                continue
            with open(p, "rb") as f:
                t = f.read().decode("utf-8", "ignore")
        except OSError:
            continue
        if SECRETS_TEXTE.search(t):
            out.append(rel)
    return out


def _trace(lancement):
    try:
        with open(os.path.join(lancement, ".claude", ".briefing.json"), encoding="utf-8") as f:
            d = json.load(f).get("derniere")
        return float(d) if isinstance(d, (int, float)) and not isinstance(d, bool) else 0.0
    except (OSError, ValueError, AttributeError):
        return 0.0


class Plan(object):
    def __init__(self, projet):
        self.projet = projet
        self.memoire = os.path.join(projet, "brain")
        self.temp = projet.rstrip("/") + ".code-demenage"
        self.agents = []          # noms, dans l'ordre de `brain/mind/`
        self.premier = None       # l'agent qui reçoit le checkout principal
        self.copies = []          # [(chemin, branche)] — toutes, principal en tête
        self.lance = {}           # nom -> copie d'où il se lance (chemin)
        self.en_plus = []         # [(nom, sujet, copie)]
        self.livrables = []       # chemins relatifs au code, copiés dans assets/
        self.restent = []         # copies qu'aucun agent ne reprend
        self.bloquants = []
        self.notes = []
        self.corr = None          # calculées avant le déplacement

    def code(self):
        return os.path.join(self.projet, "agents", self.premier, "code")

    def niche(self, copie):
        """Une copie posée DANS le checkout principal (celles de Claude Code, sous
        `.claude/worktrees/`) part avec lui : où elle se trouve après le `mv`."""
        p = self.projet.rstrip(os.sep) + os.sep
        if copie != self.projet and copie.startswith(p):
            return os.path.join(self.code(), copie[len(p):])
        return None

    def cible(self, copie):
        """Où une copie arrive."""
        if copie == self.copies[0][0]:
            return self.code()
        for n, c in self.lance.items():
            if c == copie:
                return os.path.join(self.projet, "agents", n, "code")
        for n, s, c in self.en_plus:
            if c == copie:
                return os.path.join(self.projet, "agents", n, "code-" + s)
        return None


def planifie(projet, choix, en_plus, livrables):
    projet = os.path.realpath(projet)
    pl = Plan(projet)
    r = memoire.resous(projet)
    if r.forme != Forme.Brain or not r.brain_autonome:
        pl.bloquants.append("forme `%s` : l'outil part d'une équipe `brain/` dont la mémoire a son "
                            "propre dépôt" % memoire.forme_mot(r.forme))
        return pl
    if memoire.racine_depot(projet) != projet:
        pl.bloquants.append("`%s` n'est pas le checkout principal du code" % projet)
        return pl
    mind = os.path.join(pl.memoire, "mind")
    pl.agents = sorted(n for n in os.listdir(mind) if os.path.isdir(os.path.join(mind, n))) \
        if os.path.isdir(mind) else []
    if not pl.agents:
        pl.bloquants.append("aucun agent dans `brain/mind/` : ce n'est pas une équipe")
        return pl
    try:
        toutes = copies(projet)
    except RuntimeError as e:
        pl.bloquants.append(str(e))
        return pl
    # UNE COPIE DÉJÀ DISPARUE (« prunable ») n'a rien à déménager : elle est
    # nommée, et le témoin ne la compte pas.
    pl.copies = [(c, b) for c, b in toutes if vivante(c)]
    for c, _ in toutes:
        if not os.path.isdir(c):
            pl.notes.append("copie déjà disparue du disque, ignorée : %s (`git worktree prune`)" % c)
        elif not vivante(c):
            pl.notes.append("copie sans `.git`, ignorée et laissée telle quelle : %s" % c)
    chemins = [c for c, _ in pl.copies]
    # D'OÙ CHAQUE AGENT SE LANCE : la copie dont `agents/<nom>/` a la trace
    # d'entrée la plus récente ; `--copie NOM=CHEMIN` l'impose.
    for n in pl.agents:
        if n in choix:
            c = os.path.realpath(choix[n])
            if c not in chemins:
                pl.bloquants.append("--copie %s : `%s` n'est pas une copie de ce dépôt" % (n, c))
            pl.lance[n] = c
            continue
        cands = [(_trace(os.path.join(c, "agents", n)), c) for c in chemins
                 if os.path.isdir(os.path.join(c, "agents", n))]
        if not cands:
            pl.bloquants.append("`%s` n'a de badge dans aucune copie : `--copie %s=<copie>`" % (n, n))
            continue
        pl.lance[n] = max(cands)[1]
    # LE PREMIER REÇOIT LE CHECKOUT PRINCIPAL, qui ne se déplace qu'en bloc.
    principaux = [n for n, c in pl.lance.items() if c == projet]
    if len(principaux) != 1:
        pl.bloquants.append("il faut exactement UN agent lancé depuis le checkout principal "
                            "(trouvés : %s) — `--copie`" % (", ".join(principaux) or "aucun"))
    else:
        pl.premier = principaux[0]
    vus = {}
    for n, c in pl.lance.items():
        if c in vus:
            pl.bloquants.append("`%s` et `%s` partagent la même copie" % (vus[c], n))
        vus[c] = n
    for spec in en_plus:
        m = re.match(r"^([^:=]+):([A-Za-z0-9._-]+)=(.+)$", spec)
        if m is None:
            pl.bloquants.append("--en-plus `%s` : la forme est NOM:SUJET=CHEMIN" % spec)
            continue
        n, s, c = m.group(1), m.group(2), os.path.realpath(m.group(3))
        if n not in pl.agents:
            pl.bloquants.append("--en-plus : `%s` n'est pas un agent" % n)
        if c not in chemins or c in vus:
            pl.bloquants.append("--en-plus : `%s` n'est pas une copie libre de ce dépôt" % c)
        pl.en_plus.append((n, s, c))
        vus[c] = n
    pl.restent = [c for c in chemins if c not in vus]
    pl.livrables = list(livrables)
    _verifie(pl)
    if pl.premier:
        pl.corr = correspondances(pl)
    return pl


def _verifie(pl):
    p = pl.projet
    if os.path.exists(pl.temp):
        pl.bloquants.append("`%s` existe déjà : un déménagement interrompu ? Le regarder d'abord" % pl.temp)
    c, out, _ = _git(pl.memoire, ["status", "--porcelain"])
    if c != 0:
        pl.bloquants.append("`brain/` ne répond pas à git")
    elif out.strip():
        pl.bloquants.append("la mémoire a des changements non enregistrés (%d) : laisser la "
                            "synchronisation finir, puis la couper" % len(out.strip().split("\n")))
    for x in ("agents", "shared", "docs", "assets", "CLAUDE.md"):
        if os.path.exists(os.path.join(pl.memoire, x)):
            pl.bloquants.append("`brain/%s` existe déjà : il serait écrasé par ce qui monte" % x)
    # `docs/` : UN exemplaire monte, il faut qu'il n'y en ait qu'une version.
    ref = os.path.join(p, "docs")
    if os.path.isdir(ref):
        e_ref = arbre_empreintes(ref)
        for n, c in sorted(pl.lance.items()):
            if c == p:
                continue
            d = os.path.join(c, "docs")
            e = arbre_empreintes(d) if os.path.isdir(d) else {}
            ecart = sorted(k for k in set(e_ref) | set(e) if e_ref.get(k) != e.get(k))
            if ecart:
                pl.bloquants.append("`docs/` diffère entre la copie principale et celle de %s (%d "
                                    "fichier(s) : %s) — à réunir avant le jour J"
                                    % (n, len(ecart), ", ".join(ecart[:5]) + (", …" if len(ecart) > 5 else "")))
    for x in ["docs", "assets", "CLAUDE.md"] + pl.livrables:
        s = secrets(os.path.join(p, x))
        if s:
            pl.bloquants.append("ce qui monte dans la mémoire (publiée sur GitHub) porte des fichiers "
                                "sensibles : %s" % ", ".join(s[:5]))
    for x in pl.livrables:
        if not os.path.exists(os.path.join(p, x)):
            pl.bloquants.append("--livrable `%s` n'existe pas dans le code" % x)
    for n, c in pl.lance.items():
        b = os.path.join(c, "agents", n)
        if not os.path.isfile(os.path.join(b, ".claude", "settings.json")):
            pl.notes.append("%s : aucun réglage dans `%s` — son badge sera sans droits" % (n, b))


# ── LES DROITS : réécrits vers la nouvelle forme ─────────────────────────────

def correspondances(pl):
    """`[(ancien, nouveau)]`, du plus long au plus court — CALCULÉES AVANT LE
    DÉPLACEMENT, sur la forme d'avant.

    CHAQUE ANCIENNE RÈGLE GARDE SON SENS D'ORIGINE. Tout ce qui était sous le
    checkout principal visait le code d'OPS (ou de qui l'avait), `agents/`
    compris : c'était le dossier des badges SUIVI PAR LE CODE. Le réécrire vers
    le nouveau `agents/` de la mémoire changeait son sens — trouvé au banc le
    14/10/2026 : la règle « ne touche pas `agents/` » de PO aurait visé son propre
    état et son propre code. Le périmètre de la nouvelle forme est POSÉ à part
    (`perimetre`), pas déduit."""
    p = pl.projet
    code = os.path.join(p, "agents", pl.premier, "code") if pl.premier else None
    v = [(os.path.join(p, "brain", "mind", n), os.path.join(p, "agents", n)) for n in pl.agents]
    v += [(os.path.join(p, "brain", "workspace"), os.path.join(p, "shared")),
          (os.path.join(p, "brain", "fact"), os.path.join(p, "fact")),
          (os.path.join(p, "brain"), p)]
    for c, _ in pl.copies:
        t = pl.cible(c)
        if t is not None and c != p and not pl.niche(c):
            v.append((c, t))
    if code:
        try:
            enfants = sorted(os.listdir(p))
        except OSError:
            enfants = []
        for x in enfants:
            if x not in ("brain", ".git"):
                v.append((os.path.join(p, x), os.path.join(code, x)))
        v.append((p, code))
    return sorted(v, key=lambda c: -len(c[0]))


def _orthographes(p):
    v = [p]
    h = socle.maison()
    if h:
        h = h.rstrip(os.sep)
        if p.startswith(h + os.sep):
            v.append("~/" + p[len(h) + 1:])
    return v


def remplace(texte, corr):
    """UN SEUL PASSAGE, la plus longue d'abord, à une borne de chemin : un
    remplacement n'est jamais relu par le suivant (le premier banc a vu
    `brain/workspace` devenir `shared`, puis `shared` devenir le code)."""
    table = {}
    for a, b in corr:
        for x, y in zip(_orthographes(a), _orthographes(b)):
            table.setdefault(x, y)
    if not table:
        return texte, 0
    motif = re.compile("(" + "|".join(re.escape(k) for k in sorted(table, key=len, reverse=True))
                       + r')(?=[/"\s):*,\]]|$)')
    n = [0]

    def f(m):
        n[0] += 1
        return table[m.group(1)]
    return motif.sub(f, texte), n[0]


def perimetre(pl, nom):
    """LE PÉRIMÈTRE DE LA NOUVELLE FORME, posé : le dossier de chaque autre agent
    (son état, son badge, son code), et ses propres droits."""
    import equipe
    v = []
    for a in pl.agents:
        cible = a if a != nom else None
        if cible:
            v.append(equipe._perimetre(pl.projet, a))
    # `Edit(...)` SEUL : il couvre tous les outils d'écriture de fichiers, et
    # Claude Code signale `Write(...)` comme une règle qui ne mord pas (banc).
    return v + [equipe._perimetre(pl.projet, nom).replace("/**)", "/.claude/**)")] + list(equipe.SANS_COPIE_ISOLEE)


CROCHETS = re.compile(r"\$\{CLAUDE_PROJECT_DIR(:-[^}]*)?\}/\.\./\.\./\.claude/hooks")


def reecrit_badge(texte, pl):
    """Les crochets du projet s'écrivaient depuis `agents/<nom>/` d'une copie du
    code, deux étages plus bas que sa racine ; ils vivent désormais dans
    `code/`. Les deux orthographes existent dans les équipes réelles, avec et sans valeur par
    défaut (`${CLAUDE_PROJECT_DIR:-.}`) — relevé sur les vrais droits de QA."""
    t = CROCHETS.sub(lambda m: "${CLAUDE_PROJECT_DIR%s}/code/.claude/hooks" % (m.group(1) or ""), texte)
    corr = pl.corr if pl.corr is not None else correspondances(pl)

    def marche(o):
        if isinstance(o, dict):
            return {k: marche(x) for k, x in o.items()}
        if isinstance(o, list):
            return [marche(x) for x in o]
        if isinstance(o, str):
            y, k = remplace(o, corr)
            compte[0] += k
            return y
        return o
    compte = [0]
    v = marche(json.loads(t) if t.strip() else {})
    return json.dumps(v, indent=2, ensure_ascii=False) + "\n", compte[0] + (1 if t != texte else 0)


# ── LE GESTE ────────────────────────────────────────────────────────────────

class Echec(Exception):
    pass


def _journal(pl, fait, geste):
    fait.append(geste)
    f = pl.projet.rstrip("/") + ".demenage.json"
    try:
        with open(f, "w", encoding="utf-8") as h:
            json.dump({"projet": pl.projet, "fait": fait}, h, ensure_ascii=False, indent=1)
    except OSError:
        pass


def _dossier(pl, fait, d):
    """`makedirs` qui inscrit chaque dossier créé au journal : le retour arrière les
    retire, sinon l'essai suivant trouve `brain/agents` et refuse."""
    manquants = []
    while d and not os.path.isdir(d):
        manquants.append(d)
        d = os.path.dirname(d)
    for x in reversed(manquants):
        os.mkdir(x)
        _journal(pl, fait, ["mkdir", x])


def deplace_le_code(pl, fait):
    """Étapes 2 à 6. Lève `Echec` après avoir tenté le retour arrière."""
    p, t = pl.projet, pl.temp
    avant = {c: inventaire(c) for c, _ in pl.copies if os.path.isdir(c)}
    branches = dict(pl.copies)
    fantomes = set()
    try:
        fantomes = {c for c, _ in copies(p) if not vivante(c)}
    except RuntimeError:
        pass
    os.rename(p, t)
    _journal(pl, fait, ["mv", p, t])
    os.rename(os.path.join(t, "brain"), p)
    _journal(pl, fait, ["mv", os.path.join(t, "brain"), p])
    nouveau = os.path.join(p, "agents", pl.premier, "code")
    _dossier(pl, fait, os.path.dirname(nouveau))
    os.rename(t, nouveau)
    _journal(pl, fait, ["mv", t, nouveau])
    autres = [pl.niche(c) or c for c, _ in pl.copies[1:]]
    autres = [c for c in autres if os.path.isdir(c) and c not in fantomes]
    if autres:
        _ok(nouveau, ["worktree", "repair"] + autres)
    _journal(pl, fait, ["repair"])
    for c, _ in pl.copies[1:]:
        cible = pl.cible(c)
        if cible is None or pl.niche(c) or not os.path.isdir(c):
            continue
        _dossier(pl, fait, os.path.dirname(cible))
        _ok(nouveau, ["worktree", "move", c, cible])
        _journal(pl, fait, ["move", c, cible])
    _ok(nouveau, ["worktree", "repair"])
    # LE TÉMOIN.
    mal = []
    apres = copies(nouveau)
    apres = [(c, b) for c, b in apres if c not in fantomes]
    if len(apres) != len(pl.copies):
        mal.append("%d copies avant, %d après" % (len(pl.copies), len(apres)))
    for c, b in apres:
        if not os.path.isdir(c):
            mal.append("copie absente : %s" % c)
            continue
        if _git(c, ["rev-parse", "--git-dir"])[0] != 0:
            mal.append("copie sans dépôt : %s" % c)
    for c, ib in avant.items():
        neuf = pl.niche(c) or (pl.cible(c) if c != p else nouveau) or c
        if branches.get(c) != dict(apres).get(os.path.realpath(neuf)):
            mal.append("branche changée : %s" % neuf)
        ia = inventaire(neuf)
        if c == p:
            # Le checkout principal a perdu `brain/` — c'est voulu.
            ib = ({k: v for k, v in ib[0].items() if not k.startswith("brain" + os.sep)}, ib[1])
        if ia[0] != ib[0]:
            diff = sorted(set(ia[0]) ^ set(ib[0]))[:3]
            mal.append("inventaire différent dans %s (%s)" % (neuf, ", ".join(diff) or "tailles"))
    if mal:
        raise Echec("; ".join(mal))
    return nouveau


def retour_arriere(pl, fait):
    """Les mêmes gestes, en sens inverse. Rend la liste de ce qui n'a pas pu être
    défait — vide si tout est revenu."""
    reste = []
    principal = None
    for g in fait:
        if g[0] == "mv" and g[2].endswith(os.path.join("agents", pl.premier or "", "code")):
            principal = g[2]
    for g in reversed(fait):
        try:
            if g[0] == "move" and principal:
                _ok(principal, ["worktree", "move", g[2], g[1]])
            elif g[0] == "mkdir":
                if os.path.isdir(g[1]):
                    os.rmdir(g[1])
            elif g[0] == "mv":
                os.rename(g[2], g[1])
                if principal == g[2]:
                    principal = g[1]
        except (OSError, RuntimeError) as e:
            reste.append("%s : %s" % (" ".join(g), e))
    if principal and os.path.isdir(principal):
        autres = [c for c, _ in pl.copies[1:] if os.path.isdir(c)]
        _git(principal, ["worktree", "repair"] + autres)
    return reste


def range_la_memoire(pl, ops):
    """Dans le dépôt de la mémoire seulement : `git mv`, badges, docs, livrables,
    consignes. Un seul enregistrement."""
    p = pl.projet
    code = os.path.join(p, "agents", pl.premier, "code")
    for n in pl.agents:
        src = os.path.join(p, "mind", n)
        for f in sorted(os.listdir(src)) if os.path.isdir(src) else []:
            _ok(p, ["mv", "-k", os.path.join("mind", n, f), os.path.join("agents", n, f)])
            if os.path.exists(os.path.join(src, f)):
                shutil.move(os.path.join(src, f), os.path.join(p, "agents", n, f))
        ops.append("état de %s : mind/%s -> agents/%s" % (n, n, n))
    if os.path.isdir(os.path.join(p, "mind")) and not os.listdir(os.path.join(p, "mind")):
        os.rmdir(os.path.join(p, "mind"))
    if os.path.isdir(os.path.join(p, "workspace")):
        _ok(p, ["mv", "workspace", "shared"])
        ops.append("carnet : workspace -> shared")
    else:
        os.makedirs(os.path.join(p, "shared"), exist_ok=True)
    gi = os.path.join(p, ".gitignore")
    t = _lis(gi) if os.path.isfile(gi) else ""
    ajouts = [x for x in ("agents/*/code*/", "**/.claude/settings.local.json",
                          "**/.claude/.briefing.json", "**/.claude/.briefing.lock", ".env", ".env.*",
                          "operations.md")
              if x not in t.split("\n")]
    if ajouts:
        with open(gi, "a", encoding="utf-8") as h:
            h.write(("" if not t or t.endswith("\n") else "\n")
                    + "# un dossier par agent (harnais demenage)\n" + "\n".join(ajouts) + "\n")
    # LES BADGES — un exemplaire, celui du dossier d'où l'agent se lançait.
    for n in pl.agents:
        de = os.path.join(pl.cible(pl.lance[n]) if pl.lance[n] != pl.projet else code, "agents", n)
        vers = os.path.join(p, "agents", n)
        if os.path.isfile(os.path.join(de, "CLAUDE.md")):
            shutil.copy2(os.path.join(de, "CLAUDE.md"), os.path.join(vers, "CLAUDE.md"))
        for f in ("settings.json", "settings.local.json", ".briefing.json"):
            s = os.path.join(de, ".claude", f)
            if not os.path.isfile(s):
                continue
            os.makedirs(os.path.join(vers, ".claude"), exist_ok=True)
            texte = _lis(s)
            if f != ".briefing.json":
                texte, k = reecrit_badge(texte, pl)
                ajout = 0
                if f == "settings.json":
                    v = json.loads(texte)
                    deny = v.setdefault("permissions", {}).setdefault("deny", [])
                    for r in perimetre(pl, n):
                        if r not in deny:
                            deny.append(r)
                            ajout += 1
                    texte = json.dumps(v, indent=2, ensure_ascii=False) + "\n"
                ops.append("badge de %s : %s, %d chemin(s) réécrit(s), %d règle(s) de périmètre posée(s)"
                           % (n, f, k, ajout))
            with open(os.path.join(vers, ".claude", f), "w", encoding="utf-8") as h:
                h.write(texte)
    # docs/ et les livrables : COPIÉS, vérifiés à l'octet. Le retrait du code est un
    # enregistrement du code, sur demande de l'humain.
    for de, vers in [("docs", "docs"), ("CLAUDE.md", "CLAUDE.md")] + \
            [("assets", "assets")] + [(x, os.path.join("assets", os.path.basename(x))) for x in pl.livrables]:
        s, d = os.path.join(code, de), os.path.join(p, vers)
        if not os.path.exists(s):
            continue
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
            if arbre_empreintes(s) != arbre_empreintes(d):
                raise Echec("copie de `%s` différente à l'arrivée" % de)
        else:
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            if empreinte(s) != empreinte(d):
                raise Echec("copie de `%s` différente à l'arrivée" % de)
        ops.append("copié et vérifié : %s -> %s" % (de, vers))
    _ok(p, ["add", "-A"])
    c, _, _ = _git(p, ["diff", "--cached", "--quiet"])
    if c != 0:
        _ok(p, ["-c", "user.name=harnais", "-c", "user.email=harnais@atelier", "commit", "-q",
                "-m", "Un dossier par agent : la mémoire devient le dossier du projet (harnais demenage)"])
        ops.append("mémoire enregistrée")


def conversations(pl, appliquer, ops):
    """Les fils de chaque agent, rangés par Claude Code selon le dossier de
    lancement : renommés vers le nouveau. Jamais écrasés."""
    from equipe import slug
    base = os.path.join(socle.maison(), ".claude", "projects")
    for n in pl.agents:
        ancien = os.path.join(pl.lance[n], "agents", n)
        neuf = os.path.join(pl.projet, "agents", n)
        a, b = os.path.join(base, slug(ancien)), os.path.join(base, slug(neuf))
        if a == b:
            ops.append("conversations de %s : même adresse, rien à faire" % n)
            continue
        if not os.path.isdir(a):
            ops.append("conversations de %s : aucune (%s absent)" % (n, os.path.basename(a)))
            continue
        if os.path.exists(b):
            ops.append("⚠ conversations de %s : %s existe déjà — NON déplacées, à fusionner" % (n, os.path.basename(b)))
            continue
        ops.append("conversations de %s : %s -> %s" % (n, os.path.basename(a), os.path.basename(b)))
        if appliquer:
            os.rename(a, b)


def inscriptions(pl, appliquer, ops):
    f = os.environ.get("HARNAIS_INSCRIPTIONS") or os.path.join(
        socle.maison(), ".claude", "plugins", "installed_plugins.json")
    try:
        with open(f, encoding="utf-8") as h:
            v = json.load(h)
    except (OSError, ValueError):
        ops.append("inscriptions : registre illisible — à poser à la main")
        return
    liste = v.get("plugins", {}).get("harnais@atelier", [])
    vers = {os.path.join(pl.lance[n], "agents", n): os.path.join(pl.projet, "agents", n) for n in pl.agents}
    k = 0
    for e in liste:
        pp = e.get("projectPath") if isinstance(e, dict) else None
        if isinstance(pp, str) and os.path.realpath(pp) in vers and pp != vers[os.path.realpath(pp)]:
            e["projectPath"] = vers[os.path.realpath(pp)]
            k += 1
    ops.append("inscriptions au paquet : %d chemin(s) de lancement réécrit(s)" % k)
    if appliquer and k:
        jour = datetime.date.today().strftime("%Y%m%d")
        sauve = f + ".avant-demenage-" + jour
        if not os.path.exists(sauve):
            shutil.copy2(f, sauve)
        with open(f, "w", encoding="utf-8") as h:
            json.dump(v, h, ensure_ascii=False, indent=2)
            h.write("\n")


def applique(pl):
    fait, ops = [], []
    try:
        deplace_le_code(pl, fait)
    except (Echec, OSError, RuntimeError) as e:
        reste = retour_arriere(pl, fait)
        return ["ÉCHEC du déplacement du code : %s" % e] + (
            ["RETOUR ARRIÈRE INCOMPLET : %s" % r for r in reste] if reste else ["retour arrière fait : tout est revenu"])
    ops.append("code déplacé : %d copie(s), témoin vert" % len(pl.copies))
    try:
        range_la_memoire(pl, ops)
    except (Echec, OSError, RuntimeError) as e:
        return ops + ["ÉCHEC du rangement de la mémoire : %s — le code est en place ; la mémoire "
                      "est à reprendre (git status dans %s)" % (e, pl.projet)]
    conversations(pl, True, ops)
    inscriptions(pl, True, ops)
    try:
        os.remove(pl.projet.rstrip("/") + ".demenage.json")
    except OSError:
        pass
    return ops


def _affiche(pl):
    _p("\n  %sDÉMÉNAGEMENT — un dossier par agent%s   %s%s%s" % (B, X, D, pl.projet, X))
    if pl.premier:
        _p("  %-22s %s" % ("checkout principal", "-> agents/%s/code (un seul mv)" % pl.premier))
    for n in pl.agents:
        c = pl.lance.get(n)
        if c is None:
            continue
        _p("  %-22s %s" % (n, "%s -> %s" % (c, pl.cible(c)) if c != pl.projet else "(checkout principal)"))
    for n, s, c in pl.en_plus:
        _p("  %-22s %s -> %s" % ("%s, en plus" % n, c, pl.cible(c)))
    for c in pl.restent:
        if pl.premier and pl.niche(c):
            _p("  %-22s %s — part avec le checkout principal" % ("copie imbriquée", c))
        else:
            _p("  %s%-22s %s — reste en place, signalée par la page d'équipe%s" % (J, "copie sans agent", c, X))
    for x in pl.livrables:
        _p("  %-22s %s -> assets/%s" % ("livrable", x, os.path.basename(x)))
    for n in pl.notes:
        _p("  %s· %s%s" % (D, n, X))
    ops = []
    conversations(pl, False, ops)
    inscriptions(pl, False, ops)
    for o in ops:
        _p("  · %s" % o)
    _p("\n  %sÀ ENREGISTRER DANS LE CODE, sur demande de l'humain%s : retirer %s ; ajouter au "
       "`.gitignore` : %s" % (B, X, ", ".join("`%s`" % x for x in QUITTENT_LE_CODE + tuple(pl.livrables)),
                              " ".join("/%s/" % x for x in ("agents", "brain", "docs", "assets"))))
    if pl.bloquants:
        _p("\n  %sBLOQUÉ%s" % (R, X))
        for b in pl.bloquants:
            _p("    %s✗%s %s" % (R, X, b))


def valeurs(args, cle):
    v, i = [], 0
    while i < len(args):
        if args[i] == cle and i + 1 < len(args):
            v.append(args[i + 1])
            i += 2
        else:
            i += 1
    return v


def main(args):
    if not args or args[0].startswith("-"):
        _p("usage : harnais demenage <projet> [--copie NOM=CHEMIN]… [--en-plus NOM:SUJET=CHEMIN]… "
           "[--livrable CHEMIN]… [--apply --agents-arretes]")
        return 2
    choix = {}
    for s in valeurs(args, "--copie"):
        if "=" in s:
            k, c = s.split("=", 1)
            choix[k] = c
    pl = planifie(args[0], choix, valeurs(args, "--en-plus"), valeurs(args, "--livrable"))
    _affiche(pl)
    if "--apply" not in args:
        _p("\n  %sÀ blanc%s : rien n'est écrit. `--apply --agents-arretes` pour déménager." % (D, X))
        return 1 if pl.bloquants else 0
    if pl.bloquants:
        _p("\n  Rien n'est écrit tant qu'un point bloque.")
        return 1
    if "--agents-arretes" not in args:
        _p("\n  %s--agents-arretes%s manque : un agent ouvert écrirait l'ancien chemin pendant "
           "le déplacement. Les arrêter, couper la synchronisation, puis relancer." % (B, X))
        return 1
    ops = applique(pl)
    for o in ops:
        _p("  %s %s" % ("✗" if o.startswith(("ÉCHEC", "RETOUR")) else "✓", o))
    return 1 if any(o.startswith(("ÉCHEC", "RETOUR")) for o in ops) else 0
