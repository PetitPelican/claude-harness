# -*- coding: utf-8 -*-
"""L'INSTRUMENT QUI MANQUAIT À LA MÉMOIRE : noter ce qui a SERVI.

Port de `harnais/src/usage.rs` (0.12.8).

Sans lui, impossible de distinguer une note vivante d'une note morte :
l'index grossit, tout se vaut, rien ne remonte au bon moment. Repris à
un agent de référence, qui fait vieillir ses compétences sur leur dernier usage.

CE HOOK NE DÉCIDE RIEN. Il écrit une ligne quand une note est lue. Le
vieillissement, l'archivage et le rangement sont le travail du curateur, qui
tourne à part et rend un rapport.

POURQUOI SUR `Read` ET PAS SUR UNE DÉCLARATION DE L'AGENT. Une étiquette que
l'agent pose lui-même ne se pose jamais : `échoué` existe depuis le début du
carnet et ZÉRO des vingt entrées la porte. ECC a mesuré la même chose de son
côté — une compétence part 50 à 80 % du temps, un hook 100 %. Le déclencheur
juste est celui que l'agent produit sans y penser : ouvrir le fichier.

CE QU'IL VOIT, ET C'EST LE TOTAL. On l'a d'abord présenté comme un plancher.
Mesuré le 09/09/2026 sur 40 transcriptions : 11 injections automatiques,
TOUTES l'index, zéro note individuelle. Le harnais sert le sommaire, jamais
le contenu.

BUDGET. Ce hook tourne après CHAQUE lecture de fichier. Il doit donc sortir
en quelques millisecondes quand le chemin ne le concerne pas — c'est-à-dire
presque toujours. Le Rust y gagnait 2 ms au lieu de 24 ; ici, le chemin « rien
à faire » ne regarde que le texte brut (une sous-chaîne) et n'importe RIEN :
ni `json`, ni `re`, ni `os`.
"""

MARQUE = "/.claude/projects/"
SOUS = "/memory/"

# Les blancs de Rust (`\s` du crate `regex` = White_Space ; `trim()`), pas ceux de
# `\s` ni de `str.strip()` de Python, qui y ajoutent \x1c-\x1f.
BLANCS = ("\t\n\x0b\x0c\r \x85\xa0       "
          "         　")
_CLASSE_BLANCS = ("\\t\\n\\x0b\\x0c\\r \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029"
                  "\\u202f\\u205f\\u3000")

# LE MÊME CHEMIN, RECONNU AU MILIEU D'UN TEXTE — une ligne de commande ou sa
# sortie. Sans la barre de tête : un script écrit `~/.claude/projects/…` ou
# `$HOME/.claude/…`, jamais le chemin absolu nu.
MOTIF = ("[^" + _CLASSE_BLANCS + "'\"`;|]*\\.claude/projects/[^" + _CLASSE_BLANCS
         + "'\"`;|]*?/memory/[^" + _CLASSE_BLANCS + "'\"`;|/]+\\.md")

# Au-delà de trois notes dans un seul appel, on ne compte RIEN : un `ls` du
# dossier de mémoire nomme les soixante et une notes. C'est un inventaire, pas
# une lecture, et le compter ferait de tout le monde une note vivante.
NOTES_MAX = 3

# Plafond du registre de lecture : ce fichier est relu à chaque lecture, une
# session qui ouvrirait tout finirait par le rendre lourd.
REGISTRE_MAX = 40

_RE = []


def _motif():
    if not _RE:
        import re
        _RE.append(re.compile(MOTIF))
    return _RE[0]


def _est_memory(nom):
    # `eq_ignore_ascii_case("MEMORY")` : insensible à la casse pour l'ASCII SEULEMENT
    # (le `lower()` de Python replierait aussi des lettres non ASCII).
    return len(nom) == 6 and nom.isascii() and nom.lower() == "memory"


def _stem(chemin):
    """`Path::file_stem` : le nom de fichier sans sa dernière extension. Un nom
    qui ne commence que par son point (`.md`) reste entier."""
    nom = chemin.rsplit("/", 1)[-1]
    i = nom.rfind(".")
    if i <= 0:
        return nom
    return nom[:i]


