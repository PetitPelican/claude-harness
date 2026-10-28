# -*- coding: utf-8 -*-
"""`harnais curateur` — le curateur de la mémoire : vieillir, ranger, ne JAMAIS
effacer.

Port de `harnais/src/curateur.rs` (Rust, 0.12.8).

IL VIVAIT DANS LES OUTILS DU POSTE (`claude-memoire`), donc sur ce Mac
seulement. Il entre dans le paquet le 11/09/2026, décidé par le commanditaire après
un audit : sur le PC, la confiance que la fin de tour calcule pour chaque
note n'avait AUCUN lecteur, et le briefing citait un outil absent. Le code
est repris tel quel — relu contre le témoin figé de l'outil du poste
(`controles/curateur.sh`) — et `claude-memoire` n'est plus qu'un relais.

Repris à un agent de référence, adapté à ce poste. Quatre pièces, et
chacune répond à un défaut précis :

· TROIS ÉTATS, pas deux — actif → dormant → archivé, et **retour à actif dès
  que la note ressert**. Deux états forceraient à choisir entre garder du
  bruit et perdre du signal.
· ON N'EFFACE JAMAIS, on archive. Une note archivée par erreur se retrouve ;
  une note effacée, non.
· L'ÉPINGLE — certaines règles ne doivent jamais s'endormir même si personne
  ne les rouvre pendant trois mois : elles sont vraies en permanence,
  justement parce qu'on n'a pas eu à les rouvrir.
· LA PARTIE QUI RÉFLÉCHIT N'EST PAS CONSTRUITE. Ce programme SIGNALE les
  doublons probables et ne les fusionne pas. Fusionner demande de lire, donc
  des jetons, donc une décision du commanditaire — et il la prendra sur un chiffre.

LE PIÈGE QUI AURAIT TOUT ARCHIVÉ, et il est structurel : la mesure d'usage
commence le jour où on l'installe. Avant elle, TOUTES les notes sont « jamais
servies » — vieillir là-dessus les archiverait toutes le premier jour. D'où
le garde-fou sur l'âge de la MESURE : *un compteur d'usage à zéro est une
absence de preuve, pas une péremption.*
"""
import datetime
import json
import math
import os
import re

import nature
import socle
from socle import maison

# Les seuils de cet agent de référence, repris tels quels : ils sont éprouvés, et rien chez
# nous ne justifie de les bouger avant d'avoir mesuré.
DORMANT_J = 30.0
ARCHIVE_J = 90.0

G = "\x1b[32m"  # vert  — ce qui va
J = "\x1b[33m"  # jaune — ce qui demande un œil
R = "\x1b[31m"  # rouge — ce qui ne va pas
D = "\x1b[2m"   # pâle  — le contexte
B = "\x1b[1m"   # gras  — le sujet
Z = "\x1b[0m"   # fin

# `str::trim` du Rust : les caractères White_Space d'Unicode (`str.strip()`
# retirerait aussi \x1c à \x1f).
_BLANCS = "\t\n\x0b\x0c\r \x85\xa0        " \
          "        　"


def _trim(s):
    return s.strip(_BLANCS)


def _lignes(t):
    """`str::lines` du Rust : coupe sur `\\n`, retire un `\\r` qui précède le
    `\\n`, et ne compte pas de ligne vide après le dernier `\\n`."""
    parts = t.split("\n")
    fin = parts.pop()
    out = [p[:-1] if p.endswith("\r") else p for p in parts]
    if fin != "":
        out.append(fin)
    return out


# ── lecture d'une valeur JSON comme `serde_json::Value` ─────────────────────

def _get(v, cle):
    """`Value::get(&str)` : None sur tout ce qui n'est pas un objet."""
    return v.get(cle) if isinstance(v, dict) else None


def _as_i64(v):
    if isinstance(v, int) and not isinstance(v, bool) and -2 ** 63 <= v < 2 ** 63:
        return v
    return None


