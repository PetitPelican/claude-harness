"""CONTRÔLE DIFFÉRENTIEL — la fin de tour, Python contre Rust.

Le plus gros du harnais : ONZE sorties bloquantes, un canal vers le téléphone,
et une demi-douzaine de témoins qui décident si un blocage se represente. On
compare donc quatre choses par cas, et pas une :

  · le CODE DE SORTIE (2 = l'agent est renvoyé au travail) ;
  · le MESSAGE, au caractère près — un garde qui mord avec la mauvaise phrase
    apprend le mauvais geste ;
  · les APPELS AU TÉLÉPHONE, journalisés par un faux `osascript` ;
  · tous les FICHIERS D'ÉTAT écrits, à l'octet.

Le faux `osascript` est impératif : le vrai créerait des listes dans les Rappels
de l'humain. Il rend aussi le canal mesurable.

DEPUIS LE 08/10/2026, LE CANAL DOIT RESTER MUET. Décision du commanditaire : « je ne veux plus que
la todo qui est tenue » — plus rien ne part vers ses Rappels ni n'en est lu. Le
faux `osascript` reste donc en tête du chemin, comme piège : un seul appel
journalisé est un écart. Les cas qui posaient des réponses, des coches et des
demandes dans le faux téléphone restent joués : ils doivent désormais ne RIEN
déclencher.

TÉMOINS : il faut des blocages ET des passages. Deux hooks qui ne font rien se
comparent égaux.
"""
import json, os, re, shutil, subprocess, pathlib, sys, datetime, time

S = pathlib.Path(sys.argv[1])/"att"
shutil.rmtree(S, ignore_errors=True); S.mkdir(parents=True)
FAUX = str(pathlib.Path(__file__).resolve().parent/"faux-bin")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import temoins
PY = str(pathlib.Path.home()/".claude/hooks/attente.py")
RS = os.environ.get("HARNAIS_BIN") or str(pathlib.Path.home()/"Agentic/claude-harnais/bin/harnais")
AUJ = datetime.date.today().isoformat()
RECHUTES = "# Avant d'affirmer\n\n- **Une question de contrôle ?**\n\n<!-- ÉCRITURE\nrègle\n-->\n"

T0 = 1700000000        # une date fixe, la même des deux côtés

def dater(d, n):
    """Pose la date du todo à T0 + n. Le code, lui, reste 10 s plus tard quand
    il doit paraître plus récent."""
    t = d/".mind"/"todo.md"
    if not t.exists(): t = d/"memoire"/".mind"/"todo.md"
    os.utime(t, (T0 + n, T0 + n))

def ecrire(p, t):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t)

