"""CONTRÔLE DIFFÉRENTIEL — le briefing d'entrée, Python contre Rust.

Le plus gros porté jusqu'ici, et le seul qui INJECTE : une divergence ne se
verrait pas en refus mais en texte servi à l'agent, c'est-à-dire nulle part.
On compare donc le bloc entier, ligne à ligne.

DEUX TERRAINS. Le projet CTO **en place**, parce que c'est le seul endroit où
la mémoire auto existe vraiment (elle est indexée par le CHEMIN : une copie
n'en a pas). Et des bacs à sable pour les branches que le CTO ne porte pas —
multi-agents, mémoire déportée, carnet, racine sans agent, réglages illisibles.

CE QUI EST SAUVEGARDÉ ET RENDU entre les deux exécutions : `.usage.json`
(le Python y pose la date du ménage, le Rust ne verrait plus rien à faire),
`.briefing.json` et le verrou. Sans ça, le second passage compare une machine
que le premier a déjà changée.

FIGÉ LE 10/09/2026 (lot 0) dans `temoins/briefing.json`. Deux témoins, et ils
n'ont PAS la même valeur :

- `briefing.json`, **origine Python** : le bloc servi, index replié sur le nom
  de fichier — c'est la neutralisation expliquée plus bas, et elle survit au
  gel puisque Python restait faux sur ce point ;
- `briefing-chemins.json`, **origine RUST** : les chemins annoncés, figés le
  jour où la correction a été écrite. Ce n'est pas une preuve d'équivalence,
  c'est un cliché de référence — sans lui, plus AUCUN contrôle ne regarderait
  les chemins une fois Python parti, c'est-à-dire précisément l'endroit où
  Python avait tort.

LE CARNET EST FABRIQUÉ, plus copié d'un projet réel : figer le carnet d'un autre agent
dans ce dépôt-ci, ce serait recopier sa mémoire (règle 1), et le témoin
périmerait à sa ligne suivante.
"""
import re, json, os, shutil, subprocess, pathlib, sys, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import temoins

S = pathlib.Path(sys.argv[1])/"bf"
shutil.rmtree(S, ignore_errors=True); S.mkdir(parents=True)
PY = str(pathlib.Path.home()/".claude/hooks/briefing.py")
RS = os.environ.get("HARNAIS_BIN") or str(pathlib.Path.home()/"Agentic/claude-harnais/bin/harnais")
DATA = S/"plugindata"; (DATA/"attente").mkdir(parents=True)
AUJ = datetime.date.today().isoformat()

def ecrire(p, t):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t)


# ── LA SEULE DIVERGENCE ATTENDUE SUR L'INDEX DE FICHIERS ────────────────────
#
# Depuis le 10/09/2026 (audit P4), le Rust annonce dans son index des chemins
# OUVRABLES DEPUIS LE DOSSIER DE L'AGENT : relatifs quand le fichier y est,
# absolus sinon. Python, lui, recompose `prefixe + nom`.
#
# Sur les formes courantes les deux coïncident, et tout est comparé au caractère
# près. Sur la mémoire DÉPORTÉE, elles divergent — et c'est Python qui a tort :
# il annonce `.fact/base.md` à un agent pour qui ce chemin ne désigne rien.
# Mesuré sur trois agents d'un même projet : `cat .fact/base.md` depuis leur
# dossier ne trouve aucun fichier, alors que la phrase juste au-dessus dit
# « ouvrir le fichier qui porte la réponse ».
#
# Python n'est pas corrigé : repli condamné, hors périmètre de l'audit. On
# compare donc l'index sur le NOM du fichier, et rien d'autre — le nombre de
# lignes, les titres, l'ordre et les mentions ABSENT restent comparés
# exactement. Le témoin ci-dessous exige que cette exception SERVE.
INDEX = re.compile(r"^ {2,}(\S*/)?([\w.-]+\.md) *", re.M)

# LA LIGNE « attente » NOMME AUSSI UN FICHIER, et depuis le 10/09/2026 elle
# nomme celui qu'on a VRAIMENT lu au lieu de `.mind/todo.md` en dur. C'est la
# même correction que sur l'index, au même endroit du raisonnement : un chemin
# annoncé doit s'ouvrir depuis le dossier de l'agent. Python reste faux ici
# aussi — repli condamné —, donc on replie ce chemin sur son NOM de fichier,
# exactement comme l'index, et le chemin lui-même part au cliché côté Rust.
ATTENTE = re.compile(r"^(attente: aucune tâche `@<qui>` ouverte dans )(\S+)$", re.M)
_collapses = [0]


