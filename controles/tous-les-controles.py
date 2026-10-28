#!/usr/bin/env python3
"""REJOUE TOUS LES CONTRÔLES DIFFÉRENTIELS DU PORTAGE.

    python3 controles/tous-les-controles.py <un dossier de travail>

Chacun lance la version Python d'un hook et la version Rust sur les MÊMES
entrées, puis compare ce qui sort : code de sortie, message au caractère près,
appels vers le téléphone, et tous les fichiers d'état à l'octet.

CHAQUE CONTRÔLE PORTE SON TÉMOIN. Deux programmes qui ne font rien se comparent
égaux : on exige donc que la version Python ait vraiment écrit, vraiment bloqué,
vraiment servi — sinon le contrôle se déclare raté, même sans écart.

POURQUOI ILS SE REJOUENT TOUS ENSEMBLE. Un réglage partagé — l'ordre des clés
JSON, demandé pour le carnet — a changé la façon dont un hook DÉJÀ porté et
DÉJÀ éprouvé écrivait son fichier. Une preuve n'est pas acquise : elle vaut pour
l'état du code au moment où elle a été faite.

Ils ont besoin de Python 3.9 ou plus et du lanceur `bin/harnais`, et
ils sont EN LECTURE SEULE sur les projets des autres agents : le carnet
d'un projet réel est copié, jamais lu en place.
"""
import json, os, subprocess, sys, pathlib, re, tempfile

S = sys.argv[1] if len(sys.argv) > 1 else "/tmp/controles-harnais"
pathlib.Path(S).mkdir(parents=True, exist_ok=True)
ICI = pathlib.Path(__file__).resolve().parent
R = ICI.parent
# LE PROGRAMME JUGÉ : le lanceur du paquet, pour TOUS les contrôles (12/10/2026).
# Chacun lit HARNAIS_BIN et retombe sinon sur un ancien chemin de compilation.
os.environ.setdefault("HARNAIS_BIN", str(R / "bin" / "harnais"))


def lanceur_windows():
    """SOUS WINDOWS, LE LANCEUR N'EST PAS UN EXÉCUTABLE (mesuré sur un poste
    Windows le 28/10/2026 : WinError 193 au premier appel, le banc s'arrêtait là).
    `bin/harnais` est un script `sh` : les hooks le passent à `sh`, les
    contrôles l'appelaient tel quel. On lui donne un relais `.cmd`, que
    Windows sait lancer, et qui le passe au `sh` de Git — comme les hooks."""
    import shutil
    sh = shutil.which("sh")
    if not sh:
        return None
    relais = pathlib.Path(S) / "harnais.cmd"
    relais.write_text('@"%s" "%s" %%*\r\n' % (sh, os.environ["HARNAIS_BIN"]), encoding="utf-8")
    return str(relais)


if os.name == "nt" and pathlib.Path(os.environ["HARNAIS_BIN"]) == R / "bin" / "harnais":
    os.environ["HARNAIS_BIN"] = lanceur_windows() or os.environ["HARNAIS_BIN"]
    # Les contrôles lisent des sorties en UTF-8 ; la page de code de la console
    # n'est pas un choix du paquet.
    os.environ.setdefault("PYTHONUTF8", "1")