def monte(cote, nom, todo, *, code=None, deporte=False, carnet=False, zones=None,
          consigne=None, fact_touche=False, vieux_todo=False):
    """Un bac par côté : dépôt, dossier d'état du harnais, fixtures du téléphone."""
    base = S/(cote+"_"+nom); base.mkdir(parents=True)
    d = base/"projet"; d.mkdir()
    data = base/"data"; (data/"attente").mkdir(parents=True)
    ecrire(data/"rechutes.md", RECHUTES)
    g = lambda *a, **kw: subprocess.run(["git","-C",str(kw.get("c", d))]+list(a),
                                        capture_output=True, text=True)
    g("init","-q","-b","main"); g("config","user.name","M"); g("config","user.email","m@x")
    ecrire(d/".fact/base.md", "---\ncap: un cap\n---\n\n## Nature\nx\n"
           + (("\n## Consigne\n%s\n" % consigne) if consigne else ""))
    mind = (d/"memoire/.mind") if deporte else (d/".mind")
    ecrire(mind/"state.md", "---\nmaj: %s\nsante: verte\njalon: J\n---\n" % AUJ)
    ecrire(mind/"todo.md", todo)
    if deporte:
        ecrire(d/"memoire/.fact/base.md", "---\ncap: c\n---\n"
               + (("\n## Consigne\n%s\n" % consigne) if consigne else ""))
        subprocess.run(["git","-C",str(d/"memoire"),"init","-q","-b","main"],capture_output=True)
        for k,v in (("user.name","M"),("user.email","m@x")):
            subprocess.run(["git","-C",str(d/"memoire"),"config",k,v],capture_output=True)
        subprocess.run(["git","-C",str(d/"memoire"),"add","-A"],capture_output=True)
        subprocess.run(["git","-C",str(d/"memoire"),"commit","-q","-m","x"],capture_output=True)
    if carnet:
        esp = (d/"memoire/equipe") if deporte else (d/"equipe")
        (esp/".etat").mkdir(parents=True)
        ecrire(esp/"LISEZMOI.md", "x\n")
        if zones: ecrire(esp/"ZONES", zones)
    ecrire(d/"src/a.ts", "const a = 1\n")
    g("add","-A"); g("commit","-q","-m","socle")
    if code:
        time.sleep(0.02); ecrire(d/"src/a.ts", code)
        if not vieux_todo:
            pass
        else:
            pass
    if fact_touche and deporte:
        ecrire(d/"memoire/.fact/base.md", "---\ncap: changé\n---\n")
    if code and not vieux_todo:      # le todo suit le code
        ecrire(mind/"todo.md", todo)
    os.utime(mind/"todo.md", (T0, T0))
    if code:
        # le code paraît plus récent que le todo — c'est ce que la garde lit
        os.utime(d/"src/a.ts", (T0 + 10, T0 + 10))
        if not vieux_todo:
            os.utime(mind/"todo.md", (T0 + 20, T0 + 20))
    return d, data

def lance(argv, d, data, fixtures, projet_dir=None):
    fx = data/"rappels.json"; fx.write_text(json.dumps(fixtures, ensure_ascii=False))
    jl = data/"appels.log"; jl.write_text("")
    e = dict(os.environ)
    e["PATH"] = FAUX + ":" + e["PATH"]
    e["CLAUDE_PLUGIN_DATA"] = str(data)
    e["CLAUDE_PROJECT_DIR"] = str(projet_dir or d)
    e["FAUX_RAPPELS"] = str(fx); e["FAUX_JOURNAL"] = str(jl)
    # AUCUN VRAI JUGE PENDANT LES CONTRÔLES : sans ça chaque passage
    # lancerait une douzaine dappels reels, et consommerait le plafond
    # journalier du relecteur avec des bacs a sable.
    e["HARNAIS_RELECTURE_SIMULEE"] = "1"
    e.pop("CLAUDE_PLUGIN_ROOT", None)
    r = subprocess.run(argv, cwd=str(d), input=json.dumps({"session_id":"sess-1"}),
                       capture_output=True, text=True, env=e)
    appels = [json.loads(l) for l in jl.read_text().splitlines() if l.strip()]
    return r.returncode, r.stderr, appels

def etat_fichiers(data):
    out = {}
    for p in sorted((data/"attente").rglob("*")):
        if p.is_file():
            # En `/` partout : sous Windows le nom sortait en `attente\x`, et
            # tout l'état différait du témoin pour un séparateur (28/10/2026).
            out[p.relative_to(data).as_posix()] = p.read_text(errors="replace")
    return out

# LE MOTIF (0.19.4) : une question au commanditaire nomme pourquoi elle lui
# revient. Les questions du banc le portent, pour que les gardes d'après la
# forme restent traversées ; `TODO_SANS_MOTIF` éprouve celle qui le réclame.
TODO_OK = ("- [ ] !haut @user **Une question ? oui / non**\n"
           "      oui → on fait ceci.\n"
           "      non → on fait cela.\n"
           "      motif → périmètre\n"
           "      fini quand → tu vois la page en ligne.\n")
TODO_CONSTAT_SANS = ("- [ ] !haut @user ?constat **La page manque ? oui / non**\n"
                     "      oui → on la crée.\n      non → on ferme.\n"
                     "      motif → production\n"
                     "      fini quand → tu la vois.\n")