def index_sur_le_nom(t):
    def sub_attente(m):
        chemin = m.group(2)
        if "/" in chemin:
            _collapses[0] += 1
        return m.group(1) + chemin.rsplit("/", 1)[-1]
    t = ATTENTE.sub(sub_attente, t)

    def sub(m):
        if m.group(1):
            _collapses[0] += 1
        # L'ALIGNEMENT PART AVEC LE CHEMIN, forcement : la colonne est calee sur
        # la longueur du chemin, et les deux cotes ne l'ecrivent plus pareil. Ce
        # qui reste compare est ce qui porte du SENS -- le nom du fichier, son
        # nombre de lignes, ses titres, et la mention ABSENT.
        return "  " + m.group(2) + " "
    return INDEX.sub(sub, t)


def bac(nom, multi=False, deporte=False, carnet=False, settings="ok",
        racine_sans_agent=False, cible=None, sans_fact=False):
    d = S/nom; d.mkdir(parents=True)
    g = lambda *a: subprocess.run(["git","-C",str(d)]+list(a), capture_output=True, text=True)
    g("init","-q","-b","main"); g("config","user.name","M"); g("config","user.email","m@x")
    agent = d/"agents/ios" if multi else d
    if not sans_fact:
        ecrire(d/".fact/base.md", "---\ncap: aller là-bas\n---\n\n## Nature\n## Où on va\n")
        ecrire(d/".fact/stack.md", "## Les outils\n## Les comptes\n")
        ecrire(d/".fact/rules.md", "## Ce qu'on ne franchit pas\n")
    if not racine_sans_agent:
        base = d/"memoire" if deporte else agent
        if deporte:
            ecrire(d/"memoire/.fact/base.md", "---\ncap: cap déporté\n---\n\n## Nature\n")
            ecrire(d/"memoire/.mind/state.md", f"---\nmaj: {AUJ}\nsante: verte\njalon: J1\n---\n")
            ecrire(d/"memoire/.mind/todo.md", "- [ ] !haut @user **Une question ? 1 / 2**\n")
        else:
            ecrire(agent/".mind/state.md", f"---\nmaj: {AUJ}\nsante: verte\njalon: J1\n---\n")
            ecrire(agent/".mind/todo.md",
                   "- [ ] !haut @user ?constat **Une question ? 1 / 2**\n"
                   "- [ ] @dehors attendre\n- [ ] !bas @user une broutille\n")
    if multi and not racine_sans_agent:
        (d/"agents/web/.mind").mkdir(parents=True)
        ecrire(d/"agents/web/.mind/state.md", "---\nmaj: 2020-01-01\n---\n")
    if carnet:
        dst = (d/"memoire/equipe") if deporte else (d/"equipe")
        (dst/".etat").mkdir(parents=True)
        q = datetime.datetime.now() - datetime.timedelta(hours=2)
        ecrire(dst/("%s-Un-Pair.md" % q.strftime("%Y-%m")),
               "# Carnet d'équipe — Un Pair\n\n"
               "## %s %s · Un Pair · abouti · mesuré\n"
               "Une entrée fabriquée, avec ses trois marqueurs\n"
               "↗ ios : une transmission qui t'est adressée.\n"
               "↻ machine :: echo ATTENDU :: ^ATTENDU$\n"
               "↩ aaaaaaaaaaaa\n"
               % (q.strftime("%Y-%m-%d"), q.strftime("%H:%M")))
        ecrire(dst/".etat/confiance.json", "{}\n")
    if settings == "ok":
        ecrire(agent/".claude/settings.json",
               json.dumps({"permissions":{"defaultMode":"bypassPermissions",
                           "allow":["Bash(ls*)"],"deny":["Bash(rm*)"]}}))
    elif settings == "casse":
        ecrire(agent/".claude/settings.json", "{ pas du json")
    elif settings == "sans-deny":
        ecrire(agent/".claude/settings.json", json.dumps({"permissions":{"allow":[]}}))
    if cible:
        nom = agent.name
        ecrire(DATA/"attente"/(nom + ".cible"), cible)
    g("add","-A"); g("commit","-q","-m","socle")
    return d, agent

