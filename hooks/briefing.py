#!/usr/bin/env python3
"""briefing — hook SessionStart + UserPromptSubmit.

Le pendant de `mind-guard`. Celui-là force à **écrire** la mémoire au commit ;
celui-ci force à la **lire** au démarrage. Ensemble ils ferment la boucle : un
projet dont la mémoire est à jour mais que l'agent n'ouvre jamais est aussi
inutile qu'un projet sans mémoire.

LA PANNE QU'IL CORRIGE, mesurée le 03/09/2026. Interrogé sur les outils
auxquels il avait accès, un agent a répondu de travers alors que la réponse
tenait dans son `.fact/stack.md` — 173 lignes, à jour du jour même. Il n'avait
pas négligé de lire : **rien dans son contexte de démarrage ne nommait ce
fichier**. Son `CLAUDE.md` faisait une ligne. Sur huit projets de l'atelier,
sept nommaient `.mind/` et un seul ne le faisait pas : c'était celui-là.

CE QU'IL N'EST PAS. Il ne recopie pas la mémoire dans le contexte — ce serait
la faute que `.mind/` existe pour éviter, une copie qui se périme en silence.
Il injecte **ce qui ne tient pas dans un pointeur** (le cap, la fraîcheur, le
nombre de décisions en attente, les droits réellement appliqués) et, pour tout
le reste, **les titres de section de chaque fichier** : de quoi savoir quelle
question va trouver sa réponse où, sans en lire le contenu.

CE QU'IL AFFIRME EST TOUJOURS RELU. Chaque déclenchement rouvre les fichiers.
Rien n'est mis en cache d'une session à l'autre, donc rien ne peut vieillir.

QUAND IL PARLE.
  - `SessionStart` : à chaque fois. Ses quatre sources — startup, resume,
    clear, compact — couvrent le cas qui compte le plus, la **compaction** :
    c'est l'instant précis où l'agent perd du contexte, donc celui où le
    briefing vaut le plus cher.
  - `UserPromptSubmit` : **silencieux par défaut**. Il ne parle que si rien n'a
    encore été injecté, ou si un fichier de `.mind/` ou `settings.json` a
    changé depuis. Coût nul en régime établi, et c'est ce qui permet de poser
    le hook sur une **session déjà ouverte** : vérifié le 03/09/2026, un
    `settings.json` de projet ajouté à chaud est relu sans redémarrage, et le
    premier message qui suit reçoit le briefing.

LE VERROU. Le harnais déclare chaque hook deux fois, `python` et `python3`,
pour couvrir Windows et macOS. `mind-guard` s'en moque : deux refus valent un
refus. Un injecteur, lui, injecterait **deux fois** sur une machine où les deux
interpréteurs répondent. D'où le verrou atomique : le premier des deux prend le
tour, l'autre se tait.

DEUX ÉTAGES DEPUIS LE 04/09/2026. Le hook fait **deux remontées
indépendantes** : le `.mind/` le plus proche est l'état de l'agent qui parle,
le `.fact/` le plus proche est son projet. En mono c'est le même dossier ; en
multi-agents, l'agent vit dans `<projet>/agents/<nom>/` et le `.fact/` est deux
étages plus haut. C'est pour ça que les deux dossiers ne portent pas le même
nom : une remontée s'arrête au premier dossier trouvé, et deux étages homonymes
empêcheraient l'agent de voir jamais l'architecture de son projet.

LA SEULE FOIS OÙ IL PARLE SANS ÉTAT. Un `.fact/` trouvé **sans** `.mind/`
signifie qu'on est à la racine d'un projet multi-agents, là où personne ne
travaille — l'erreur la plus probable de cette architecture. Se taire y
produirait exactement la sortie d'un projet en bonne santé, donc il avertit et
nomme les agents disponibles.

**fail-open** : toute erreur, tout fichier absent, tout dépôt sans `.mind/` NI
`.fact/` laisse passer sans rien injecter. Un briefing n'a jamais à empêcher un
tour de parole.
"""
import datetime, errno, json, os, pathlib, re, subprocess, sys, time

