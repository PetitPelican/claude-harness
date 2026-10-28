# -*- coding: utf-8 -*-
"""PASSER UN PROJET EN ÉQUIPE — ou lui ajouter un agent.

Port de `harnais/src/equipe.rs` (Rust, 0.12.8) ; le Rust gagne. (Le Rust avait
été porté de `agentic-agents.py` le 11/09/2026 : le script n'existait qu'en
Python, donc échouait en silence sur un Windows sans interpréteur. Il rend à
l'octet ce qu'il rendait sur les projets fabriqués de `controles/equipe.sh`.)

UNE SEULE COMMANDE, DEUX COMPORTEMENTS, ET C'EST LA FORME DU PROJET QUI
DÉCIDE. Sur un projet mono elle convertit et crée les premiers agents ; sur
un projet déjà multi elle en ajoute un.

    en `brain/`      brain/mind/{state,todo}.md -> brain/mind/<premier>/
                     brain/fact/roles.md, carnet dans brain/workspace/
    à l'ancienne     .mind/                     -> agents/<premier>/.mind/
                     .fact/roles.md, carnet dans equipe/
    dans les deux    .claude/settings.json      -> agents/<premier>/.claude/
                     ~/.claude/projects/<slug>/ -> slug du dossier d'agent
                     agents/<autres>/           -> CLAUDE.md de rôle + réglages

CE QU'ELLE NE FAIT PAS : découper le `CLAUDE.md` (éditorial), supprimer
l'ancienne mémoire auto (elle la marque `.migre-<date>`), toucher aux faits,
aux traces ni au code.

LE PIÈGE QU'ELLE EXISTE POUR ÉVITER. La mémoire auto d'un agent est classée
par CHEMIN. Convertir déplace le dossier de travail de `<projet>/` vers
`<projet>/agents/<nom>/` : sans migration, l'agent repart sur une adresse
neuve et vide, et `--resume` ne retrouve plus rien.

**À blanc par défaut.** `--apply` (ou `--go`) pour écrire.

DIVERGENCE CONNUE avec le Rust : le gabarit des rôles ne voyage plus DANS le
programme (`include_str!`) ; il se lit à l'appel dans
`skills/agentic-agents/templates/roles.md` du paquet, à côté de `py/`.
"""
import os
import shutil
import subprocess
import sys

CATALOGUE = "atelier"
PAQUET = "harnais"
DEPOT = "PetitPelican/claude-harness"
ROLE = """# {} — rôle

> Le `CLAUDE.md` du projet est **hérité** : il est chargé en même temps que
> celui-ci, à chaque démarrage. N'y recopier AUCUNE de ses phrases. Le test :
> si une phrase resterait vraie pour un autre agent du projet, elle est à
> l'étage au-dessus.

## Ce que cet agent tient

[LE_PÉRIMÈTRE — en dossiers, pas en intentions. « orienté produit » n'empêche
personne de toucher au backend ; la frontière qui tient est celle écrite en
`deny` dans `.claude/settings.json`, à côté.]

## Ce qu'il ne touche pas

[LES_AUTRES_LOTS — et qui les tient.]
"""


def _gabarit_roles():
    ici = os.path.dirname(os.path.abspath(__file__))
    chemin = os.path.join(os.path.dirname(ici), "skills", "agentic-agents", "templates", "roles.md")
    with open(chemin, encoding="utf-8", newline="") as f:
        return f.read()


# LES RÔLES TYPES (14/10/2026). Décision : ce qui a été éprouvé doit pouvoir
# se redéployer sur une autre équipe multi-agents. L'organisation
# éprouvée — OPS seul en Production, PO au produit, QA au contrôle et
# guichet unique des questions, NXT aux versions à venir — devient un gabarit :
# `--modeles ops,po,qa` aligné sur `--agents`. Rien d'un projet réel n'y est écrit.
MODELES = ("ops", "po", "qa", "nxt")
_TYPES = {}      # nom d'agent -> modèle, posé par main()


def _gabarit(*morceaux):
    ici = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(os.path.dirname(ici), "skills", "agentic-agents", "templates", *morceaux),
              encoding="utf-8", newline="") as f:
        return f.read()


def _qui(modele, defaut):
    for n, m in _TYPES.items():
        if m == modele:
            return n
    return defaut


def _remplit(texte, nom_agent, projet):
    agents = ", ".join("%s (%s)" % (n, m.upper()) for n, m in _TYPES.items()) or "[LES_AGENTS]"
    for k, v in (("{AGENT}", nom_agent), ("{PROJET}", projet or "[PROJET]"), ("{AGENTS}", agents),
                 ("{PROD}", _qui("ops", "l'agent OPS")), ("{GUICHET}", _qui("qa", "l'agent QA"))):
        texte = texte.replace(k, v)
    return texte


def role(nom, projet=""):
    m = _TYPES.get(nom)
    if m:
        return _remplit(_gabarit("roles", m + ".md"), nom, projet)
    return ROLE.replace("{}", nom, 1)


def consignes_equipe(projet):
    """Le CLAUDE.md commun d'une équipe typée : posé seulement s'il n'y en a pas."""
    return _remplit(_gabarit("equipe-CLAUDE.md"), "", projet)


def _p(s=""):
    sys.stdout.write(s + "\n")


def _panique(msg):
    """Là où le Rust panique (code 101), le Python sort en 101 de même."""
    sys.stdout.flush()
    sys.stderr.write("thread 'main' panicked: %s\n" % msg)
    sys.exit(101)


def maison():
    h = os.environ.get("HOME")
    if h is None:
        h = os.environ.get("USERPROFILE")
    return h if h is not None else ""


