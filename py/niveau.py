# -*- coding: utf-8 -*-
"""`harnais mise-a-niveau` — AMENER UN PROJET À LA FORME ACTUELLE, MONO OU ÉQUIPE.

POURQUOI (décision du 14/10/2026 : il faut un outil qui mette à jour le harnais
des projets mono et multi-agents, car ce cas peut ne pas être le seul).
Mesuré le même jour sur un projet réel : monté avant `brain/`, jamais migré,
et RIEN ne le disait — le harnais sert l'ancienne forme à l'identique.
`brain-migre` le refusait pour trois raisons, dont une à lui (`workflow.md`).
Et même accepté, il aurait laissé derrière lui la moitié du travail :

- les DROITS : les `deny` de l'agent QA visent `memoire/agents/OPS/**`.
  Après un déplacement nu, ils pointent un dossier qui n'existe plus — un
  périmètre qui ne mord plus, et qui ne le dit pas ;
- le `.gitignore` du dépôt de code ignore `memoire/` : le dossier de mémoire
  (un dépôt à part) y apparaîtrait d'un coup comme du code non suivi ;
- les faits manquants, l'esprit d'un agent sans le sien, le carnet absent.

UN SEUL GESTE, QUELLE QUE SOIT LA FORME DE DÉPART :

    en place     .fact/  .mind/  agents/<nom>/.mind/   -> brain/   (git mv)
    déportée     memoire/  (dépôt à part ou non)        -> brain/   (le dossier
                 entier, son dépôt avec lui), puis DEDANS :
                 .fact -> fact · agents/<nom>/.mind -> mind/<nom> · equipe -> workspace
    brain        rien ne bouge ; on complète seulement

puis, dans toutes les formes : les chemins des réglages réécrits (une copie
`.avant-mise-a-niveau-<date>` de chaque fichier touché), les faits manquants
posés « À REMPLIR », l'état de chaque agent lancé, le carnet d'une équipe,
le paquet déclaré dans chaque dossier de lancement.

**CE QU'IL NE FAIT PAS, ET LE DIT** : trier. Un fichier de trop dans les faits,
un dossier que la méthode ne prévoit pas, une phrase d'un CLAUDE.md qui cite
l'ancien chemin — ce sont des jugements de contenu, ils appartiennent au
projet. Le premier BLOQUE (il serait déplacé parmi les faits sans que personne
l'ait vérifié) ; les autres sont NOMMÉS, fichier et ligne.

**À BLANC PAR DÉFAUT.** `--apply` écrit, et seulement si rien ne bloque. Quand
la mémoire bouge, il exige aussi `--agents-arretes` : un agent resté ouvert
réécrirait l'ancien chemin, recréant l'ancienne forme à côté de la neuve — et
un projet à cheval ne reçoit AUCUNE mémoire.

**UN PROJET À LA FOIS.** `--atelier <dossier>` fait le diagnostic de tous et
n'écrit jamais : arrêter les agents, et dire oui, se fait projet par projet.
"""
import datetime
import json
import os
import re
import sys

import adopte
import memoire
import migration
import socle
from memoire import Forme

V = "\x1b[32m"
R = "\x1b[31m"
J = "\x1b[33m"
B = "\x1b[1m"
D = "\x1b[2m"
X = "\x1b[0m"

# Ce que `brain/` a le droit de porter à sa racine. Le reste est NOMMÉ, pas
# déplacé : la méthode ne lui donne pas de place, mais seul le projet sait où
# il va (docs/ s'il est daté, assets/ s'il est livré, ailleurs sinon).
# `.logs/` y est légitime quand `brain/` est un dépôt à part : le journal s'écrit à
# la racine du dépôt où l'on commite, et la mémoire se commite chez elle.
DANS_BRAIN = {"fact", "mind", "workspace", "local", ".git", ".gitignore", ".gitattributes",
              ".logs", ".DS_Store"}


def _p(s=""):
    sys.stdout.write(s + "\n")


def _lis(f):
    try:
        with open(f, encoding="utf-8", newline="") as h:
            return h.read()
    except (OSError, UnicodeDecodeError):
        return None


def _ecris(f, t):
    d = os.path.dirname(f)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(f, "w", encoding="utf-8", newline="") as h:
        h.write(t)


def _dirs(d):
    try:
        return sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)))
    except OSError:
        return []


def _court(p, racine):
    return migration.sans_prefixe(p, racine)