FENETRE_VERROU = 5          # s — au-delà, un verrou est considéré abandonné
# Deux étages depuis le 04/09/2026. `.fact/` : ce qu'un seul écrivain tient
# pour tout le projet, fermé à quatre fichiers. `.mind/` : ce que chaque agent
# tient seul. Les noms DOIVENT différer : la remontée s'arrête au premier
# dossier trouvé, et deux étages homonymes empêcheraient un agent de
# `agents/<nom>/` de voir jamais l'architecture de son projet.
MIND = ("state.md", "todo.md")
# `roles.md` EN FAIT PARTIE, et son absence était le trou le plus ironique du
# harnais : c'est LE fichier qui dit à chaque agent ce que les autres tiennent,
# et c'était le seul des cinq à ne pas rebriefer quand il changeait. Un agent
# pouvait donc travailler des jours sur une frontière déplacée la veille — le
# cas précis que ce fichier existe pour éviter. Trouvé le 09/09/2026 en
# vérifiant si une règle qu'on venait d'y écrire atteindrait vraiment QA.
FACT = ("base.md", "architecture.md", "stack.md", "rules.md", "roles.md")
# Avant migration, les cinq fichiers vivent dans `.mind/`. Le briefing lit les
# deux formes : un projet non migré ne doit rien perdre.
MIND_ANCIEN = ("state.md", "todo.md", "stack.md", "architecture.md", "rules.md")
CHAMPS = ("maj", "cap", "sante", "jalon")
ENTETE = re.compile(r"\s*---\s*\n(.*?)\n---\s*(\n|$)", re.S)
TACHE = re.compile(r"^\s*[-*]\s*\[( |x|X|>|~)\]\s+(.+?)\s*$")
PRIO = re.compile(r"!(haut|moyen|bas)\b")
# Même dialecte que `.mind/todo.md` et le tableau de bord : tout `@nom`, et
# `@dehors` seul réservé. Le `@` doit ouvrir un mot, sinon `root@serveur`
# passerait pour un destinataire.
QUI = re.compile(r"(?:^|(?<=\s))@([A-Za-zÀ-ÿ][\w-]*)\b")
# QUATRIÈME LECTEUR DU DIALECTE, et il fuyait. `?constat` marque une ligne qui
# peut cesser d'être vraie toute seule ; c'est de la mécanique, pas du texte, et
# il n'a rien à faire dans la ligne d'entrée d'un agent. Signalé par un agent PO le
# 07/09/2026, le soir même où la règle a été posée : mon essai portait sur le
# hook qui écrit les Rappels, celui-ci lit le même fichier par un autre chemin.
CONSTAT = re.compile(r"(?:^|(?<=\s))\?constat\b", re.I)
DEHORS = "dehors"
TITRE = re.compile(r"^##\s+(.+?)\s*$", re.M)


def rien():
    """Sortie muette. Pas de JSON = pas d'injection, et surtout pas d'erreur."""
    sys.exit(0)


