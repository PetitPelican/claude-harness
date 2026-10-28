#!/usr/bin/env python3
"""LA MOITIÉ DE LA PASSE QUI NE JUGE RIEN — donc la seule que l'auteur puisse
faire sur son propre travail sans se mentir.

Elle ne demande jamais « est-ce bien ? ». Elle demande « est-ce branché, est-ce
rejoué, est-ce que ça correspond ». Le jugement du fond est ailleurs, et il ne
peut pas être ici.

Six questions, et les six sont des pièges que ce poste a déjà payés :
  ① les contrôles passent-ils DEPUIS UN DOSSIER VIDE — pas depuis l'état où je
     les ai laissés, qui contient peut-être ce qui les fait passer ;
  ② le programme livré répond-il, et annonce-t-il le paquet et son code ;
  ③ ce que j'ai ajouté aujourd'hui a-t-il un APPELANT — « un mécanisme sans
     appelant se lit comme présent », quatre fois cette semaine ;
  ④ une déclaration qui ne trouve pas son programme le DIT-elle ;
  ⑤ chaque voie du code a-t-elle une déclaration qui l'alimente ;
  ⑥ le paquet INSTALLÉ correspond-il au dépôt.

QUAND LA LANCER : avant de demander à l'humain de publier, sur le source
enregistré. COMMENT : `python3 controles/passe-mecanique.py <dossier jetable>`,
en chemin ABSOLU — un argument qui commence par un tiret est pris pour un
dossier (`--help` en a créé un dans le dépôt le 26/09/2026). Elle relance tous
les contrôles, donc réécrit leur verdict.
"""
import json, pathlib, re, subprocess, sys, shutil

ICI = pathlib.Path(__file__).resolve().parent
R = ICI.parent
S = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/passe")
echecs, notes = [], []

def dit(ok, quoi, detail=""):
    print("  %-58s %s%s" % (quoi, "oui" if ok else "NON", "  " + detail if detail else ""))
    if not ok: echecs.append(quoi)

print("① les contrôles, depuis un dossier VIDE")
shutil.rmtree(S, ignore_errors=True); S.mkdir(parents=True)
r = subprocess.run(["python3", str(ICI/"tous-les-controles.py"), str(S)],
                   capture_output=True, text=True)
# LE PROGRAMME LIVRÉ EST À PART, comme dans le verdict : avant que la chaîne
# ait construit ce source, il est en écart par construction. Compter les
# autres ligne à ligne, et non par le code de sortie, qui les mêle.
# (Cassé jusqu'au 26/09/2026 : elle exigeait « /11 » en dur, le banc en était
# à « 12/12 », et elle tombait sur une exception au lieu de répondre.)
lignes = r.stdout.splitlines()
autres = [l.split("  ")[0].strip() for l in lignes
          if re.match(r"^\S.{0,23}\s+ÉCART", l)]
total = [l for l in lignes if re.match(r"^\d+ contrôle\(s\) en écart sur \d+", l)]
dit(bool(total) and not autres, "tous les contrôles passent sur un état neuf",
    (", ".join(autres) + " — " if autres else "") + (total[-1] if total
    else "le lanceur n'a pas rendu son total : %s" % (r.stderr.strip().splitlines() or ["?"])[-1]))
g = [re.search(r"gardes traversées : (\d+)/(\d+)", l) for l in lignes]
g = [m for m in g if m]
n, d = (int(g[0].group(1)), int(g[0].group(2))) if g else (0, 0)
dit(g and n == d and d >= 10, "chaque garde de fin de tour qui a un banc est traversée",
    "%d/%d" % (n, d) if g else "le banc n'a pas dit combien")

print("② le programme livré correspond-il à son source")
# DEPUIS LE RETOUR EN PYTHON (12/10/2026), le programme est son source : un
# lanceur (`bin/harnais`) et `py/*.py`. La question « Mac et Windows viennent-ils
# du même état » n'a plus d'objet — il n'y a plus rien à construire. Reste à
# savoir si le lanceur répond, et s'il annonce le paquet ET le code qu'on lit.
LANCEUR = R/"bin"/"harnais"
dit(LANCEUR.exists(), "le lanceur du programme est livré")
import hashlib
h = hashlib.sha1()
for f in sorted((R/"py").glob("*.py")):
    h.update(f.name.encode()); h.update(f.read_bytes())
dite = subprocess.run(["sh", str(LANCEUR), "version"],
                      capture_output=True, text=True).stdout.split()