class Plan(object):
    def __init__(self, racine):
        self.racine = racine
        self.forme = None
        self.equipe = False
        self.agents = []          # les dossiers de lancement agents/<nom>
        self.deplacements = []    # [(de, vers, comment, mode)] — mode : "dossier" | "geste"
        self.correspondances = [] # [(ancien, nouveau)] chemins absolus, du plus précis au plus large
        # Un ancien dossier qui se SÉPARE en deux : `memoire/agents/<nom>/` donne
        # son état à `brain/mind/<nom>/` et garde le reste (preuves, notes) sous
        # `brain/agents/<nom>/`. Un droit qui le visait doit viser LES DEUX.
        self.multiples = {}       # {ancien: [nouveau, nouveau…]}
        self.reglages = []        # [(fichier, ancien, nouveau, n)]
        self.ignore = None        # (fichier, ancien, nouveau)
        self.poses = []           # [(chemin, quoi, contenu)]
        self.dossiers = []        # [(chemin, quoi)]
        self.bloquants = []
        self.a_relire = []
        self.v3 = False           # forme « un dossier par agent » : on complète, rien ne bouge

    @property
    def bouge(self):
        return bool(self.deplacements)


# ── ce qui bouge ────────────────────────────────────────────────────────────

def _agents_lances(racine):
    a = os.path.join(racine, "agents")
    return [n for n in _dirs(a)
            if os.path.isfile(os.path.join(a, n, "CLAUDE.md"))
            or os.path.isdir(os.path.join(a, n, ".claude"))]


def _plan_deplacements(pl, r):
    j = os.path.join
    racine = pl.racine
    brain = j(racine, "brain")
    if r.forme == Forme.EnPlace:
        v, m = migration.gestes(r, racine)
        if v is None:
            pl.bloquants.append(m)
            return
        for g in v:
            pl.deplacements.append((g.de, g.vers, "", "geste"))
            pl.correspondances.append((g.de, g.vers))
        # Le plus précis d'abord : `agents/X/.mind` avant `.mind`.
        pl.correspondances.sort(key=lambda c: -len(c[0]))
        return
    if r.forme != Forme.Deportee:
        return
    b = memoire.base(racine)
    if b is None:
        pl.bloquants.append("mémoire déportée introuvable")
        return
    # LE DOSSIER ENTIER D'ABORD. Ne déplacer que `.fact/` et les `.mind/`
    # laisserait `memoire/` debout avec le reste : le résolveur verrait
    # l'ancien ET le neuf, et le projet ne recevrait plus aucune mémoire.
    pl.deplacements.append((b, brain, "", "dossier"))
    dedans = []
    if os.path.isdir(j(b, ".fact")):
        dedans.append((".fact", "fact"))
    ag = j(b, "agents")
    for n in _dirs(ag):
        if os.path.isdir(j(ag, n, ".mind")):
            dedans.append((j("agents", n, ".mind"), j("mind", n)))
    if not any(d.startswith("agents") for d, _ in dedans) and os.path.isdir(j(b, ".mind")):
        dedans.append((".mind", "mind"))
    if os.path.isdir(j(b, "equipe")):
        dedans.append(("equipe", "workspace"))
    for de, vers in dedans:
        pl.deplacements.append((j(brain, de), j(brain, vers), "", "geste"))
        pl.correspondances.append((j(b, de), j(brain, vers)))
    for n in _dirs(ag):
        if not os.path.isdir(j(ag, n, ".mind")):
            continue
        reste = [x for x in os.listdir(j(ag, n)) if x not in (".mind", ".DS_Store")]
        pl.multiples[j(ag, n)] = [j(brain, "mind", n)] + ([j(brain, "agents", n)] if reste else [])
    pl.correspondances.sort(key=lambda c: -len(c[0]))
    pl.correspondances.append((b, brain))     # le reste du dossier, tel quel


def _verifie_avant(pl, r):
    j = os.path.join
    racine = pl.racine
    brain = j(racine, "brain")
    if not pl.bouge:
        return
    if os.path.exists(brain):
        pl.bloquants.append("`brain/` existe déjà à côté de l'ancienne mémoire : une migration "
                            "interrompue. Trancher à la main avant de rejouer.")
    # Rien d'enregistré en attente SUR CE QUI BOUGE — sans ça, revenir en arrière
    # ne rend pas l'état de départ.
    vus = set()
    for (src, _v, _c, _m) in pl.deplacements:
        if not os.path.exists(src):
            continue      # un geste INTÉRIEUR : sa source n'existe qu'après le premier
        porteur = migration.depot_porteur(src, racine)
        rel = migration.sans_prefixe(src, porteur)
        rel = "." if (rel == src or rel == "") else rel
        rc, out = migration.git(porteur, ["status", "--porcelain", "--", rel])
        # `.DS_Store` : le Finder en sème partout, il voyage avec le dossier.
        sales = [l for l in migration.lignes(out) if not l.rstrip('"').endswith(".DS_Store")]
        if rc == 0 and sales:
            pl.bloquants.append("%d modification(s) non enregistrée(s) dans `%s`. Les enregistrer "
                                "d'abord : sans ça, revenir en arrière ne rend pas l'état de "
                                "départ." % (len(sales), _court(src, racine)))
        # UN DÉPÔT DE MÉMOIRE À PART DOIT AVOIR UNE COPIE AILLEURS.
        if not migration.egaux(porteur, racine) and porteur not in vus:
            vus.add(porteur)
            _, o = migration.git(porteur, ["remote"])
            if not o:
                pl.bloquants.append("le dépôt de la mémoire (`%s`) n'a AUCUN dépôt distant : pas de "
                                    "retour arrière possible hors de cette machine. Lui en donner "
                                    "un et y pousser d'abord." % (_court(porteur, racine) or porteur))