T = [("compteur d'usage",      "diff-usage.py"),
     ("journal",               "diff-journal.py"),
     ("résolveur mémoire",     "diff-memoire.py"),
     ("garde de commit",       "diff-mindguard.py"),
     ("carnet d'équipe",       "diff-carnet.py"),
     ("briefing",              "diff-briefing.py"),
     ("briefing · mémoire",    "diff-briefing-mem.py"),
     ("fin de tour",           "diff-attente.py"),
     ("fin de tour · mémoire", "diff-attente-memoire.py"),
     # Celui-ci n'est PAS différentiel : le relecteur n'existe que côté Rust.
     # C'est un contrôle de comportement, et chaque assertion porte son
     # contraire — un dispositif qui ne part jamais passerait sinon pour un
     # dispositif qui n'a rien trouvé.
     ("relecteur (Rust seul)",  "relecteur.py"),
     # Pas différentiel non plus : la conversion en équipe n'a jamais existé en
     # deux versions. Ce qu'il vérifie n'est pas la forme produite mais que le
     # harnais PARLE depuis un dossier d'agent — le reste peut être juste et le
     # dispositif rester muet, ce qui est exactement arrivé au carnet d'équipe.
     ("conversion en équipe",   "conversion-triptyque.py"),
     # Ni différentiel ni sur un bac à sable : celui-ci juge l'ATELIER RÉEL —
     # par quel canal chaque agent reçoit ses hooks, et si le code qu'il appelle
     # est celui du jour. Il est ici parce que personne ne surveillait ça : au
     # 10/09/2026, un agent sur dix-huit tournait sur le paquet, et publier une
     # version ne changeait rien pour les dix-sept autres. Il échoue s'il
     # n'examine AUCUN agent — un contrôle qui ne trouve rien n'est pas un
     # contrôle qui passe.
     ("canal de déploiement",   "canal-deploiement.py"),
     # Le treizieme, et lui non plus n'est pas différentiel : il juge la FORME
     # des projets réels. Il ne refuse pas qu'un projet soit encore en v1 — une
     # flotte mixte est l'état normal d'une migration progressive. Il refuse le
     # seul état qu'aucun projet ne doit atteindre : être À CHEVAL sur les deux
     # arbres, ce qu'une migration interrompue laisse derrière elle et que rien
     # ne signale — le briefing se tait, la serrure perd son préfixe, et tout a
     # l'air normal. Son témoin est un arbre à cheval fabriqué exprès : s'il ne
     # le voit pas, il se déclare aveugle au lieu de rendre « rien trouvé ».
     ("formes réelles",         "formes-reelles.py"),
     # Le ménage, porté du Python le 11/09/2026 : relu contre le témoin figé
     # du script retiré. Écrit en shell, parce qu'il n'appelle que le binaire.
     ("ménage (témoin figé)",   "menage.sh"),
     ("équipe (témoin figé)",   "equipe.sh"),
     ("vue d'équipe (témoin figé)", "vue-equipe.sh"),
     # 11/09/2026, après un audit : le curateur entre dans le paquet (relu
     # contre le témoin de l'outil du poste), les demandes `!cible` et le
     # cadre des pairs, et la documentation sous garde.
     ("curateur (témoin figé)",  "curateur.sh"),
     ("demandes !cible, pairs",  "cible.sh"),
     # 12/09/2026 : une fin de tour qui ne peut pas écrire doit le DIRE. Pas
     # différentiel — ce comportement n'a jamais existé en Python, et il tient à
     # un détail mesuré ce jour-là : à code de sortie 0, seule une note JSON
     # arrive jusqu'à l'humain.
     ("plus rien vers les Rappels", "sans-rappels.sh"),
    ("mémoire partagée à deux", "synchro.sh"),
    ("un dossier par agent", "equipe-v3.py"),
    ("faits des experts", "faits-experts.sh"),
     ("renvois de fin de tour",  "renvois.sh"),
     ("canal Notion",            "notion.sh"),
     ("doc et code",             "doc-code.sh"),
     # 17/10/2026 : le garde du coffre, joué avec le vrai Doppler sur un faux
     # coffre local — chaque refus doit cacher une fuite réelle, chaque passage
     # n'en laisser aucune. Sans Doppler, il se déclare aveugle.
     ("garde du coffre",         "coffre-factice.py")]
# LE PROGRAMME LIVRÉ CORRESPOND-IL À SON SOURCE ? Question née avec Rust (un
# binaire périmé ne se voit jamais). Depuis le retour en Python (12/10/2026) le
# programme EST son source : on vérifie que le lanceur répond et annonce la
# version du paquet (`binaire_a_jour`, plus bas). Plus de programme Windows à
# part, donc plus d'identité déposée par la chaîne.