TODO_SANS_MOTIF = ("- [ ] !haut @user **Je range les vieux fichiers ? oui / non**\n"
                   "      oui → je les déplace.\n      non → rien ne bouge.\n"
                   "      fini quand → le dossier est vide.\n")
TODO_CONSTAT_KO = (TODO_CONSTAT_SANS.rstrip("\n")
                   + "\n      ↻ machine :: echo rien-du-tout :: ^ATTENDU$\n")
TODO_CONSTAT_OK = (TODO_CONSTAT_SANS.rstrip("\n")
                   + "\n      ↻ machine :: echo ATTENDU :: ^ATTENDU$\n")
TODO_MAUVAIS = "- [ ] !haut @user **Le service est cassé**\n      un constat, pas une question.\n"
TODO_COCHE = ("- [x] Réparer l'inscription\n      ↗ PO : c'est réparé.\n\n" + TODO_OK)

# LES GESTES ENTRE DEUX TOURS. Cinq gardes sur onze sont INACCESSIBLES à un
# second tour identique : la poussée vers le téléphone s'arrête net si la date
# du todo n'a pas bougé, et tout ce qui suit — la forme, la liste de contrôle,
# les constats tombés, l'acharnement — vit après cette barrière. Le carnet, lui,
# demande un commit entre les deux. Un contrôle qui ne les traverse jamais ne
# dit RIEN d'elles, et c'est exactement l'erreur qu'il est censé attraper.
def touche(d, n):                    # même contenu, date neuve
    t = d/".mind"/"todo.md"
    if not t.exists(): t = d/"memoire"/".mind"/"todo.md"
    t.write_text(t.read_text()); dater(d, n)
def remplace(txt):
    def f(d, n):
        t = d/".mind"/"todo.md"
        if not t.exists(): t = d/"memoire"/".mind"/"todo.md"
        t.write_text(txt); dater(d, n)
    return f
def commit_src(d, n=0):
    (d/"src"/"b.ts").write_text("const b = 1\n")
    subprocess.run(["git","-C",str(d),"add","-A"], capture_output=True)
    subprocess.run(["git","-C",str(d),"commit","-q","-m","travail"], capture_output=True)

TODO_AUTRE = ("- [ ] !haut @user **Une AUTRE question ? oui / non**\n"
              "      oui → on fait ceci.\n      non → on fait cela.\n"
              "      motif → cap\n"
              "      fini quand → tu vois la page.\n")

def question(n):
    """Une question NEUVE à chaque tour : c'est ce qui rearme la garde des
    rechutes, qui ne compte que les affirmations jamais vues."""
    return ("- [ ] !haut @user **Question numéro %d ? oui / non**\n"
            "      oui → on fait ceci.\n      non → on fait cela.\n"
            "      motif → cap\n"
            "      fini quand → tu vois la page.\n" % n)

CAS = [
 ("code sans todo",      dict(todo=TODO_OK, code="const a = 2\n", vieux_todo=True), {}),
 ("todo à jour",         dict(todo=TODO_OK), {}),
 ("réponse de l'humain",  dict(todo=TODO_OK), {"faits": ["🔴 Une question ? oui / non · Ta réponse : oui"]}),
 ("point tranché",       dict(todo=TODO_OK), {"faits": ["🔴 Une question ? oui / non"]}),
 ("demande de l'humain",  dict(todo=TODO_OK), {"ouverts": ["achète du café"]}),
 ("constat sans rejeu",  dict(todo=TODO_CONSTAT_SANS), {}),
 ("constat qui tient",   dict(todo=TODO_CONSTAT_OK), {}),
 ("constat qui tombe",   dict(todo=TODO_CONSTAT_KO), {}),
 ("ligne mal formée",    dict(todo=TODO_MAUVAIS), {}),
 ("carnet, zone touchée",dict(todo=TODO_OK, deporte=True, carnet=True, zones="src/*"), {}),
 ("faits déportés",      dict(todo=TODO_OK, deporte=True, fact_touche=True), {}),
 ("cible tombée",        dict(todo=TODO_OK, consigne="Zéro page cassée.\n↻ machine :: echo non :: ^oui$"), {}),
 ("cible sans mesure",   dict(todo=TODO_OK, consigne="Zéro page cassée."), {}),
 ("rappels existants",   dict(todo=TODO_OK), {"ouverts": ["🟠 Un vieux rappel", "🔴 Une question ? oui / non"]}),
]

