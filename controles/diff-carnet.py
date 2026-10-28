"""CONTRÔLE SUR TÉMOIN — le carnet d'équipe.

Il lisait LE CARNET RÉEL d'un projet. Deux raisons de ne plus le faire au moment
de figer (lot 0, 10/09/2026) :

- **un différentiel sur l'état vivant ne prouve que les chemins que le jour
  emprunte** — et un TÉMOIN figé sur l'état vivant est pire : il périme en
  silence dès que cet agent écrit une ligne de plus ;
- figer le carnet d'un projet réel, ce serait recopier la mémoire d'un autre agent
  dans ce dépôt-ci. Règle 1.

Le corpus est donc FABRIQUÉ, et il reproduit les formes relevées dans le vrai
carnet le 10/09/2026 : les deux issues (`abouti`, `échoué`), les trois niveaux,
les trois marqueurs `↗ ↻ ↩` — dont un `↗` sur deux lignes et un `↻` de chaque
source —, un titre barré, un agent SANS fichier, et un registre `.lu` déjà
rempli. Ce qu'un corpus ne SÉPARE pas, il ne le prouve pas : chaque forme est
donc présente ET absente quelque part.

DEUX SEUILS SONT JOUÉS DE PART ET D'AUTRE, à l'unité :
- la fenêtre du résumé (48 h) : une entrée à −47 h, une à −50 h ;
- l'oubli de la confiance : une note vue il y a 29 j, une à 31 j. Depuis les
  trois natures (11/09/2026) ce n'est plus UN seuil mais un par nature — 15 j
  pour une croyance, 45 j pour une expérience —, et ce corpus les joue d'un
  seul côté chacun ; les deux côtés, à l'unité, sont éprouvés dans le
  programme lui-même (`l_oubli_suit_la_nature_de_part_et_d_autre_de_chaque_seuil`).

LES DATES SONT RELATIVES À MAINTENANT, et masquées une par une dans le témoin
(`<auj>`, `<auj-29>`…). Un témoin daté en dur aurait cessé de valoir à minuit ;
un témoin dont toutes les dates seraient réduites au même jeton ne verrait plus
une date fausse.
"""
import datetime, hashlib, json, shutil, subprocess, pathlib, sys
import os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import temoins

S   = pathlib.Path(sys.argv[1])/"carnet"
RS  = os.environ.get("HARNAIS_BIN") or str(pathlib.Path.home()/"Agentic/claude-harnais/bin/harnais")
# Le programme comparé doit avoir DÉMARRÉ avant qu'on juge quoi que ce soit :
# un lanceur mort rend une sortie qu'on confondrait avec un verdict (23/09/2026).
temoins.exige_que_ca_demarre([RS])
GEL = temoins.gel_demande()
PYH = pathlib.Path.home()/".claude/hooks/carnet.py"

MAINTENANT = datetime.datetime.now()
AUJ = MAINTENANT.date()

# La surcouche de confiance du corpus : (entrée, n, mouvements, niveau, vue il y
# a N jours). AU NIVEAU DU MODULE pour que l'oracle des natures la relise —
# c'est depuis le CORPUS qu'il prédit, jamais depuis ce que le témoin a gravé.
ORPHELINE = "ffffffffffff"      # une confiance dont l'entrée n'existe pas
CONF_CORPUS = [(("Alpha QA", 1),  84.1, 12, "mesuré",  0),
               (("Alpha QA", 10), 67.6, 4,  "supposé", 29),
               (("Alpha PO", 47), 80,   5,  "observé", 31),
               (None,              50,   1,  "observé", 31)]

def slug(nom):
    return nom.replace(" ", "-")

def texte_de(titre, extra):
    """LE TEXTE QUE LE LECTEUR RECOMPOSE, pas celui qu'on croit avoir écrit.

    Le parseur retire les lignes qui COMMENCENT par `↗ ↻ ↩` et recolle le
    reste. Une transmission qui court sur deux lignes laisse donc sa SECONDE
    ligne dans le texte — et le texte décide de l'empreinte. Calculer
    l'empreinte sur le seul titre rend un identifiant qui n'existe nulle part,
    donc un masque qui ne masque rien, donc un témoin qui clignote.
    Mesuré le 10/09/2026 : l'entrée à −10 h en portait une.
    """
    lignes = [titre] + [x for x in extra if not x.lstrip().startswith(("↗", "↻", "↩"))]
    return " ".join(x.strip() for x in lignes if x.strip())