def notes_citees(texte, ecarter_cibles):
    """Les notes nommées dans un texte, dans l'ordre, sans doublon.

    `ecarter_cibles` : ignorer ce qui suit un `>` ou `>>`, c'est-à-dire ce que la
    commande ÉCRIT. `cat > …/note.md` crée la note, il ne la consulte pas ; la
    créditer d'une lecture gonflerait sa demi-vie avec ma propre plume. Vrai pour
    une commande, faux pour une sortie — une sortie ne redirige rien.
    """
    out = []
    for m in _motif().finditer(texte):
        if ecarter_cibles and texte[:m.start()].rstrip(BLANCS).endswith(">"):
            continue
        nom = _stem(m.group(0))
        if _est_memory(nom) or nom in out:
            continue
        out.append(nom)
    return out


def deplie(brut):
    import os
    maison = _maison()
    s = brut.replace("$HOME", maison)
    if s.startswith("~/"):
        return os.path.join(maison, s[2:])
    return s


def _maison():
    import os
    return os.environ.get("HOME") or os.environ.get("USERPROFILE") or "."


def _sortie_de(rep):
    if isinstance(rep, str):
        return rep
    if isinstance(rep, dict):
        return "".join(rep[k] for k in ("stdout", "stderr", "output")
                       if isinstance(rep.get(k), str))
    return ""


def par_le_shell(d):
    """Un appel au shell : la commande, puis sa sortie. Les deux voies sont
    nécessaires — la première rate ce qui passe par une variable, la seconde
    rate ce qui ne s'affiche pas."""
    ti = d.get("tool_input")
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(cmd, str):
        cmd = ""
    sortie = _sortie_de(d.get("tool_response"))

    noms = notes_citees(cmd, True)
    for n in notes_citees(sortie, False):
        if n not in noms:
            noms.append(n)
    if not noms or len(noms) > NOTES_MAX:
        return                          # rien, ou un inventaire

    # Le dossier : celui du premier chemin rencontré, tel quel. On ne
    # reconstruit RIEN — un chemin deviné ferait écrire à côté en silence.
    import os
    dossier = None
    for texte, ec in ((cmd, True), (sortie, False)):
        for m in _motif().finditer(texte):
            if ec and texte[:m.start()].rstrip(BLANCS).endswith(">"):
                continue
            par = os.path.dirname(deplie(m.group(0)))
            if os.path.isdir(par):
                dossier = par
                break
        if dossier is not None:
            break
    if dossier is None:
        return
    session = d.get("session_id")
    if not isinstance(session, str):
        session = ""
    jour = _aujourdhui()
    for nom in noms:
        if os.path.exists(os.path.join(dossier, nom + ".md")):
            note_l_usage(os.path.join(dossier, ".usage.json"), nom, session, jour)


def _aujourdhui():
    import time
    return time.strftime("%Y-%m-%d")


def chemin_lu(d):
    """Le chemin lu, s'il y en a un. `tool_response` gagne sur `tool_input` quand
    les deux sont là — c'est l'ordre qu'avait la version Python."""
    trouve = None
    for cle in ("tool_input", "tool_response"):
        o = d.get(cle)
        if isinstance(o, dict):
            for k in ("file_path", "filePath"):
                s = o.get(k)
                if isinstance(s, str) and s:
                    trouve = s
    return trouve


def est_une_note(chemin):
    """Est-ce une NOTE de mémoire ? `MEMORY.md` est l'index, pas une note : le lire
    ne prouve rien sur les notes."""
    if MARQUE not in chemin or SOUS not in chemin or not chemin.endswith(".md"):
        return False
    return not _est_memory(_stem(chemin))


def _entier(v):
    """`Value::as_i64` : un entier JSON qui tient dans 64 bits, sinon None."""
    if isinstance(v, bool) or not isinstance(v, int):
        return None
    if -(2 ** 63) <= v < 2 ** 63:
        return v
    return None