attendue_v = json.loads((R/".claude-plugin"/"plugin.json").read_text())["version"]
# LA VERSION QUE LE PROGRAMME ANNONCE EST-ELLE CELLE DU PAQUET ?
# Trouvé le 10/09/2026 sur un poste Windows : paquet installé en 0.1.2, et le
# programme répondait 0.1.0 — `version` ne permettait pas de savoir ce qui tourne.
dit(bool(dite) and dite[0] == attendue_v,
    "le programme livré annonce la version du paquet",
    "il dit %s, le paquet dit %s" % (dite[0] if dite else "rien", attendue_v))
dit(len(dite) > 1, "il annonce l'empreinte du code qu'il exécute",
    dite[1] if len(dite) > 1 else "rien")
notes.append("empreinte annoncée %s ; calcul indépendant (nom+contenu) %s — deux recettes, "
             "comparées par `binaire livré` du lanceur des contrôles"
             % (dite[1] if len(dite) > 1 else "?", h.hexdigest()[:12]))

# Et le diagnostic répond — c'est la seule sous-commande qu'on lance sur un
# poste inconnu, donc celle dont le silence coûterait le plus cher.
diag = subprocess.run(["sh", str(LANCEUR), "diagnostic", str(R)],
                      capture_output=True, text=True).stdout
dit("QUI TOURNE" in diag and "LE PROJET" in diag,
    "le diagnostic répond et nomme ses sections",
    "%d lignes rendues" % len(diag.splitlines()))

print("③ ce que j'ai ajouté a-t-il un appelant")
src = {p.name: p.read_text() for p in (R/"py").glob("*.py")}
tout = "\n".join(src.values())
# `main.py` appelle les points d'entrée par leur NOM (sa table) : un nom cité
# entre guillemets y vaut un appel.
table = set(re.findall(r'\("\w+", "(\w+)", "(?:stdin|args|code)"\)', src["main.py"]))
orphelines = []
for f, t in src.items():
    for m in re.finditer(r"^def ([a-z]\w*)", t, re.M):
        nom = m.group(1)
        if nom in ("main", "essai") or nom in table: continue
        # appelée ailleurs que dans sa propre déclaration ?
        n_app = len(re.findall(r"\b%s\s*\(" % re.escape(nom), tout))
        if n_app <= 1:
            orphelines.append("%s.%s" % (f[:-3], nom))
dit(not orphelines, "aucune fonction publique sans appelant",
    ", ".join(orphelines) if orphelines else "")
sous = set(re.findall(r'^\s*"([a-z-]+)":\s*\(', src["main.py"], re.M))
dit(len(sous) >= 15, "le contrôle a bien LU les sous-commandes", "%d lues" % len(sous))
appelees = set()
declarees = set()
# DEPUIS LA BASCULE DU 10/09, LE CTO NE DÉCLARE PLUS SES HOOKS LUI-MÊME : ils
# viennent du paquet. Un fichier de réglages sans clé `hooks` est donc l'état
# NORMAL, pas une anomalie — mais il ne doit pas faire passer le contrôle en
# silence, d'où le témoin plus bas qui exige au moins une déclaration trouvée.
for f in (R/"hooks"/"hooks.json", pathlib.Path.home()/"Agentic/CTO/.claude/settings.json"):
    d = json.loads(f.read_text())
    for l in d.get("hooks", {}).values():
        for m in l:
            for h in m.get("hooks", []):
                declarees |= set(re.findall(r'exec (?:sh )?"\$b" ([a-z-]+)', h["command"]))
# Les appelants ne sont pas tous des hooks : les sous-commandes de diagnostic
# sont appelées par les contrôles, d'autres par les compétences (plus bas).
# Oublier une source d'appels fabrique un faux « code mort » — et on finit par
# retirer ce qui servait.
p2 = pathlib.Path(__file__).read_text()   # ce fichier appelle aussi le programme
ctrl = "\n".join(f.read_text() for f in
                 list(ICI.glob("*.py")) + list((R/"skills").rglob("*.py")))
