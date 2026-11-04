# -*- coding: utf-8 -*-
"""LE GARDE DE LA PRODUCTION — hook PreToolUse (Bash), et `harnais laissez-passer`.

Décision du 14/10/2026 : sécuriser la production. Rien ne refusait une poussée
sur `main` ; la règle n'était qu'écrite. Un projet avait posé son propre garde ;
la 0.19 en fait un garde du paquet,
pour toute équipe et tout projet seul, Mac et Windows.

CE QUI EST REFUSÉ, à tout agent sans laissez-passer :
  · `git push` dont la destination est une branche de production, sous toutes
    ses formes (`origin main`, `HEAD:main`, `refs/heads/main`, `+main`, un motif
    qui la couvre, `--all`, `--mirror`, ou un `git push` nu depuis cette branche) ;
  · `gh pr merge`, et l'API GitHub en écriture sur une de ces branches ;
  · (0.19.7) les commandes de publication déclarées. `vercel` : `--prod`,
    `--environment production` (et `--target`, l'ancien nom), `promote`,
    `rollback`, `redeploy` sauf vers un autre environnement nommé — y compris
    derrière `env`, `npx`, `pnpm dlx`, `bunx` ou un chemin vers le binaire.
    `vercel -p` n'en est PAS un : c'est `--project`.

RIEN N'EST FERMÉ SANS RÉGLAGE. Le projet le déclare dans ses règles — l'en-tête
de `fact/rules.md` (équipe) ou `brain/fact/rules.md` (seul) :

    ---
    production: main, production     les branches qui partent en Production
    production-commandes: vercel     les commandes qui publient (familles connues : vercel)
    production-agent: OPS            le seul qui peut demander un laissez-passer
    production-duree: 15             minutes de validité
    ---

L'une OU l'autre des deux premières clés suffit à fermer le projet.

Un fait ne s'écrit qu'à la demande de l'humain (` # fact-ok`) : un agent ne
peut pas desserrer ce réglage en silence.

LE LAISSEZ-PASSER. `harnais laissez-passer "motif"`, que seul l'agent nommé
obtient, après le oui de l'humain au moment du geste. Il vaut `production-duree`
minutes et chaque usage laisse une ligne au journal (agent, heure, commande,
motif). Il vit dans le dossier de données du paquet, hors du projet et hors de
git. Que l'agent nommé puisse se l'accorder est une CONVENTION — le journal la
rend visible, il ne l'empêche pas.

**fail-open** sur une entrée illisible ; **fail-closed** sur l'identité : un
appelant que le garde n'identifie pas n'est pas l'agent nommé.
"""
import os
import re
import sys
import time

DUREE_DEFAUT = 15
FINS = {"&&", "||", ";", "|", "&", "|&", ";;", "\n"}
PUSH_AVEC_VALEUR = {"-o", "--push-option", "--repo", "--receive-pack", "--exec", "--signed"}
PORTEUSES = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
ECRIT_GITHUB = re.compile(
    r"(?:-X\s*|--method[\s=]+|--request\s+)(?:POST|PUT|PATCH|DELETE)\b|\s-f\s|\s-F\s|\s--field\s|"
    r"--raw-field|--input\b|--data|\s-d\s", re.I)
# Vercel CLI 65 : options qui portent une valeur (sa valeur n'est pas une sous-commande).
VERCEL_AVEC_VALEUR = {"--cwd", "-Q", "--global-config", "-A", "--local-config", "-S", "--scope",
                      "-t", "--token", "-T", "--team", "-p", "--project", "--archive", "-b",
                      "--build-env", "-e", "--env", "--environment", "--target", "-m", "--meta",
                      "--regions", "--timeout"}
# Les sous-commandes qui ne déploient pas ; tout le reste (rien, `deploy`, un chemin) déploie.
VERCEL_AUTRES = {"alias", "api", "bisect", "blob", "build", "cache", "certs", "dev", "dns", "domains",
                 "env", "git", "guidance", "help", "init", "inspect", "install", "integration",
                 "integration-resource", "link", "list", "login", "logout", "logs", "ls", "mcp",
                 "microfrontends", "open", "project", "projects", "pull", "remove", "rm", "rolling-release",
                 "switch", "target", "teams", "telemetry", "upgrade", "whoami"}