def _expert(pl):
    for f in _fichiers_reglages(pl):
        t = _lis(f) or ""
        if re.search(r'"HARNAIS_PROFIL"\s*:\s*"expert"', t):
            return True
    return False


def _verifie_faits(pl, fact_actuel):
    """UN FICHIER DE TROP DANS LES FAITS BLOQUE. Il serait déplacé parmi les faits
    sans que personne l'ait vérifié — et les faits ne s'écrivent qu'à la demande."""
    if fact_actuel is None or not os.path.isdir(fact_actuel) or _expert(pl):
        return
    autorises = socle.faits_tous()
    try:
        vus = sorted(n for n in os.listdir(fact_actuel) if n.endswith(".md"))
    except OSError:
        vus = []
    for n in vus:
        if n not in autorises:
            pl.bloquants.append("`%s` n'est pas un fait de la méthode (%s). Le ranger d'abord : "
                                "dans `docs/` s'il est daté, sinon dans le fait qui lui répond."
                                % (_court(os.path.join(fact_actuel, n), pl.racine), ", ".join(autorises)))


# ── ce qui se réécrit ───────────────────────────────────────────────────────

def _fichiers_reglages(pl):
    j = os.path.join
    ou = [pl.racine] + [j(pl.racine, "agents", a) for a in pl.agents]
    out = []
    for d in ou:
        for n in ("settings.json", "settings.local.json"):
            f = j(d, ".claude", n)
            if os.path.isfile(f):
                out.append(f)
    return out


def _orthographes(p):
    """Les façons dont un chemin s'écrit dans des réglages : absolu, et ancré sur
    le home (`~/…`), la seule forme d'ancrage qui mord dans un `deny`."""
    v = [p]
    if os.name == "nt":
        # Un réglage écrit `C:\\…\\Proj/memoire/…` aussi bien que `C:/…` : les deux
        # séparateurs se lisent, et chacun garde le sien en sortie.
        v.append(p.replace("\\", "/"))
    h = socle.maison()
    r = None
    # Le home tel qu'écrit ET tel qu'il est vraiment : sous Windows `RUNNER~1` et
    # `runneradmin` sont le même dossier (nom court 8.3), comparés tels quels non.
    for hh in ([h, os.path.realpath(h)] if h else []):
        r = r or migration.strip_prefix(p, hh) or migration.strip_prefix(os.path.realpath(p), hh)
    if r:
        v.append("~/" + r)
    return v


def reecrit(texte, correspondances):
    """Rend `(texte, n)`. Un chemin n'est remplacé que s'il s'arrête à une borne :
    `memoire` ne doit pas mordre `memoire-old`."""
    n_tot = 0
    for ancien, nouveau in correspondances:
        for a, b in zip(_orthographes(ancien), _orthographes(nouveau)):
            motif = re.compile(re.escape(a) + r'(?=[/"\s):*,\]]|$)')
            texte, n = motif.subn(lambda _m, b=b: b, texte)
            n_tot += n
    return texte, n_tot


def _borne(a):
    return re.compile(re.escape(a) + r'(?=[/"\s):*,\]]|$)')