# (nom, réglages, fixtures, gestes entre les tours) — un tour de plus par geste.
CAS_MULTI = [
 ("forme rappelée",   dict(todo=TODO_OK), {}, [remplace(TODO_MAUVAIS)]),
 ("motif manquant",   dict(todo=TODO_OK), {}, [remplace(TODO_OK + TODO_SANS_MOTIF)]),
 ("constat tombé 2×", dict(todo=TODO_CONSTAT_KO), {}, [touche]),
 ("liste de contrôle",dict(todo=TODO_OK), {}, [remplace(TODO_OK + TODO_AUTRE)]),
 ("acharnement",      dict(todo=TODO_OK, consigne="Zéro page cassée.\n↻ machine :: echo non :: ^oui$"),
                      {}, [touche, touche]),
 ("carnet non versé", dict(todo=TODO_OK, deporte=True, carnet=True, zones="src/*"), {}, [commit_src]),
 # LE PLAFOND DES RECHUTES, DE PART ET D'AUTRE, À L'UNITÉ. Cinq tours, une
 # question NEUVE à chacun : la garde doit mordre trois fois puis se taire.
 # LE DERNIER TOUR DOIT LUI AUSSI PORTER UNE QUESTION NEUVE. Au premier essai,
 # il ne faisait que dater le fichier : la garde ne se déclenchait donc pas, et
 # le tour d'après le seuil n'était jamais joué. Un cas qui s'arrête AVANT le
 # seuil ressemble en tout point à un cas qui le franchit sans dommage.
 # Sans ce cas, le corpus traversait la garde sans jamais toucher son seuil —
 # mesuré le 10/09/2026 en portant le plafond de 3 à 4 : les témoins figés
 # n'ont RIEN vu. Une garde traversée n'est pas une garde éprouvée.
 ("rechutes, le plafond", dict(todo=question(1)), {},
  [remplace(question(2)), remplace(question(3)), remplace(question(4)),
   remplace(question(5))]),
]

def etat_normalise(d, data):
    """LES FICHIERS D'ÉTAT, RENDUS COMPARABLES À UN TÉMOIN FIGÉ.

    Trois d'entre eux ne peuvent PAS être figés à l'octet, et les figer quand
    même reviendrait à mesurer le bac à sable :
    · `blocages.log` porte un horodatage → on garde les colonnes stables ;
    · `.tete` porte l'empreinte de `HEAD`, propre à chaque dépôt jetable ;
    · `.pousse` porte la date du fichier todo, propre à chaque bac.
    Pour les deux derniers on fige le VERDICT — « il porte bien le HEAD de son
    dépôt » — et pas la valeur. Un témoin qui garderait la valeur échouerait au
    prochain bac, c'est-à-dire toujours, et on apprendrait à l'ignorer.

    DIVERGENCE DÉCLARÉE, ET ELLE EST VOULUE : le relecteur n'existe que côté
    Rust. Ses fichiers sont retirés de la comparaison et NOMMÉS. Ce que ça
    coûte, et qu'il faut savoir : là où le binaire ne peut pas tourner, l'agent
    garde ses onze gardes et perd son relecteur, sans que rien ne le lui dise.
    """
    f = etat_fichiers(data)
    RUST_SEUL = ("attente/%s.relu" % "projet", "attente/relectures.log")
    for k in RUST_SEUL:
        if k in f:
            divergences_declarees.add(k)
            del f[k]
    tete = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    t1, t2 = d/".mind"/"todo.md", d/"memoire"/".mind"/"todo.md"
    td = t1 if t1.exists() else t2
    att = "%.0f" % td.stat().st_mtime if td.exists() else "(pas de todo)"
    out = {}
    for k in sorted(f):
        v = f[k]
        if k.endswith("blocages.log"):
            out[k] = [l.split("\t")[1:4] for l in v.splitlines()]
        elif k.endswith(".tete"):
            out[k] = "porte le HEAD de son dépôt" if v.strip() == tete else "HEAD ÉTRANGER : %r" % v
        elif k.endswith(".pousse"):
            out[k] = "porte la date de son todo" if v == att else "DATE ÉTRANGÈRE : %r" % v
        else:
            out[k] = v
    return out