def source_a_bouge(depot, etat, chemins):
    """LE SOURCE A-T-IL BOUGÉ DEPUIS `etat` — ARBRE DE TRAVAIL COMPRIS ?

    Il n'y a pas de `HEAD` dans cette comparaison, et c'est tout le sujet.
    `git diff <état> HEAD` compare deux ENREGISTREMENTS : il répond sur
    l'historique et se tait sur le fichier qu'on vient d'éditer — c'est-à-dire
    exactement dans la situation où on lance les contrôles, après avoir modifié
    du code et avant de le commiter.

    Mesuré le 10/09/2026 par l'audit : un octet corrompu dans un module, non
    commité, laissait ce contrôle imprimer « identique à ce que le source
    produit » pendant que c'était faux. Les deux commandes lancées au même
    instant sur le même arbre rendaient 0 avec `HEAD`, 1 sans.

    Trois issues et non deux : `git` peut aussi ne pas répondre — un état
    inconnu du dépôt rend 128. Un contrôle qui échoue ne doit jamais se lire
    comme un contrôle qui confirme.

    Limite connue, non couverte : un fichier de source JAMAIS ajouté au dépôt
    reste invisible à `git diff`. En pratique il faut le déclarer dans un
    fichier suivi pour qu'il entre dans le programme, et cette déclaration-là
    est vue.
    """
    d = subprocess.run(["git", "diff", "--quiet", etat, "--"] + list(chemins),
                       cwd=str(depot), capture_output=True, text=True)
    if d.returncode == 0:
        return "identique"
    if d.returncode == 1:
        return "bouge"
    return "muet"


def temoin_detection_source():
    """DEUX CAS, le refusé ET le passé, sur un dépôt jetable.

    Un détecteur qui répond toujours « identique » et un détecteur juste rendent
    le même verdict sur un arbre intact. On exige donc qu'il voie l'octet changé
    ET qu'il se taise quand rien n'a bougé — sinon ce contrôle se déclare cassé
    au lieu de rassurer.
    """
    with tempfile.TemporaryDirectory() as t:
        d = pathlib.Path(t)
        def git(*a):
            return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t"]
                                  + list(a), cwd=str(d), capture_output=True, text=True)
        git("init", "-q", "-b", "essai")
        (d / "src").mkdir()
        (d / "src" / "m.rs").write_text('const N: &str = "base.md";\n')
        git("add", "-A")
        git("commit", "-q", "-m", "socle")
        etat = git("rev-parse", "HEAD").stdout.strip()
        if len(etat) != 40:
            return "témoin muet : le dépôt jetable n'a pas été enregistré"

        passe = source_a_bouge(d, etat, ["src"])
        (d / "src" / "m.rs").write_text('const N: &str = "bose.md";\n')  # PAS commité
        refuse = source_a_bouge(d, etat, ["src"])
        # Et l'état qu'on n'a pas : `git` ne peut pas comparer, il ne doit ni
        # rassurer ni accuser. C'est la troisième issue, celle qu'on oublie.
        inconnu = source_a_bouge(d, "0" * 40, ["src"])

        if passe != "identique":
            return ("témoin cassé : un arbre intact est déclaré %r — le détecteur "
                    "crie sur tout, ses écarts ne veulent plus rien dire" % passe)
        if refuse != "bouge":
            return ("témoin cassé : un octet changé et NON COMMITÉ est déclaré %r — "
                    "c'est le défaut mesuré le 10/09/2026" % refuse)
        if inconnu != "muet":
            return ("témoin cassé : un état introuvable est déclaré %r au lieu de "
                    "muet — une panne de comparaison se lirait comme un verdict"
                    % inconnu)
    return None