par_controle = set(re.findall(r'RS, "([a-z-]+)"', ctrl)) | set(re.findall(r'(?:arm64"|LANCEUR)\), "([a-z-]+)"', ctrl + p2)) | set(re.findall(r'"([a-z][a-z-]+)", str\(p\)', ctrl)) | set(re.findall(r'prog\), "([a-z-]+)"', ctrl)) | set(re.findall(r'"relecture", "--sec"', ctrl) and ["relecture"])
# TROIS SOURCES D'APPELS DE PLUS, le 26/09/2026 — la passe criait « onze
# sous-commandes sans appelant », dont huit en avaient un :
#  · une COMPÉTENCE qui fait taper `harnais x` à un agent l'appelle, autant
#    qu'un hook (adopte, equipe, menage…) ;
#  · les outils du POSTE appellent le programme (atelier/src) — `harnais rappels`
#    jusqu'au 08/10/2026, retiré avec les Rappels ;
#  · un contrôle en shell écrit `"$B" x`, que l'expression Python ne voyait pas.
# Et le mode d'emploi, qui fait taper une commande à un HUMAIN, compte aussi :
# ce qui n'est ni appelé ni documenté nulle part, voilà le code mort.
def cites(t):
    out = set(re.findall(r"`harnais ([a-z][a-z-]*)", t))
    bloc = False
    for l in t.splitlines():
        if l.strip().startswith("```"):
            bloc = not bloc; continue
        m = bloc and re.match(r"^\s*harnais ([a-z][a-z-]*)", l)
        if m: out.add(m.group(1))
    return out
par_competence = set().union(*(cites(f.read_text()) for f in (R/"skills").rglob("*.md")))
par_poste = set(re.findall(r'harnais(?:_json)?\(&\["([a-z-]+)"', "\n".join(
    f.read_text() for f in (R/"atelier"/"src").rglob("*.rs"))))
par_controle |= set(re.findall(r'"\$B" ([a-z][a-z-]+)', "\n".join(
    f.read_text() for f in ICI.glob("*.sh"))))
par_humain = cites((R/"README.md").read_text()) | cites((R/"COMMENT-CA-MARCHE.md").read_text())
jamais = (sous - declarees - appelees - par_controle - par_competence - par_poste
          - par_humain - {"version", "--version", "-V"})
dit(len(declarees) >= 5, "le contrôle a bien LU des déclarations",
    "%d sous-commande(s) déclarée(s)" % len(declarees))
# TÉMOIN : chaque source doit avoir rendu quelque chose, sinon son expression
# est aveugle et la passe retomberait sur le faux « code mort ».
vides = [n for n, s in (("compétences", par_competence), ("poste", par_poste),
                        ("mode d'emploi", par_humain)) if not s]
dit(not vides, "chaque source d'appels a rendu au moins un appel",
    ("aveugle : " + ", ".join(vides)) if vides else "%d par les compétences, %d par le poste, "
    "%d par le mode d'emploi" % (len(par_competence), len(par_poste), len(par_humain)))
dit(not jamais, "aucune sous-commande sans appelant ni mode d'emploi", ", ".join(sorted(jamais)))

print("④ une déclaration qui ne trouve pas son programme le DIT-elle ?")
# LA QUESTION S'EST INVERSÉE LE 10/09/2026, ET C'EST LE POINT DU LOT 1.
#
# Elle était : « chaque mécanisme a-t-il un repli Python qui existe ? ». Le repli
# a été supprimé — il supposait un interpréteur que la machine d'arrivée n'a pas
# toujours, ce qui est la panne qu'on voulait éliminer. Reste alors le vrai
# danger, et il était DÉJÀ là avant : la ligne se terminait par `exit 0`. Un
# programme manquant faisait donc disparaître le garde SANS UN MOT — le succès
# apparent, la maladie de cet atelier.
#
# On exige maintenant deux choses de chaque déclaration : qu'elle ne finisse
# jamais en `exit 0` silencieux, et qu'elle écrive sur la sortie d'erreur ce
# qu'on perd. Le garde de commit, lui, doit REFUSER : `exit 2`.
muets = []
for f in (R/"hooks"/"hooks.json", pathlib.Path.home()/"Agentic/CTO/.claude/settings.json"):
    if not f.exists():
        continue
    d = json.loads(f.read_text())
    for ev, l in d.get("hooks", {}).items():
        for m in l:
            for h in m.get("hooks", []):
                c = h["command"]
                if ".py" in c and "guard-" not in c:
                    muets.append("%s:%s appelle encore du Python" % (f.name, ev)); continue
                if "harnais" not in c:
                    continue          # une déclaration qui ne vise pas le paquet
                if re.search(r"exit 0\s*$", c):
                    muets.append("%s:%s se tait quand le programme manque" % (f.name, ev))
                elif ">&2" not in c:
                    muets.append("%s:%s ne dit rien sur la sortie d'erreur" % (f.name, ev))
                elif ev == "PreToolUse" and not re.search(r"exit 2\s*$", c):
                    muets.append("%s:%s laisse passer au lieu de refuser" % (f.name, ev))
dit(not muets, "un programme manquant se dit, et le garde refuse", "; ".join(muets))

