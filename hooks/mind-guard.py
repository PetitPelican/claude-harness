#!/usr/bin/env python3
"""mind-guard - hook PreToolUse (matcher Bash, sur `git commit`).

Remplace `memory-guard`, qui gardait `.memory/` et se déclenchait au `git push`.
Deux changements, et chacun corrige une panne réelle :

1. LE DÉCLENCHEUR PASSE DE `push` À `commit`. Le tableau de bord
   (`claude-cadrage`, qui importe `claude-projets`) lit les fichiers `.mind/`
   du **disque local**, jamais le dépôt distant. Garder au push ne protégeait
   donc pas ce qu'on croyait protéger : un projet pouvait rester des semaines
   sans pousser, et le tableau de bord affichait sa dernière déclaration comme
   si elle était fraîche.

2. IL NE SUFFIT PLUS DE « TOUCHER » LA MÉMOIRE. `memory-guard` acceptait
   n'importe quel fichier de `.memory/` : un commit qui ne modifiait que
   `decisions.md` le satisfaisait en laissant `state.md` périmé. Ici on exige
   `.mind/state.md`, et on vérifie qu'il **parse encore**.

3. LE TODO A QUITTÉ CE HOOK (06/09/2026). `.mind/todo.md` était exigé ici lui
   aussi ; il appartient désormais à `attente.py`, hook `Stop`, qui se
   déclenche à chaque fin de tour. Sur `commit`, un agent qui analyse ou qui
   est bloqué maintenant n'écrivait rien : ce qui attend le commanditaire n'arrivait
   qu'au prochain commit, parfois jamais. Un instantané (`state.md`) se pose
   à un jalon, une alerte (`todo.md`) ne peut pas attendre le jalon suivant.

Le second point est le plus important : un en-tête cassé est PIRE qu'un en-tête
vieux. `claude-projets` signale « aucun en-tête dans .mind/state.md — on ne sait
ni où va le projet ni qui doit bouger », et le projet sort du tableau de bord
sans que personne ne s'en aperçoive. Un fichier illisible est un silence, et un
silence se lit comme une absence de problème.

Contrat repris **du parseur**, pas de mémoire (`claude-projets`, v. 03/09/2026) :
  - en-tête : `---\n…\n---` en tête de `.mind/state.md`, YAML plat
  - champs lus : maj, cap, sante, jalon, balle, depuis, attente, suivant
  (le dialecte des tâches — `- [ ] Libellé`, `!haut`, `@user` — est passé
  avec le todo dans `attente.py`.)

Échappatoire : ` # mind-ok` à la fin de la commande.
**fail-open** : toute erreur, ambiguïté ou dépôt non git laisse passer.
"""
import sys, json, subprocess, re, datetime, os, pathlib

# --- à ajuster selon le projet -------------------------------------------------
# Relatifs au DOSSIER DE L'AGENT, pas à la racine git : en multi-agents, git
# renvoie `agents/ios/src/x.ts` et le préfixe du lot est ajouté à l'exécution.
IGNORED_PREFIXES = (".claude/", ".mind/", ".fact/", "docs/", ".memory/", ".logs/")
CODE_EXT = (
    ".py", ".sql", ".qmd", ".ipynb", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".rb", ".php", ".c", ".h", ".hpp", ".cpp", ".cc",
    ".cs", ".swift", ".scala", ".sh", ".ps1", ".r", ".jl", ".vue", ".svelte",
    ".dart", ".ex", ".exs",
)
SRC_DIRS = ("src/", "app/", "lib/", "python/", "sql/", "packages/", "services/", "api/")
# ------------------------------------------------------------------------------

# Deux contrats, selon la forme. Avant migration le `cap` est dans `state.md` ;
# après, il appartient au projet et vit dans `.fact/base.md` — le réclamer ici
# ferait échouer tout commit d'un projet correctement migré.
CHAMPS_REQUIS = ("maj", "cap", "jalon")
CHAMPS_REQUIS_FACT = ("maj", "sante", "jalon")