def lis(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _remonte(depart, marqueur):
    """Le premier ancêtre qui porte `marqueur`, `depart` compris."""
    try:
        p = pathlib.Path(depart).resolve()
    except (OSError, ValueError):
        return None
    while True:
        if (p / marqueur).is_dir():
            return p
        if p.parent == p:
            return None
        p = p.parent


def _mod(nom):
    """Importe un module voisin de ce hook. Importé, jamais recopié."""
    try:
        import importlib.machinery, importlib.util
        c = pathlib.Path(__file__).resolve().parent / (nom + ".py")
        if not c.exists():
            return None
        l = importlib.machinery.SourceFileLoader(nom, str(c))
        s = importlib.util.spec_from_loader(l.name, l)
        m = importlib.util.module_from_spec(s)
        l.exec_module(m)
        return m
    except Exception:
        return None


def _memoire():
    return _mod("memoire")


def mind_de(r):
    """Le `.mind/` de CET agent — déporté ou en place."""
    mm = _memoire()
    if mm is not None:
        mind, _ = mm.pour_agent(r)
        if mind is not None:
            return mind
    return r / ".mind"


def fait_de(r, projet):
    """Le `.fact/` du projet — déporté ou en place. None si pas encore migré."""
    mm = _memoire()
    if mm is not None:
        _, fact = mm.pour_agent(r)
        if fact is not None:
            return fact if fact.is_dir() else None
    if projet is None:
        return None
    f = projet / ".fact"
    return f if f.is_dir() else None


def racines(charge):
    """**Deux remontées indépendantes** — le coeur du dispositif multi-agents.

    `agent` porte le `.mind/` : c'est celui qui parle, et c'est chez lui que
    vivent le verrou et l'état du briefing. `projet` porte le `.fact/`. En mono
    les deux sont le même dossier ; en multi, `projet` est deux étages plus
    haut (`<projet>/agents/<nom>/`). Un projet non migré n'a pas de `.fact/` :
    `projet` vaut alors None, et tout se lit dans `.mind/`.

    `CLAUDE_PROJECT_DIR` fait AUTORITÉ quand il est posé — et depuis le
    04/09/2026 on sait qu'il vaut **le dossier de lancement de l'agent**, pas
    la racine du projet. Repli interdit : mesuré le 03/09/2026, une chaîne de
    repli qui finissait sur `os.getcwd()` briefait le projet du **répertoire
    courant du processus** au lieu de celui demandé, c'est-à-dire injectait le
    cap, les décisions en attente et les droits d'un projet étranger."""
    declare = (os.environ.get("CLAUDE_PROJECT_DIR") or charge.get("cwd")
               or os.getcwd())
    # FORME DÉPORTÉE (08/09/2026) : la mémoire d'état d'un projet multi-copies
    # vit dans `<racine>/memoire/`, pour n'exister qu'une fois. La remontée
    # ci-dessous ne la trouverait pas — elle cherche sous le dossier de
    # l'agent, et il n'y a plus rien.
    #
    # ON RENVOIE QUAND MÊME LES DOSSIERS DE L'AGENT ET DU PROJET, pas ceux de
    # la mémoire : `r` et `projet` servent aussi d'ancre au verrou, à l'état du
    # briefing et au titre. C'est `compose()` qui lit la mémoire, et lui seul.
    mm = _memoire()
    if mm is not None:
        mind, fact = mm.pour_agent(declare)
        if mind is not None:
            racine = mm.racine_depot(declare)
            agent = pathlib.Path(declare).resolve()
            return agent, (racine if racine else agent)
    return _remonte(declare, ".mind"), _remonte(declare, ".fact")


def entete(texte):
    m = ENTETE.match(texte or "")
    if not m:
        return {}
    d = {}
    for ligne in m.group(1).splitlines():
        if ":" in ligne and not ligne.lstrip().startswith("#"):
            k, _, v = ligne.partition(":")
            k = k.strip().lower()
            if k in CHAMPS:
                d[k] = v.strip()
    return d


def jours(iso):
    try:
        d = datetime.date.fromisoformat((iso or "").strip()[:10])
    except ValueError:
        return None
    return (datetime.date.today() - d).days


def attentes(texte):
    """Les tâches ouvertes qui portent un destinataire nommé, `@dehors` exclu."""
    out = []
    for ligne in (texte or "").splitlines():
        m = TACHE.match(ligne)
        if not m or m.group(1) in ("x", "X"):
            continue
        libelle = m.group(2)
        q = QUI.search(libelle)
        if not q or q.group(1).lower() == DEHORS:
            continue
        p = PRIO.search(libelle)
        out.append((p.group(1) if p else "moyen",
                    CONSTAT.sub("", PRIO.sub("", QUI.sub("", libelle)))
                    .replace("**", "").strip(" -—·")))
    out.sort(key=lambda t: {"haut": 0, "moyen": 1, "bas": 2}.get(t[0], 1))
    return out


def sommaire(p, combien=7):
    """Les titres `##` d'un fichier — de quoi savoir ce qu'il répond, sans le
    lire. C'est le cœur du dispositif : un pointeur nu (« voir stack.md ») ne
    dit pas quelle question y trouve sa réponse, donc ne déclenche pas
    l'ouverture."""
    t = lis(p)
    if not t:
        return None
    titres = [x.strip() for x in TITRE.findall(t)][:combien]
    return len(t.splitlines()), titres


def droits(r):
    """Ce qui est **appliqué**, pas ce qui est écrit. Un droit en prose est un
    espoir ; une règle `deny` est un fait."""
    for nom in ("settings.json", "settings.local.json"):
        p = r / ".claude" / nom
        if not p.exists():
            continue
        try:
            j = json.loads(lis(p) or "{}")
        except ValueError:
            return nom, None
        perm = j.get("permissions", {}) or {}
        return nom, (perm.get("defaultMode", "—"),
                     perm.get("allow", []) or [], perm.get("deny", []) or [])
    return None, None


def a_change(r, projet, depuis):
    """Un fichier surveillé est-il plus récent que la dernière injection ?

    `.fact/` en fait partie : une architecture mise à jour par un autre agent
    doit rebriefer celui-ci. L'omettre laisserait un agent travailler une
    session entière sur une frontière qui a bougé."""
    md = mind_de(r)
    surveilles = [md / n for n in MIND_ANCIEN] + \
                 [r / ".claude" / "settings.json", r / "CLAUDE.md"]
    if projet is not None:
        ft = fait_de(r, projet)
        if ft is not None:
            surveilles += [ft / n for n in FACT]
        surveilles += [projet / "CLAUDE.md"]
    for p in surveilles:
        try:
            if p.stat().st_mtime > depuis:
                return True
        except OSError:
            continue
    return False


def prends_le_tour(r):
    """Un seul des deux interpréteurs déclarés injecte. Création atomique :
    celui qui obtient le fichier parle, l'autre se tait."""
    v = r / ".claude" / ".briefing.lock"
    try:
        v.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(v), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.write(fd, str(time.time()).encode())
        os.close(fd)
        return True
    except OSError as e:
        if e.errno != errno.EEXIST:
            return False
        try:                      # verrou abandonné (interpréteur mort) : on reprend
            if time.time() - v.stat().st_mtime > FENETRE_VERROU:
                v.unlink()
                return prends_le_tour(r)
        except OSError:
            pass
        return False


def rends_le_tour(r):
    try:
        (r / ".claude" / ".briefing.lock").unlink()
    except OSError:
        pass


# ── L'ESPACE COMMUN DU PROJET ────────────────────────────────────────────
# Ce qu'un agent ne peut PAS savoir tout seul : ce que ses coéquipiers ont fait.
# Mesuré le 08/09/2026 sur un projet — les trois agents travaillent sur trois copies
# physiques du dépôt, chacune portant un GEL des fichiers des deux autres, et
# rien ne le leur dit. un agent QA avait deux jours et 187 enregistrements de
# retard, et lisait une liste de tâches de 1 202 lignes là où la vraie en faisait
# 2 810.
#
# Le carnet est le seul endroit qui n'existe QU'UNE FOIS. Ce hook en est le
# lecteur, et c'est ce qui rend possible le mécanisme de confiance du harnais de référence :
# **il sait exactement ce qu'il a servi**, donc l'agent n'a jamais à désigner ce
# qu'il a lu.

def _carnet():
    """Importé, jamais recopié — même règle que le dialecte de `todo.md`."""
    try:
        import importlib.machinery, importlib.util
        c = pathlib.Path(__file__).resolve().parent / "carnet.py"
        if not c.exists():
            return None
        loader = importlib.machinery.SourceFileLoader("carnet", str(c))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        return mod
    except Exception:
        return None


MENAGE_J, MEM_DORMANT_J = 7, 30


def memoire_a_ranger(r):
    """Une ligne au démarrage quand la mémoire mérite un ménage — ou rien.

    LE DÉCLENCHEUR EST L'ACTIVITÉ, PAS UNE HORLOGE. Repris à un agent de référence, qui ne pose
    aucun démon : il regarde, quand l'agent bouge, si assez de temps a passé.
    Zéro service à installer, et jamais un réveil en plein travail.

    IL COMPTE, IL NE RANGE PAS. Archiver retire des choses de la vue de l'humain ;
    aucun automatisme ne fait ça ici. `claude-memoire --appliquer` est un geste,
    et il reste le sien — ou le mien, en connaissance de cause.

    Coût : un glob et une lecture de JSON. Aucun fichier de note n'est ouvert."""
    try:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", str(r.resolve()))
        mem = pathlib.Path.home() / ".claude" / "projects" / slug / "memory"
        if not mem.is_dir():
            return None
        f = mem / ".usage.json"
        u = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        return None
    if not u.get("_depuis"):
        return None
    def j(iso):
        try:
            return (datetime.date.today() - datetime.date.fromisoformat(iso)).days
        except Exception:
            return 0
    if j(u.get("_menage") or "1970-01-01") < MENAGE_J:
        return None
    notes = [x.stem for x in mem.glob("*.md") if x.stem.upper() != "MEMORY"]
    if not notes:
        return None
    depuis = j(u["_depuis"])
    froides = [n for n in notes
               if not (u.get(n) or {}).get("epingle")
               and j((u.get(n) or {}).get("vu") or u["_depuis"]) >= MEM_DORMANT_J]
    servies = len([n for n in notes if (u.get(n) or {}).get("vu")])
    try:
        u["_menage"] = datetime.date.today().isoformat()
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(u, ensure_ascii=False, indent=1, sort_keys=True))
        os.replace(tmp, f)
    except Exception:
        pass
    if not froides:
        return None
    return ("mémoire: %d note(s) sur %d n'ont pas servi depuis %d j — %d ont servi "
            "au moins une fois.\n         `claude-memoire` pour voir, "
            "`--appliquer` pour ranger. Rien n'est jamais effacé."
            % (len(froides), len(notes), MEM_DORMANT_J, servies))


