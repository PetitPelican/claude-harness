#!/usr/bin/env python3
"""LA MOITIÉ QUI JUGE — celle que l'auteur ne peut pas faire sur son propre travail.

L'EXTRACTION EST MÉCANIQUE, ET C'EST LE POINT. Si l'auteur choisit les
affirmations à soumettre, il soumettra celles dont il est sûr. La règle est donc
écrite ici, elle ne change pas d'un passage à l'autre, et elle est vérifiable :

  1. On prend les MESSAGES D'ENREGISTREMENT du jour, paragraphe par paragraphe,
     chacun précédé de son titre pour qu'il tienne debout tout seul.
  2. On prend les LIGNES AJOUTÉES le jour même aux fichiers d'état et de
     décisions — pas leur contenu entier, qui remonte à des semaines.
  3. On ne garde que ce qui PORTE UN CHIFFRE : le plus réfutable.
  4. On dédoublonne, puis on TRIE PAR EMPREINTE et on prend les N premières.
     Un tri par empreinte est un tirage : l'auteur ne peut ni prévoir ni
     infléchir quelles affirmations partiront.

CHAQUE JUGE A UN CONTEXTE NEUF, des outils EN LECTURE SEULE, et ni la
conversation ni le raisonnement de l'auteur. Il peut mesurer ; il ne peut pas
écrire. Le verdict est un jeu fermé, et le MUET n'est jamais un accord.

QUAND LA LANCER : après la passe mécanique, avant de demander à l'humain de
publier. COMMENT : `python3 controles/passe-jugee.py [JOUR] [N]` — JOUR au
format AAAA-MM-JJ (aujourd'hui par défaut), N juges au plus (20 par défaut).
`N = 0` ne lance aucun juge : il dit seulement combien d'affirmations
l'extraction trouve, et c'est le geste pour vérifier qu'elle voit quelque chose.
Chaque juge est un `claude -p` en sonnet, sans outil d'écriture, lancé dans le
dépôt du paquet — qui n'est le dossier d'aucun agent.

LES SOURCES ONT CHANGÉ LE 26/09/2026. Elle lisait le dépôt du paquet et celui
du CTO, en cherchant `.mind/state.md` : depuis la passation du 11/09, les
affirmations du mainteneur vivent dans le projet Harness, sous `brain/`, et
elle n'en voyait aucune — une passe qui ne trouve rien à juger rend le même
silence qu'une passe où tout est confirmé.
"""
import concurrent.futures as cf, hashlib, json, os, pathlib, re, subprocess, sys

ICI = pathlib.Path(__file__).resolve().parent
R = ICI.parent
HARNESS = pathlib.Path.home()/"Agentic/Harness"
JOUR = sys.argv[1] if len(sys.argv) > 1 else __import__("datetime").date.today().isoformat()
MAXI = int(sys.argv[2]) if len(sys.argv) > 2 else 20
CLAUDE = str(pathlib.Path.home()/".local/bin/claude")
DELAI = 300

def _propre(p):
    return " ".join(p.split())

def affirmations():
    b = []
    for depot, nom in ((R, "claude-harnais"), (HARNESS, "Harness")):
        t = subprocess.run(["git", "log", "--since", JOUR + " 00:00",
                            "--format=%H%x01%s%x01%b%x02"],
                           cwd=str(depot), capture_output=True, text=True).stdout
        for c in t.split("\x02"):
            if "\x01" not in c: continue
            sha, suj, corps = c.strip().split("\x01", 2)
            for par in re.split(r"\n\s*\n", corps):
                par = _propre(par)
                if par.startswith(("Co-Authored", "Claude-Session", "http")): continue
                if len(par) < 60: continue
                b.append(("%s %s" % (nom, sha[:8]), suj + " — " + par, sha))
        # ce qui a été AJOUTÉ le jour même à l'état et aux décisions
        for rel in ("brain/mind/state.md", "docs/decisions.md", "brain/mind/todo.md"):
            if not (depot/rel).exists(): continue
            d = subprocess.run(["git", "log", "--since", JOUR + " 00:00", "-p",
                                "--format=", "--", rel],
                               cwd=str(depot), capture_output=True, text=True).stdout
            bloc = []
            for l in d.splitlines():
                if l.startswith("+++") or l.startswith("---"): continue
                if l.startswith("+"):
                    bloc.append(l[1:])
                else:
                    if bloc: b.append((rel, _propre(" ".join(bloc)), None)); bloc = []
            if bloc: b.append((rel, _propre(" ".join(bloc)), None))
    net = [t for t in b if re.search(r"\d", t[1]) and 60 <= len(t[1]) <= 700]
    vivants = {}
    def encore_la(o, p):
        if o not in vivants:
            for d in (R, HARNESS):
                if (d/o).exists(): vivants[o] = _propre((d/o).read_text()); break
            else: vivants[o] = ""
        tete = _propre(p)[:70]
        return tete and tete in vivants[o]
    vus, fin = set(), []
    for o, p, sha in net:
        if sha is None and not encore_la(o, p):
            continue                    # raturé dans la journée : plus une affirmation
        k = hashlib.sha1(re.sub(r"[^a-z0-9]", "", p.lower()).encode()).hexdigest()
        if k in vus: continue
        vus.add(k); fin.append((k, o, p, sha))
    fin.sort()                     # le tirage : par empreinte, donc imprévisible
    return fin