def reecrit_reglages(texte, correspondances, multiples):
    """Les réglages, champ par champ. Une chaîne quelconque prend la première
    adresse ; un DROIT (allow / deny / ask) qui visait un dossier qui se sépare
    est dédoublé, une règle par nouvelle adresse — sinon un `deny` ne protège
    plus que la moitié de ce qu'il protégeait, sans un mot."""
    v = json.loads(texte) if texte.strip() else {}
    tout = sorted(list(correspondances) + [(a, c[0]) for a, c in multiples.items()],
                  key=lambda c: -len(c[0]))
    compte = [0]

    def chaine(x):
        y, k = reecrit(x, tout)
        compte[0] += k
        return y

    def droits(l):
        out = []
        for x in l:
            if not isinstance(x, str):
                out.append(x)
                continue
            for y in [chaine(x)] + [
                    reecrit(reecrit(x, [(a, c)])[0], tout)[0]
                    for a, cibles in sorted(multiples.items())
                    if any(_borne(o).search(x) for o in _orthographes(a))
                    for c in cibles[1:]]:
                if y not in out:
                    out.append(y)
        return out

    def marche(o, cle=None):
        if isinstance(o, dict):
            return {k: (droits(x) if cle == "permissions" and k in ("allow", "deny", "ask")
                        and isinstance(x, list) else marche(x, k)) for k, x in o.items()}
        if isinstance(o, list):
            return [marche(x, cle) for x in o]
        if isinstance(o, str):
            return chaine(o)
        return o
    neuf = marche(v)
    if not compte[0]:
        return texte, 0
    return json.dumps(neuf, indent=2, ensure_ascii=False) + "\n", compte[0]


def _plan_reglages(pl):
    if not pl.correspondances:
        return
    for f in _fichiers_reglages(pl):
        t = _lis(f)
        if t is None:
            continue
        try:
            neuf, n = reecrit_reglages(t, pl.correspondances, pl.multiples)
        except ValueError:
            pl.bloquants.append("`%s` n'est pas du JSON valide : le réparer d'abord" % _court(f, pl.racine))
            continue
        if n:
            try:
                json.loads(neuf)
            except ValueError:
                pl.bloquants.append("`%s` ne serait plus du JSON valide après réécriture"
                                    % _court(f, pl.racine))
                continue
            pl.reglages.append((f, t, neuf, n))


def _plan_ignore(pl):
    """Le dossier de mémoire déporté, dépôt à part, était ignoré par le dépôt du
    code. `brain/` doit l'être de la même façon, sinon il y apparaît en entier."""
    if not pl.deplacements or pl.deplacements[0][3] != "dossier":
        return
    if not os.path.isdir(os.path.join(pl.deplacements[0][0], ".git")):
        return
    f = os.path.join(pl.racine, ".gitignore")
    t = _lis(f) or ""
    neuf, n = re.subn(r"(?m)^(/?)memoire(/?)[ \t]*$", r"\1brain\2", t)
    if not n:
        neuf = t + ("" if t.endswith("\n") or not t else "\n") + "# la mémoire, dépôt à part\nbrain/\n"
    pl.ignore = (f, t, neuf)


# ── ce qui se pose ──────────────────────────────────────────────────────────

def _plan_poses(pl):
    j = os.path.join
    brain = j(pl.racine, "brain")
    fact, mind = j(brain, "fact"), j(brain, "mind")
    if pl.v3:
        # UN DOSSIER PAR AGENT : la mémoire est le projet, l'état est dans le
        # dossier de l'agent. Poser ici un `brain/` recréerait la dispersion.
        brain, fact, mind = pl.racine, j(pl.racine, "fact"), j(pl.racine, "agents")
    nom = os.path.basename(pl.racine.rstrip("/")) or "ce projet"
    jour = datetime.date.today().strftime("%Y-%m-%d")

    def pose(p, quoi, c):
        if not os.path.exists(p) and not _arrive(pl, p):
            pl.poses.append((p, quoi, c))

    if not _expert(pl):
        pose(j(fact, "stack.md"), "avec quoi c'est fait, à remplir", adopte.stack_md(nom))
        pose(j(fact, "architecture.md"), "comment c'est agencé, à remplir", adopte.architecture_md(nom))
        pose(j(fact, "rules.md"), "ce qu'on ne franchit pas, à remplir", adopte.rules_md(nom))
    pose(j(fact, "base.md"), "le cap, à remplir", adopte.base_md(nom))
    pose(j(fact, "workflow.md"), "comment procéder, à remplir", adopte.workflow_md(nom))
    if pl.equipe:
        pose(j(fact, "roles.md"), "qui tient quoi, et les zones partagées", adopte.roles_md(pl.agents))
        for a in pl.agents:
            pose(j(mind, a, "state.md"), "l'état de %s" % a, adopte.state_md(jour))
            pose(j(mind, a, "todo.md"), "ce qui attend %s" % a, adopte.TODO_MD)
        ws = j(brain, "shared" if pl.v3 else "workspace")
        if not os.path.isdir(ws) and not _arrive(pl, ws):
            pl.dossiers.append((j(ws, ".etat"), "le carnet d'équipe"))
    else:
        pose(j(mind, "state.md"), "où on en est aujourd'hui", adopte.state_md(jour))
        pose(j(mind, "todo.md"), "ce qui attend une décision", adopte.TODO_MD)

    # LE PAQUET DÉCLARÉ DANS CHAQUE DOSSIER DE LANCEMENT — et seulement là.
    lancements = [j(pl.racine, "agents", a) for a in pl.agents] if pl.equipe else [pl.racine]
    for d in lancements:
        f = j(d, ".claude", "settings.json")
        base = None
        for (ff, _a, neuf, _n) in pl.reglages:
            if ff == f:
                base = neuf
        if base is None:
            texte, manque = adopte.reglages(f)
        else:
            texte, manque = _reglages_depuis(base)
        if manque:
            pl.reglages = [x for x in pl.reglages if x[0] != f]
            pl.reglages.append((f, _lis(f) or "", texte, len(manque)))