def empreinte(date, heure, auteur, texte):
    """RECALCULÉE ICI, exprès. Le contrôle ne doit pas emprunter au code qu'il
    juge la fonction qui décide de l'identité des entrées."""
    return hashlib.sha1(("%s %s|%s|%s" % (date, heure, auteur, texte[:120]))
                        .encode("utf-8")).hexdigest()[:12]

# ── le corpus fabriqué ────────────────────────────────────────────────────
def t(heures):
    return MAINTENANT - datetime.timedelta(hours=heures)

# (agent, heures avant maintenant, issue, niveau, titre, corps supplémentaire)
ENTREES = [
 ("Alpha QA",  1,  "abouti", "mesuré",
  "~~ **Une tâche barrée, comme le vrai carnet en porte**~~",
  ["↗ Alpha PO : une transmission qui tient sur une seule ligne.",
   "↻ machine :: git rev-list --count origin/production..origin/main :: ^0$",
   "↩ aaaaaaaaaaaa"]),
 ("Alpha QA", 10,  "échoué", "supposé",
  "Une issue qui n'est pas « abouti », et un niveau jamais vu ailleurs",
  ["↗ Alpha OPS : une transmission qui court sur deux lignes, parce que le",
   "vrai carnet en porte et que le repli de ligne a déjà cassé un lecteur.",
   "↻ service :: curl -s -o /dev/null -w '%{http_code}' https://x/contact :: ^404$"]),
 ("Alpha PO", 47,  "abouti", "observé",
  "À l'INTÉRIEUR de la fenêtre du résumé, à une heure près",
  ["↗ Alpha QA : dans les 48 h.", "↩ bbbbbbbbbbbb", "↩ cccccccccccc"]),
 ("Alpha PO", 50,  "abouti", "observé",
  "AU-DELÀ de la fenêtre du résumé, à deux heures près",
  ["↗ Alpha QA : hors des 48 h — cette ligne ne doit PAS être résumée."]),
 ("Alpha OPS", 3,  "abouti", "mesuré",
  "Une entrée sans aucun marqueur : ni transmission, ni rejeu, ni acquittement",
  []),
]
AGENTS = ["Alpha QA", "Alpha PO", "Alpha OPS", "CTO"]   # CTO n'a AUCUN fichier

def monte(d):
    shutil.rmtree(d, ignore_errors=True)
    (d/".etat").mkdir(parents=True)
    ids = {}
    for agent, h, issue, niveau, titre, extra in ENTREES:
        q = t(h)
        f = d/("%s-%s.md" % (q.strftime("%Y-%m"), slug(agent)))
        bloc = []
        if not f.exists():
            bloc += ["# Carnet d'équipe — %s · %s" % (agent, q.strftime("%B %Y")), "",
                     "Écrit par le hook `attente` quand une tâche cochée porte `↗`.",
                     "**En ajout seul** : on n'y réécrit rien, on n'y supprime rien.", ""]
        bloc.append("## %s %s · %s · %s · %s"
                    % (q.strftime("%Y-%m-%d"), q.strftime("%H:%M"), agent, issue, niveau))
        bloc.append(titre)
        bloc += extra
        bloc.append("")
        with f.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(bloc) + "\n")
        ids[(agent, h)] = empreinte(q.strftime("%Y-%m-%d"), q.strftime("%H:%M"),
                                    agent, texte_de(titre, extra))
    # LA SURCOUCHE DE CONFIANCE, avec les deux côtés du seuil d'oubli.
    def j(n): return (AUJ - datetime.timedelta(days=n)).isoformat()
    conf = {(ids[qui] if qui else ORPHELINE): {"n": n, "m": m, "niveau": niv, "vu": j(jours)}
            for qui, n, m, niv, jours in CONF_CORPUS}
    (d/".etat/confiance.json").write_text(
        json.dumps(conf, ensure_ascii=False, indent=1) + "\n")
    # UN REGISTRE DÉJÀ REMPLI : l'agent a déjà vu une entrée, pas les autres.
    (d/(".etat/%s-sess-A.lu" % slug("Alpha OPS"))).write_text(
        ids[("Alpha QA", 1)] + "\n")
    return ids