BRUT = ICI/"verdicts-bruts"

def juge(item, criteres):
    _, origine, affirmation, sha = item
    if sha:
        cadre = ("Cette affirmation est FIGÉE : c'est un message d'enregistrement "
                 "écrit au moment du commit " + sha[:12] + ". Juge-la sur l'état du "
                 "dépôt À CE COMMIT (`git show " + sha[:12] + "`, `git show "
                 + sha[:12] + ":<fichier>`), PAS sur l'état d'aujourd'hui. Qu'un "
                 "enregistrement ULTÉRIEUR l'ait corrigée n'en fait pas une "
                 "affirmation fausse — c'est une trace datée, et elle a le droit "
                 "d'être dépassée.")
    else:
        cadre = ("Cette affirmation est VIVANTE : elle est écrite au présent dans "
                 + origine + ", telle quelle, aujourd'hui. Juge-la sur l'état "
                 "ACTUEL du dépôt et de la machine.")
    invite = (
        "Tu es un contrôleur indépendant. Tu n'as PAS écrit ce qui suit, tu n'as "
        "aucun accès à la conversation qui l'a produit, et tu ne dois rien en "
        "supposer.\n\nTes critères, que tu ne peux pas modifier :\n\n" + criteres +
        "\n\n" + cadre + "\n\n=== L'AFFIRMATION À JUGER (source : " + origine +
        ") ===\n\n" +
        affirmation + "\n\n=== FIN DE L'AFFIRMATION ===\n\nLe travail décrit vit "
        "dans " + str(pathlib.Path(__file__).resolve().parent.parent) + " et " + str(HARNESS) + ". "
        "Mesure avant de conclure : lis les fichiers, cherche dans le texte, "
        "interroge l'historique.\n\nRéponds par UNE SEULE LIGNE commençant par "
        "exactement l'un de ces trois mots : CONFIRME, ou CONTREDIT suivi du "
        "motif, ou INSUFFISANT suivi de ce qui manque. Aucun préambule, aucune "
        "suggestion. Dans le doute, INSUFFISANT.")
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
    try:
        r = subprocess.run(
            [CLAUDE, "-p", "--model", "claude-sonnet-5",
             "--allowedTools", "Read", "Grep", "Glob", "Bash(git log:*)",
             "Bash(git show:*)", "Bash(git diff:*)", "Bash(ls:*)", "Bash(cat:*)",
             "Bash(wc:*)", "Bash(grep:*)", "Bash(find:*)",
             "--disallowedTools", "Write", "Edit", "NotebookEdit",
             "--permission-mode", "plan", invite],
            capture_output=True, text=True, env=env, cwd=str(R), timeout=DELAI)
    except subprocess.TimeoutExpired:
        return "INSUFFISANT le contrôleur n'a pas rendu de verdict en %d s" % DELAI
    s = (r.stdout or "").strip()
    (BRUT/("%s.txt" % item[0][:12])).write_text(
        invite[-400:] + "\n\n===== RÉPONSE =====\n" + s)
    trouve = None
    for l in s.splitlines():
        n = l.strip().lstrip("*#>- ")
        h = n.upper().replace("É", "E").replace("CONFIRMED", "CONFIRME")
        if h.startswith(("CONFIRME", "CONTREDIT", "INSUFFISANT")):
            trouve = n                      # la DERNIÈRE l'emporte : c'est la conclusion
    if trouve:
        return trouve
    return "INSUFFISANT verdict illisible : %s" % (s.replace("\n", " ")[:90] or "(rien)")

def main():
    criteres = (R/"criteres-passe.md").read_text()
    BRUT.mkdir(exist_ok=True)
    tout = affirmations()
    lot = tout[:MAXI]
    print("extraction mécanique : %d affirmations chiffrées · %d tirées par "
          "empreinte" % (len(tout), len(lot)), flush=True)
    res = []
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        for it, v in zip(lot, ex.map(lambda x: juge(x, criteres), lot)):
            res.append((it[1], it[2], v))
            print("  %-12s %-14s %s" % (v.split()[0], it[1][:14], it[2][:70]),
                  flush=True)
    tombes = [r for r in res if r[2].upper().startswith("CONTREDIT")]
    flous = [r for r in res if r[2].upper().replace("É","E").startswith("INSUFFISANT")]
    print("\nCONFIRMÉES %d · CONTREDITES %d · INSUFFISANTES %d"
          % (len(res)-len(tombes)-len(flous), len(tombes), len(flous)), flush=True)
    if not lot:
        return                      # N = 0 : un essai à blanc n'efface pas le dernier verdict
    (ICI/"dernier-verdict.json").write_text(json.dumps(
        [{"source": o, "affirmation": a, "verdict": v} for o, a, v in res],
        ensure_ascii=False, indent=1))
    for o, a, v in tombes + flous:
        print("\n· [%s] %s\n  → %s" % (o, a[:280], v[:420]), flush=True)

main()
