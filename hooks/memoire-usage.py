#!/usr/bin/env python3
"""L'INSTRUMENT QUI MANQUAIT À LA MÉMOIRE : noter ce qui a SERVI.

54 notes, aucune trace de celles qui ont déjà servi. Impossible donc de
distinguer une note vivante d'une note morte : l'index grossit, tout se vaut, et
rien ne remonte au bon moment. C'est le même trou que le harnais avait sur ses
propres blocages jusqu'au 09/09/2026 — **un mécanisme sans trace ne peut pas
être jugé**, et une mémoire dont on ignore l'usage ne peut pas être entretenue.

Repris à un agent de référence, qui fait vieillir ses compétences sur leur
dernier usage. Sa mécanique est bonne ; il lui fallait, chez nous, la mesure.

CE HOOK NE DÉCIDE RIEN. Il écrit une ligne quand une note de mémoire est lue.
Le vieillissement, l'archivage et le rangement sont le travail de
`claude-memoire`, qui tourne à part et rend un rapport.

POURQUOI SUR `Read` ET PAS SUR UNE DÉCLARATION DE L'AGENT. Une étiquette que
l'agent pose lui-même ne se pose jamais : `échoué` existe depuis le début du
carnet d'équipe et ZÉRO des vingt entrées la porte. Le déclencheur juste est
celui que l'agent produit sans y penser — ici, ouvrir le fichier.

ET LA VOIE PAR OÙ CET AGENT LIT VRAIMENT SES NOTES N'ÉTAIT PAS BRANCHÉE.
Mesuré le 10/09/2026, neuf heures après la mise en service : le registre portait
SIX épingles et ZÉRO lecture. Le hook était juste, déclaré, appelé — sur l'outil
de lecture. Or en mode autonome le harnais demande de lire avec `cat`, `sed`,
`grep`, `python3`, c'est-à-dire par le SHELL. Le déclencheur était donc branché
sur la porte que l'agent n'emprunte pas. La leçon est déjà écrite en mémoire —
un mécanisme sans appelant se lit comme présent — et elle valait ici.

On regarde donc aussi les appels au shell, sur DEUX voies, parce qu'aucune des
deux ne suffit :
  1. LE CHEMIN CITÉ DANS LA COMMANDE — attrape `cat <chemin>`, un chemin écrit
     en toutes lettres dans un script. Rate ce qui passe par une variable.
  2. LE CHEMIN RENDU PAR LA SORTIE — attrape `grep -l "$M"/*.md`, où la commande
     ne montre aucun chemin mais où le résultat les énumère.

DEUX GARDES, et elles portent le sens :
  · une CIBLE D'ÉCRITURE ne compte pas. `cat > .../note.md` écrit la note, il ne
    la consulte pas ; la créditer d'une lecture gonflerait sa demi-vie avec ma
    propre plume. Détecté sur le `>` ou `>>` qui précède.
  · au-delà de TROIS notes dans un seul appel, on ne compte RIEN. Un `ls` du
    dossier de mémoire nomme les soixante et une notes ; c'est un inventaire,
    pas une lecture, et le compter ferait de tout le monde une note vivante.

CE QU'IL VOIT, ET C'EST PLUS QUE CE QU'ON CROYAIT. On l'a d'abord présenté
comme un plancher : « les notes que le harnais glisse dans le contexte lui
échappent ». MESURÉ LE 09/09/2026 sur 40 transcriptions récentes : 11 injections
automatiques, **toutes l'index `MEMORY.md`, zéro note individuelle**. Le harnais
sert le sommaire, jamais le contenu — donc ce compte est le TOTAL. Reste hors de
sa vue une note lue autrement que par l'outil de lecture. À revérifier si Claude
Code change sa façon de servir la mémoire ; la sonde tient en un hook
`InstructionsLoaded`, qui lui ne part QUE pour les `CLAUDE.md`.

BUDGET. Ce hook tourne après CHAQUE lecture de fichier. Il doit donc sortir en
quelques millisecondes quand le chemin ne le concerne pas — c'est-à-dire
presque toujours. D'où la forme : un test de sous-chaîne, puis `sys.exit(0)`.
Aucun import lourd, aucune I/O avant le test.
"""
import sys, os, json, pathlib, datetime, re

# Le dossier de mémoire auto, quel que soit le projet. La clé est le CHEMIN
# slugifié du projet : `~/.claude/projects/<slug>/memory/`.
MARQUE = "/.claude/projects/"
SOUS = "/memory/"

# Le même chemin, mais reconnu AU MILIEU d'un texte — une ligne de commande ou
# sa sortie. Sans la barre de tête : un script écrit `~/.claude/projects/...`
# ou `$HOME/.claude/...`, jamais le chemin absolu nu.
CHEMIN = re.compile(r"[^\s'\"`;|]*\.claude/projects/[^\s'\"`;|]*?/memory/[^\s'\"`;|/]+\.md")
NOTES_MAX = 3