def cible(nom):
    """La cible du projet et l'écart au dernier rejeu — ou None.

    LECTURE SEULE D'UN TÉMOIN. C'est `attente.py` qui rejoue la vérification en
    fin de tour, sur son budget ; ce hook-ci tient en 15 s et ne doit lancer
    aucune commande. Il lit donc un verdict d'il y a un tour, ce qui est
    exactement ce qu'il faut : une cible se juge sur la journée, pas sur la
    seconde."""
    try:
        # Même socle que le hook de fin de tour : dans un plugin, l'état vit
        # sous CLAUDE_PLUGIN_DATA pour survivre aux mises à jour. Hors plugin,
        # ~/.claude, inchangé.
        _base = pathlib.Path(os.environ["CLAUDE_PLUGIN_DATA"]) \
            if os.environ.get("CLAUDE_PLUGIN_DATA") else pathlib.Path.home() / ".claude"
        t = (_base / "attente"
             / ("%s.cible" % re.sub(r"[^A-Za-z0-9_-]", "-", nom))).read_text()
        ch = t.split("\t")
        verdict, jour, phrase = ch[0], ch[1], ch[-1]
        suite = int(ch[2]) if len(ch) > 3 and ch[2].isdigit() else 1
    except Exception:
        return None
    ecart = {"TIENT": "tenue au %s" % jour,
             "TOMBÉ": ("PAS TENUE au %s — c'est ton sujet" % jour) if suite < 3
                      else ("PAS TENUE, et l'écart n'a pas bougé depuis %d "
                            "mesures — ce qu'on essaie ne marche pas" % suite),
             "SANS": "AUCUNE MESURE n'est encore écrite — c'est le premier "
                     "travail : sans elle, cette phrase est un vœu"}.get(
                 verdict, "pas mesurée au %s : la vérification n'a pas abouti" % jour)
    return "cible  : %s\n         → %s" % (phrase[:150], ecart)