# LES EMPREINTES D'ENTRÉE SONT DES HACHÉS DE LA DATE : elles changent à chaque
# minute qui passe. Sans ce masque, le témoin figé à 20 h 41 échouerait à 20 h 42
# — et on apprendrait à ignorer un contrôle rouge, ce qui est pire que pas de
# contrôle. Chaque empreinte reçoit son propre jeton : une empreinte FAUSSE
# resterait donc visible.
def _ids_attendus():
    out = {}
    for agent, h, issue, niveau, titre, extra in ENTREES:
        q = t(h)
        out[(agent, h)] = empreinte(q.strftime("%Y-%m-%d"), q.strftime("%H:%M"),
                                    agent, texte_de(titre, extra))
    return out

JETONS = {i: "<id-%s-%dh>" % (slug(agent), h)
          for (agent, h), i in _ids_attendus().items()}

def jeton(i):
    """UN TRI SUR UNE EMPREINTE N'EST PAS UN ORDRE, c'est un tirage. On trie
    donc sur le NOM stable, jamais sur le haché : sinon la liste change d'ordre
    à chaque exécution et le témoin clignote."""
    return JETONS.get(i, i)

MASQUE = [(str(S), "<bac>")]
for i, j in JETONS.items():
    MASQUE.append((i, j))
# LE JOUR NU D'UNE ENTRÉE N'A PAS DE MASQUE, ET C'EST VOULU.
# Il en a eu un — `<j-47h>` — et ce masque ne servait à rien : nulle part la
# sortie ne porte le jour d'une entrée tout seul, l'en-tête le donne toujours
# collé à son heure, et c'est le masque long qui l'attrape. Il ne mordait donc
# que par accident, sur les dates de la surcouche de confiance, qui sont
# `AUJ − n jours` et pas `maintenant − n heures`. Deux façons de nommer le même
# jour, et laquelle gagne dépend de l'HEURE à laquelle on joue : le témoin gelé
# à 21 h a enregistré `<j-1h>` là où le programme rejoué à 00 h 21 rendait
# `<auj>`. Un contrôle rouge, et rien n'avait bougé.
#
# TOUT CE QUI DÉRIVE DE « MAINTENANT » SE MASQUE — mais chaque chose UNE fois,
# par le masque qui nomme ce qu'elle est.
# Le témoin portait la date complète et l'heure, mais pas la date NUE : le
# lecteur la rend dans un champ à part.
#
# ET CE N'EST PAS L'HORLOGE QUI DOIT PASSER MINUIT, C'EST `maintenant − 47 h`.
# Témoin figé à 21 h le 10/09 : −47 h tombe le 08/09. Rejoué à 23 h le MÊME
# soir : −47 h tombe le 09/09. Deux heures d'écart, un jour de différence, et
# un contrôle qui rougit sans qu'une ligne ait bougé. J'avais d'abord écrit
# « à minuit » — c'est faux, et ça enverrait chercher au mauvais endroit :
# le décalage se produit à 48 h moins la profondeur du cas, pas à minuit.
#
# Du plus long au plus court, sinon le masque court mange le début du long.
for h in sorted({h for _, h, *_ in ENTREES}):
    MASQUE.append((t(h).strftime("%Y-%m-%d %H:%M"), "<t-%dh>" % h))
    MASQUE.append((t(h).strftime("%H:%M"), "<h-%dh>" % h))
for n in (0, 29, 30, 31):
    MASQUE.append(((AUJ - datetime.timedelta(days=n)).isoformat(),
                   "<auj>" if n == 0 else "<auj-%d>" % n))
MASQUE.append((AUJ.strftime("%Y-%m"), "<mois>"))