def _reglages_depuis(texte):
    """`adopte.reglages` sur un texte déjà réécrit, sans le poser sur le disque."""
    v = json.loads(texte) if texte.strip() else {}
    manque = []
    m = v.setdefault("extraKnownMarketplaces", {})
    if adopte.MARCHE not in m:
        manque.append("le marché")
        m[adopte.MARCHE] = {"source": {"source": "github", "repo": adopte.DEPOT}}
    pl_ = v.setdefault("enabledPlugins", {})
    if pl_.get(adopte.PAQUET) is not True:
        manque.append("le paquet")
        pl_[adopte.PAQUET] = True
    if not manque:
        return texte, []
    return json.dumps(v, indent=2, ensure_ascii=False) + "\n", manque


def _arrive(pl, p):
    """Ce chemin existera-t-il APRÈS les déplacements ? (une pose qui l'ignorerait
    poserait un gabarit à l'endroit où arrive le vrai fichier)."""
    for ancien, nouveau in pl.correspondances:
        r = migration.strip_prefix(p, nouveau)
        if r is not None:
            src = os.path.join(ancien, r) if r else ancien
            if os.path.exists(src):
                return True
    return False


# ── ce qui se nomme ─────────────────────────────────────────────────────────

_ANCIENS = re.compile(r"memoire/|\.fact/|\.mind/|memoire/equipe")


def _plan_relire(pl, r):
    j = os.path.join
    racine = pl.racine
    cl = [j(racine, "CLAUDE.md")] + [j(racine, "agents", a, "CLAUDE.md") for a in pl.agents]
    if pl.bouge:
        for f in cl:
            t = _lis(f)
            if not t:
                continue
            for i, l in enumerate(t.split("\n"), 1):
                if _ANCIENS.search(l):
                    pl.a_relire.append("%s:%d cite l'ancien chemin — %s"
                                       % (_court(f, racine), i, l.strip()[:90]))
        # Ce qui reste écrit à l'ancienne dans les réglages sans être ancré : on
        # ne le devine pas (« memoire/** » relatif peut viser autre chose).
        for f in _fichiers_reglages(pl):
            t = _lis(f) or ""
            for (ff, _a, neuf, _n) in pl.reglages:
                if ff == f:
                    t = neuf
            for i, l in enumerate(t.split("\n"), 1):
                if re.search(r"(?<![\w/])memoire/|(?<![\w])\.fact/|(?<![\w])\.mind/", l):
                    pl.a_relire.append("%s:%d mention à l'ancienne, non réécrite (note, ou chemin relatif) — %s"
                                       % (_court(f, racine), i, l.strip()[:90]))
    # LES CROCHETS GIT DU DÉPÔT DE MÉMOIRE voyagent avec lui, et peuvent viser
    # l'ancien chemin (un projet réel : la trace « Corrige-par » ne regarde que `.fact/`).
    # Ils ne cassent rien — ils cessent de servir, sans un mot.
    if pl.bouge and pl.deplacements[0][3] == "dossier":
        crochets = j(pl.deplacements[0][0], ".git", "hooks")
        for n in sorted(os.listdir(crochets)) if os.path.isdir(crochets) else []:
            if n.endswith(".sample"):
                continue
            t = _lis(j(crochets, n)) or ""
            if _ANCIENS.search(t):
                pl.a_relire.append("crochet git `%s` du dépôt de mémoire vise l'ancien chemin : "
                                   "il cessera de servir" % n)
    # LE CONTENU QUE LA MÉTHODE NE PRÉVOIT PAS DANS `brain/`.
    src = None
    if pl.bouge and pl.deplacements[0][3] == "dossier":
        src = pl.deplacements[0][0]
    elif r.forme == Forme.Brain:
        src = j(racine, "brain")
    if src:
        try:
            noms = sorted(os.listdir(src))
        except OSError:
            noms = []
        avant = {".fact": "fact", ".mind": "mind", "equipe": "workspace"} if src != j(racine, "brain") else {}
        for n in noms:
            if avant.get(n, n) in DANS_BRAIN:
                continue
            if n == "agents" and avant:
                for a in _dirs(j(src, "agents")):
                    reste = [x for x in os.listdir(j(src, "agents", a)) if x not in (".mind", ".DS_Store")]
                    if reste:
                        pl.a_relire.append("brain/agents/%s/ garde %s : hors méthode, à ranger"
                                           % (a, ", ".join(sorted(reste))))
                continue
            pl.a_relire.append("brain/%s : hors méthode, à ranger (docs/ si c'est daté, assets/ "
                               "si c'est livré)" % n)
    # UN ESPRIT SANS DOSSIER DE LANCEMENT — un agent retiré, ou lancé d'ailleurs.
    if pl.equipe:
        esprits = set()
        if r.forme == Forme.Brain:
            esprits = set(_dirs(j(racine, "brain", "mind")))
        else:
            for (de, vers, _c, _m) in pl.deplacements:
                rr = migration.strip_prefix(vers, j(racine, "brain", "mind"))
                if rr:
                    esprits.add(rr)
        for n in sorted(esprits - set(pl.agents)):
            pl.a_relire.append("brain/mind/%s/ n'a pas de dossier de lancement dans agents/ : "
                               "agent retiré, ou lancé d'ailleurs ? À décider." % n)
        if os.path.isfile(j(racine, ".claude", "settings.json")):
            pl.a_relire.append(".claude/settings.json à la racine : inerte en équipe (seul le "
                               "dossier de lancement est lu). Le vider ou le retirer, à la main.")