# ── LA SEULE DIVERGENCE ATTENDUE, ET ELLE EST DATÉE ────────────────────────
#
# Depuis le 10/09/2026 (audit P1), le Rust nomme dans ses messages le chemin
# RÉSOLU du todo. Python, lui, écrit toujours `.mind/todo.md` en dur. Sur les
# formes où les deux coïncident, rien ne change ; sur la mémoire DÉPORTÉE, le
# fichier est sous `memoire/.mind/todo.md` et Python nomme donc un chemin qui
# N'EXISTE PAS — un agent qui le suit se heurte à un refus d'écriture et rend la
# main sans rien noter. C'est ce qui a été observé en session réelle.
#
# Python n'est PAS corrigé, et c'est délibéré : c'est un repli condamné, hors du
# périmètre de cet audit. On cesse donc de comparer le chemin du todo dans les
# messages — CE CHEMIN-LÀ, et rien d'autre : tout le reste du message reste
# comparé au caractère près.
#
# LA COUVERTURE NE DISPARAÎT PAS, ELLE DÉMÉNAGE. Le chemin annoncé est désormais
# éprouvé côté Rust par `le_garde_nomme_le_fichier_qui_existe_dans_les_trois_formes`,
# qui vérifie les TROIS formes et qu'aucune ne rend le chemin d'une autre —
# c'est-à-dire plus que ce que cette comparaison voyait.
TODO_NOMME = re.compile(r"`[^`\n]*todo\.md`")
_masques = [0]


def neutralise_todo(s):
    n = len(TODO_NOMME.findall(s))
    _masques[0] += n
    return TODO_NOMME.sub("`<TODO>`", s)


# ── LE SCRIPT D'EFFACEMENT RÉPARÉ, ET C'EST UNE DIVERGENCE DATÉE ───────────
#
# Le 11/09/2026 : `delete cibles`, où `cibles` est la liste rendue par un
# filtre, échoue dès que le filtre rend DEUX rappels (-1700). Python avait le
# même défaut, donc le témoin le porte : tout titre en double faisait tomber
# l'effacement, et un doublon ne partait jamais. Le script réparé passe le
# filtre à `delete` tel quel. Son empreinte change, et SEULEMENT elle : on
# rend à l'appel l'empreinte figée, et la charge, la liste et l'ordre des
# appels restent comparés au caractère près. Éprouvé sur une vraie liste
# d'essai à deux copies : l'ancien script rend -1700, le nouveau efface les deux.
# VIDÉE LE 23/09/2026, ET C'EST LA FIN DE SA RAISON D'ÊTRE. Cette table
# réconciliait un témoin figé à l'ÈRE PYTHON avec le script d'effacement réparé
# le 11/09 : elle réécrivait l'empreinte DANS LE RENDU, jamais dans le témoin.
# Le témoin étant désormais regelé depuis le PROGRAMME, il porte déjà
# l'empreinte du jour ; continuer à réécrire le rendu fabriquait un écart à
# partir de deux valeurs pourtant identiques. Une correspondance d'empreintes
# écrite en dur ne survit pas au regel de ce qu'elle corrigeait — on la vide
# plutôt que de la mettre à jour, sinon elle redeviendra fausse au prochain.
SCRIPT_REPARE = {}
_repares = [0]