def _git(args):
    return subprocess.run(["git"] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=15)


# LES DEUX ÉCHAPPATOIRES SE LISENT EN FIN DE COMMANDE, PAS N'IMPORTE OÙ.
# C'était un test de sous-chaîne brut : un nom de branche `essai-fact-ok`, un
# chemin de fichier, une phrase du message de commit — n'importe quoi contenant
# ces six caractères désarmait le garde, sans intention et sans trace. La prose
# du refus disait déjà « à la fin de la commande » ; le code ne le vérifiait pas.
# Ce que la forme exige : un `#` de commentaire shell, le mot, puis la fin.
def _autorise(cmd, mot):
    return re.search(r"#\s*%s\s*$" % re.escape(mot), cmd or "") is not None


def allow():
    sys.exit(0)  # pas de sortie = décision par défaut (allow)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def _memoire():
    """Le module qui dit OÙ vit la mémoire. Importé, jamais recopié."""
    try:
        import importlib.machinery, importlib.util
        c = pathlib.Path(__file__).resolve().parent / "memoire.py"
        if not c.exists():
            return None
        l = importlib.machinery.SourceFileLoader("memoire", str(c))
        s = importlib.util.spec_from_loader(l.name, l)
        m = importlib.util.module_from_spec(s)
        l.exec_module(m)
        return m
    except Exception:
        return None


def deportee():
    """`(dossier .mind, dossier .fact)` si la mémoire est hors du dépôt.

    CE QUE ÇA CHANGE POUR CE GARDE, et il faut l'avoir en tête : déportés, ces
    fichiers n'apparaissent JAMAIS dans `git diff --cached` du dépôt de code.
    Les chercher là rendrait le garde inerte — et silencieusement, puisqu'il
    laisse passer par défaut. On lit donc le disque au lieu de l'index."""
    mm = _memoire()
    if mm is None:
        return None, None
    try:
        return mm.pour_agent()
    except Exception:
        return None, None


def contexte():
    """Où l'agent travaille, et sous quelle forme — tout le reste en découle.

    MESURÉ le 04/09/2026 : `git diff --cached --name-only` renvoie des chemins
    relatifs à la **racine du dépôt**, jamais au dossier courant. Un agent de
    `agents/ios/` voit donc `agents/ios/.mind/state.md`, et la constante
    `.mind/state.md` ne matche plus rien : le garde laissait passer TOUT, sans
    le dire. C'est cette fonction qui répare ça.

    `CLAUDE_PROJECT_DIR` vaut le dossier de lancement de l'agent (mesuré le
    même jour), donc le lot s'en déduit par différence avec la racine git.

    Renvoie (lot, projet, faits) : le préfixe du lot (« agents/ios/ » ou « »),
    le préfixe du projet depuis la racine git, et celui de `.fact/` s'il
    existe — None si le projet n'a pas encore migré.
    """
    racine = _git(["rev-parse", "--show-toplevel"])
    if racine.returncode != 0:
        return "", "", None
    racine = pathlib.Path(racine.stdout.strip())
    depart = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        agent = pathlib.Path(depart).resolve()
        lot = agent.relative_to(racine.resolve())
    except (OSError, ValueError):
        return "", "", None
    lot = "" if str(lot) == "." else str(lot) + "/"

    # Le projet : le premier ancêtre qui porte un `.fact/`, sans jamais sortir
    # du dépôt. Absent = forme d'avant migration, et tout se lit dans `.mind/`.
    p = agent
    while True:
        if (p / ".fact").is_dir():
            rel = p.relative_to(racine.resolve())
            pre = "" if str(rel) == "." else str(rel) + "/"
            return lot, pre, pre + ".fact/"
        if p == racine.resolve() or p.parent == p:
            return lot, lot, None
        p = p.parent