# ── le plan, puis l'exécution ───────────────────────────────────────────────

def planifie(depart):
    r = memoire.resous(depart)
    if r.racine is None:
        return None, "aucun dépôt git au-dessus de %s" % depart
    racine = r.racine
    pl = Plan(racine)
    pl.forme = r.forme
    pl.agents = _agents_lances(racine)
    pl.equipe = bool(pl.agents)
    if r.forme in (Forme.SansMemoire, Forme.HorsDepot):
        return pl, "aucune mémoire : c'est `harnais adopte` qui pose le harnais"
    if r.forme == Forme.Equipe:
        # Déjà dans la forme la plus récente : on COMPLÈTE, rien ne bouge, aucun
        # chemin n'est réécrit (14/10/2026 : sans cette branche, l'outil y
        # recréait `brain/` à côté de la mémoire — la dispersion qu'il combat).
        pl = Plan(r.projet)
        pl.forme, pl.v3 = r.forme, True
        pl.agents = _agents_lances(r.projet)
        pl.equipe = True
        _verifie_faits(pl, r.fact)
        _plan_poses(pl)
        return pl, None
    if r.forme == Forme.Ambigue:
        pl.bloquants.append("ce projet porte l'ANCIENNE mémoire et `brain/` à la fois : une "
                            "migration interrompue, ou un agent resté ouvert pendant la "
                            "migration. Trancher à la main.")
        return pl, None
    _plan_deplacements(pl, r)
    if r.forme == Forme.Deportee:
        b = memoire.base(racine)
        _verifie_faits(pl, os.path.join(b, ".fact") if b else None)
    else:
        _verifie_faits(pl, r.fact)
    _verifie_avant(pl, r)
    _plan_reglages(pl)
    _plan_ignore(pl)
    _plan_poses(pl)
    _plan_relire(pl, r)
    return pl, None


def _sauve(f, jour):
    s = "%s.avant-mise-a-niveau-%s" % (f, jour)
    if os.path.exists(f) and not os.path.exists(s):
        with open(f, "rb") as a, open(s, "wb") as b:
            b.write(a.read())