def lance(argv, cwd, projet_dir, evenement="SessionStart"):
    e = dict(os.environ)
    e["CLAUDE_PROJECT_DIR"] = str(projet_dir)
    e["CLAUDE_PLUGIN_DATA"] = str(DATA)
    entree = json.dumps({"hook_event_name": evenement, "cwd": str(projet_dir),
                         "session_id": "sess-diff"})
    r = subprocess.run(argv, cwd=str(cwd), input=entree, capture_output=True, text=True, env=e)
    s = r.stdout.strip()
    if not s: return None
    try:
        return json.loads(s)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return {"BRUT": s[:400]}

def sauve(paths):
    return {p: (p.read_bytes() if p.exists() else None) for p in paths}
def rends(snap):
    for p, b in snap.items():
        if b is None:
            if p.exists(): p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)

CAS = []
CAS.append(("mono simple",      bac("mono")))
CAS.append(("multi-agents",     bac("multi", multi=True)))
CAS.append(("racine sans agent",bac("racine", multi=True, racine_sans_agent=True)))
CAS.append(("déporté + carnet", bac("dep", multi=True, deporte=True, carnet=True)))
CAS.append(("réglages cassés",  bac("cass", settings="casse")))
CAS.append(("aucun deny",       bac("nodeny", settings="sans-deny")))
CAS.append(("aucun settings",   bac("nosett", settings="rien")))
CAS.append(("sans .fact",       bac("nofact", sans_fact=True)))
for v in ("TIENT", "TOMBÉ", "SANS", "MUET"):
    CAS.append((f"cible {v}", bac("cib"+v.replace("É","E"),
        cible=f"{v}\t2026-09-08\t4\tla phrase de la cible")))

GEL  = temoins.gel_demande()
ARGV = ["python3", PY] if GEL else [RS, "briefing"]
# Le programme comparé doit avoir DÉMARRÉ avant qu'on juge quoi que ce soit :
# un lanceur mort rend une sortie qu'on confondrait avec un verdict (23/09/2026).
temoins.exige_que_ca_demarre(ARGV)

def _sans_chemin(a, d):
    """LE RUST CANONISE, PAS PYTHON : `/tmp/x` d'un côté, `/private/tmp/x` de
    l'autre. Un masque qui n'enlève qu'une des deux formes laisse un chemin de
    bac à sable dans le témoin — donc un témoin qui ne vaut que pour ce
    dossier-là."""
    if not isinstance(a, str):
        return a
    for forme in ("/private" + str(d), str(d)):
        a = a.replace(forme, "<D>")
    return a

# ── LA DEUXIÈME DIVERGENCE VOULUE : `workflow.md` POUR TOUS (12/10/2026) ──────
# Décision du commanditaire : « on doit intégrer un fichier workflow.md dans le folder fact aussi,
# pour tous les agents ». Le briefing l'annonce donc partout, ABSENT quand il
# manque — ce que ni Python ni Rust ne faisaient quand le témoin a été figé. La
# ligne (et ses titres s'il y en a) est retirée AVANT la comparaison ; tout le
# reste se compare comme avant. Le témoin : elle doit avoir été retirée au moins
# une fois, sinon l'exception masque quelque chose qui n'existe plus.
WORKFLOW = re.compile(r"^ {2,}\S*workflow\.md .*\n(?: {6}\S.*\n)?", re.M)
_workflow = [0]


def sans_workflow(t):
    t2, n = WORKFLOW.subn("", t)
    _workflow[0] += n
    return t2


ecarts, produit, chemins, parle, muet = [], {}, {}, 0, 0
for nom, (d, agent) in CAS:
    a = lance(ARGV, d, agent)
    if a is None: muet += 1
    else: parle += 1
    a = sans_workflow(a) if isinstance(a, str) else a
    brut = _sans_chemin(a, d)
    produit[nom] = index_sur_le_nom(brut) if isinstance(brut, str) else brut
    if isinstance(brut, str):
        chemins[nom] = "\n".join(l for l in brut.splitlines()
                                  if INDEX.match(l) or ATTENTE.match(l))

# LE CLICHÉ DES CHEMINS SE PREND TOUJOURS CÔTÉ RUST, gel compris. C'est le seul
# endroit où Python est FAUX et ne sera pas corrigé : figer sa version aurait
# gravé l'erreur au lieu de la référence.
if GEL:
    chemins = {}
    for nom, (d, agent) in CAS:
        for f in (agent/".claude/.briefing.json", agent/".claude/.briefing.lock"):
            if f.exists(): f.unlink()
        brut = _sans_chemin(lance([RS, "briefing"], d, agent), d)
        if isinstance(brut, str):
            chemins[nom] = "\n".join(l for l in brut.splitlines()
                                      if INDEX.match(l) or ATTENTE.match(l))