def binaire_a_jour():
    """Le programme livré répond-il, et dit-il la version du paquet ?

    DEPUIS LE RETOUR EN PYTHON (12/10/2026) il n'y a plus de binaire à comparer à
    son source : le programme EST le source (`py/`), lu à chaque lancement. La
    panne qui reste, et qu'on mesure, est la même que celle des hooks sous
    Windows : le lanceur ne trouve pas de Python, ou en trouve un trop vieux, et
    rien ne part. On demande donc au lanceur de répondre à `version`, et la
    version annoncée doit être celle de `.claude-plugin/plugin.json`.
    """
    lanceur = R / "bin" / "harnais"
    if not lanceur.exists():
        return "le lanceur `bin/harnais` n'est pas livré"
    appel = ["sh", str(lanceur)] if os.name == "nt" else [str(lanceur)]
    r = subprocess.run(appel + ["version"], capture_output=True, text=True)
    if r.returncode != 0 or len(r.stdout.split()) < 2:
        return ("le lanceur ne répond pas à `version` (code %d) : %s"
                % (r.returncode, (r.stderr.strip() or "aucun message")[:140]))
    annoncee = r.stdout.split()[0]
    declaree = json.loads((R / ".claude-plugin" / "plugin.json").read_text())["version"]
    if annoncee != declaree:
        return ("le programme annonce %s, le paquet en déclare %s" % (annoncee, declaree))
    return None


ANSI = re.compile(r"\x1b\[[0-9;]*m")
RIEN = "⚠ ce contrôle n'a affiché AUCUNE preuve — on ne sait pas ce qu'il a examiné"


def preuve(sortie):
    """CE QUE LE CONTRÔLE A PROUVÉ, quelle que soit sa mise en forme.

    Avant, on ne gardait que les lignes commençant par trois mots choisis.
    Mesuré le 10/09/2026 par l'audit : trois contrôles sur treize présentent
    autrement leurs témoins — ils s'affichaient « OK » suivi du VIDE, donc
    indiscernables d'un contrôle qui n'aurait rien examiné. La visibilité d'une
    preuve ne doit pas dépendre de sa typographie.

    À défaut de ligne reconnue, on montre la dernière ligne utile, débarrassée
    des couleurs du terminal. Et un contrôle qui n'a VRAIMENT rien dit le dit :
    le vide ne se lit pas comme un succès sobre.
    """
    lignes = [ANSI.sub("", l).rstrip() for l in sortie.splitlines()]
    retenues = [l for l in lignes if l.startswith(("ÉCARTS", "témoin", "gardes"))]
    if retenues:
        return " · ".join(retenues)
    utiles = [l.strip() for l in lignes if l.strip()]
    return utiles[-1] if utiles else RIEN


def temoin_affichage_preuve():
    """TROIS CAS, dont celui qui doit rester vide.

    Un extracteur qui rend toujours quelque chose et un extracteur juste se
    ressemblent tant qu'on ne lui donne que des sorties riches.
    """
    reconnue = preuve("bla\ntémoin : 12 cas\nbla")
    if reconnue != "témoin : 12 cas":
        return "témoin cassé : la ligne reconnue n'est plus extraite (%r)" % reconnue
    colorée = preuve("détail\n  \x1b[32m✓\x1b[0m aucun projet à cheval\n")
    if colorée != "✓ aucun projet à cheval":
        return ("témoin cassé : une preuve mise en forme autrement n'apparaît pas "
                "nettoyée (%r) — c'est le défaut mesuré le 10/09/2026" % colorée)
    muet = preuve("\n   \n")
    if muet != RIEN:
        return "témoin cassé : une sortie vide passe pour une preuve (%r)" % muet
    return None


# LES INSTRUMENTS AVANT CE QU'ILS MESURENT. Ces deux témoins ne jugent pas le
# harnais : ils jugent ce fichier-ci. Ils sont en tête parce qu'un lanceur qui
# ment sur ses propres résultats rend tout ce qui suit sans valeur.
casses = [m for m in (temoin_detection_source(), temoin_affichage_preuve()) if m]
print("%-24s %s  %s" % ("témoins du lanceur", "OK  " if not casses else "ÉCART",
                        " · ".join(casses) if casses else
                        "détection du source : 3 cas (intact / un octet non commité / "
                        "état introuvable) · "
                        "affichage des preuves : 3 cas (reconnue / autre forme / vide)"))

ecart_binaire = binaire_a_jour()
print("%-24s %s  %s" % ("binaire livré", "OK  " if ecart_binaire is None else "ÉCART",
                        ecart_binaire or "identique à ce que le source produit, "
                        "arbre de travail compris"))