def applique(pl):
    """Rend la liste des écarts d'après (vide = tenu)."""
    jour = datetime.date.today().strftime("%Y%m%d")
    for i, (de, vers, _c, mode) in enumerate(pl.deplacements):
        if mode == "dossier" and os.path.isdir(os.path.join(de, ".git")):
            os.rename(de, vers)
            pl.deplacements[i] = (de, vers, "dossier déplacé avec son dépôt", mode)
            continue
        g = migration.Geste(de, vers)
        m = migration.deplace(g, pl.racine)
        if m is not None:
            return ["ÉCHEC du déplacement %s : %s" % (_court(de, pl.racine), m)]
        pl.deplacements[i] = (de, vers, g.comment, mode)
        # Un `agents/<nom>/` vidé de son `.mind/` ne doit pas rester comme coquille.
        par = os.path.dirname(de)
        if os.path.basename(par) and os.path.isdir(par):
            try:
                restes = [x for x in os.listdir(par) if x != ".DS_Store"]
                if not restes:
                    for x in os.listdir(par):
                        os.remove(os.path.join(par, x))
                    os.rmdir(par)
                    gp = os.path.dirname(par)
                    if os.path.basename(gp) == "agents" and not os.listdir(gp):
                        os.rmdir(gp)
            except OSError:
                pass
    # LE DÉPLACEMENT S'ENREGISTRE, DÉPÔT PAR DÉPÔT, ET RIEN D'AUTRE AVEC LUI. Laissé
    # en attente, il partirait dans le prochain commit de code de quelqu'un — ou
    # ferait refuser le suivant. Seuls les chemins déplacés sont nommés.
    par_depot = {}
    for (de, vers, c, mode) in pl.deplacements:
        if not c.startswith("git mv"):
            continue
        d = migration.depot_porteur(vers, pl.racine)
        par_depot.setdefault(d, []).extend([migration.sans_prefixe(de, d), migration.sans_prefixe(vers, d)])
    for d, chemins in par_depot.items():
        rc, out = migration.git(d, ["commit", "-q", "-m",
                                    "Mise à niveau : la mémoire passe dans la forme brain/ "
                                    "(harnais mise-a-niveau) # fact-ok # mind-ok", "--"] + chemins)
        if rc != 0:
            return ["le déplacement est fait mais PAS enregistré dans `%s` : %s"
                    % (_court(d, pl.racine) or d, out[:200])]
    for (f, _a, neuf, _n) in pl.reglages:
        _sauve(f, jour)
        _ecris(f, neuf)
    if pl.ignore:
        _ecris(pl.ignore[0], pl.ignore[2])
    for (p, _q, c) in pl.poses:
        if not os.path.exists(p):
            _ecris(p, c)
    for (d, _q) in pl.dossiers:
        os.makedirs(d, exist_ok=True)

    # ── LES ASSERTIONS D'APRÈS, dans la même exécution ──
    mal = []
    apres = memoire.resous(pl.racine)
    attendue = Forme.Equipe if pl.v3 else Forme.Brain
    if apres.forme != attendue:
        mal.append("le résolveur, relancé à froid, dit `%s` et non `%s`"
                   % (memoire.forme_mot(apres.forme), memoire.forme_mot(attendue)))
    if pl.v3 and os.path.exists(os.path.join(pl.racine, "brain")):
        mal.append("un `brain/` est apparu dans une équipe « un dossier par agent »")
    for (de, vers, _c, _m) in pl.deplacements:
        if os.path.exists(de):
            mal.append("l'ancien dossier existe encore : %s" % _court(de, pl.racine))
        if not os.path.exists(vers):
            mal.append("le nouveau dossier manque : %s" % _court(vers, pl.racine))
    for (f, _a, _n2, _n) in pl.reglages:
        t = _lis(f) or ""
        try:
            json.loads(t)
        except ValueError:
            mal.append("%s n'est plus du JSON valide" % _court(f, pl.racine))
        for ancien, _nv in pl.correspondances:
            for o in _orthographes(ancien):
                if re.search(re.escape(o) + r'(?=[/"\s):*,\]]|$)', t):
                    mal.append("%s cite encore %s" % (_court(f, pl.racine), o))
    if apres.fact is not None and not os.path.isfile(os.path.join(apres.fact, "base.md")):
        mal.append("brain/fact/base.md introuvable après coup")
    return mal


def _affiche(pl):
    rc = lambda p: _court(p, pl.racine)
    _p("  %-16s %s%s" % ("forme", memoire.forme_mot(pl.forme),
                         "  ·  équipe : " + ", ".join(pl.agents) if pl.equipe else "  ·  un agent"))
    if pl.deplacements:
        _p("\n  %sLA MÉMOIRE BOUGE (%d)%s" % (B, len(pl.deplacements), X))
        for (de, vers, c, _m) in pl.deplacements:
            _p("    %-40s -> %s %s%s%s" % (rc(de), rc(vers), D, c, X))
    if pl.reglages:
        _p("\n  %sRÉGLAGES RÉÉCRITS (%d)%s %s— copie gardée à côté%s" % (B, len(pl.reglages), X, D, X))
        for (f, _a, _n2, n) in pl.reglages:
            _p("    %-40s %d chemin(s) ou clé(s)" % (rc(f), n))
    if pl.ignore:
        _p("\n  %s.gitignore%s      memoire/ -> brain/ (le dépôt de mémoire reste à part)" % (B, X))
    if pl.poses or pl.dossiers:
        _p("\n  %sÀ POSER (%d)%s %s— jamais par-dessus un fichier%s" % (B, len(pl.poses) + len(pl.dossiers), X, D, X))
        for (p, q, _c) in pl.poses:
            _p("    %-40s %s%s%s" % (rc(p), D, q, X))
        for (d, q) in pl.dossiers:
            _p("    %-40s %s%s%s" % (rc(d), D, q, X))
    if pl.a_relire:
        _p("\n  %sÀ RELIRE (%d)%s %s— rien n'y est touché : c'est du contenu%s" % (B, len(pl.a_relire), X, D, X))
        for x in pl.a_relire:
            _p("    · %s" % x)
    if pl.bloquants:
        _p("\n  %sBLOQUÉ — %d raison(s), rien ne sera écrit tant qu'elles tiennent :%s" % (R, len(pl.bloquants), X))
        for x in pl.bloquants:
            _p("    · %s" % x)