def slug(p):
    """La clé de `~/.claude/projects/` — celle de `socle.cle_memoire`, APPELÉE.

    Ce module en tenait sa propre copie, qui fondait les suites de caractères en
    un seul tiret : `/Agentic/.worktrees` y rendait `-Agentic-worktrees` au lieu
    de `-Agentic--worktrees`. Trouvé le 14/10/2026 par le premier passage à blanc
    de `demenage` sur une équipe réelle : « aucune conversation » pour trois agents qui en
    ont des centaines de Mo. La règle juste existait déjà, à portée d'appel."""
    import socle
    return socle.cle_memoire(p)


def git(p, a):
    import subprocess
    try:
        r = subprocess.run(["git", "-C", p] + list(a), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        return False
    return r.returncode == 0


# ── chemins : la sémantique de `std::path` ──────────────────────────────────

def _composants(p):
    """(racine, composants) — la racine est "" (relatif), "/" ou, sous Windows,
    le lecteur ("C:/"). Sous Windows `\\` vaut `/` : sans cela un chemin entier
    n'est qu'UN composant, et rien n'est jamais « sous » le dossier personnel —
    le périmètre d'un agent s'écrivait `Edit(/C:\\…)` et ne mordait pas (0.19,
    même défaut que ménage et migration, cdafcc2 côté Copilot)."""
    if os.name == "nt":
        p = p.replace("\\", "/")
        if p.startswith("//?/"):
            p = p[4:]
        if len(p) >= 2 and p[1] == ":" and p[0].isalpha():
            return p[0].upper() + ":/", [c for c in p[2:].split("/") if c not in ("", ".")]
    return ("/" if p.startswith("/") else ""), [c for c in p.split("/") if c not in ("", ".")]


def strip_prefix(p, base):
    """`Path::strip_prefix` : le reste (en `/`), ou None. Comparaison par COMPOSANTS."""
    rp, cp = _composants(p)
    rb, cb = _composants(base)
    if rp != rb or cp[:len(cb)] != cb:
        return None
    return "/".join(cp[len(cb):])


def file_name(p):
    _, c = _composants(p)
    if not c or c[-1] == "..":
        return None
    return c[-1]


def extension(nom):
    """`Path::extension` d'un nom de fichier."""
    i = nom.rfind(".")
    if i <= 0 or nom == "..":
        return None
    return nom[i + 1:]


def canonicalize(p):
    if not os.path.exists(p):
        return None
    try:
        return os.path.realpath(p)
    except OSError:
        return None


def rel(racine, p):
    r = strip_prefix(p, racine)
    if r is not None:
        return r
    # `components()` d'un chemin absolu porte aussi la racine `/` : elle se joint
    # comme un composant (d'où `//a/b`), exactement ce que fait le Rust.
    rp, cp = _composants(p)
    return rp + "/".join(cp)


class Disposition(object):
    """OÙ VIVENT LES FAITS ET LES ESPRITS — la seule chose qui change entre les
    deux organisations. En `brain/`, l'esprit d'un agent vit dans le CERVEAU,
    rangé par nom : `agents/<nom>/` ne porte plus que le rôle et les réglages."""

    def __init__(self, racine, cerveau, faits):
        self.racine = racine
        self.cerveau = cerveau
        self.faits = faits

    def esprit(self, nom):
        if self.cerveau:
            return os.path.join(self.racine, "brain/mind", nom)
        return os.path.join(self.racine, "agents", nom, ".mind")

    def esprit_mono(self):
        return os.path.join(self.racine, "brain/mind" if self.cerveau else ".mind")

    def etiquette_faits(self):
        return "brain/fact" if self.cerveau else ".fact"

    def rel(self, p):
        return rel(self.racine, p)


def trie(d):
    try:
        return [os.path.join(d, n) for n in sorted(os.listdir(d))]
    except OSError:
        return []


def nom(p):
    n = file_name(p)
    return n if n is not None else ""


def forme(p):
    """La forme du projet. MULTI se reconnaît à un esprit PAR AGENT, et l'endroit
    où le chercher dépend de l'organisation — chercher au seul ancien endroit
    déclarait « mono » un projet `brain/` déjà converti."""
    j = os.path.join
    cerveau = os.path.isdir(j(p, "brain/fact"))
    disp = Disposition(p, cerveau, j(p, "brain/fact" if cerveau else ".fact"))
    if cerveau:
        etats = [nom(d) for d in trie(j(p, "brain/mind"))
                 if os.path.isdir(d) and os.path.isfile(j(d, "state.md"))]
    else:
        etats = [nom(d) for d in trie(j(p, "agents")) if os.path.isdir(j(d, ".mind"))]
    if etats:
        return "multi", etats, disp
    if cerveau or os.path.isdir(j(p, ".fact")):
        return "mono", [], disp
    return "ancienne", [], disp


def json_indent2(v):
    """Le JSON tel que `json.dumps(indent=2, ensure_ascii=False)` l'écrit."""
    import json
    return json.dumps(v, indent=2, ensure_ascii=False)


def _lit_objet(chemin):
    import json
    try:
        with open(chemin, encoding="utf-8", newline="") as h:
            v = json.loads(h.read(), parse_constant=_refuse_constante)
    except (OSError, ValueError, RecursionError):
        return {}
    return v if isinstance(v, dict) else {}


def _refuse_constante(c):
    raise ValueError(c)


def reglages_agent(sources, cible, projet, autres, appliquer, rap):
    """Les réglages d'un agent, SOUS LE PAQUET. Les hooks viennent du paquet : on
    RETIRE les déclarations à la main — deux jeux de hooks sur le même
    événement, ce sont deux briefings et personne ne voit lequel a parlé. Il ne
    reste que QUEL PAQUET, et CE QUE CET AGENT N'A PAS LE DROIT DE TOUCHER — en
    `deny` ANCRÉ SUR LE HOME : un motif relatif ne mord pas (mesuré le 04/09)."""
    src = next((s for s in sources if os.path.isfile(s)), None)
    d = _lit_objet(src) if src is not None else {}
    retirees = 0
    if "hooks" in d:
        h = d.pop("hooks")
        if isinstance(h, dict):
            for bl in h.values():
                if isinstance(bl, list):
                    for b in bl:
                        x = b.get("hooks") if isinstance(b, dict) else None
                        retirees += len(x) if isinstance(x, list) else 0

    mk = d.setdefault("extraKnownMarketplaces", {})
    if isinstance(mk, dict):
        mk[CATALOGUE] = {"source": {"source": "github", "repo": DEPOT}}
    ep = d.setdefault("enabledPlugins", {})
    if isinstance(ep, dict):
        ep["%s@%s" % (PAQUET, CATALOGUE)] = True

    perm = d.setdefault("permissions", {})
    if isinstance(perm, dict):
        ancien = perm.get("deny")
        deny = list(ancien) if isinstance(ancien, list) else []
        deny = [x for x in deny if not (isinstance(x, str) and "/agents/" in x)]
        # Ancré sur le home QUAND le projet y est : un `~/` collé devant un
        # chemin absolu ne matche rien, et ne dit pas qu'il ne matche rien.
        h = maison()
        r = strip_prefix(projet, h) if h else None
        ancre = "~/" + r if r is not None else projet
        for a in autres:
            deny.append("Edit(%s/agents/%s/**)" % (ancre, a))
        perm["deny"] = deny
    rap.append(("+", "%s — paquet %s@%s déclaré, %d deny de périmètre%s" % (
        rel(projet, cible), PAQUET, CATALOGUE, len(autres),
        (", %d hooks à la main retirés" % retirees) if retirees > 0 else "")))
    if appliquer:
        try:
            os.makedirs(os.path.dirname(cible), exist_ok=True)
        except OSError:
            pass
        try:
            with open(cible, "w", encoding="utf-8", newline="") as f:
                f.write(json_indent2(d) + "\n")
        except OSError:
            pass


def porte_les_non_herites(projet, cible, appliquer, rap):
    """`.mcp.json` et `settings.local.json` ne remontent PAS depuis un dossier
    d'agent — mesuré le 04/09 : un agent démarré dans `agents/<nom>/` ne voyait
    aucun serveur MCP du projet. On copie, on ne déplace pas."""
    for r in (".mcp.json", ".claude/settings.local.json"):
        src = os.path.join(projet, r)
        if not os.path.isfile(src):
            continue
        rap.append(("+", "%s/%s — copié depuis la racine (ne s'hérite pas)" % (rel(projet, cible), r)))
        if appliquer:
            import shutil
            dst = os.path.join(cible, r)
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
            except OSError:
                pass
            try:
                shutil.copy(src, dst)
            except (OSError, shutil.Error):
                pass


def copie_arbre(src, dst):
    """Lève OSError au premier échec, comme le `?` du Rust."""
    import shutil
    os.makedirs(dst, exist_ok=True)
    with os.scandir(src) as it:
        entrees = list(it)
    for e in entrees:
        s, d = e.path, os.path.join(dst, e.name)
        if e.is_dir(follow_symlinks=False):
            copie_arbre(s, d)
        else:
            shutil.copy(s, d)


def migre_memoire_auto(ancien, neuf, appliquer, rap):
    # DANS UN DÉPÔT, L'ADRESSE NE CHANGE PAS : Claude Code range la mémoire à
    # la racine du dépôt, et `agents/<nom>/` reste dans le même. Déplacer ici,
    # c'est ce qui a coupé une équipe en deux le 04/09/2026 — la mémoire partie
    # chez un agent que Claude Code ne lit jamais là, un carnet neuf recommencé
    # à la racine (`socle::dossier_de_la_memoire`).
    import memoire
    if memoire.racine_depot(ancien) is not None:
        rap.append(("·", "mémoire auto : même dépôt, même adresse — rien à migrer"))
        return
    base = os.path.join(maison(), ".claude/projects")
    src = os.path.join(base, slug(ancien))
    dst = os.path.join(base, slug(neuf))
    if not os.path.isdir(src):
        rap.append(("·", "aucune mémoire auto à migrer (%s absent)" % nom(src)))
        return
    if os.path.exists(dst):
        rap.append(("⚠", "%s existe déjà — mémoire auto NON migrée, à fusionner" % nom(dst)))
        return
    n = len([p for p in trie(src) if os.path.isfile(p) and extension(nom(p)) == "jsonl"])
    m = len([p for p in trie(os.path.join(src, "memory")) if extension(nom(p)) == "md"])
    import datetime
    jour = datetime.datetime.now().strftime("%Y%m%d")
    rap.append(("→", "mémoire auto : %s -> %s (%d fils, %d mémoires) ; l'ancien sera marqué .migre-%s" % (
        nom(src), nom(dst), n, m, jour)))
    if appliquer:
        try:
            copie_arbre(src, dst)
        except OSError:
            return
        try:
            os.rename(src, os.path.join(os.path.dirname(src), "%s.migre-%s" % (nom(src), jour)))
        except OSError:
            pass


def valeur(args, cle):
    it = iter(args)
    for a in it:
        if a == cle:
            return next(it, None)
        if a.startswith(cle + "="):
            return a[len(cle) + 1:]
    return None


def _ecrit(chemin, texte):
    try:
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            f.write(texte)
    except OSError:
        pass


def _mkdirs(d):
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass


# LA COPIE ISOLÉE DE CLAUDE CODE SE FAIT SUR LE DÉPÔT DE DÉMARRAGE — ici la
# MÉMOIRE. Mesuré au banc le 14/10/2026 (le point 4 de QA) : un sous-agent
# `isolation: worktree` lancé depuis `agents/<nom>/` reçoit une copie de la
# mémoire, sans le code. Ces règles le refusent (refus mesuré) ; une copie de
# plus se fait par `git -C code worktree add ../code-<sujet>`.
SANS_COPIE_ISOLEE = ("Agent(isolation:worktree)", "EnterWorktree")

# LE PÉRIMÈTRE TYPE D'UN AGENT DEV (27/10/2026), celui d'une équipe éprouvée : il
# lit tout et agit sans demander ; il n'écrit que son lot (les `deny`). Demande
# de l'humain : plus jamais « je n'ai pas accès ». La maison entière en
# `additionalDirectories` n'est PAS posée : mesuré le 27/10 (Claude Code
# 2.1.311), un fichier hors de l'arbre se lit en `bypassPermissions` sans elle,
# et avec `Read(*)` seul en mode par défaut ; témoin : sans l'un ni l'autre, refusé.
MODE_DEV = "bypassPermissions"
PERMIS_DEV = ("Bash(*)", "Read(*)")


def _perimetre(x, nom, *sous):
    """La règle `deny` qui ferme le dossier d'un agent aux autres — ancrée sur le
    home quand elle peut l'être, la seule forme qui mord (consigne de l'atelier)."""
    d = os.path.join(x, "agents", nom, *sous)
    h = maison()
    r = None
    # Le home tel qu'écrit ET tel qu'il est vraiment (nom court 8.3 sous Windows).
    for hh in ([h, os.path.realpath(h)] if h else []):
        r = r or strip_prefix(d, hh)
    # Hors du home, un chemin absolu s'écrit `//` : avec UN seul `/`, Claude Code
    # le lit RELATIF AU FICHIER DE RÉGLAGES, et la règle ne mord jamais (mesuré au
    # banc le 14/10/2026 : une écriture chez un autre agent est passée).
    if r:
        return "Edit(~/%s/**)" % r
    if os.name == "nt":
        # Claude Code lit un chemin Windows sous sa forme POSIX : `C:\\x` → `//c/x`.
        rp, cp = _composants(d)
        if rp.endswith(":/"):
            return "Edit(//%s/%s/**)" % (rp[0].lower(), "/".join(cp))
    return "Edit(/%s/**)" % d


def equipe_v3(x, noms, retirer, appliquer, naissance=False):
    """FORME « UN DOSSIER PAR AGENT » (14/10/2026) : ajouter ou retirer un agent en
    UNE commande — son dossier, son badge, son état, SA copie du code. C'est ce qui
    empêche les copies de se poser ailleurs : le bon geste est le plus court.

    Le périmètre des autres reçoit UNE ligne (`deny` sur le nouveau dossier) :
    sans elle, un agent existant pourrait écrire chez le nouveau, et rien ne le
    dirait. C'est la seule écriture hors du dossier ajouté."""
    import json
    import adopte
    j = os.path.join
    rap, reste = [], []
    agents = j(x, "agents")
    existants = [nom(d) for d in trie(agents) if os.path.isdir(d)]
    codes = [j(agents, n, "code") for n in existants if os.path.isdir(j(agents, n, "code"))]
    jour = __import__("datetime").date.today().isoformat()
    for n in retirer:
        d = j(agents, n)
        if not os.path.isdir(d):
            rap.append(("✗", "%s : pas d'agent à ce nom" % n))
            continue
        sales = []
        for c in [j(d, e) for e in os.listdir(d) if e == "code" or e.startswith("code-")]:
            o = subprocess.run(["git", "status", "--porcelain"], cwd=c, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
            if o.returncode != 0 or o.stdout.strip():
                sales.append(nom(c))
        if sales:
            rap.append(("✗", "%s : travail non enregistré dans %s — RIEN n'est retiré" % (n, ", ".join(sales))))
            continue
        rap.append(("→", "%s : copies du code retirées (git worktree remove), dossier retiré ; son "
                         "état reste dans l'historique de la mémoire" % n))
        reste.append("retirer l'inscription au paquet de `%s`, et sa ligne des faits `roles.md`" % d)
        if appliquer:
            for c in [j(d, e) for e in os.listdir(d) if e == "code" or e.startswith("code-")]:
                subprocess.run(["git", "worktree", "remove", c], cwd=c, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
            subprocess.run(["git", "rm", "-r", "-q", "--", os.path.relpath(d, x)], cwd=x,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            shutil.rmtree(d, ignore_errors=True)
    for n in noms:
        d = j(agents, n)
        if os.path.exists(d):
            rap.append(("·", "%s : existe déjà, rien n'est touché" % n))
            continue
        rap.append(("→", "agents/%s/ : rôle%s, état, tâches, badge (paquet déclaré, lit tout et agit sans "
                         "demander, périmètre fermé%s)" % (
                             n, (" type %s" % _TYPES[n].upper()) if n in _TYPES else "",
                             " — code fermé : il prescrit" if _TYPES.get(n) == "qa" else "")))
        autres = [e for e in existants if e != n]
        if codes:
            rap.append(("→", "agents/%s/code : sa copie du code, branche `%s`" % (n, slug(n).strip("-").lower())))
        elif not naissance:
            reste.append("aucune copie du code chez les autres agents : poser `agents/%s/code` à la main" % n)
        if autres:
            rap.append(("→", "périmètre : une ligne `deny` vers agents/%s/ chez %s" % (n, ", ".join(autres))))
        reste.append("inscrire le paquet dans `%s` : `claude plugin install harnais@atelier --scope project`" % d)
        reste.append("décrire %s dans `fact/roles.md` (faits : à la demande de l'humain)" % n)
        if not appliquer:
            continue
        _mkdirs(j(d, ".claude"))
        _ecrit(j(d, "CLAUDE.md"), role(n, nom(x)) if n in _TYPES else adopte.claude_md_agent(n, nom(x)))
        _ecrit(j(d, "state.md"), adopte.state_md(jour))
        _ecrit(j(d, "todo.md"), adopte.TODO_MD)
        texte, _ = adopte.reglages(j(d, ".claude", "settings.json"))
        v = json.loads(texte)
        v.setdefault("permissions", {}).setdefault("defaultMode", MODE_DEV)
        allow = v["permissions"].setdefault("allow", [])
        for r in PERMIS_DEV:
            if r not in allow:
                allow.append(r)
        deny = v["permissions"].setdefault("deny", [])
        fermes = [_perimetre(x, a) for a in autres] + list(SANS_COPIE_ISOLEE)
        # QA à l'envers : il prescrit, il ne corrige pas (son rôle type) — sa
        # copie du code lui est fermée ; son dossier et `docs/` restent ouverts.
        if _TYPES.get(n) == "qa":
            fermes.append(_perimetre(x, n, "code"))
        for r in fermes:
            if r not in deny:
                deny.append(r)
        # L'agent démarre dans `agents/<nom>/` : sans ceci, les faits, `docs/`,
        # `shared/` et `assets/` de l'équipe sont HORS de son espace de travail
        # (posé à la main dans chaque badge, avant).
        ad = v["permissions"].setdefault("additionalDirectories", [])
        if x not in ad:
            ad.append(x)
        _ecrit(j(d, ".claude", "settings.json"), json.dumps(v, indent=2, ensure_ascii=False) + "\n")
        for a in autres:
            f = j(agents, a, ".claude", "settings.json")
            if not os.path.isfile(f):
                reste.append("périmètre de %s : aucun réglage, ligne non ajoutée" % a)
                continue
            w = _lit_objet(f)
            dl = w.setdefault("permissions", {}).setdefault("deny", [])
            r = _perimetre(x, n)
            if r not in dl:
                dl.append(r)
                _ecrit(f, json.dumps(w, indent=2, ensure_ascii=False) + "\n")
        if codes:
            o = subprocess.run(["git", "worktree", "add", "-q", "-b", slug(n).strip("-").lower(), j(d, "code")],
                               cwd=codes[0], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if o.returncode != 0:
                reste.append("copie du code de %s non posée : %s" % (n, o.stderr.decode("utf-8", "replace").strip()[:200]))
        existants.append(n)
    if _TYPES:
        if os.path.exists(j(x, "CLAUDE.md")):
            reste.append("règles communes d'équipe (autonomie git, guichet {g}, Production à {o}) : le "
                         "CLAUDE.md du projet existe, le CTO y reporte le gabarit "
                         "`skills/agentic-agents/templates/equipe-CLAUDE.md`".format(
                             g=_qui("qa", "QA"), o=_qui("ops", "OPS")))
        else:
            rap.append(("→", "CLAUDE.md du projet : règles communes d'équipe (gabarit du paquet)"))
            if appliquer:
                _ecrit(j(x, "CLAUDE.md"), consignes_equipe(nom(x)))
    _p("\n  ÉQUIPE — un dossier par agent   %s" % x)
    for sg, l in rap:
        _p("  %s %s" % (sg, l))
    if reste:
        _p("\n  RESTE À FAIRE")
        for l in reste:
            _p("  - %s" % l)
    if not appliquer:
        _p("\n  À blanc : rien n'est écrit. `--apply` pour le faire.")
    return 1 if any(sg == "✗" for sg, _ in rap) else 0


# ── NAÎTRE EN ÉQUIPE (0.19, 16/10/2026) ──────────────────────────────────
#
# Décision : le harnais doit servir à bien déployer cette nouvelle
# architecture. Jusqu'ici une équipe neuve naissait dans la forme d'AVANT
# (`adopte --equipe` : `brain/mind/<nom>/`, des badges sans copie du code), et
# `demenage` refusait de la porter plus loin (mesuré le 16/10). Elle naît
# désormais dans la forme d'aujourd'hui, celle d'aujourd'hui, détaillée ici :
#
#     X/                  dépôt de la MÉMOIRE
#       CLAUDE.md         les règles communes de l'équipe (étage 3)
#       fact/ shared/ docs/ assets/
#       agents/<nom>/     rôle · droits · état · tâches · code/
#
# Le code : `--code SRC` le clone chez le premier agent ; sans lui, un dépôt
# neuf. Les autres reçoivent une copie git (`worktree`) du même dépôt.

GITIGNORE_EQUIPE = (
    "# un dossier par agent : chaque copie du code a son propre dépôt\n"
    "agents/*/code*/\n"
    "**/.claude/settings.local.json\n"
    "**/.claude/.briefing.json\n"
    "**/.claude/.briefing.lock\n"
    ".env\n.env.*\n"
    "operations.md\n"
    "# accès des connexions (MCP) : jamais sur GitHub\n"
    ".mcp.json\n")

CLAUDE_PROJET = """# {PROJET}

<!-- Étage 3 sur 4 : ce qui vaut pour tous les agents de ce projet, et rien que
     ce que les consignes communes ne disent pas. Posé « À REMPLIR » par le
     harnais ; seul le CTO le modifie. -->

À REMPLIR — une phrase sur le produit, et pour qui.

## Règles

À REMPLIR — ce qui vaut pour tout agent de ce projet : branches, Production,
contrôles avant d'envoyer. Une règle par ligne, et ce qu'elle protège.
"""

CARNET_LISEZMOI = """# Le carnet d'équipe

Chaque agent travaille sur SA copie du code : ce qu'il change chez un autre ne
se voit pas tant qu'il ne le dit pas. Pour le dire, sous une tâche que tu coches
dans ton `todo.md`, une ligne :

    ↗ <agent> : <ce que tu as changé chez lui, et où>

Le harnais la range ici et la sert au briefing de l'agent visé jusqu'à ce qu'il
l'acquitte. Le reste de ce dossier : ce que plusieurs agents lisent et écrivent ;
le daté va dans `docs/`, les livrables dans `assets/`.
"""

DECISIONS = "# Décisions\n\nLe pourquoi de chaque choix, daté. Une entrée par décision.\n"


def _git_ok(cwd, *a):
    try:
        o = subprocess.run(["git"] + list(a), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        return False, str(e)
    return o.returncode == 0, o.stderr.decode("utf-8", "replace").strip()


def _regles(projet):
    """Les règles d'une équipe neuve. Avec un agent de type OPS, la Production est
    fermée d'office : c'est l'organisation voulue le
    14/10/2026 (`main` sur sa seule demande, OPS seul à pousser, laissez-passer)."""
    import adopte
    ops = [n for n, m in _TYPES.items() if m == "ops"]
    if not ops:
        return adopte.rules_md(projet)
    return ("---\nproduction: main, master, production\nproduction-agent: %s\n"
            "production-duree: 15\n---\n\n" % ops[0]) + adopte.rules_md(projet)


def naissance(x, noms, code, appliquer):
    """Monte une équipe NEUVE dans `x`. Rend le code de sortie."""
    import adopte
    j = os.path.join
    if not noms:
        _p("harnais adopte --equipe : au moins un nom d'agent")
        return 2
    # 1. Le dossier doit être neuf : y naître par-dessus un code ou une mémoire,
    #    c'est mêler deux dépôts sans que rien ne le dise.
    if os.path.isdir(x):
        presents = [e for e in os.listdir(x) if e not in (".git", ".DS_Store")]
        suivis = subprocess.run(["git", "ls-files"], cwd=x, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE).stdout.strip() if os.path.isdir(j(x, ".git")) else b""
        if presents or suivis:
            _p("REFUS — une équipe naît dans un dossier VIDE : ce dossier porte déjà %s.\n"
               "  Son code ? Monter l'équipe dans un dossier neuf, avec `--code %s`.\n"
               "  Un projet seul qui passe à plusieurs : `harnais equipe --agents …`."
               % (", ".join(sorted(presents)[:5]) or "un dépôt git suivi", x))
            return 1
    vus = {}
    for n in noms:
        vus.setdefault(slug(n), []).append(n)
    collisions = [", ".join(v) for v in vus.values() if len(v) > 1]
    if collisions:
        _p("REFUS — ces noms donnent la même adresse de mémoire auto : %s. "
           "Ils partageraient une seule mémoire sans que rien ne le dise." % " / ".join(collisions))
        return 1
    projet = nom(x)
    import datetime
    jour = datetime.date.today().isoformat()
    poses = [(j(x, ".gitignore"), GITIGNORE_EQUIPE),
             (j(x, "fact", "base.md"), adopte.base_md(projet)),
             (j(x, "fact", "stack.md"), adopte.stack_md(projet)),
             (j(x, "fact", "architecture.md"), adopte.architecture_md(projet)),
             (j(x, "fact", "rules.md"), _regles(projet)),
             (j(x, "fact", "workflow.md"), adopte.workflow_md(projet)),
             (j(x, "fact", "roles.md"), adopte.roles_md(noms)),
             (j(x, "docs", "decisions.md"), DECISIONS),
             (j(x, "shared", "LISEZMOI.md"), CARNET_LISEZMOI),
             (j(x, "assets", "LISEZMOI.md"), "# Livrables\n\nLogos, maquettes, exports : un seul "
                                             "exemplaire, ici.\n")]
    if not _TYPES:
        poses.append((j(x, "CLAUDE.md"), CLAUDE_PROJET.replace("{PROJET}", projet)))
    _p("\n  NAISSANCE D'UNE ÉQUIPE — un dossier par agent   %s" % x)
    dossiers = set(os.path.relpath(f, x).split(os.sep)[0] for f, _ in poses) | {"shared"}
    _p("  → dépôt de la mémoire : %s" % ", ".join(sorted(dossiers)))
    _p("  → code : %s" % (("clone de %s chez %s" % (code, noms[0])) if code else
                          "dépôt neuf chez %s" % noms[0]) +
       (", copie git chez %s" % ", ".join(noms[1:]) if noms[1:] else ""))
    if appliquer:
        _mkdirs(x)
        ok, err = _git_ok(x, "init", "-q", "-b", "main")
        if not ok:
            _p("  ✗ git init de la mémoire : %s" % err)
            return 1
        for f, texte in poses:
            if not os.path.exists(f):
                _mkdirs(os.path.dirname(f))
                _ecrit(f, texte)
    # 2. Les agents : la commande qui en ajoute un, appelée une fois pour tous.
    rc = equipe_v3(x, noms, [], appliquer, naissance=True)
    if not appliquer:
        return rc
    # 3. Le code, une fois les dossiers posés.
    principal = j(x, "agents", noms[0], "code")
    if code:
        ok, err = _git_ok(x, "clone", "-q", code, principal)
    else:
        _mkdirs(principal)
        ok, err = _git_ok(principal, "init", "-q", "-b", "main")
        if ok:
            ok, err = _git_ok(principal, "-c", "user.name=harnais", "-c", "user.email=harnais@atelier",
                              "commit", "-q", "--allow-empty", "-m", "Départ de l'équipe")
    if not ok:
        _p("  ✗ code de %s non posé : %s" % (noms[0], err[:200]))
        return 1
    for n in noms[1:]:
        ok, err = _git_ok(principal, "worktree", "add", "-q", "-b", slug(n).strip("-").lower(),
                          j(x, "agents", n, "code"))
        if not ok:
            _p("  ✗ copie du code de %s non posée : %s" % (n, err[:200]))
            return 1
    _p("  ✓ code posé : %s" % ", ".join("agents/%s/code" % n for n in noms))
    # Le carnet d'équipe, dans `shared/` : la règle qui le place est dans `carnet`.
    import carnet
    e = carnet.amorce(j(x, "agents", noms[0]))
    _p("  %s carnet d'équipe : %s" % (("✓", rel(x, e)) if e else ("✗", "non amorcé")))
    _p("\n  ENSUITE : remplir le cap (`fact/base.md`), le rôle de chaque agent, puis enregistrer "
       "la mémoire (`git add -A && git commit`). Chaque agent démarre DANS `agents/<nom>/`.")
    return rc


def main(args):
    if any(a == "-h" or a == "--help" for a in args):
        _p("harnais equipe --agents A,B[,C] [--modeles ops,po,qa,nxt] [--project-root P] [--apply]\n\n"
           "Passe un projet mono en équipe (le PREMIER nommé hérite de l'état existant),\n"
           "ou ajoute des agents à un projet déjà en équipe. À blanc par défaut.\n"
           "--modeles : un rôle type par agent (OPS seul en Production, PO produit, QA contrôle\n"
           "et guichet unique des questions, NXT versions à venir) ; sur une équipe neuve, le\n"
           "CLAUDE.md du projet reçoit aussi les règles communes s'il n'existe pas.")
        return 0
    liste = valeur(args, "--agents")
    if liste is None and valeur(args, "--retire") is not None:
        liste = ""
    if liste is None:
        sys.stderr.write("harnais equipe : --agents est requis (noms séparés par des virgules ; "
                         "le PREMIER hérite de l'état existant)\n")
        return 2
    appliquer = any(a == "--apply" or a == "--go" for a in args)
    p0 = valeur(args, "--project-root")
    if p0 is None:
        p0 = "."
    c = canonicalize(p0)
    p = c if c is not None else p0
    noms = [x.strip() for x in liste.split(",") if x.strip()]
    types = [t.strip().lower() for t in (valeur(args, "--modeles") or "").split(",") if t.strip()]
    if types:
        inconnus = [t for t in types if t not in MODELES]
        if inconnus or len(types) != len(noms):
            sys.stderr.write("harnais equipe : --modeles prend un modèle par agent, dans l'ordre de "
                             "--agents, parmi %s%s\n" % (", ".join(MODELES),
                                                        (" — inconnu : " + ", ".join(inconnus)) if inconnus else ""))
            return 2
    _TYPES.clear()
    _TYPES.update(zip(noms, types))
    import memoire
    if memoire.resous(p).forme == memoire.Forme.Equipe:
        x = memoire.resous(p).projet
        retirer = [r.strip() for r in (valeur(args, "--retire") or "").split(",") if r.strip()]
        return equipe_v3(x, noms, retirer, appliquer)
    rap = []     # [(signe, ligne)]
    reste = []

    j = os.path.join
    f, existants, disp = forme(p)
    if f == "ancienne":
        _p("Ce projet n'a de faits ni dans `brain/fact/` ni dans `.fact/`. "
           "Lancer d'abord la migration de mémoire, puis revenir.")
        return 1
    # Deux agents dont les noms se slugifient pareil partageraient une seule
    # mémoire auto, en silence. Irrattrapable une fois installé.
    vus = []     # [(slug, [noms])], dans l'ordre d'apparition
    for n in list(noms) + list(existants):
        s = slug(n)
        for k, v in vus:
            if k == s:
                v.append(n)
                break
        else:
            vus.append((s, [n]))
    collisions = [", ".join(v) for _, v in vus if len(v) > 1]
    if collisions:
        _p("REFUS — ces noms donnent la même adresse de mémoire auto : %s. "
           "Ils partageraient une seule mémoire sans que rien ne le dise." % " / ".join(collisions))
        return 1
    hook = j(p, ".claude/hooks/briefing.py")
    if os.path.isfile(hook):
        try:
            with open(hook, "rb") as h:
                contenu = h.read().decode("utf-8", "replace")
        except OSError:
            contenu = ""
        if "racines(" not in contenu:
            _p("REFUS — les hooks de ce projet sont d'avant le 04/09/2026 : le briefing ne fait "
               "qu'une remontée et ne verrait jamais les faits depuis un dossier d'agent. Retirer ces hooks locaux et déclarer "
               "le paquet d'abord : `harnais adopte --go`.")
            return 1

    if f == "mono":
        if not noms:
            _panique("index out of bounds: the len is 0 but the index is 0")
        premier = noms[0]
        cible = j(p, "agents", premier)
        src, dst = disp.esprit_mono(), disp.esprit(premier)
        # Cerveau : `brain/mind/` NE bouge PAS, ce sont ses FICHIERS qui
        # descendent d'un cran. Ancienne forme : le dossier descend en entier.
        rap.append(("→", "%s -> %s (l'agent qui était là garde sa mémoire)" % (disp.rel(src), disp.rel(dst))))
        if appliquer:
            if disp.cerveau:
                _mkdirs(dst)
                for fic in trie(src):
                    if os.path.isfile(fic):
                        cible_f = j(dst, nom(fic))
                        if not git(p, ["mv", disp.rel(fic), disp.rel(cible_f)]):
                            try:
                                os.rename(fic, cible_f)
                            except OSError:
                                pass
            else:
                _mkdirs(os.path.dirname(dst))
                if not git(p, ["mv", disp.rel(src), disp.rel(dst)]):
                    try:
                        os.rename(src, dst)
                    except OSError:
                        pass
        reglages_agent([j(p, ".claude/settings.json")], j(cible, ".claude/settings.json"),
                       p, noms[1:], appliquer, rap)
        if os.path.isfile(j(p, ".claude/settings.json")):
            rap.append(("−", ".claude/settings.json de la racine SUPPRIMÉ — il ne s'exécute plus "
                             "(les réglages ne s'héritent pas) et quelqu'un l'éditerait un jour en croyant agir sur tous"))
            if appliquer and not git(p, ["rm", "-q", ".claude/settings.json"]):
                try:
                    os.remove(j(p, ".claude/settings.json"))
                except OSError:
                    pass
        porte_les_non_herites(p, cible, appliquer, rap)
        migre_memoire_auto(p, cible, appliquer, rap)
        # Le premier agent hérite de l'état, pas d'un rôle : il lui faut le sien.
        rap.append(("+", "agents/%s/CLAUDE.md — rôle à remplir" % premier))
        if appliquer and not os.path.exists(j(cible, "CLAUDE.md")):
            _ecrit(j(cible, "CLAUDE.md"), role(premier, nom(p)))
        neufs = noms[1:]
        tous = list(noms)
        modeles = [j(p, ".claude/settings.agent.json.example"),
                   j(cible, ".claude/settings.json"), j(p, ".claude/settings.json")]
    else:
        neufs = list(noms)
        tous = list(existants) + list(noms)
        modeles = [j(p, ".claude/settings.agent.json.example")] + [
            j(p, "agents", e, ".claude/settings.json") for e in existants]

    import datetime
    jour = datetime.datetime.now().strftime("%Y-%m-%d")
    for n in neufs:
        d = j(p, "agents", n)
        esprit = disp.esprit(n)
        rap.append(("+", "agents/%s/ — CLAUDE.md de rôle, settings.json ; esprit neuf dans %s" % (n, disp.rel(esprit))))
        if appliquer:
            _mkdirs(esprit)
            _mkdirs(d)
            _ecrit(j(d, "CLAUDE.md"), role(n, nom(p)))
            _ecrit(j(esprit, "state.md"),
                   "---\nmaj: %s\nsante: vert\njalon: [LE_PROCHAIN_CAILLOU de ce lot]\n---\n\n# État — %s\n\n[où en est CET agent]\n" % (jour, n))
            _ecrit(j(esprit, "todo.md"), "# À faire — %s\n\n- [ ] [première tâche de ce lot]\n" % n)
        autres = [x for x in tous if x != n]
        reglages_agent(modeles, j(d, ".claude/settings.json"), p, autres, appliquer, rap)
        porte_les_non_herites(p, d, appliquer, rap)

    # LE CARNET D'ÉQUIPE — LU partout, CRÉÉ nulle part jusqu'au 10/09. On
    # appelle la règle qui le place, on ne la recopie pas.
    if appliquer:
        import carnet
        e = carnet.amorce(p)
        if e is not None:
            rap.append(("+", "carnet d'équipe amorcé : %s" % rel(p, e)))
        else:
            rap.append(("⚠", "carnet d'équipe NON amorcé : le programme n'a rien rendu"))
    else:
        rap.append(("+", "carnet d'équipe à amorcer (créé à l'application)"))

    # Le cinquième fichier, qui n'existe qu'en équipe : chacun connaît sa
    # frontière et ignore celle des autres — ici, chacun lit TOUT le découpage.
    fichier_roles = j(disp.faits, "roles.md")
    if os.path.isdir(disp.faits) and not os.path.exists(fichier_roles):
        rap.append(("+", "%s/roles.md — qui tient quoi, à remplir" % disp.etiquette_faits()))
        if appliquer:
            # La maison des faits est NOMMÉE, jamais écrite en dur : le gabarit
            # sert les deux organisations. Écrit `.fact/` jusqu'au 11/09/2026,
            # y compris dans un projet en `brain/` — le Python le posait ainsi.
            texte = _gabarit_roles().replace("[PROJECT_NAME]", nom(p)).replace("[FAITS]", disp.etiquette_faits())
            for i, n in enumerate(tous):
                texte = texte.replace("`<agent-%d>`" % (i + 1), "`%s`" % n)
            _ecrit(fichier_roles, texte)
        reste.append("REMPLIR %s/roles.md — qui tient quoi, et surtout LES ZONES PARTAGÉES. Un "
                     "périmètre propre se lit dans les deny ; une zone partagée ne se lit nulle part, et c'est là que les "
                     "collisions arrivent. Ce sont des FAITS : ça s'écrit à la demande du commanditaire (` # fact-ok` au commit)."
                     % disp.etiquette_faits())
    if _TYPES:
        reste.append("RÈGLES COMMUNES D'ÉQUIPE (autonomie git, guichet %s, Production à %s) : le CTO "
                     "reporte le gabarit `skills/agentic-agents/templates/equipe-CLAUDE.md` dans le "
                     "CLAUDE.md du projet" % (_qui("qa", "QA"), _qui("ops", "OPS")))
    reste.append("DÉCOUPER LE CLAUDE.md — la seule étape qui ne s'automatise pas. Le commun reste à la "
                 "racine, le rôle descend dans agents/<nom>/CLAUDE.md. Contrôle de sortie : aucune phrase du bas ne "
                 "resterait vraie pour un autre agent.")
    reste.append("ÉCRIRE LES PÉRIMÈTRES en dossiers dans chaque settings.json : les deny posés ne couvrent "
                 "que les dossiers d'agents. Le code, lui, n'est pas partagé au hasard — dire qui tient quoi.")
    reste.append("RELANCER LES SESSIONS tmux DANS les dossiers d'agents, sous des noms slugifiés "
                 "(%s). L'ancienne session à la racine n'a plus d'agent : le briefing l'avertira au lieu de se taire."
                 % ", ".join(slug(n).lower().strip("-") for n in tous))

    _p("── agents — %s (%s)%s" % (nom(p), f, "" if appliquer else "  [DRY-RUN]"))
    for signe, ligne in rap:
        _p("  %s %s" % (signe, ligne))
    _p("\n── À reprendre à la main")
    for r in reste:
        _p("  · %s" % r)
    if not appliquer:
        _p("\nDry-run. Relancer avec --apply pour écrire.")
    return 0