# LE CAS `UserPromptSubmit` : muet en régime établi, parlant si un fichier bouge.
d, agent = bac("ups")
lance(ARGV, d, agent)                                 # première injection
sil = lance(ARGV, d, agent, "UserPromptSubmit")
produit["UserPromptSubmit-en-regime-etabli"] = "muet" if sil is None else "parle"
temoin_silence = (sil is None)

# ── LE REPLI DOIT DIRE QU'IL EST LE REPLI ────────────────────────────────────
# Ajouté le 10/09/2026 : le repli Python n'a PAS le relecteur — onze sorties
# bloquantes au lieu de douze — et rien ne le disait. Un repli silencieux se lit
# comme le régime normal, donc on lui fait la confiance de l'original.
# Les deux sens sont joués : sans la variable, rien ne s'annonce — sinon
# l'avertissement finirait par polluer le régime normal sans qu'on le voie.
# On réutilise le dossier DÉJÀ PEUPLÉ ci-dessus : sur un bac vide le briefing
# sort avant d'avoir rien à dire, et le témoin échouerait pour la mauvaise
# raison — il mesurerait l'absence d'état, pas l'absence d'avertissement.
charge = json.dumps({"session_id": "repli", "cwd": str(agent),
                     "hook_event_name": "SessionStart"})
def _neuf():
    # Le briefing ne se sert qu'une fois par période : sans ce nettoyage les
    # deux sondes tomberaient sur le silence du régime établi, et le témoin
    # échouerait en mesurant autre chose que ce qu'il croit mesurer.
    for f in (agent/".claude/.briefing.json", agent/".claude/.briefing.lock"):
        if f.exists():
            f.unlink()

# CE TÉMOIN NE VAUT QUE CÔTÉ PYTHON, et il part avec lui : c'est le repli
# Python qui devait s'annoncer, et le lot 1 le supprime. Tant qu'il existe, on
# l'exige au gel.
if GEL:
    _neuf()
    avec = subprocess.run(["python3", PY], input=charge, capture_output=True, text=True,
                          env=dict(os.environ, HARNAIS_REPLI="1")).stdout
    _neuf()
    sans = subprocess.run(["python3", PY], input=charge, capture_output=True, text=True).stdout
    temoin_repli = ("REPLI PYTHON" in avec) and ("REPLI PYTHON" not in sans)
    if not temoin_repli:
        ecarts.append("TÉMOIN RATÉ — le repli ne s'annonce pas, ou s'annonce hors repli "
                      "(avec=%s, sans=%s)" % ("REPLI PYTHON" in avec, "REPLI PYTHON" in sans))
else:
    temoin_repli = "sans objet (le repli Python n'est plus interrogé)"

print(f"témoins : {parle} briefings servis, {muet} silences — "
      f"UserPromptSubmit muet en régime établi : {temoin_silence} · "
      f"le repli s'annonce : {temoin_repli}"
      + ("" if parle and temoin_silence else "   ← TÉMOIN RATÉ"))
print()
# UNE EXCEPTION DOIT SERVIR, SINON ELLE CACHE AUTRE CHOSE. Si plus aucun chemin
# n'a été replié sur son nom, c'est que Python a été corrigé, retiré, ou que le
# cas déporté a disparu des essais : dans les trois cas la neutralisation doit
# partir plutôt que rester à masquer un écart futur.
if _collapses[0] == 0:
    ecarts.append("témoin : l'index n'a JAMAIS été replié sur le nom de fichier — "
                  "l'exception ne sert plus. La retirer, et comparer les chemins "
                  "annoncés au caractère près.")
else:
    print(f"témoin : index replié sur le nom {_collapses[0]} fois "
          f"(divergence Python attendue sur la mémoire déportée)")
if not GEL and _workflow[0] == 0:
    ecarts.append("témoin : la ligne `workflow.md` n'a JAMAIS été retirée — l'exception du "
                  "12/10/2026 ne sert plus et masquerait un écart futur : la retirer")
elif not GEL:
    print(f"témoin : ligne workflow.md retirée {_workflow[0]} fois (divergence voulue du 12/10/2026)")