def rend_empreinte_figee(appels):
    out = []
    for a in appels:
        if isinstance(a, dict) and a.get("script") in SCRIPT_REPARE:
            _repares[0] += 1
            a = dict(a, script=SCRIPT_REPARE[a["script"]])
        out.append(a)
    return out


GEL  = temoins.gel_demande()

# LE REPLI PYTHON EST MORT DEPUIS LE 10/09/2026, ET LE GEL LE LANÇAIT ENCORE.
# `PY` désigne `~/.claude/hooks/attente.py`, retiré du dépôt ET du poste ce
# jour-là — la référence d'aujourd'hui est le PROGRAMME. Le mode gel continuait
# pourtant de l'appeler. Ce que ça donnait, et pourquoi personne ne l'a vu
# pendant treize jours : `python3 <fichier absent>` sort en code 2, et ce
# contrôle compte `code == 2` comme un BLOCAGE. Cinquante « fichier
# introuvable » se lisaient donc comme cinquante refus réussis, et les onze
# gardes ressortaient à zéro — un trou de couverture, jamais une panne.
# L'échec de l'instrument était l'exact sosie de son succès.
#
# Le mode COMPARAISON, lui, marchait : il relit le témoin déjà figé. Seul le
# REGEL était mort. Un dispositif de preuve qu'on ne peut plus mettre à jour
# pousse à publier avec des écarts, ou à ne plus rien changer.
ARGV = [RS, "attente"]
COTE = "rs"

# ET ON EXIGE QU'IL RÉPONDE AVANT DE JUGER QUOI QUE CE SOIT. C'est la leçon du
# défaut ci-dessus : un lanceur qui ne démarre pas rend une sortie qu'on peut
# confondre avec un verdict. Le coût est une ligne ; il aurait valu treize jours.
_v = subprocess.run([RS, "version"], capture_output=True, text=True)
if _v.returncode != 0 or not _v.stdout.strip():
    raise SystemExit(
        "CONTRÔLE IMPOSSIBLE : le programme de référence ne répond pas à "
        "`version` (%s). Rien n'a été jugé — et surtout rien n'a été figé." % RS)

ecarts, produit, bloc, passe, appels_tot = [], {}, 0, 0, 0
divergences_declarees = set()

def joue(nom, kw, fx, gestes=None):
    global bloc, passe, appels_tot
    d, data = monte(COTE, re.sub(r"\W+", "_", nom), **kw)
    tours = range(len(gestes) + 2) if gestes else (1, 2)
    for tour in tours:
        if gestes and tour > 0:
            g = gestes[tour - 1] if tour - 1 < len(gestes) else touche
            g(d, tour * 100)
        code, msg, appels = lance(ARGV, d, data, fx)
        if not GEL:
            appels = rend_empreinte_figee(appels)
        if code == 2: bloc += 1
        else: passe += 1
        appels_tot += len(appels)
        m = neutralise_todo(msg.replace(str(d), "<D>")) if isinstance(msg, str) else msg
        produit["%s · tour %d" % (nom, tour)] = {
            "code": code, "message": m, "appels": appels}
    produit["%s · état" % nom] = etat_normalise(d, data)
    return d

# DEUX PASSAGES AU MOINS : beaucoup de gardes ne mordent qu'au second (témoin de
# première rencontre, deux échecs consécutifs, garde anti-boucle).
for nom, kw, fx in CAS:
    joue(nom, kw, fx)
for nom, kw, fx, gestes in CAS_MULTI:
    joue(nom, kw, fx, gestes)

# CE QUE LE CONTRÔLE A VRAIMENT TRAVERSÉ. Sans ce compte, « aucun écart » se lit
# comme « les onze gardes sont portées », alors que six seulement avaient été
# atteintes au premier essai.
vues = set()
for f in S.glob(COTE + "_*/data/attente/blocages.log"):
    for l in f.read_text().splitlines():
        c = l.split("\t")
        if len(c) >= 3: vues.add(c[2])