# ── le réglage du projet ────────────────────────────────────────────────

def _entete(f):
    try:
        with open(f, encoding="utf-8") as h:
            t = h.read()
    except (OSError, ValueError):
        return {}
    if not t.startswith("---"):
        return {}
    fin = t.find("\n---", 3)
    if fin < 0:
        return {}
    v = {}
    for l in t[3:fin].splitlines():
        k, s, val = l.partition(":")
        if s:
            v[k.strip().lower()] = val.strip()
    return v


def reglage(depart):
    """`(projet, branches, agent, durée, commandes)` ou None si le projet ne ferme rien."""
    import memoire
    r = memoire.resous(depart)
    if r.fact is None:
        return None
    e = _entete(os.path.join(r.fact, "rules.md"))
    branches = {b.strip() for b in e.get("production", "").split(",") if b.strip()}
    commandes = {c.strip().lower() for c in e.get("production-commandes", "").split(",") if c.strip()}
    if not branches and not commandes:
        return None
    try:
        duree = int(e.get("production-duree", "") or DUREE_DEFAUT)
    except ValueError:
        duree = DUREE_DEFAUT
    return (r.projet or r.racine, branches, e.get("production-agent", "").strip(), duree, commandes)


def agent_appelant(depart):
    """Le nom de l'agent : le dossier qui suit `agents/`, sinon celui du projet seul."""
    import memoire
    r = memoire.resous(depart)
    if r.nom_agent:
        return r.nom_agent
    morceaux = [m for m in re.split(r"[\\/]", os.path.abspath(depart)) if m]
    for i, m in enumerate(morceaux):
        if m == "agents" and i + 1 < len(morceaux):
            return morceaux[i + 1]
    return ""


# ── le laissez-passer ────────────────────────────────────────────────────

def _dossier():
    import socle
    d = os.path.join(socle.socle(), "production")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def _fichiers(projet):
    import equipe
    s = equipe.slug(projet).strip("-") or "projet"
    d = _dossier()
    return os.path.join(d, s + ".laissez-passer"), os.path.join(d, s + ".log")