def is_project_code(f, lot="", projet=""):
    """Deux jeux de préfixes à ignorer, pas un : le harnais de l'AGENT
    (`agents/ios/.claude/`, `.mind/`) et celui du PROJET (`.fact/`, `docs/`,
    `.logs/`). N'ignorer que le second laissait compter `agents/ios/.claude/
    hooks/x.py` pour du code projet, et réclamait une mise à jour d'état pour
    une modification de harnais."""
    ignores = tuple(lot + p for p in IGNORED_PREFIXES) + \
              tuple(projet + p for p in IGNORED_PREFIXES)
    if any(f.startswith(p) for p in ignores):
        return False
    if f.startswith(projet + "site/") and not f.startswith(projet + "site/_content/"):
        return False  # moteur / rendu généré du site de doc
    srcs = tuple(lot + d for d in SRC_DIRS) + tuple(projet + d for d in SRC_DIRS)
    return f.endswith(CODE_EXT) or f.startswith(srcs)


def stage(chemin):
    """Le contenu tel qu'il sera COMMITÉ, pas celui du disque.

    Lire le disque laisserait passer une correction non indexée : l'agent
    répare `state.md`, oublie de l'ajouter, et commite la version cassée."""
    r = _git(["show", ":" + chemin])
    return r.stdout if r.returncode == 0 else None


def lis_disque(p):
    """Le fichier tel qu'il est SUR LE DISQUE — pas tel qu'il sera commité.

    `stage()` juste au-dessus fait l'inverse, et c'est voulu : quand la mémoire
    est dans le dépôt, ce qui compte est ce qui sera enregistré. Déportée, elle
    n'est pas dans cet index-là ; le disque est alors la seule vérité."""
    try:
        return pathlib.Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def entete(texte):
    """Le même en-tête que celui de `claude-projets`. Renvoie {} si absent."""
    m = re.match(r"\s*---\s*\n(.*?)\n---\s*(\n|$)", texte, re.S)
    if not m:
        return {}
    out = {}
    for ligne in m.group(1).splitlines():
        if ":" in ligne and not ligne.lstrip().startswith("#"):
            cle, _, val = ligne.partition(":")
            out[cle.strip().lower()] = re.sub(r"\s+#.*$", "", val).strip()
    return out


def verifie_state(texte, champs=CHAMPS_REQUIS):
    """Reproches, étiquetés par nature.

    La distinction n'est pas cosmétique : un fichier ILLISIBLE fait disparaître
    le projet du tableau de bord sans bruit, un fichier PÉRIMÉ l'y montre avec
    une date fausse. Les deux se corrigent, mais pas pour la même raison, et
    confondre les deux dans un même message apprend à l'agent le mauvais geste."""
    d = entete(texte)
    if not d:
        return [("structure",
                 "il n'a plus d'en-tête `---` en première ligne — le collecteur "
                 "le range en « aucune déclaration » et le projet disparaît du "
                 "tableau de bord")]
    maux = []
    manquants = [c for c in champs if not d.get(c)]
    if manquants:
        maux.append(("structure",
                     "il lui manque " + ", ".join("`%s:`" % c for c in manquants)))
    maj = d.get("maj", "")
    if maj and not re.match(r"^\d{4}-\d{2}-\d{2}$", maj):
        maux.append(("structure",
                     "`maj:` doit être une date ISO `AAAA-MM-JJ`, pas « %s »" % maj[:20]))
    elif maj and maj != datetime.date.today().isoformat():
        maux.append(("fraicheur",
                     "`maj:` porte %s alors que le commit est d'aujourd'hui (%s) — "
                     "le tableau de bord datera ce projet du mauvais jour"
                     % (maj, datetime.date.today().isoformat())))
    return maux