# LA LISTE DES GARDES QUE CE BANC ÉPROUVE, et rien d'autre. Elle se compare au
# code : le 23/09/2026, `attente.rs` portait QUATORZE gardes et cette liste en
# nommait ONZE. Le contrôle affichait donc « 11/11 » — vert, complet, faux. Un
# dénominateur écrit en dur ne peut pas signaler ce qu'il ignore.
# B2, B3 et B4-demande lisaient les Rappels : retirées avec eux le 08/10/2026.
TOUTES = {"B1-code-sans-todo","B5-carnet",
          "B6-faits","B7-constat-sans-rejeu","B8-forme","B8-motif","B9-tombe","B10-rechutes",
          "B11-acharnement","B13-poser"}
# CE QUE CE BANC N'ÉPROUVE PAS, ET QUI SE DIT AU LIEU DE SE TAIRE. Les deux
# suivants existent dans le programme et aucun cas ne les déclenche ici. Les
# omettre de `TOUTES` rendait le verdict vert en les ignorant — c'est la forme
# exacte du défaut que ce fichier est censé attraper. Les y mettre ferait
# échouer un contrôle qui, par ailleurs, mesure bien. On les DÉCLARE donc :
# « pas mesuré » n'est ni « bon » ni « mauvais », et les trois se ressemblent en
# sortie.
SANS_BANC = {"B4-cible", "B12-contredit", "B14-notion", "B15-synchro"}  # B14 : controles/notion.sh · B15 : controles/synchro.sh
manque = TOUTES - vues
if manque:
    ecarts.append("GARDES JAMAIS ATTEINTES, donc jamais comparées : "
                  + ", ".join(sorted(manque)))
print("gardes traversées : %d/%d — %s"
      % (len(vues & TOUTES), len(TOUTES), ", ".join(sorted(vues & TOUTES))))
# Le code est la source, pas cette liste : si un garde neuf apparaît sans être
# rangé dans l'une des deux, on le dit plutôt que de l'ignorer.
_src = pathlib.Path(__file__).resolve().parent.parent/"harnais"/"src"/"attente.rs"
if _src.is_file():
    _codes = set(re.findall(r'Some\("(B\d+-[a-z-]+)"\)', _src.read_text(encoding="utf-8")))
    _inconnus = _codes - TOUTES - SANS_BANC
    if _inconnus:
        ecarts.append("GARDES DU PROGRAMME ABSENTS DE CE BANC ET NON DÉCLARÉS : "
                      + ", ".join(sorted(_inconnus))
                      + " — les ajouter à TOUTES s'ils sont éprouvés, à SANS_BANC sinon")
if SANS_BANC:
    print("  jamais éprouvés par ce banc, donc NI bons NI mauvais : %s"
          % ", ".join(sorted(SANS_BANC)))
if divergences_declarees:
    print("divergence VOULUE (le relecteur n'existe que côté Rust) : "
          + ", ".join(sorted(divergences_declarees)))
print(f"témoins : {bloc} blocages et {passe} passages · "
      f"{appels_tot} appels au téléphone"
      + ("" if bloc and passe else "   ← TÉMOIN RATÉ"))
if appels_tot:
    ecarts.append("LES RAPPELS SONT ENCORE APPELÉS : %d appel(s) journalisé(s) par "
                  "le faux téléphone — la fin de tour ne doit plus rien y écrire "
                  "ni y lire (décision du 08/10/2026)" % appels_tot)