# ── les deux côtés ────────────────────────────────────────────────────────
def normalise_les_jours(v):
    """LE JOUR D'UNE ENTRÉE SE NOMME PAR L'ENTRÉE, jamais par sa valeur.

    Trois fois en deux jours, le témoin du carnet a rougi sans qu'une ligne ait
    bougé, et toujours pour la même raison de fond : **deux masques différents
    peuvent revendiquer la même chaîne de date, et lequel gagne dépend de
    l'HEURE à laquelle on joue.**

      · le jour d'une entrée vaut `maintenant − N heures` ;
      · une date de la surcouche de confiance vaut `AUJ − N jours` ;
      · et ces deux calculs tombent sur le même jour une partie du temps.

    Gelé à 21 h, le jour de l'entrée « −1 h » était hier et recevait `<j-1h>` ;
    rejoué à 00 h 21, il est aujourd'hui et reçoit `<auj>`. Puis, le masque
    `<j-Nh>` retiré, il est redevenu `<mois>-10` d'un côté et `<auj>` de
    l'autre. Chaque correction déplaçait la collision au lieu de la retirer.

    Un masque de TEXTE ne peut pas exprimer « ce champ est le jour de cette
    entrée-là » : il ne voit qu'une chaîne. On nomme donc le champ AVANT que
    les masques ne le voient, à partir de l'identité de l'entrée — qui, elle,
    ne dépend pas de l'heure. Le témoin cesse ainsi d'avoir une durée de vie.

    Ce qu'on garde malgré tout : une date d'entrée FAUSSE reste visible, parce
    que le jeton ne dit pas la date, il dit de QUI elle est. Deux entrées dont
    les dates seraient échangées produiraient deux jetons échangés.
    """
    if isinstance(v, dict):
        if "id" in v and "date" in v:
            v = dict(v, date="<jour de %s>" % jeton(v["id"]))
        return {k: normalise_les_jours(x) for k, x in v.items()}
    if isinstance(v, list):
        return [normalise_les_jours(x) for x in v]
    return v


def cote_python(d, agent):
    sys.path.insert(0, str(pathlib.Path.home()/".claude/hooks"))
    import carnet as C
    es = C.entrees(d)
    lignes, servis = C.resume(d, agent)
    return {"entrees": [{k: (v if k != "pour" else [list(x) for x in v])
                         for k, v in e.items() if k != "_rang"} for e in es],
            "resume": lignes, "servis": servis, "confiances": C.confiances(d)}