# `verifie_todo` A ÉTÉ RETIRÉ LE 06/09/2026 — et avec lui toute exigence sur
# `.mind/todo.md` à cet endroit. Le todo est passé au hook `Stop` (`attente.py`),
# qui se déclenche à CHAQUE FIN DE TOUR. La raison est mesurée : ce hook-ci ne
# s'arme que sur `git commit`, donc un agent qui analyse, qui est bloqué
# maintenant, ou qui n'a pas encore commité n'écrivait rien. Le todo était un
# journal rétrospectif alors qu'on lui demandait d'être une alerte.
#
# Ce hook garde `state.md` : c'est un INSTANTANÉ, et un instantané n'a de sens
# qu'à un jalon — le commit en est un. Le partage est donc net :
#
#     mind-guard (commit)  ->  .mind/state.md   où en est le projet
#     attente    (Stop)    ->  .mind/todo.md    ce qui attend le commanditaire
#     journal    (commit)  ->  .logs/<jour>.md  ce qui a été fait


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()

    cmd = ((data.get("tool_input") or {}).get("command") or "")
    if not re.search(r"\bgit\b.+\bcommit\b", cmd):
        allow()

    # `mind-ok` N'EST PAS TESTÉ ICI. Il l'était jusqu'au 05/09/2026, avant le
    # contrôle `.fact/` — donc une seule clé ouvrait deux serrures qui ne
    # protègent pas la même chose : « ma déclaration d'agent n'a pas à bouger »
    # désarmait aussi la garde de la mémoire PARTAGÉE du projet. Chaque
    # échappatoire est désormais testée devant la règle qu'elle lève, et pas
    # avant. Repéré par `<projet> OPS` en franchissant le trou en connaissance
    # de cause, ce qui est la bonne façon de le signaler.
    lot, projet, faits = contexte()
    state, todo = lot + ".mind/state.md", lot + ".mind/todo.md"
    d_mind, d_fact = deportee()
    if d_fact is not None:
        faits = faits or "«déporté»"     # le projet A des faits, ailleurs
    champs = CHAMPS_REQUIS_FACT if faits else CHAMPS_REQUIS

    r = _git(["diff", "--cached", "--name-only"])
    if r.returncode != 0:
        allow()  # pas un dépôt git, ou git indisponible -> ne bloque pas
    fichiers = [f.strip() for f in r.stdout.splitlines() if f.strip()]
    if not fichiers:
        allow()  # `git commit --amend`, commit vide… : rien à juger

    # 0. `.fact/` NE S'ÉCRIT QU'À LA DEMANDE DE L'UTILISATEUR. C'est la seule mémoire
    # partagée par tous les agents d'un projet : un agent qui la réécrit depuis
    # son lot efface ce qu'un autre y avait mis, et personne ne le voit. La
    # règle existait en prose ; ici elle devient vérifiable, et l'autorisation
    # laisse une trace dans l'historique.
    if faits and not _autorise(cmd, "fact-ok"):
        touches = [f for f in fichiers if f.startswith(faits)]
        if touches:
            deny("mind-guard : ce commit modifie `.fact/` (%s). Ces fichiers "
                 "sont partagés par TOUS les agents du projet et ne s'écrivent "
                 "qu'à la demande du commanditaire — un agent qui les réécrit depuis "
                 "son lot efface le travail d'un autre en silence. Si le commanditaire "
                 "l'a demandé, ajoute ` # fact-ok` à la fin de la commande : "
                 "l'autorisation restera dans l'historique."
                 % (", ".join(touches[:4]) + (", …" if len(touches) > 4 else "")))

    # `mind-ok` ne lève QUE les règles sur la déclaration de l'agent, jamais
    # celle sur `.fact/` ci-dessus. Voir le commentaire en tête de fonction.
    if _autorise(cmd, "mind-ok"):
        allow()

    # 1. LISIBILITÉ — vaut même sans code, un fichier cassé est le pire cas.
    for nom, verif in ((state, lambda x: verifie_state(x, champs)),):
        if nom in fichiers or d_mind is not None:
            texte = (lis_disque(d_mind / "state.md") if d_mind is not None
                     else stage(nom))
            if texte is None:
                continue  # suppression ou renommage : ce n'est pas notre sujet
            maux = verif(texte)
            if maux:
                tete = ("ne serait plus lisible par le tableau de bord"
                        if any(k == "structure" for k, _ in maux)
                        else "n'est pas à jour")
                deny("mind-guard : `%s` %s — %s. Corrige, réindexe "
                     "(`git add %s`), puis recommite."
                     % (nom, tete, " ; ".join(m for _, m in maux), nom))

    # 2. FRAÎCHEUR — du code sort, la déclaration doit suivre.
    code = [f for f in fichiers if is_project_code(f, lot, projet)]
    if not code:
        allow()

    # Le projet doit savoir dire où il va. `.fact/base.md` porte le `cap:` —
    # il a quitté `state.md` le 04/09/2026, parce qu'un projet n'a qu'une
    # destination même à plusieurs agents.
    if faits:
        if d_fact is not None:
            contenu = lis_disque(d_fact / "base.md")
        else:
            texte = _git(["show", "HEAD:" + faits + "base.md"])
            contenu = stage(faits + "base.md") or (texte.stdout if texte.returncode == 0 else "")
        if not entete(contenu).get("cap"):
            deny("mind-guard : `%sbase.md` ne porte pas de `cap:` — le tableau "
                 "de bord n'a alors AUCUNE réponse au niveau du projet, quel "
                 "que soit le nombre d'agents qui s'y déclarent. Écris-y "
                 "l'en-tête `---` avec `cap:`, puis recommite (` # fact-ok`, "
                 "c'est `.fact/`)." % faits)

    # DÉPORTÉ, `state.md` n'est JAMAIS dans l'index du dépôt de code : exiger
    # qu'il y soit bloquerait tous les commits, pour toujours. La règle devient
    # « il doit être plus récent que le code », lue sur le disque — même
    # intention, autre preuve.
    if d_mind is not None:
        # LES CHEMINS DE `git diff --cached` SONT RELATIFS À LA RACINE DU
        # DÉPÔT, jamais au dossier courant — qui est ici celui de l'agent. Les
        # stat-er tels quels ne trouverait rien, `recent` vaudrait 0, et le
        # garde laisserait tout passer sans le dire. Même piège que celui qui a
        # rendu ce fichier inerte le 04/09/2026.
        rr = _git(["rev-parse", "--show-toplevel"])
        if rr.returncode != 0:
            allow()
        rr = pathlib.Path(rr.stdout.strip())
        try:
            s = (d_mind / "state.md").stat().st_mtime
        except OSError:
            allow()
        recent = 0
        for f in code:
            q = rr / f
            try:
                recent = max(recent, q.stat().st_mtime)
            except OSError:
                pass
        if not recent or s >= recent:
            allow()
        echantillon = ", ".join(code[:5]) + (", …" if len(code) > 5 else "")
        deny("mind-guard : du code projet est indexé (%s) alors que ta "
             "déclaration d'état n'a pas bougé depuis. C'est ce que le tableau "
             "de bord lit pour savoir où en est ce projet. Mets `.mind/state.md` "
             "à jour (dont le champ `maj:`), puis recommite. Si elle n'a vraiment "
             "pas à bouger, ajoute ` # mind-ok` à la fin de la commande.\n\n"
             "Ta mémoire est DÉPORTÉE dans `memoire/` : il n'y a rien à `git "
             "add`, elle est versionnée à part et commitée toute seule en fin "
             "de tour." % echantillon)

    if state not in fichiers:
        echantillon = ", ".join(code[:5]) + (", …" if len(code) > 5 else "")
        deny(
            "mind-guard : du code projet est indexé (%s) sans mise à jour de "
            "`%s`. C'est ce que le tableau de bord lit pour savoir où en est ce "
            "projet — pas poussé, mais lu sur le disque : un commit qui le laisse "
            "en arrière rend le projet muet. Mets-le à jour (dont le champ "
            "`maj:`), indexe-le (`git add %s`), puis recommite. Si la déclaration "
            "n'a vraiment pas à bouger, ajoute ` # mind-ok` à la fin de la "
            "commande.\n\n`.mind/todo.md` n'est plus exigé ICI — c'est le hook "
            "`Stop` qui le réclame, à chaque fin de tour."
            % (echantillon, state, state)
        )
    allow()


if __name__ == "__main__":
    main()