def _plus_un(n):
    """`n + 1` sur un `i64` : le programme livré (mode release) boucle au lieu de
    déborder, et Python n'a pas de borne."""
    n += 1
    if n > 2 ** 63 - 1:
        n -= 2 ** 64
    return n


def _refuse(c):
    # serde_json refuse NaN et Infinity ; `json.loads` de Python les accepte.
    raise ValueError(c)


def note_l_usage(fichier, nom, session, aujourdhui):
    """Met à jour le compte et le registre. Rend True si quelque chose a été écrit."""
    import json
    import os
    try:
        with open(fichier, encoding="utf-8") as h:
            d = json.loads(h.read(), parse_constant=_refuse)
    except (OSError, ValueError, RecursionError):
        d = {}
    if not isinstance(d, dict):
        return False

    # `entry().or_insert()` : seule une clé ABSENTE reçoit un objet vide (un `null`
    # présent reste `null`, et n'est pas mis à jour).
    if nom not in d:
        d[nom] = {}
    e = d[nom]
    if isinstance(e, dict):
        e["vu"] = aujourdhui
        e["n"] = _plus_un(_entier(e.get("n")) or 0)

    # LE REGISTRE DE LECTURE — repris à sense-lab, qui l'appelle ReadTracker.
    # Il retient ce qui a été lu DEPUIS LE DERNIER VERDICT, et rien d'autre :
    # quand un résultat tombe, ce sont ces notes-là qui gagnent ou qui perdent.
    # Le vidage par le hook de fin de tour est ce qui rend le lien CAUSAL au
    # lieu de cumulatif — sans lui, une note lue il y a trois jours serait
    # punie pour un échec d'aujourd'hui.
    if session:
        if "_encours" not in d:
            d["_encours"] = {}
        enc = d["_encours"]
        if isinstance(enc, dict):
            if session not in enc:
                enc[session] = []
            lot = enc[session]
            if isinstance(lot, list):
                if not any(isinstance(v, str) and v == nom for v in lot):
                    lot.append(nom)
                if len(lot) > REGISTRE_MAX:
                    del lot[0:len(lot) - REGISTRE_MAX]

    # ÉCRITURE ATOMIQUE. Ce fichier est lu par le curateur pendant que des
    # agents écrivent dedans. Un fichier tronqué se lirait comme une mémoire
    # jamais servie, et ferait archiver ce qui vient de servir.
    # LA FORME EXACTE DE PYTHON, et pas seulement le même contenu : indentation
    # d'un espace, clés triées à TOUS les niveaux, accents écrits tels quels.
    # Elle vivait ici en dur, et le jour où le carnet a demandé l'ordre
    # d'insertion à serde, ce fichier-ci a changé de forme sans que rien le
    # dise — un réglage partagé périme les preuves des voisins.
    import socle
    socle.ecrire_json(fichier, d)
    return os.path.exists(fichier)


def main(entree):
    # LE CHEMIN « RIEN À FAIRE », SANS IMPORT : ni une note de mémoire ni un
    # appel qui en nomme une ne peut se passer de `.claude/projects/` dans son
    # texte. Une échappation JSON (`\uXXXX`, `\/`) pourrait le déguiser : on
    # envoie alors au chemin complet. Aucun cas que le Rust attrape n'y échappe.
    if ".claude/projects/" not in entree and "\\u" not in entree and "\\/" not in entree:
        return
    import json
    try:
        d = json.loads(entree, parse_constant=_refuse)
    except (ValueError, RecursionError):
        return  # fail-open, toujours
    if not isinstance(d, dict):
        return
    if d.get("tool_name") == "Bash":
        par_le_shell(d)
        return
    chemin = chemin_lu(d)
    if chemin is None:
        return
    if not est_une_note(chemin):
        return  # le cas de très loin le plus fréquent
    import os
    nom = _stem(chemin)
    parent = os.path.dirname(chemin)
    etat = os.path.join(parent, ".usage.json")
    session = d.get("session_id")
    if not isinstance(session, str):
        session = ""
    note_l_usage(etat, nom, session, _aujourdhui())