def notes_citees(texte, ecarter_cibles):
    """Les notes nommées dans un texte, dans l'ordre, sans doublon.

    `ecarter_cibles` : ignorer ce qui suit un `>` ou `>>`, c'est-à-dire ce que
    la commande ÉCRIT. Vrai pour une commande, faux pour une sortie — une
    sortie ne redirige rien.
    """
    vus, out = set(), []
    for m in CHEMIN.finditer(texte):
        if ecarter_cibles:
            avant = texte[:m.start()].rstrip()
            if avant.endswith(">"):
                continue
        nom = pathlib.PurePath(m.group(0)).stem
        if nom.upper() == "MEMORY" or nom in vus:
            continue
        vus.add(nom)
        out.append(nom)
    return out


def par_le_shell(data):
    """Un appel au shell : la commande, puis sa sortie."""
    cmd = ""
    ti = data.get("tool_input")
    if isinstance(ti, dict):
        cmd = str(ti.get("command") or "")
    rep = data.get("tool_response")
    if isinstance(rep, dict):
        sortie = "".join(str(rep.get(k) or "") for k in ("stdout", "stderr", "output"))
    else:
        sortie = str(rep or "")

    noms = notes_citees(cmd, True)
    for n in notes_citees(sortie, False):
        if n not in noms:
            noms.append(n)
    if not noms or len(noms) > NOTES_MAX:
        return                                   # rien, ou un inventaire

    # Le dossier : celui du premier chemin rencontré, tel quel. On ne
    # reconstruit RIEN — un chemin deviné ferait écrire à côté en silence.
    dossier = None
    for texte, ec in ((cmd, True), (sortie, False)):
        for m in CHEMIN.finditer(texte):
            if ec and texte[:m.start()].rstrip().endswith(">"):
                continue
            c = pathlib.Path(os.path.expanduser(m.group(0).replace("$HOME", "~")))
            if c.parent.is_dir():
                dossier = c.parent
                break
        if dossier:
            break
    if dossier is None:
        return

    sess = str(data.get("session_id") or "")
    for nom in noms:
        if (dossier / (nom + ".md")).exists():
            compte(dossier / ".usage.json", nom, sess)


def compte(etat, nom, sess):
    """Une lecture de plus pour `nom`, et le registre de la session."""
    try:
        d = json.loads(etat.read_text()) if etat.exists() else {}
    except Exception:
        d = {}
    e = d.get(nom) or {}
    e["vu"] = datetime.date.today().isoformat()
    e["n"] = int(e.get("n", 0)) + 1
    d[nom] = e
    if sess:
        lot = d.setdefault("_encours", {}).setdefault(sess, [])
        if nom not in lot:
            lot.append(nom)
        if len(lot) > 40:
            del lot[:-40]
    try:
        tmp = etat.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True))
        os.replace(tmp, etat)
    except Exception:
        pass


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return                                   # fail-open, toujours

    if str(data.get("tool_name") or "") == "Bash":
        return par_le_shell(data)

    chemin = ""
    for source in (data.get("tool_input") or {}, data.get("tool_response") or {}):
        if isinstance(source, dict):
            chemin = str(source.get("file_path") or source.get("filePath") or "") or chemin

    if not chemin or MARQUE not in chemin or SOUS not in chemin:
        return                                   # le cas de très loin le plus fréquent
    if not chemin.endswith(".md"):
        return

    p = pathlib.Path(chemin)
    nom = p.stem
    # MEMORY.md est l'index, pas une note : le lire ne prouve rien sur les notes.
    if nom.upper() == "MEMORY":
        return

    etat = p.parent / ".usage.json"
    try:
        d = json.loads(etat.read_text()) if etat.exists() else {}
    except Exception:
        d = {}
    e = d.get(nom) or {}
    e["vu"] = datetime.date.today().isoformat()
    e["n"] = int(e.get("n", 0)) + 1
    d[nom] = e

    # LE REGISTRE DE LECTURE — repris à sense-lab (AMFS), qui l'appelle
    # ReadTracker. Il retient ce qui a été LU DEPUIS LE DERNIER VERDICT, et rien
    # d'autre : quand un résultat tombe, ce sont ces notes-là qui gagnent ou qui
    # perdent, pas toute la mémoire. Le hook de fin de tour vide la liste après
    # l'avoir appliquée — c'est ce vidage qui rend le lien CAUSAL au lieu de
    # cumulatif. Sans lui, une note lue il y a trois jours serait punie pour un
    # échec d'aujourd'hui.
    sess = str(data.get("session_id") or "")
    if sess:
        enc = d.setdefault("_encours", {})
        lot = enc.setdefault(sess, [])
        if nom not in lot:
            lot.append(nom)
        # Un plafond, parce que ce fichier est relu à chaque lecture : une
        # session qui ouvrirait tout finirait par le rendre lourd.
        if len(lot) > 40:
            del lot[:-40]
    try:
        # Écriture atomique : ce fichier est lu par `claude-memoire` pendant que
        # des agents écrivent dedans. Un fichier tronqué se lirait comme une
        # mémoire jamais servie, et ferait archiver ce qui vient de servir.
        tmp = etat.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True))
        os.replace(tmp, etat)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