def equipe(r, projet, session):
    """Les lignes du carnet à servir, ou []. Fail-open comme le reste."""
    if projet is None or r is None or r == projet:
        return []                       # mono-agent : pas d'espace commun
    k = _carnet()
    if k is None:
        return []
    esp = k.espace(r)
    if esp is None:
        return []
    lignes, servis = k.resume(esp, r.name)
    if servis:
        k.sert(esp, r.name, session or "sans-session", servis)
        if any("POUR TOI" in x for x in lignes):
            lignes = lignes + [
                "         Ce qui te vise reste en tête tant que tu ne l'as pas",
                "         acquitté : `↩ <empreinte>` dans ta prochaine entrée."]
        return lignes
    # CARNET VIDE : il faut quand même le dire, une fois. Sinon un agent
    # n'apprend l'existence de l'espace commun QU'EN SE FAISANT BLOQUER par le
    # hook de fin de tour — on lui reprocherait une convention qu'on ne lui a
    # jamais servie. Deux lignes, et elles disparaissent dès qu'il y a mieux à
    # montrer.
    if (esp / "LISEZMOI.md").exists():
        return ["  (rien de neuf) — tes coéquipiers travaillent sur d'AUTRES "
                "copies du dépôt.",
                "  Pour leur dire ce que tu changes chez eux : une ligne "
                "`↗ <agent> : <quoi>`",
                "  sous une tâche que tu coches. Le détail : `equipe/LISEZMOI.md`."]
    return []