def journalise(projet, ligne):
    _, log = _fichiers(projet)
    try:
        with open(log, "a", encoding="utf-8") as h:
            h.write("%s\t%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), ligne.replace("\n", " ")))
    except OSError:
        pass


def valide(projet, duree):
    """Le motif d'un laissez-passer encore valide, ou None."""
    f, _ = _fichiers(projet)
    try:
        if time.time() - os.path.getmtime(f) > duree * 60:
            return None
        with open(f, encoding="utf-8") as h:
            return h.read().strip() or "(sans motif)"
    except (OSError, ValueError):
        return None


# ── la commande qui pousse ───────────────────────────────────────────────

def _jetons(cmd):
    import shlex
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:
        return cmd.split()


def _resoudre(base, cible):
    return os.path.normpath(os.path.join(base, os.path.expanduser(cible)))


def _branche_courante(dossier):
    import subprocess
    try:
        o = subprocess.run(["git", "-C", dossier, "rev-parse", "--abbrev-ref", "HEAD"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return o.stdout.decode("utf-8", "replace").strip() if o.returncode == 0 else ""


def _nom(ref):
    ref = ref.lstrip("+")
    return ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref


def _analyse_push(args, dossier, branches):
    options, positionnels, j = set(), [], 0
    while j < len(args):
        a = args[j]
        if a in PUSH_AVEC_VALEUR:
            j += 2
            continue
        if a.startswith("-") and a != "-":
            options.add(a.split("=")[0])
            j += 1
            continue
        positionnels.append(a)
        j += 1
    tout = options & {"--mirror", "--all", "--branches"}
    if tout:
        return "`git push %s` pousse aussi la branche de production" % sorted(tout)[0]
    refspecs = positionnels[1:]
    if not refspecs:
        courante = _branche_courante(dossier)
        if courante in branches:
            return "`git push` depuis une copie qui est SUR `%s`" % courante
        return None
    for spec in refspecs:
        src, _, dst = spec.lstrip("+").partition(":")
        dst = _nom(dst if ":" in spec else src)
        if "*" in dst or ("*" in src and ":" not in spec):
            return "un motif de références (`%s`) qui comprend la branche de production" % spec
        if dst == "HEAD":
            dst = _branche_courante(dossier)
        if dst in branches:
            return "la destination `%s` est une branche de production" % dst
    return None


def _programme(jeton):
    """`C:\\x\\vercel.cmd`, `/usr/bin/git`, `vercel@65` → `vercel`, `git`, `vercel`."""
    p = re.split(r"[\\/]", jeton)[-1].lower()
    p = re.sub(r"\.(?:exe|cmd|bat|ps1)$", "", p)
    # `npx vercel@65`, mais pas `ssh git@hôte` : la version ne se retire qu'à vercel.
    return p.split("@", 1)[0] if p.split("@", 1)[0] in ("vercel", "vc") else p


def _analyse_vercel(args):
    options, positionnels, j = {}, [], 0
    while j < len(args):
        a = args[j]
        if a == "--":
            positionnels.extend(args[j + 1:])
            break
        if a.startswith("-") and a != "-":
            cle, egal, val = a.partition("=")
            if cle in VERCEL_AVEC_VALEUR and not egal:
                val = args[j + 1] if j + 1 < len(args) else ""
                j += 1
            options[cle] = val.lower()
            j += 1
            continue
        positionnels.append(a.lower())
        j += 1
    sous = positionnels[0] if positionnels else "deploy"
    vers = options.get("--environment") or options.get("--target") or ""
    if sous == "redeploy":
        vers = vers or options.get("-e", "")
    if sous in ("promote", "rollback"):
        if positionnels[1:2] == ["status"]:
            return None
        return "`vercel %s` change le déploiement servi en Production" % sous
    if sous == "redeploy":
        if vers and vers != "production":
            return None
        return ("`vercel redeploy` reconstruit vers l'environnement d'origine, la Production "
                "comprise (sauf `--environment` autre que production)")
    if sous in VERCEL_AUTRES:
        return None
    if "--prod" in options:
        return "`vercel --prod` publie en Production"
    if vers == "production":
        return "`vercel --environment production` publie en Production"
    return None


def pousse_vers_la_production(cmd, base, branches, commandes=()):
    """La raison si la ligne fait avancer une branche de production, ou publie
    par une commande déclarée, sinon None. Lit TOUTES les commandes de la
    ligne : `echo x && git push origin main` ne passe pas parce que `echo`
    vient d'abord."""
    jetons = _jetons(cmd)
    alt = "|".join(re.escape(b) for b in sorted(branches))
    point = re.compile(r"/merges\b|git/refs/heads/(?:%s)\b|branches/(?:%s)/protection|"
                       r"/(?:%s)/merge-upstream" % (alt, alt, alt))
    # Sans branche déclarée, git et gh ne sont pas regardés (`--all` ne fermerait rien).
    progs = ({"git", "gh"} if branches else set()) | ({"vercel", "vc"} if "vercel" in commandes else set())
    cwd, i = base, 0
    while i < len(jetons):
        t = jetons[i]
        if t in ("cd", "pushd") and i + 1 < len(jetons) and not jetons[i + 1].startswith("-"):
            cwd = _resoudre(cwd, jetons[i + 1])
            i += 2
            continue
        fin = i + 1
        while fin < len(jetons) and jetons[fin] not in FINS:
            fin += 1
        # Le programme peut ne pas venir en tête : `env X=1 git push`, `npx vercel --prod`.
        tete = i
        while tete < fin and _programme(jetons[tete]) not in progs:
            tete += 1
        prog = _programme(jetons[tete]) if tete < fin else ""
        i = tete
        if prog in ("vercel", "vc"):
            raison = _analyse_vercel(jetons[i + 1:fin])
            if raison:
                return raison
        elif prog == "git":
            dossier, k, verbe = cwd, i + 1, None
            while k < fin:
                u = jetons[k]
                if u == "-C" and k + 1 < fin:
                    dossier = _resoudre(dossier, jetons[k + 1])
                    k += 2
                    continue
                if u.startswith("-"):
                    k += 2 if u in PORTEUSES else 1
                    continue
                verbe = u
                break
            if verbe == "push":
                raison = _analyse_push(jetons[k + 1:fin], dossier, branches)
                if raison:
                    return raison
        elif prog == "gh":
            mots = jetons[i + 1:fin]
            reste = " ".join(mots)
            if mots[:2] == ["pr", "merge"]:
                return "`gh pr merge` fusionne une branche sans dire laquelle reçoit"
            if mots[:1] == ["api"] and point.search(reste) and ECRIT_GITHUB.search(" " + reste + " "):
                return "`gh api` en écriture sur une branche de production"
        i = fin + 1 if fin < len(jetons) else fin
    if branches and "api.github.com" in cmd and point.search(cmd) and ECRIT_GITHUB.search(" " + cmd + " "):
        return "l'API GitHub en écriture sur une branche de production"
    return None


# ── le hook ──────────────────────────────────────────────────────────────

def juge(d):
    """Le motif du refus (`str`), ou None pour laisser passer."""
    if not isinstance(d, dict) or d.get("tool_name") not in ("Bash", "PowerShell"):
        return None
    ti = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
    cmd = ti.get("command")
    if not isinstance(cmd, str):
        return None
    if d.get("tool_name") == "PowerShell":
        # La barre oblique inverse y sépare des dossiers, elle n'échappe rien (0.19.7 :
        # sans ce garde, l'outil PowerShell contournait toute la Production sous Windows).
        cmd = cmd.replace("\\", "/")
    base = d.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    depart = os.environ.get("CLAUDE_PROJECT_DIR") or base
    r = reglage(depart)
    if r is None:
        return None
    projet, branches, nomme, duree, commandes = r
    raison = pousse_vers_la_production(cmd, base, branches, commandes)
    if raison is None:
        return None
    qui = agent_appelant(depart)
    if nomme and qui.lower() != nomme.lower():
        return ("production : %s.\n\nLa Production n'est poussée que par %s, sur demande "
                "explicite de l'humain. Pas de laissez-passer pour toi : travaille hors Production "
                "(ta branche, un déploiement de prévisualisation), et dis à %s ce qui doit partir."
                % (raison, nomme, nomme))
    motif = valide(projet, duree)
    if motif is None:
        return ("production : %s.\n\nIl faut le oui de l'humain AU MOMENT du geste, puis un "
                "laissez-passer : `harnais laissez-passer \"<son oui, cité>\"` (valable %d min, "
                "chaque usage journalisé)." % (raison, duree))
    journalise(projet, "%s\tusage\t%s\t%s" % (qui or "?", motif, cmd))
    return None


def main(entree):
    bas = entree.lower()
    if not any(m in bas for m in ("push", "merge", "api", "vercel", "vc")):
        return
    import json
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


def laissez_passer(args):
    """`harnais laissez-passer "motif"` : seul l'agent nommé l'obtient."""
    depart = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    r = reglage(depart)
    if r is None:
        sys.stderr.write("laissez-passer : ce projet ne ferme rien (ni `production:` ni "
                         "`production-commandes:` dans l'en-tête de ses règles) — rien à ouvrir.\n")
        return 1
    projet, branches, nomme, duree, commandes = r
    qui = agent_appelant(depart)
    if nomme and qui.lower() != nomme.lower():
        sys.stderr.write("laissez-passer : réservé à %s ; tu es « %s ».\n" % (nomme, qui or "?"))
        journalise(projet, "%s\tREFUSÉ\t%s" % (qui or "?", " ".join(args)))
        return 1
    motif = " ".join(a for a in args if a).strip()
    if not motif:
        sys.stderr.write("laissez-passer : cite le oui de l'humain, entre guillemets.\n")
        return 2
    f, log = _fichiers(projet)
    with open(f, "w", encoding="utf-8") as h:
        h.write(motif + "\n")
    journalise(projet, "%s\tdéposé\t%s" % (qui or "?", motif))
    portee = ["branches " + ", ".join(sorted(branches))] if branches else []
    portee += ["commandes " + ", ".join(sorted(commandes))] if commandes else []
    sys.stdout.write("Laissez-passer posé pour %s : %d min, %s. Journal : %s\n"
                     % (qui or "ce projet", duree, " ; ".join(portee), log))
    return 0