print()
# UNE EXCEPTION DOIT SERVIR, SINON ELLE CACHE AUTRE CHOSE. Si plus aucun message
# ne nomme de todo, c'est que Python a été corrigé, retiré, ou que les messages
# ont changé : dans les trois cas la neutralisation ci-dessus n'a plus de raison
# d'être et doit partir, plutôt que de rester à masquer un écart futur.
# UNE TABLE VIDE N'EST PAS UNE TABLE PÉRIMÉE. Ce garde existe pour attraper une
# correspondance qui ne masque plus rien et qu'on aurait laissée traîner — il
# avait raison de mordre tant que la table portait une entrée morte. Une table
# délibérément RETIRÉE n'a rien à signaler : c'est l'état d'arrivée, pas l'oubli.
if not GEL and SCRIPT_REPARE and _repares[0] == 0:
    ecarts.append("témoin : l'empreinte du script d'effacement réparé n'a servi "
                  "à AUCUN appel — le script a encore changé, ou ne passe plus "
                  "par ici. Revoir SCRIPT_REPARE plutôt que de le laisser masquer.")
elif not GEL:
    print(f"divergence VOULUE (script d'effacement réparé le 11/09) : "
          f"{_repares[0]} appel(s) rendus à l'empreinte figée")
if _masques[0] == 0:
    ecarts.append("témoin : la neutralisation du chemin du todo n'a RIEN masqué — "
                  "elle ne sert plus. La retirer, et comparer à nouveau ces "
                  "messages au caractère près.")
else:
    print(f"témoin : chemin du todo neutralisé {_masques[0]} fois "
          f"(divergence Python attendue, voir l'en-tête)")

MASQUE = [(str(S), "<bac>")]


def chemins_en_slash(v):
    """SOUS WINDOWS, UN CHEMIN DU BAC S'ÉCRIT EN `\\` : le masque le remplaçait
    par `<bac>` mais laissait la suite en `\\rs_x\\data\\…`, et chaque cas qui
    cite un fichier différait du témoin (mesuré le 28/10/2026). On écrit la
    suite du chemin en `/`, comme sur le Mac où le témoin est figé. Le masque
    lui-même ne suffit pas : le témoin passe la sortie en JSON AVANT de
    masquer, et les `\\` y sont doublés — `<bac>` est donc posé ici."""
    if isinstance(v, str):
        return re.sub(re.escape(str(S)) + r"[^\s\"'`»)]*",
                      lambda m: "<bac>" + m.group(0)[len(str(S)):].replace("\\", "/"), v)
    if isinstance(v, dict):
        return {k: chemins_en_slash(x) for k, x in v.items()}
    if isinstance(v, list):
        return [chemins_en_slash(x) for x in v]
    return v


if os.name == "nt":
    produit = {k: chemins_en_slash(v) for k, v in produit.items()}
if GEL:
    if ecarts or not (bloc and passe):
        # Un gel refusé DIT ce qui manque : sans ces trois chiffres, « témoin
        # manquant » couvrait aussi bien un vrai trou qu'un lanceur mort.
        detail = ecarts or ["aucun écart relevé, mais le banc n'a pas mordu : "
                            "%d blocage(s), %d passage(s) — il en faut au "
                            "moins un de chaque" % (bloc, passe)]
        raise SystemExit("GEL REFUSÉ :\n  " + "\n  ".join(detail))
    cas = [(n, "bac fabriqué", v) for n, v in produit.items()]
    f = temoins.fige("attente", cas,
                     ("code sans todo · tour 1", "todo à jour · tour 1")
                     if "code sans todo · tour 1" in produit and "todo à jour · tour 1" in produit
                     else (list(produit)[0], list(produit)[-1]),
                     # Le relais `.cmd` de Windows n'est qu'un passe-plat :
                     # la source jugée reste le lanceur du paquet.
                     [str(pathlib.Path(__file__).resolve().parent.parent / "bin" / "harnais")
                      if RS.endswith(".cmd") else RS], MASQUE, origine="rust")
    print("témoin figé :", f)
    sys.exit(0)

e2, ligne = temoins.compare("attente", produit, MASQUE)
ecarts = ecarts + e2
print(ligne)
print()
print("\n\n".join(ecarts[:14]) or f"ÉCARTS : AUCUN sur {len(CAS)+len(CAS_MULTI)} cas")
if len(ecarts) > 14: print(f"\n… et {len(ecarts)-14} autres écarts")
sys.exit(1 if ecarts else 0)