def _atelier(dossier):
    _p("\n  %sMISE À NIVEAU — DIAGNOSTIC DE L'ATELIER%s   %s%s%s" % (B, X, D, dossier, X))
    _p("  %s(rien n'est écrit ; chaque projet se met à niveau seul, agents arrêtés)%s\n" % (D, X))
    _p("  %-24s %-12s %5s %5s %5s %5s %5s" % ("projet", "forme", "bouge", "régl.", "pose", "relir", "BLOQ"))
    a_faire = 0
    for n in sorted(os.listdir(dossier)):
        d = os.path.join(dossier, n)
        if not os.path.isdir(os.path.join(d, ".git")):
            continue
        pl, m = planifie(d)
        if pl is None or m:
            _p("  %-24s %s%s%s" % (n[:24], D, m or "—", X))
            continue
        travail = pl.deplacements or pl.reglages or pl.poses or pl.dossiers or pl.ignore
        a_faire += 1 if (travail or pl.bloquants) else 0
        _p("  %-24s %-12s %5d %5d %5d %5d %s%5d%s" % (
            n[:24], memoire.forme_mot(pl.forme), len(pl.deplacements), len(pl.reglages),
            len(pl.poses) + len(pl.dossiers), len(pl.a_relire),
            R if pl.bloquants else "", len(pl.bloquants), X if pl.bloquants else ""))
    _p("\n  %d projet(s) à mettre à niveau. Le détail : `harnais mise-a-niveau <projet>`." % a_faire)
    return 0


def main(args):
    if "--atelier" in args:
        i = args.index("--atelier")
        d = args[i + 1] if i + 1 < len(args) else os.getcwd()
        return _atelier(os.path.abspath(os.path.expanduser(d)))
    appliquer = "--apply" in args or "--go" in args
    arretes = "--agents-arretes" in args
    depart = next((a for a in args if not a.startswith("--")), None) or os.getcwd()
    pl, m = planifie(depart)
    if pl is None:
        _p("  %s%s%s" % (R, m, X))
        return 2
    _p("\n  %sMISE À NIVEAU%s   %s%s%s" % (B, X, D, pl.racine, X))
    if m:
        _p("  %s%s%s" % (J, m, X))
        return 1
    _affiche(pl)
    travail = pl.deplacements or pl.reglages or pl.poses or pl.dossiers or pl.ignore
    if not travail and not pl.bloquants:
        _p("\n  %sDéjà à niveau.%s %s" % (V, X, "Reste à relire ce qui est nommé ci-dessus." if pl.a_relire else ""))
        return 0
    if pl.bloquants:
        _p("\n  %sRien n'a été écrit.%s" % (J, X))
        return 2
    if not appliquer:
        _p("\n  %sRien n'a été écrit.%s Relance avec %s--apply%s%s pour agir." % (
            J, X, B, X, " --agents-arretes" if pl.bouge else ""))
        if pl.bouge:
            _p("  %sLa mémoire bouge : arrêter d'abord TOUTES les sessions de ce projet.%s" % (D, X))
        return 0
    if pl.bouge and not arretes:
        _p("\n  %sREFUSÉ%s — la mémoire bouge : arrêter toutes les sessions de ce projet, puis "
           "relancer avec %s--agents-arretes%s." % (R, X, B, X))
        return 2
    mal = applique(pl)
    _p()
    if mal:
        _p("  %s⚠ %d assertion(s) d'après ONT ÉCHOUÉ :%s" % (R, len(mal), X))
        for x in mal:
            _p("    · %s" % x)
        return 2
    _p("  %s✓ Fait.%s La mémoire est lue dans `brain/` ; relancer les agents un par un, puis "
       "`harnais equipe-vue --racine <atelier> --projet %s`." % (V, X, os.path.basename(pl.racine)))
    return 0