def _as_f64(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _as_str(v):
    return v if isinstance(v, str) else None


def _as_bool(v):
    return v if isinstance(v, bool) else None


def mult_niveau(n):
    """LE VIEILLISSEMENT N'EST PAS PLAT — repris à sense-lab (AMFS).

    Trois idées, et les trois nous manquaient. Une SUPPOSITION périme deux fois
    plus vite qu'une MESURE. Ce qui SERT souvent périme lentement. Et une note
    déjà mise à L'ÉPREUVE tient deux fois plus longtemps qu'une note jamais
    confrontée à rien.

    `dit` prend le multiplicateur long : un fait que le commanditaire a énoncé ne périme
    pas avec le temps, il périme quand il change d'avis — et ça, aucune horloge
    ne le voit."""
    if n == "mesuré":
        return 1.0
    if n == "dit":
        return 1.5
    if n == "observé":
        return 0.7
    # `lu` (12/10/2026, profil expert) : un document lu fait foi jusqu'à sa
    # version suivante, comme une mesure — il ne s'use pas avec le temps.
    if n == "lu":
        return 1.0
    # `supposé` N'A PLUS DE POIDS ICI depuis le 11/09/2026 : une supposition
    # EST une croyance, et c'est sa NATURE qui la fait vieillir deux fois
    # plus vite (`nature.de`). Le poids était juste ; il était rangé sur
    # le mauvais axe, et c'est ce qui le rendait inapplicable à tout le
    # reste. Même produit pour une supposition — 0,5 —, le témoin figé
    # le garde.
    # Une note d'avant la règle n'est pas punie pour ça.
    return 1.0


def projet_courant():
    """LE PROJET PAR DÉFAUT EST CELUI OÙ L'ON EST. Dans les outils du poste,
    c'était le CTO, écrit en dur : un outil du poste sert son propriétaire. Un
    outil du paquet sert l'agent qui l'appelle — son dossier de projet, résolu
    comme Claude Code range sa mémoire."""
    d = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return socle.cle_memoire(socle.dossier_de_la_memoire(d))


def prefixe_atelier():
    """Le préfixe qu'on retire du nom affiché : `~/Agentic/`, slugifié."""
    return "%s-" % socle.cle_memoire(os.path.join(maison(), "Agentic"))


def seuils(e, niv, declaree):
    """Les deux seuils d'une note, gradués. Rend (dormante_j, archivée_j).

    × la NATURE (`nature`) depuis le 11/09/2026 : une croyance s'endort deux
    fois plus tôt qu'un fait, une expérience une fois et demie plus tard.

    Appliqué au DÉLAI D'ENDORMISSEMENT et non à un chiffre de confiance, parce
    que c'est le levier qu'on a : le curateur range, il ne note pas."""
    n = _as_i64(_get(e, "n"))
    n = float(max(n if n is not None else 0, 0))
    r = _get(e, "res")
    res = (r is not None) and not (isinstance(r, int) and not isinstance(r, bool) and r == 0)
    nat, _ = nature.de(nature.Maison.MemoireAuto, niv, declaree)
    f = nature.pente(nat) * mult_niveau(niv) * (1.0 + math.log1p(n)) * (2.0 if res else 1.0)
    return (DORMANT_J * f, ARCHIVE_J * f)


def marque(niv, declaree):
    """Ce que la note dit d'elle-même, entre crochets. LA NATURE N'APPARAÎT QUE
    QUAND ELLE N'EST PAS CELLE DE LA MAISON — un fait —, sinon « fait » serait
    imprimé sur presque toutes les lignes pour ne rien dire."""
    nat, _ = nature.de(nature.Maison.MemoireAuto, niv, declaree)
    p = []
    if niv is not None:
        p.append(niv)
    if nat != nature.Nature.Fait:
        p.append(nature.mot(nat))
    return " [%s]" % " · ".join(p) if p else ""


def racine(slug):
    """Où vit la mémoire de ce projet.

    LA RACINE EST SURCHARGEABLE, et uniquement pour la mesurer. Cet outil DÉPLACE
    des fichiers avec `--appliquer` : aucun contrôle ne peut l'éprouver sur la
    vraie mémoire sans risquer de l'abîmer, et un jeu d'essai posé sous le vrai
    dossier serait ramassé par la sauvegarde. Sans cette couture, seule la
    branche « rapport » serait jamais vérifiée."""
    b = os.environ.get("CLAUDE_MEMOIRE_RACINE")
    if b:
        return os.path.join(b, slug, "memory")
    return os.path.join(maison(), ".claude/projects", slug, "memory")


def _lire(p):
    try:
        with open(p, "rb") as f:
            return f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def entete(p):
    """Le frontmatter, en table plate. Rend une table vide plutôt que de lever."""
    out = {}
    t = _lire(p)
    if t is None:
        return out
    m = _FM.match(t)
    if m is None:
        return out
    for l in _lignes(m.group(1)):
        s = _trim(l)
        if s == "" or s.startswith("#"):
            continue
        if ":" in s:
            k, v = s.split(":", 1)
            out[_trim(k)] = _trim(v).strip('"')
    return out


_NIVEAU = re.compile(r"^> \*\*(mesuré|observé|supposé|dit|lu)\*\* · (\d\d/\d\d)/\d{4}", re.M)


def niveau(p):
    """Le niveau de confiance déclaré par la note, ou None.

    ON NE DEVINE PAS. Un classement automatique tenté le 09/09/2026 sur les
    55 notes en a rendu 51 « mesuré » : un niveau qui tombe sur 93 % des notes
    ne distingue rien. Une note sans niveau est donc rendue SANS niveau — un
    poids inconnu qui se dit inconnu vaut mieux qu'un poids inventé."""
    t = _lire(p)
    if t is None:
        return None
    m = _NIVEAU.search(t[:900])
    return m.group(1) if m else None


def _refuse_constante(nom):
    raise ValueError(nom)


def _entier(s):
    # serde_json lit `-0` comme le flottant -0.0.
    return -0.0 if s == "-0" else int(s)


def usage(mem):
    t = _lire(os.path.join(mem, ".usage.json"))
    if t is None:
        return {}
    try:
        v = json.loads(t, parse_constant=_refuse_constante, parse_int=_entier)
    except ValueError:
        return {}
    # Un `null` devient un objet à la première écriture (serde) ; tout autre
    # type non objet fait paniquer le Rust — ici on repart d'une table vide.
    return v if isinstance(v, dict) else {}


def ecrire_usage(mem, d):
    f = os.path.join(mem, ".usage.json")
    tmp = os.path.join(mem, ".usage.json.tmp")
    # `indent=1` côté Python d'origine ; le Rust garde l'ORDRE D'INSERTION des
    # clés (`preserve_order`) et ne les trie pas — nous non plus.
    try:
        texte = json.dumps(d, ensure_ascii=False, indent=1)
    except (TypeError, ValueError):
        return
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as h:
            h.write(texte)
    except OSError:
        return
    try:
        os.replace(tmp, f)
    except OSError:
        pass


def aujourdhui():
    return datetime.date.today()


def jours(iso):
    try:
        d = datetime.datetime.strptime(iso, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (aujourdhui() - d).days


def g(x):
    """Le `%g` de Python : six chiffres significatifs, zéros de queue retirés."""
    if math.isfinite(x) and x == math.trunc(x) and abs(x) < 1e15:
        return "%d" % int(x)
    s = "%.6f" % x
    return s.rstrip("0").rstrip(".")


_STOP = ("le la les de des du un une et ou à a au aux en dans sur pour par "
         "que qui ne pas plus est sont ce cet cette son sa ses il elle on n'est d'un d'une c'est nest "
         "pas être avoir fait quand")
_MOT = re.compile(r"[a-zà-ÿ]{5,}")


def doublons(notes):
    """Signale, ne fusionne pas.

    Deux descriptions qui partagent beaucoup de mots rares sont *probablement*
    la même leçon écrite deux fois — mais seul un lecteur peut trancher, et
    c'est justement la partie qui coûte."""
    stop = _STOP.split()
    mots = {}
    for n in sorted(notes):
        e = notes[n]
        desc = e.get("description", "").lower()
        m = sorted(set(w for w in _MOT.findall(desc) if w not in stop))
        if m:
            mots[n] = m
    noms = sorted(mots)
    paires = []
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            c = [w for w in mots[a] if w in mots[b]]
            if len(c) >= 3:
                paires.append((len(c), a, b, c[:4]))
    # `sorted(..., reverse=True)` trie sur le tuple entier : compte, puis noms.
    paires.sort(reverse=True)
    return paires[:6]


def valeur(args, nom):
    """La valeur d'une option, dans SES DEUX FORMES.

    `--du <valeur>` ET `--du=<valeur>`. Ce n'est pas un raffinement : mesuré le
    10/09/2026, la version Python n'accepte QUE la seconde, parce que son
    analyseur d'arguments prend toute valeur commençant par un tiret pour une
    option — et **tous les identifiants de projet commencent par un tiret**. Sa
    propre ligne d'aide, `--du <slug>`, ne fonctionne donc sur aucun projet réel.

    On accepte les deux plutôt que de reproduire le refus : la forme permissive
    ne casse aucun appel existant, et refuser ce que la documentation promet
    serait porter un défaut sans même le signaler. L'écart est délibéré, et il
    est listé comme tel."""
    prefixe = nom + "="
    for i, a in enumerate(args):
        if a.startswith(prefixe):
            return a[len(prefixe):]
        if a == nom:
            return args[i + 1] if i + 1 < len(args) else None
    return None


AIDE = """Le curateur de la mémoire — vieillir, ranger, ne JAMAIS effacer.

    harnais curateur                 rapport sur la mémoire de ce projet, ne touche à rien
    harnais curateur --appliquer     applique les transitions
    harnais curateur --epingle <nom> cette note ne s'endort jamais
    harnais curateur --du <slug>     un autre projet que celui-ci"""


def main(args):
    if "-h" in args or "--help" in args:
        print(AIDE)
        return 0
    appliquer = "--appliquer" in args
    epingle = valeur(args, "--epingle")
    du = valeur(args, "--du")
    if du is None:
        du = projet_courant()

    mem = racine(du)
    if not os.path.isdir(mem):
        print("  %saucune mémoire à ce nom : %s%s" % (R, du, Z))
        return 1

    u = usage(mem)
    if "_depuis" not in u:
        u["_depuis"] = aujourdhui().strftime("%Y-%m-%d")
        if appliquer:
            ecrire_usage(mem, u)
    depuis = _as_str(u.get("_depuis"))
    depuis_j = jours(depuis) if depuis is not None else None
    if depuis_j is None:
        depuis_j = 0

    try:
        noms = os.listdir(mem)
    except OSError:
        noms = []
    fichiers = []
    for nom in noms:
        stem, ext = os.path.splitext(nom)
        if ext == ".md" and stem.upper() != "MEMORY":
            fichiers.append(nom)
    fichiers.sort()
    notes = {}
    for nom in fichiers:
        notes[os.path.splitext(nom)[0]] = entete(os.path.join(mem, nom))
    cles = sorted(notes)

    def chemin(n):
        return os.path.join(mem, "%s.md" % n)

    if epingle is not None:
        nom = epingle
        if nom not in notes:
            print("  %sinconnue : %s%s" % (R, nom, Z))
            return 1
        e = u.get(nom)
        if e is None:
            e = {}
        e["epingle"] = True
        u[nom] = e
        ecrire_usage(mem, u)
        print("  %s%s%s ne s'endormira plus." % (G, nom, Z))
        return 0

    # ── les natures, et d'où elles viennent ──────────────────────────────
    nf = nc = ne = nd = 0
    for n in cles:
        h = notes[n]
        niv = niveau(chemin(n))
        nat, orig = nature.de(nature.Maison.MemoireAuto, niv, h.get("nature"))
        if nat == nature.Nature.Fait:
            nf += 1
        elif nat == nature.Nature.Croyance:
            nc += 1
        else:
            ne += 1
        if orig == nature.Origine.Declaree:
            nd += 1

    # ── classement ────────────────────────────────────────────────────────
    actifs, dormantes, a_archiver, jamais = [], [], [], []
    for n in cles:
        e = u.get(n)
        if e is None:
            e = {}
        if _as_bool(_get(e, "epingle")) is True:
            actifs.append((n, "épinglée"))
            continue
        # Les seuils sont PROPRES À CHAQUE NOTE depuis le 09/09/2026 : ce
        # qu'elle dit d'elle-même, ce qu'elle a servi, et si un résultat l'a
        # éprouvée.
        niv = niveau(chemin(n))
        declaree = notes[n].get("nature")
        s_dorm, s_arch = seuils(e, niv, declaree)
        mq = marque(niv, declaree)
        vu = _as_str(_get(e, "vu"))
        if vu is not None and vu == "":
            vu = None
        if vu is None:
            # JAMAIS SERVIE. Elle ne peut vieillir que si la MESURE, elle, a
            # l'âge du seuil — sinon on punirait une note pour un instrument
            # qu'on vient d'installer.
            d = float(depuis_j)
            if d >= s_arch:
                a_archiver.append((n, "jamais servie en %d j%s" % (depuis_j, mq)))
            elif d >= s_dorm:
                dormantes.append((n, "jamais servie en %d j%s" % (depuis_j, mq)))
            else:
                jamais.append((n, "pas encore observée (mesure : %d j)" % depuis_j))
            continue
        d = jours(vu)
        if d is None:
            actifs.append((n, "date illisible"))
        elif float(d) >= s_arch:
            a_archiver.append((n, "dernier usage il y a %d j%s" % (d, mq)))
        elif float(d) >= s_dorm:
            dormantes.append((n, "dernier usage il y a %d j%s" % (d, mq)))
        else:
            c = _as_f64(_get(e, "conf"))
            n_lu = _as_i64(_get(e, "n"))
            if n_lu is None:
                n_lu = 1
            conf = " · confiance %s" % g(c) if c is not None else ""
            actifs.append((n, "servie il y a %d j, %d fois%s%s" % (d, n_lu, mq, conf)))

    # ── rapport ───────────────────────────────────────────────────────────
    if appliquer:
        mode = "%sAPPLIQUÉ%s" % (G, Z)
    else:
        mode = "%srapport seul — rien n'est touché%s" % (D, Z)
    print("\n  %sMémoire — %s%s   %s" % (B, du.replace(prefixe_atelier(), ""), Z, mode))
    print("  %s" % ("─" * 62))
    print("  %d notes · mesure d'usage en place depuis %d j" % (len(notes), depuis_j))
    print("  natures : %d fait · %d croyance · %d expérience %s— %d déclarée(s) par la note%s"
          % (nf, nc, ne, D, nd, Z))
    print("  seuils de base : dormante à %d j, archivée à %d j — puis GRADUÉS"
          % (int(DORMANT_J), int(ARCHIVE_J)))
    print("  %spar note : × nature (croyance 0,5 · fait 1 · expérience 1,5 — une supposition est une croyance)%s"
          % (D, Z))
    print("  %s× niveau (observé 0,7 · mesuré 1 · dit 1,5) × (1 + log(lectures)) × 2 si un résultat l'a déjà éprouvée%s\n"
          % (D, Z))

    def lectures(n):
        v = _as_i64(_get(u.get(n), "n"))
        return v if v is not None else 0

    servies = []
    for n in cles:
        vu = _as_str(_get(u.get(n), "vu"))
        if vu is not None and vu != "":
            servies.append(n)
    print("  %sservies au moins une fois%s : %d sur %d" % (B, Z, len(servies), len(notes)))
    # MESURÉ LE 09/09/2026, ET ÇA INVERSE CE QU'ON CROYAIT. On tenait ce compte
    # pour un plancher : « les notes que le harnais injecte lui échappent ».
    # Vérifié sur 40 transcriptions — 11 injections de mémoire, TOUTES l'index,
    # ZÉRO note individuelle. Le harnais sert le sommaire, jamais le contenu.
    print("  %sce compte est complet, et c'est mesuré : le harnais n'injecte%s" % (D, Z))
    print("  %sque l'index, jamais une note (40 transcriptions, 09/09/2026).%s" % (D, Z))
    print("  %sIl ne verrait pas une note lue autrement que par l'outil de%s" % (D, Z))
    print("  %slecture — copiée à la main, par exemple. À revérifier si Claude%s" % (D, Z))
    print("  %sCode change sa façon de servir la mémoire.%s" % (D, Z))
    if servies:
        top = sorted(servies, key=lambda n: -lectures(n))
        for n in top[:5]:
            print("    %s%2d ×%s  %s" % (G, lectures(n), Z, n))
    print("")

    for titre, lot, coul in (("à archiver", a_archiver, R),
                             ("à endormir", dormantes, J),
                             ("jamais observées", jamais, D)):
        if not lot:
            continue
        print("  %s%s%s : %d" % (coul, titre, Z, len(lot)))
        for n, why in lot[:8]:
            print("    %s %s%s%s" % (n, D, why, Z))
        if len(lot) > 8:
            print("    %s… et %d autres%s" % (D, len(lot) - 8, Z))
        print("")

    # ── poids des notes ───────────────────────────────────────────────────
    niv = dict((n, niveau(chemin(n))) for n in cles)
    nus = [n for n in cles if niv[n] is None]
    faibles = [n for n in cles if niv[n] == "supposé"]
    print("  %sce qui établit chaque note%s : %d sur %d le disent"
          % (B, Z, len(notes) - len(nus), len(notes)))
    par = {}
    for v in niv.values():
        if v is not None:
            par[v] = par.get(v, 0) + 1
    if par:
        print("    %s" % " · ".join("%s %d" % (k, par[k]) for k in sorted(par)))
    if nus:
        print("    %s%d sans niveau — poids INCONNU, pas faible.%s" % (J, len(nus), Z))
        for n in nus[:8]:
            print("      %s%s%s" % (D, n, Z))
        if len(nus) > 8:
            print("      %s… et %d autres%s" % (D, len(nus) - 8, Z))
        print("    %sne pas leur en inventer un : on le pose en ROUVRANT la note.%s" % (D, Z))
    if faibles:
        # Le cas dangereux n'est pas la note faible, c'est la note faible QUI
        # SERT : à force d'être lue, elle prend le poids d'une mesure.
        chaud = [n for n in faibles if lectures(n) >= 3]
        if chaud:
            print("    %ssupposé ET servi ≥3 fois — à rejouer, pas à relire :%s" % (R, Z))
            for n in chaud:
                print("      %s (%d ×)" % (n, lectures(n)))
    print("")

    # ── ce qu'un RÉSULTAT a démenti ───────────────────────────────────────
    # Une note dont la confiance est tombée sous son point de départ a été lue
    # pendant qu'un constat tombait ou qu'une garde mordait. Ce n'est pas une
    # preuve qu'elle a tort — c'est une invitation à la REJOUER.
    dementies = []
    for n in cles:
        e = u.get(n)
        if e is None:
            e = {}
        c = _as_f64(_get(e, "conf"))
        if c is None:
            continue
        lvl = niveau(chemin(n))
        # Le départ vient de `nature.depart`, pas d'une copie : la copie d'ici
        # ignorait « lu » (12/10/2026) et le faisait partir de 50 au lieu de 60.
        depart = float(nature.depart(lvl or "", nature.Maison.MemoireAuto))
        if c < depart:
            r_ = _as_i64(_get(e, "res"))
            n_ = _as_i64(_get(e, "n"))
            dementies.append((n, c, depart, r_ if r_ is not None else 0,
                              n_ if n_ is not None else 0))
    if dementies:
        print("  %sdémenties par un résultat%s — à REJOUER, pas à relire :" % (J, Z))
        dementies.sort(key=lambda x: x[1])
        for n, c, dep, r_, lu in dementies[:6]:
            court = n[:40]
            print("    %-40s %s → %s  %s(%d résultat(s), %d lecture(s))%s"
                  % (court, g(dep), g(c), D, r_, lu, Z))
        print("")

    dbl = doublons(notes)
    if dbl:
        print("  %sdoublons probables%s — SIGNALÉS, jamais fusionnés :" % (J, Z))
        for _, x, y, mots in dbl:
            print("    %s ⟷ %s  %s(%s)%s" % (x[:28], y[:28], D, ", ".join(mots), Z))
        print("    %sfusionner demande de lire : c'est la partie qui coûte,%s" % (D, Z))
        print("    %set c'est au commanditaire de dire si elle vaut son prix.%s\n" % (D, Z))

    # ── application ───────────────────────────────────────────────────────
    if not appliquer:
        if a_archiver or dormantes:
            print("  %s--appliquer pour ranger. Rien n'est jamais effacé :%s" % (D, Z))
            print("  %sarchiver, c'est déplacer dans archive/ et retirer de l'index.%s\n" % (D, Z))
        return 0

    arch = os.path.join(mem, "archive")
    bouge = 0
    if a_archiver:
        try:
            os.makedirs(arch, exist_ok=True)
        except OSError:
            pass
        for n, _ in a_archiver:
            src = chemin(n)
            if os.path.exists(src):
                try:
                    os.replace(src, os.path.join(arch, "%s.md" % n))
                    bouge += 1
                except OSError:
                    pass
    # L'INDEX SUIT, SINON IL POINTE DANS LE VIDE. C'est lui qui est chargé à
    # chaque session : une ligne qui reste après le déplacement du fichier
    # coûte de l'attention et ne rend rien.
    idx = os.path.join(mem, "MEMORY.md")
    if bouge > 0 and os.path.exists(idx):
        t = _lire(idx)
        if t is not None:
            gardees = [l for l in _lignes(t)
                       if not any(("(%s.md)" % n) in l for n, _ in a_archiver)]
            texte = "\n".join(gardees).rstrip("\n") + "\n"
            try:
                with open(idx, "w", encoding="utf-8", newline="") as h:
                    h.write(texte)
            except OSError:
                pass
    for n, _ in dormantes:
        e = u.get(n)
        if e is None:
            e = {}
        e["etat"] = "dormante"
        u[n] = e
    ecrire_usage(mem, u)
    print("  %s%d archivée(s), %d endormie(s). Index mis à jour.%s\n"
          % (G, bouge, len(dormantes), Z))
    return 0