def retard(r):
    """« Ta copie a N enregistrements de retard. »

    Un worktree ne voit du travail des autres que ce que sa dernière fusion lui
    a apporté, et git ne le signale JAMAIS de lui-même : `git status` d'une
    branche locale ne parle que d'elle. C'est exactement ce qui a rendu QA
    aveugle pendant deux jours sans qu'il puisse s'en douter."""
    k = _carnet()
    if k is None:
        return None
    principal = k.racine_commune(r)
    if principal is None:
        return None
    try:
        ici = pathlib.Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True,
            text=True, timeout=10, cwd=str(r)).stdout.strip())
        if ici.resolve() == principal.resolve():
            return None                 # je SUIS la copie principale
        ref = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=10,
                             cwd=str(principal)).stdout.strip()
        if not ref or ref == "HEAD":
            return None
        n = subprocess.run(["git", "rev-list", "--count", "HEAD..%s" % ref],
                           capture_output=True, text=True, timeout=10,
                           cwd=str(ici))
        if n.returncode != 0:
            return None
        c = int(n.stdout.strip() or 0)
        return (c, ref) if c else None
    except Exception:
        return None


def compose(r, projet, session=None):
    """Le briefing. `r` est le dossier de l'agent, `projet` celui qui porte le
    `.fact/` — le même en mono, None avant migration."""
    l = []
    a = l.append
    faits = fait_de(r, projet)
    md = mind_de(r)
    e = entete(lis(md / "state.md"))
    # Le `cap` appartient au PROJET, pas à l'agent : à plusieurs, ils visent la
    # même destination. Avant migration il est encore dans `state.md`.
    base = entete(lis(faits / "base.md")) if faits else {}
    cap = base.get("cap") or (e.get("cap") if faits is None else None)
    ou_cap = ".fact/base.md" if faits else ".mind/state.md"
    j = jours(e.get("maj", ""))
    frais = ("à jour" if j is not None and j <= 7 else
             "TIÈDE" if j is not None and j <= 28 else
             "PÉRIMÉ" if j is not None else "EN-TÊTE ILLISIBLE")

    titre = r.name if projet is None or projet == r else "%s · %s" % (projet.name, r.name)
    a("── Briefing d'entrée · %s ─ relu à l'instant, jamais recopié ──" % titre)
    a("cap    : %s" % (cap or "AUCUN `cap:` déclaré dans %s" % ou_cap))
    a("état   : %s%s · santé %s · jalon : %s"
      % (frais, "" if j is None else " (%d j)" % j,
         e.get("sante") or "—", e.get("jalon") or "—"))

    att = attentes(lis(md / "todo.md"))
    if att:
        a("attente: %d décision(s) humaine(s) — la première : [%s] %s"
          % (len(att), att[0][0], att[0][1][:70]))
        a("         Ça passe avant tout le reste dans un point d'avancement.")
    else:
        a("attente: aucune tâche `@<qui>` ouverte dans .mind/todo.md")

    # LA CIBLE, AU-DESSUS DE TOUT LE RESTE DU PROJET. Un agent qui démarre voit
    # d'abord ce qui attend l'humain, puis vers quoi il va — et seulement ensuite
    # ce que les autres ont fait. Un projet sans cible ne voit RIEN : pas de
    # ligne vide, qui se lirait comme un oubli plutôt que comme une absence.
    try:
        c = cible(r.name if r is not None else "")
    except Exception:
        c = None
    if c:
        for x in c.split("\n"):
            a(x)
    try:
        mr = memoire_a_ranger(r) if r is not None else None
    except Exception:
        mr = None
    if mr:
        for x in mr.split("\n"):
            a(x)

    # L'ÉQUIPE. Placé ici et pas ailleurs : le bloc au-dessus est ce qui te
    # revient, celui-ci est ce qui revient du reste du projet. Les deux passent
    # avant les sommaires de fichiers, qui ne disent qu'où chercher.
    try:
        lignes = equipe(r, projet, session)
    except Exception:
        lignes = []
    if lignes:
        a("équipe : ce que les autres ont fait — carnet commun `equipe/`")
        for x in lignes:
            a(x)
    try:
        rt = retard(r)
    except Exception:
        rt = None
    if rt:
        a("copie  : ta copie du projet a %d enregistrement(s) de retard sur "
          "`%s`." % rt)
        a("         Tu lis donc un GEL des fichiers de tes coéquipiers.")

    a("")
    a("Avant toute affirmation sur ce projet, ouvrir le fichier qui porte la")
    a("réponse — ces titres disent lequel :")
    # Deux formes, deux adresses. Après migration ces fichiers sont dans
    # `.fact/` — partagés par tous les agents du projet ; avant, dans `.mind/`.
    ou = faits if faits else md
    prefixe = ".fact/" if faits else ".mind/"
    fichiers = [("base.md", "la nature du projet, et où il va")] if faits else []
    fichiers += [("stack.md", "outils, comptes, accès, versions"),
                 ("rules.md", "ce qu'on ne franchit pas"),
                 ("architecture.md", "comment c'est agencé, les frontières")]
    for nom, quoi in fichiers:
        s = sommaire(ou / nom)
        if not s:
            a("  %s%-16s ABSENT — %s : personne ne le sait." % (prefixe, nom, quoi))
            continue
        n, titres = s
        a("  %s%-16s %3d l. · %s" % (prefixe, nom, n, quoi))
        if titres:
            a("      %s" % " · ".join(titres))
    racine_doc = projet if projet is not None else r
    if faits and (racine_doc / "docs").is_dir():
        a("  docs/decisions.md      le pourquoi de chaque choix, daté")
    else:
        a("  .memory/decisions.md   le pourquoi de chaque choix, daté")

    fichier, d = droits(r)
    a("")
    if d is None:
        a("Droits : %s — rien n'est mécaniquement interdit dans ce projet."
          % ("`%s` illisible" % fichier if fichier else
             "aucun settings.json"))
        a("         Tout ce qui a été dit à l'oral n'est retenu par rien.")
    else:
        mode, allow, deny = d
        a("Droits appliqués (%s) : mode %s · %d allow · %d deny"
          % (fichier, mode, len(allow), len(deny)))
        for rg in deny[:6]:
            a("    refusé : %s" % rg)
        if not deny:
            a("    ⚠ aucun `deny` : ce qui doit être interdit ici ne l'est que")
            a("      par la prose. Un droit en prose est un espoir.")
    return "\n".join(l)