print("⑤ le code se branche sur un outil — cet outil est-il déclaré ?")
# TROUVÉ LE 10/09/2026, ET C'EST LE PIÈGE D'HIER REMONTÉ D'UN CRAN. `usage.rs`
# se branche sur `tool_name == "Bash"` depuis la veille ; la déclaration qui
# fait arriver ces charges vivait dans le fichier de réglages du CTO — que la
# bascule vers le paquet a supprimé. Le code savait compter les lectures faites
# par le shell, et plus rien ne l'appelait sur ce chemin. Ni le compilateur ni
# les contrôles différentiels ne peuvent le voir : eux passent la charge à la
# main. Seule la DÉCLARATION dit quelles charges arriveront vraiment.
decl = json.loads((R/"hooks"/"hooks.json").read_text())["hooks"]
pose = set()
for ev, gs in decl.items():
    for g in gs:
        for h in g.get("hooks", []):
            sc = re.search(r'exec (?:sh )?"\$b" ([\w-]+)', h.get("command", ""))
            if sc:
                pose.add((sc.group(1), g.get("matcher")))
manquants = []
branches = 0
for f in sorted((R/"py").glob("*.py")):
    src = f.read_text()
    sub = f.stem.replace("_", "-")
    for o in sorted(set(re.findall(r'tool_name"\)\s*==\s*"(\w+)"', src))):
        branches += 1
        if (sub, o) not in pose:
            manquants.append("%s se branche sur %s, non déclaré" % (sub, o))
dit(branches > 0, "le contrôle a bien LU des branchements sur un outil", "%d lu(s)" % branches)
dit(not manquants, "chaque voie du code a une déclaration qui l'alimente",
    "; ".join(manquants))

print("⑥ le paquet INSTALLÉ correspond-il au dépôt ?")
# MESURÉ LE 10/09/2026 : correction poussée, catalogue rafraîchi, et
# `plugin update` répond « déjà à la dernière version ». Le cache est épinglé
# par le NUMÉRO DE VERSION, jamais par le contenu — la machine gardait
# l'ancienne déclaration sans que rien ne le dise. C'est « un binaire livré
# peut se périmer sans le dire », remonté d'un cran : ici c'est le PAQUET.
manif = json.loads((R/".claude-plugin"/"plugin.json").read_text())
attendue = manif["version"]
cache = pathlib.Path.home()/".claude/plugins/cache/atelier/harnais"/attendue
dit(cache.is_dir(), "la version du dépôt est installée", "attendue %s" % attendue)
if cache.is_dir():
    ecarts = []
    rels = ["hooks/hooks.json", "bin/harnais", "rechutes.md",
            "criteres-relecture.md"]
    rels += ["py/" + f.name for f in sorted((R/"py").glob("*.py"))]
    rels += ["hooks/" + f.name for f in sorted((R/"hooks").glob("*.py"))]
    for rel in rels:
        a, b = R/rel, cache/rel
        if not b.exists():
            ecarts.append("%s absent du paquet" % rel)
        elif a.read_bytes() != b.read_bytes():
            ecarts.append("%s diffère" % rel)
    dit(not ecarts, "ce que le paquet livre est ce que le dépôt contient",
        "; ".join(ecarts))

# IL N'Y A PLUS DE COPIE À COMPARER — ET C'EST ÇA QU'ON VÉRIFIE.
#
# Cette question était : « le repli Python du poste est-il celui du dépôt ? ».
# Trois copies existaient — dépôt, repli du poste, paquet installé — et deux
# fois en deux jours une correction écrite dans le dépôt avait été jouée contre
# `~/.claude/hooks`, donc contre un autre code.
#
# Le 10/09/2026, le lot 1 a supprimé le repli : la question n'a plus d'objet.
# Mais une boucle sur un dossier vide rend « rien à signaler », c'est-à-dire le
# même verdict qu'un repli parfaitement synchronisé — ne rien voir n'est pas un
# succès. On retourne donc la question : plus AUCUN hook Python ne doit exister,
# nulle part. Le jour où quelqu'un en repose un, ce point le dira.
morts = []
for d in (R/"hooks", pathlib.Path.home()/".claude/hooks"):
    for f in sorted(d.glob("*.py")) if d.is_dir() else []:
        morts.append(str(f).replace(str(pathlib.Path.home()), "~"))
dit(not morts, "aucun hook Python ne subsiste — ni au dépôt, ni sur le poste",
    "; ".join(morts))

print()
for x in notes:
    print("  note : " + x)
print(("PASSE MÉCANIQUE : %d point(s) en échec — " % len(echecs)) + " · ".join(echecs)
      if echecs else "PASSE MÉCANIQUE : rien à signaler")
sys.exit(1 if echecs else 0)