def construit():
    """Rien à construire : le programme est le source. Le lanceur a déjà répondu à
    `version` (contrôle du programme livré, plus haut) ; il n'y a pas de
    seconde étape qui pourrait échouer ici."""
    return None


def empreinte_source():
    """L'ÉTAT DU SOURCE QUE CES CONTRÔLES ONT JUGÉ — ou None s'il n'est pas
    enregistré. Un verdict sur des modifications non enregistrées ne se
    rattache à aucun état qu'on puisse retrouver : il ne vaut pas preuve."""
    chemins = ["py", "hooks", "skills"]
    st = subprocess.run(["git", "status", "--porcelain", "--"] + chemins,
                        cwd=str(R), capture_output=True, text=True)
    if st.returncode != 0 or st.stdout.strip():
        return None
    h = []
    for c in chemins:
        r = subprocess.run(["git", "rev-parse", "HEAD:" + c], cwd=str(R),
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None
        h.append("%s=%s" % (c, r.stdout.strip()))
    return " ".join(h)


panne = construit()
if panne:
    print("%-24s ÉCART  la construction échoue — rien n'est jugé\n    %s" % ("construction", panne))
    sys.exit(1)

mauvais = (1 if casses else 0) + (1 if ecart_binaire else 0)
resultats = []
for nom, f in T:
    lanceur = ["bash", str(ICI/f)] if f.endswith(".sh") else ["python3", str(ICI/f), S]
    r = subprocess.run(lanceur, capture_output=True, text=True)
    if r.returncode != 0:
        mauvais += 1
    resultats.append((nom, r.returncode == 0, preuve(r.stdout)[:150]))
    print("%-24s %s  %s" % (nom, "OK  " if r.returncode == 0 else "ÉCART",
                            preuve(r.stdout)[:150]))
    if r.returncode != 0:
        print("    " + "\n    ".join((r.stdout + r.stderr).splitlines()[-12:]))
print()
# LE TOTAL COMPTE TOUT CE QUI PEUT ÊTRE EN ÉCART. Avant il annonçait `len(T)`,
# alors que les témoins du lanceur et le contrôle du binaire pouvaient eux aussi
# compter dans les écarts : « 1 en écart sur 13 » portait en réalité sur 14
# vérifications. Un dénominateur faux dévalue les deux chiffres.
print("%d contrôle(s) en écart sur %d" % (mauvais, len(T) + 2))

# LE VERDICT EST ÉCRIT, DATÉ, ET RATTACHÉ AU SOURCE (audit du 11/09/2026).
# « Quinze verts » était affirmé au présent par le mode d'emploi, obtenu la
# veille, avant cinq modifications du code : rien dans le dépôt n'attestait
# qu'on les avait rejoués. Plus aucune chaîne ne le lit depuis le retour en
# Python (12/10/2026) : publier sans un verdict à zéro écart sur le source
# enregistré est une discipline, plus une porte.
#
# Le programme LIVRÉ n'est plus à part : il est son source, donc un écart y est
# un vrai écart (lanceur muet, version qui ne correspond pas) et il compte.
source = empreinte_source()
hors_binaire = mauvais
lignes = ["controles: verdict du %s" % __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
          "source: %s" % (source or "NON ENREGISTRÉ — ce verdict ne vaut pas preuve"),
          "ecarts: %d sur %d" % (hors_binaire, len(T) + 2),
          "binaire livre: %s" % ("OK" if ecart_binaire is None else
                                 "ÉCART (%s)" % ecart_binaire),
          "temoins du lanceur: %s" % ("OK" if not casses else "ÉCART")]
lignes += ["- %s %s · %s" % ("OK   " if ok else "ÉCART", nom, p) for nom, ok, p in resultats]
(ICI / "verdict.txt").write_text("\n".join(lignes) + "\n")
if source is None:
    print("verdict écrit, mais le source n'est pas enregistré : il ne vaut pas preuve")
sys.exit(1 if mauvais else 0)