def cote_rust(d, agent):
    r = subprocess.run([RS, "carnet", str(d), agent], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else {"ERREUR": r.stderr[:300]}

produit = {}
for agent in AGENTS:
    d = S/("lecture_" + slug(agent))
    monte(d)
    v = normalise_les_jours(cote_python(d, agent) if GEL else cote_rust(d, agent))
    v["confiance.json"] = (d/".etat/confiance.json").read_text()
    produit["lecture-" + slug(agent)] = v

# ── les écritures : naissance, bouge, replancher, sert ────────────────────
d = S/"ecritures"; ids = monte(d)
liste = [ids[("Alpha QA", 1)], ids[("Alpha QA", 10)], ids[("Alpha PO", 47)]]
if GEL:
    sys.path.insert(0, str(pathlib.Path.home()/".claude/hooks"))
    import carnet as C
    for i, niveau in zip(liste, ("mesuré", "observé", "supposé")):
        C._naissance(d, i, niveau)
    C.bouge(d, liste, C.REUSSITE); C.bouge(d, liste[:1], C.ECHEC)
    C.replancher(d, liste[0], "TIENT"); C.replancher(d, liste[1], "TOMBÉ")
    C.replancher(d, liste[2], "MUET")
    C.sert(d, "CTO", "sess-1", liste)
    servi = sorted(jeton(x) for x in C.lu(d, "CTO", "sess-1"))
else:
    r = subprocess.run([RS, "carnet-essai", str(d), json.dumps(liste)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("sous-commande d'essai absente : %s" % r.stderr[:200])
    servi = sorted(jeton(x) for x in json.loads(r.stdout)["lu"])
produit["ecritures"] = {"confiance.json": (d/".etat/confiance.json").read_text(),
                        "servi": servi}

# ── témoins : le corpus doit avoir MORDU, sinon il ne prouve rien ─────────
alertes = []
qa = produit["lecture-Alpha-QA"]
if len(qa.get("entrees", [])) != len(ENTREES):
    alertes.append("TÉMOIN RATÉ — %d entrées lues sur %d fabriquées"
                   % (len(qa.get("entrees", [])), len(ENTREES)))
if not qa.get("resume"):
    alertes.append("TÉMOIN RATÉ — résumé vide : la fenêtre de 48 h n'a rien laissé passer")
if not qa.get("confiances"):
    alertes.append("TÉMOIN RATÉ — aucune confiance lue")
# LA LECTURE N'EST PAS CLOISONNÉE : un agent SANS carnet lit quand même celui
# des autres. Mesuré ici le 10/09/2026 — j'avais écrit l'inverse, et c'est le
# code qui avait raison. Ce qui doit différer, c'est ce que CHACUN reçoit.
if len(produit["lecture-CTO"].get("entrees", [])) != len(ENTREES):
    alertes.append("TÉMOIN RATÉ — un agent sans carnet ne lit pas celui des autres")
if produit["lecture-CTO"].get("resume") == qa.get("resume"):
    alertes.append("TÉMOIN RATÉ — deux agents reçoivent exactement le même résumé : "
                   "le corpus ne SÉPARE pas ce que chacun a déjà vu")

if GEL:
    if alertes:
        raise SystemExit("GEL REFUSÉ — le côté Python ne tient pas ses témoins :\n  "
                         + "\n  ".join(alertes))
    cas = [(n, "corpus fabriqué : %d entrées, 4 agents" % len(ENTREES), v)
           for n, v in produit.items()]
    f = temoins.fige("carnet", cas, ("lecture-Alpha-QA", "lecture-CTO"), [PYH], MASQUE)
    print("témoin figé :", f)
    sys.exit(0)

# LE JOUR D'UNE LIGNE DE RÉSUMÉ SE NOMME AUSSI PAR SON ENTRÉE.
# `normalise_les_jours` traitait le champ `date` des entrées ; les lignes du
# résumé portent la même date, écrite `MM-JJ` en tête de texte — et elle
# change de jour selon l'heure où l'on joue. Figé à 01 h 12, rejoué à 07 h 00
# le même jour : « 09-10 · Alpha OPS » d'un côté, « 09-11 » de l'autre, deux
# contrôles rouges et pas une ligne de code bougée (mesuré le 11/09/2026).
#
# On nomme la ligne par l'entrée qu'elle résume, retrouvée par un fragment de
# son texte. ET ON NE MASQUE QU'UNE DATE JUSTE : côté programme, la date doit
# valoir celle de l'entrée aujourd'hui, sinon on la laisse telle quelle — une
# date fausse reste un écart visible. Côté témoin, figé par Python, on nomme.
FRAGMENTS = {
    ("Alpha QA", 1): ("Une tâche barrée", "une transmission qui tient"),
    ("Alpha QA", 10): ("Une issue qui n", "une transmission qui court"),
    ("Alpha PO", 47): ("INTÉRIEUR de la fenêtre", "dans les 48 h"),
    ("Alpha PO", 50): ("AU-DELÀ de la fenêtre", "hors des 48 h"),
    ("Alpha OPS", 3): ("Une entrée sans aucun marqueur",),
}

def jours_des_lignes(texte, cote):
    import re
    def sub(m):
        jour, agent, reste = m.groups()
        qui = [h for (a, h), fr in FRAGMENTS.items()
               if a == agent and any(f in reste for f in fr)]
        if len(qui) != 1:
            return m.group(0)
        if cote == "produit" and jour != t(qui[0]).strftime("%m-%d"):
            return m.group(0)
        return "<jour-%dh> · %s · %s" % (qui[0], agent, reste)
    return re.sub(r'(\d\d-\d\d) · (Alpha QA|Alpha PO|Alpha OPS) · ((?:[^"\\]|\\.)*)',
                  sub, texte)

# ── LE SEUL CHANGEMENT DÉCLARÉ DEPUIS LE GEL : les trois natures (11/09/2026)
#
# Ce témoin est d'origine Python, et c'est ce qui le rend indépendant du
# programme qu'il juge. Le repli Python a gardé l'oubli PLAT — 30 j pour tout —
# et ne sera pas corrigé : il est condamné. Refiger sur le Rust ferait perdre au
# carnet ENTIER sa référence indépendante pour un changement qui ne touche
# qu'une fonction. On applique donc au témoin la seule règle qui a changé,
# énoncée ICI sans une ligne du programme, et on compare :
#   une entrée de carnet est une EXPÉRIENCE et attend 45 j avant l'oubli ;
#   une entrée « supposé » est une CROYANCE et en attend 15.
# Et la prédiction part du CORPUS, jamais de ce que le témoin a gravé : un
# oracle qui recopierait le témoin ne prédirait rien.
_oracle = {"a_mordu": False, "acquit": False}

def _apres_oubli(n, jours, niveau):
    delai = 15 if niveau in ("supposé", "suppose") else 45
    if jours > delai:
        return round(n * 0.97, 1), "<auj>"
    return n, ("<auj>" if jours == 0 else "<auj-%d>" % jours)

def natures(texte, cote):
    if cote != "temoin":
        return texte
    try:
        v = json.loads(texte)
    except ValueError:
        return texte
    if not isinstance(v, dict) or "confiances" not in v:
        return texte                    # « ecritures » : aucun oubli n'y joue
    predit = {}
    for qui, n, m, niv, jours in CONF_CORPUS:
        cle = ("<id-%s-%dh>" % (slug(qui[0]), qui[1])) if qui else ORPHELINE
        predit[cle] = (_apres_oubli(n, jours, niv), m)
    brut = v["confiance.json"]
    fichier = json.loads(brut)
    if json.dumps(fichier, ensure_ascii=False, indent=1) != brut.rstrip("\n"):
        raise SystemExit("ORACLE DES NATURES — le témoin ne se relit pas à l'octet : "
                         "il ne peut pas être réécrit sans mentir")
    for table in (v["confiances"], fichier):
        for cle, ((n, vu), _) in predit.items():
            if cle in table and (table[cle]["n"], table[cle]["vu"]) != (n, vu):
                table[cle]["n"], table[cle]["vu"] = n, vu
                _oracle["a_mordu"] = True
    v["confiance.json"] = (json.dumps(fichier, ensure_ascii=False, indent=1)
                           + ("\n" if brut.endswith("\n") else ""))
    # Le résumé affiche le chiffre d'une entrée qui a bougé au moins deux fois :
    # la ligne i résume l'entrée servie en i.
    import re
    for i, cle in enumerate(v.get("servis", [])):
        if cle in predit and predit[cle][1] >= 2 and i < len(v["resume"]):
            v["resume"][i] = re.sub(r" \((\d+)\) — ", " (%d) — " % round(predit[cle][0][0]),
                                    v["resume"][i], count=1)
    # SECOND ÉCART DÉCLARÉ, 12/09/2026 : la ligne qui demande d'acquitter porte
    # désormais l'empreinte à recopier. Python ne l'écrivait pas — le briefing
    # réclamait un identifiant qu'il ne montrait jamais, et le seul geste social
    # du carnet restait inerte. La ligne i résume l'entrée servie en i : c'est
    # d'elle que vient l'empreinte, jamais du témoin.
    for i, cle in enumerate(v.get("servis", [])):
        if i < len(v["resume"]) and "→ POUR TOI" in v["resume"][i] and "↩" not in v["resume"][i]:
            v["resume"][i] = v["resume"][i].replace("→ POUR TOI", "→ POUR TOI ↩ %s" % cle, 1)
            _oracle["acquit"] = True
    return json.dumps(v, ensure_ascii=False, sort_keys=True)

ecarts, ligne = temoins.compare("carnet", produit, MASQUE,
                                normalise=lambda x, c: jours_des_lignes(natures(x, c), c))
# L'ORACLE PORTE SON TÉMOIN DE PÉREMPTION : s'il ne change plus rien, le témoin
# a été refigé depuis le 11/09 et ce bloc est mort. Un bloc mort qui passe se
# lit comme une vérification.
if not _oracle["a_mordu"]:
    ecarts.append("ORACLE DES NATURES MORT — il ne change plus rien au témoin : "
                  "celui-ci a été refigé, retirer ce bloc")
if not _oracle["acquit"]:
    ecarts.append("ORACLE DE L'ACQUITTEMENT MORT — aucune ligne « POUR TOI » du témoin "
                  "n'a reçu son empreinte : le témoin a été refigé, retirer ce bloc")
ecarts = alertes + ecarts
print("%s · %d entrées, %d agents" % (ligne, len(ENTREES), len(AGENTS)))
print()
print("\n\n".join(ecarts) or "ÉCARTS : AUCUN — le Rust rend le témoin, lectures et écritures")
sys.exit(1 if ecarts else 0)