def avertit_racine(projet):
    """Un `.fact/` sans `.mind/` : on est à la racine d'un projet
    multi-agents, là où **aucun agent ne travaille**.

    Se taire ici serait la pire sortie possible : elle est identique à celle
    d'un projet en bonne santé. C'est l'erreur la plus probable de cette
    architecture — lancer l'agent au mauvais endroit — et jusqu'ici rien ne la
    signalait."""
    dossier = projet / "agents"
    noms = []
    if dossier.is_dir():
        try:
            mm = _memoire()
            b = mm.base_projet(projet) if mm else None
            noms = sorted(
                d.name for d in dossier.iterdir()
                if (d / ".mind").is_dir()
                or (b is not None and (b / "agents" / d.name / ".mind").is_dir()))
        except OSError:
            noms = []
    l = ["── Briefing · %s ─ TU N'ES DANS AUCUN AGENT ──" % projet.name,
         "",
         "Ce dossier porte un `.fact/` mais pas de `.mind/` : c'est la racine",
         "d'un projet MULTI-AGENTS, et aucun agent n'y travaille. Tu n'as donc",
         "ni état, ni todo, ni droits appliqués — et `.claude/settings.json`",
         "d'ici ne s'exécute pas (les réglages ne s'héritent pas).",
         ""]
    if noms:
        l.append("Les agents de ce projet sont dans `agents/` :")
        for n in noms:
            l.append("  · %s" % n)
        l.append("")
        l.append("Relance la session DANS le dossier de l'agent voulu.")
    else:
        l.append("Aucun agent n'est encore déclaré : `agents/<nom>/` est vide")
        l.append("ou absent. Soit ce projet doit être converti, soit il lui")
        l.append("manque son premier agent.")
    return "\n".join(l)