MASQUE = [(str(S), "<bac>"), (AUJ, "<auj>")]
if GEL:
    if ecarts or not parle or not temoin_silence:
        raise SystemExit("GEL REFUSÉ :\n  " + "\n  ".join(ecarts or ["témoin manquant"]))
    cas = [(n, "bac fabriqué", produit[n]) for n in produit]
    f = temoins.fige("briefing", cas, ("mono simple", "racine sans agent"), [PY], MASQUE)
    print("témoin figé :", f)
    # LE CLICHÉ DES CHEMINS, côté Rust — voir l'en-tête.
    cc = [(n, "chemins annoncés dans l'index", v) for n, v in chemins.items()]
    f2 = temoins.fige("briefing-chemins", cc, ("mono simple", "déporté + carnet"),
                      [RS], MASQUE, origine="rust")
    print("cliché figé  :", f2, "(origine RUST — pas une preuve d'équivalence)")
    sys.exit(0)

# L'ENTRÉE DU CARNET FABRIQUÉ vaut `maintenant − 2 h` : son jour, écrit `MM-JJ`
# dans le briefing, change selon l'heure où l'on joue (figé à 01 h 12, rejoué à
# 07 h 00 le même jour : « 09-10 » contre « 09-11 », mesuré le 11/09/2026). On
# le nomme par l'entrée — mais côté programme SEULEMENT s'il est juste, pour
# qu'une date fausse reste un écart.
def jour_du_pair(texte, cote):
    import re
    attendu = (datetime.datetime.now() - datetime.timedelta(hours=2)).strftime("%m-%d")
    def sub(m):
        if cote == "produit" and m.group(1) != attendu:
            return m.group(0)
        return "<jour-2h> · Un Pair · "
    return re.sub(r"(\d\d-\d\d) · Un Pair · ", sub, texte)

# ── ÉCART DÉCLARÉ, 12/09/2026 : L'EMPREINTE DANS LA LIGNE ───────────────────
# Le briefing marquait une entrée « → POUR TOI » et demandait de l'acquitter par
# `↩ <empreinte>` SANS JAMAIS AFFICHER CETTE EMPREINTE : le seul geste social du
# carnet était inerte, mesuré chez un agent d'épreuve (trois entrées
# qui le visaient depuis le 08/09, dont une re-versée à l'identique). La ligne
# la porte désormais, et l'invite dit où la recopier. Le témoin reste celui du
# jour de sa prise ; l'écart est appliqué à SON côté, et l'empreinte — qui
# dépend de l'heure du passage — est nommée des DEUX côtés.
_ecart = {"empreinte": False, "invite": False}
_INVITE_AVANT = "         acquitté : `↩ <empreinte>` dans ta prochaine entrée."
_INVITE_APRES = ("         acquitté : recopie `↩ <empreinte>` (donnée ci-dessus) dans TON\n"
                 "         fichier du carnet, jamais dans celui de l'auteur.")

def acquittement(texte, cote):
    if not isinstance(texte, str):
        return texte
    t = re.sub(r"↩ [0-9a-f]{6,12}", "↩ <empreinte>", texte)
    if cote == "temoin":
        apres = re.sub(r"(→ POUR TOI)(?! ↩)", r"\1 ↩ <empreinte>", t)
        if apres != t:
            _ecart["empreinte"] = True
            t = apres
        if _INVITE_AVANT in t:
            t = t.replace(_INVITE_AVANT, _INVITE_APRES)
            _ecart["invite"] = True
    return t

e2, ligne = temoins.compare("briefing", produit, MASQUE,
                            normalise=lambda x, c: acquittement(jour_du_pair(x, c), c))
e3, ligne2 = temoins.compare("briefing-chemins", chemins, MASQUE)
# L'ÉCART PORTE SON TÉMOIN DE PÉREMPTION : s'il ne mord plus, le témoin a été
# refait depuis et ce bloc ne vérifie plus rien.
for quoi, vu in _ecart.items():
    if not vu:
        e2.append("ÉCART DÉCLARÉ MORT (%s) — il ne change plus rien au témoin : "
                  "celui-ci a été refait, retirer ce bloc" % quoi)
ecarts = ecarts + e2 + e3
print("%s\n%s" % (ligne, ligne2))
print()
print("\n\n".join(ecarts) or "ÉCARTS : AUCUN sur %d cas + le silence + les chemins annoncés" % len(CAS))
sys.exit(1 if (ecarts or not parle) else 0)