def main():
    try:
        charge = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        charge = {}
    evenement = charge.get("hook_event_name") or "SessionStart"

    r, projet = racines(charge)
    if r is None and projet is None:    # aucun harnais : rien à briefer
        rien()
    # Le verrou et l'état vivent chez l'agent quand il y en a un. Deux agents
    # d'un même projet ne doivent jamais partager un verrou : le premier
    # prendrait le tour du second.
    ancre = r if r is not None else projet
    etat = ancre / ".claude" / ".briefing.json"
    if evenement == "UserPromptSubmit":
        # Silencieux, sauf si jamais injecté ou si la mémoire a bougé depuis.
        try:
            depuis = float(json.loads(lis(etat) or "{}").get("derniere", 0))
        except (ValueError, TypeError):
            depuis = 0
        if depuis and r is not None and not a_change(r, projet, depuis):
            rien()

    if not prends_le_tour(ancre):       # l'autre interpréteur s'en charge
        rien()
    try:
        texte = (compose(r, projet, charge.get("session_id"))
                 if r is not None else avertit_racine(projet))
        etat.parent.mkdir(parents=True, exist_ok=True)
        etat.write_text(json.dumps({"derniere": time.time(),
                                    "evenement": evenement}), encoding="utf-8")
    except Exception:
        rends_le_tour(ancre)
        rien()
    rends_le_tour(ancre)

    # LE REPLI DIT QU'IL EST LE REPLI. Le lanceur pose `HARNAIS_REPLI` quand
    # aucun programme natif n'a répondu sur cette machine. Sans cette ligne, le
    # repli est indiscernable du régime normal — or il n'est PAS équivalent :
    # onze sorties bloquantes au lieu de douze, le relecteur en moins. Mesuré le
    # 10/09/2026 en comparant les deux sources. Un repli silencieux fait croire
    # à un harnais complet, et c'est le pire des deux mondes : on lui fait la
    # confiance de l'original.
    #
    # L'avertissement va DANS le texte, jamais devant le JSON : le harnais
    # analyse cette sortie, et une ligne posée avant la rendrait illisible —
    # on perdrait le briefing entier pour annoncer qu'il est dégradé.
    if os.environ.get("HARNAIS_REPLI"):
        texte = ("⚠ HARNAIS EN REPLI PYTHON — aucun programme natif n'a répondu "
                 "sur cette machine. ONZE gardes de fin de tour sur DOUZE : le "
                 "relecteur, celui qui juge ce qui part vers le commanditaire, "
                 "n'existe pas ici. Tout le reste est identique à l'octet.\n\n"
                 + texte)

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": evenement,
        "additionalContext": texte,
    }}))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:                   # fail-open, sans exception
        rien()
