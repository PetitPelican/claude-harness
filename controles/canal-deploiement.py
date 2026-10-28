#!/usr/bin/env python3
"""PAR OÙ PART LE HOOK — et est-ce que le code qu'il appelle est celui d'aujourd'hui.

POURQUOI CE CONTRÔLE EXISTE. Le 10/09/2026, en préparant le déménagement de la
mémoire, on a mesuré une chose que personne ne surveillait : **le paquet n'est
pas le canal principal**. Un seul agent sur douze tourne dessus. Les autres
appellent `~/.claude/hooks/*.py` ou une copie locale, par des chemins écrits à
la main dans leur `settings.json`.

Trois conséquences, et aucune ne se voyait :

  · publier une version du paquet ne change RIEN pour onze projets sur douze ;
  · six projets portent une copie de `briefing.py` de 410 lignes, contre 731 en
    vigueur — soit une version qui n'a jamais entendu parler de `.fact/` ;
  · le modèle d'agent du starter pointe sur ces copies : **tout agent monté
    aujourd'hui naît sourd**, et rien ne le dit.

CE QUE CE CONTRÔLE AFFIRME, et c'est deux choses distinctes :

  ① par quel canal chaque agent reçoit ses hooks — un fait, pas un jugement ;
  ② que le code EFFECTIVEMENT APPELÉ est celui d'aujourd'hui — un jugement.

Un `settings.json` qui déclare proprement un fichier périmé passe le premier
test et échoue le second. C'est exactement la panne qu'on cherche : **la
déclaration est juste, le code est vieux, et le silence est le même.**

Il ne modifie rien. On peut le lancer n'importe quand.
"""
import hashlib, json, pathlib, re, subprocess, sys

HOME = pathlib.Path.home()
ATELIER = HOME / "Agentic"
DEPOT = pathlib.Path(__file__).resolve().parent.parent

G, J, R, D, B, X = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"

# La MARQUE d'un briefing d'aujourd'hui. On ne compare pas des lignes — un
# fichier peut grossir pour vingt raisons — on cherche la fonction qui résout
# les deux racines, celle qui est apparue avec `.fact/`. Un fichier qui ne la
# porte pas ne peut pas servir un projet migré, quelle que soit sa taille.
# La MARQUE ne sert plus de mesure d'écart entre deux Python : elle sert à
# reconnaître une COPIE SURVIVANTE et à dire si elle est périmée. Le 10/09/2026
# (lot 1) le repli Python a été supprimé du dépôt et du poste ; la référence
# d'aujourd'hui est le PROGRAMME.
MARQUE = "def racines("
REFERENCE = DEPOT / "bin" / "harnais"

# LES FICHIERS DU HARNAIS, PAR NOM EXACT — la même liste que `py/bascule.py`, et
# pour la même raison : `journal.py` est du harnais, `journal-metier.py` ne
# l'est pas. Un test sur la sous-chaîne confondrait les deux.
NOMS_HARNAIS = ("briefing.py", "attente.py", "journal.py", "usage.py",
                "mind-guard.py", "carnet.py", "memoire.py", "relecture.py")


def liste_du_programme():
    """CE QUE `py/bascule.py` CONSIDÈRE COMME DU HARNAIS — lu, pas recopié.

    Cette liste vit des deux côtés, dans deux langages, et le commentaire
    ci-dessus le reconnaissait sans rien en faire. Mesuré le 10/09/2026 (audit
    P5) : les deux copies s'accordaient. C'est le cas tranquille, celui qui
    précède le désaccord — le jour où l'une gagne un nom, l'autre continue de
    répondre sans lui, et **rien ne le dit**.

    On ne fusionne pas : les deux vivent dans des langages différents et le côté
    Python part avec les replis. On CONFRONTE, ce qui suffit à faire échouer le
    contrôle le jour du désaccord.
    """
    import re
    f = pathlib.Path(__file__).resolve().parent.parent / "py" / "bascule.py"
    if not f.is_file():
        return None, "`py/bascule.py` introuvable : la confrontation des deux listes n'a PAS eu lieu"
    m = re.search(r"^NOMS_HARNAIS = \[(.*?)\]", f.read_text(encoding="utf-8"), re.S | re.M)
    if not m:
        return None, "la liste de `py/bascule.py` n'a pas pu être lue — confrontation impossible"
    return tuple(sorted(re.findall(r'"([^"]+)"', m.group(1)))), None
PAQUET = "harnais@atelier"


def canal(cmd):
    """Le canal d'une commande de hook, et le fichier qu'elle appelle vraiment."""
    if "CLAUDE_PLUGIN_ROOT" in cmd:
        return "paquet", None
    m = re.search(r'"([^"]*\.claude/hooks/[a-z-]+\.py)"', cmd)
    if not m:
        return "?", None
    brut = m.group(1)
    if brut.startswith("$HOME") or "/.claude/hooks/" in brut and brut.startswith("/"):
        return "maison", pathlib.Path(brut.replace("$HOME", str(HOME)))
    if "CLAUDE_PROJECT_DIR" in brut:
        return "local", brut          # résolu par l'appelant, pas ici
    return "?", None


def resous(brut, base):
    """Le chemin réel d'un appel `${CLAUDE_PROJECT_DIR:-.}/...`."""
    rel = brut.split("}", 1)[-1].lstrip("/")
    return (base / rel).resolve()


def arbre_principal(p):
    """L'arbre de travail PRINCIPAL du dépôt qui contient `p`, ou None.

    `git worktree list --porcelain` rend le principal en premier — c'est la
    définition de git, pas une convention qu'on se donne ici.
    """
    try:
        r = subprocess.run(["git", "-C", str(p.parent), "worktree", "list",
                            "--porcelain"], capture_output=True, text=True,
                           timeout=10)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    for ligne in r.stdout.splitlines():
        if ligne.startswith("worktree "):
            return pathlib.Path(ligne.split(" ", 1)[1])
    return None


def gardes_derives(propres, base):
    """LES GARDES DU PROJET ONT-ILS DÉRIVÉ DE L'ARBRE PRINCIPAL ?

    POURQUOI CETTE FONCTION EXISTE. Jusqu'au 16/09/2026 ce contrôle COMPTAIT
    les gardes propres au projet — « 4 garde(s) propre(s) au projet » — puis
    passait au suivant, et concluait « tout le code appelé porte la marque du
    jour ». La phrase portait sur TOUT le code appelé ; la mesure ne couvrait
    que le canal du paquet. Zéro comparaison d'empreinte dans tout le fichier.

    Ce qu'il ne pouvait donc pas voir, et qu'un audit a trouvé à la main : un
    garde du projet vit DANS le dépôt, donc il vieillit avec la BRANCHE de
    l'arbre qui l'ouvre. Chez `Alpha QA`, l'arbre s'était séparé du tronc le
    06/09 ; le garde qui réserve la base de Production à un seul agent est du
    09/09 ; il n'y est jamais arrivé. Un agent par arbre de travail, c'est
    aussi un jeu de gardes par arbre, et rien ne les resynchronise.

    La référence est l'arbre PRINCIPAL du même dépôt, pas une adresse écrite
    ici : c'est ce qui rend la fonction vraie pour un autre projet qu'Alpha.

    CE QU'ELLE NE MESURE PAS, et qui doit se dire plutôt que se taire : hors
    dépôt git, ou si `git` ne répond pas, on ne conclut RIEN. Un garde qu'on
    n'a pas pu comparer n'est pas un garde vérifié bon.
    """
    # UN MÊME GARDE DÉCLARÉ DANS DEUX GROUPES DE HOOKS EST UN SEUL FICHIER.
    # Sans ce dédoublonnage le contrôle comptait deux écarts là où il y en
    # avait un, et un chiffre gonflé décrédibilise un vrai constat.
    verdicts, vus = [], set()
    for cmd in propres:
        m = re.search(r'"([^"]+\.(?:py|sh))"', cmd)
        if not m:
            continue
        brut = m.group(1)
        if brut in vus:
            continue
        vus.add(brut)
        f = (resous(brut, base) if "CLAUDE_PROJECT_DIR" in brut
             else pathlib.Path(brut.replace("$HOME", str(HOME))))
        if not f.is_file():
            verdicts.append(("absent", f, "le fichier appelé n'existe pas"))
            continue
        principal = arbre_principal(f)
        if principal is None:
            verdicts.append(("pas mesuré", f, "hors dépôt git, ou git muet"))
            continue
        try:
            rel = f.resolve().relative_to(
                subprocess.run(["git", "-C", str(f.parent), "rev-parse",
                                "--show-toplevel"], capture_output=True,
                               text=True, timeout=10).stdout.strip())
        except Exception:
            verdicts.append(("pas mesuré", f, "chemin non rattachable au dépôt"))
            continue
        ref = principal / rel
        if f.resolve() == ref.resolve():
            continue                       # c'est LUI l'arbre principal
        if not ref.is_file():
            # ABSENT DE L'ARBRE PRINCIPAL N'EST PAS « PÉRIMÉ ». Un garde ajouté
            # sur une seule branche est un cas légitime — celui d'Alpha QA,
            # qui porte son propre hook de fin de tour. Le déclarer en écart
            # ferait crier le contrôle sur du travail normal, et un contrôle
            # qui crie à tort finit désarmé. Il n'a simplement PAS DE
            # RÉFÉRENCE : on le dit, on ne conclut pas.
            verdicts.append(("pas mesuré", f,
                             "propre à cette branche, aucune référence dans "
                             "l'arbre principal"))
            continue
        a = hashlib.sha256(f.read_bytes()).hexdigest()
        b = hashlib.sha256(ref.read_bytes()).hexdigest()
        if a != b:
            verdicts.append(("dérivé", f,
                             "diffère de l'arbre principal (%s… contre %s…)"
                             % (a[:8], b[:8])))
    return verdicts


def reglages():
    """Tous les `settings.json` d'agent de l'atelier, worktrees compris.

    LES WORKTREES COMPTENT. Deux des trois agents d'Alpha n'existent que là, et
    leur `settings.json` est suivi par git : il vit donc sur la branche de leur
    arbre, et peut diverger de celui de l'arbre principal sans qu'on le voie.
    """
    vus = []
    for motif in ("*/.claude/settings.json",
                  "*/agents/*/.claude/settings.json",
                  ".worktrees/*/agents/*/.claude/settings.json"):
        vus += sorted(ATELIER.glob(motif))
    return vus


def main():
    # LA RÉFÉRENCE EST LE PROGRAMME, et il doit RÉPONDRE. Un binaire présent
    # mais muet jugerait la flotte avec une référence morte.
    if not REFERENCE.is_file():
        print("  %s⚠ la référence %s est introuvable — rien n'a été jugé%s"
              % (R, REFERENCE, X))
        return 2
    import subprocess
    v = subprocess.run([str(REFERENCE), "version"], capture_output=True, text=True)
    if v.returncode != 0 or not v.stdout.strip():
        print("  %s⚠ la référence ne répond pas à `version` — rien n'a été jugé%s"
              % (R, X))
        return 2
    print("  %sréférence : le programme du dépôt, %s%s"
          % (D, v.stdout.split()[0], X))

    # LES DEUX LISTES DISENT-ELLES LA MÊME CHOSE ? Avant de juger l'atelier,
    # on confronte la liste de ce fichier à celle du programme. Si elles
    # divergent, tout ce qui suit est jugé avec la mauvaise définition de
    # « fichier du harnais » — et le verdict serait faux sans en avoir l'air.
    rust, motif = liste_du_programme()
    if rust is None:
        print("  %s⚠ %s%s" % (R, motif, X))
        return 2
    if rust != tuple(sorted(NOMS_HARNAIS)):
        manque_ici = sorted(set(rust) - set(NOMS_HARNAIS))
        manque_la = sorted(set(NOMS_HARNAIS) - set(rust))
        print("  %s⚠ les deux listes de fichiers du harnais ont DIVERGÉ : "
              "absent(s) ici %s · absent(s) du programme %s%s"
              % (R, manque_ici or "—", manque_la or "—", X))
        return 2
    print("  %sles deux listes du harnais s'accordent — %d noms confrontés%s"
          % (D, len(rust), X))

    fichiers = reglages()
    # UN CONTRÔLE QUI N'EXAMINE RIEN N'EST PAS UN CONTRÔLE QUI PASSE.
    if not fichiers:
        print("  %s⚠ aucun `settings.json` trouvé sous %s — le contrôle n'a "
              "rien pu juger%s" % (R, ATELIER, X))
        return 2

    comptes, ecarts, lignes, non_mesures = {}, [], [], []
    for s in fichiers:
        base = s.parent.parent
        nom = str(base.relative_to(ATELIER))
        d = json.loads(s.read_text(encoding="utf-8"))
        cmds = [h.get("command", "")
                for bl in d.get("hooks", {}).values() for b in bl
                for h in (b.get("hooks", []) if isinstance(b, dict) else [])]
        # ÊTRE SUR LE PAQUET N'EST PLUS « N'AVOIR AUCUN HOOK ». Cette ligne
        # testait `enabledPlugins and not hooks`, ce qui était vrai des six
        # projets sans garde propre et FAUX d'un projet qui garde deux hooks à
        # lui — dont le seul qui empêche d'écrire dans la vraie base. Le
        # 10/09/2026, juste après leur bascule, le contrôle les a tous les neuf
        # classés « local » : il encodait la recette d'avant, celle que les
        # trois agents avaient refusée. Un contrôle qui porte l'ancienne règle
        # condamne le geste qui la corrige.
        #
        # Ce qui décide est la DÉCLARATION du paquet. Ce qui reste à côté est
        # examiné pour ce qu'il est : un hook du HARNAIS déclaré à la main est
        # un écart — il double ou périme le paquet ; un hook du PROJET est
        # normal, et on le compte pour qu'il se voie.
        du_harnais = [c for c in cmds
                      if any(("/%s" % f) in c for f in NOMS_HARNAIS)]
        propres = [c for c in cmds if c not in du_harnais
                   and "CLAUDE_PLUGIN_ROOT" not in c]
        if d.get("enabledPlugins", {}).get(PAQUET):
            comptes["paquet"] = comptes.get("paquet", 0) + 1
            detail = ""
            if du_harnais:
                detail = ("déclare AUSSI %d hook(s) du harnais à la main — "
                          "ils doublent le paquet" % len(du_harnais))
                ecarts.append((nom, detail))
            # LES GARDES DU PROJET SONT MAINTENANT COMPARÉS, PAS COMPTÉS.
            # Compter satisfaisait la ligne d'affichage et laissait le verdict
            # final mentir : voir `gardes_derives`.
            derives = gardes_derives(propres, base)
            for etat, f, motif in derives:
                # « le fichier appelé n'existe pas » RESTE un écart : un hook
                # qui pointe dans le vide se tait exactement comme un hook qui
                # autorise. Seule l'absence de RÉFÉRENCE est une réserve.
                if etat in ("dérivé", "absent"):
                    ecarts.append((nom, "garde du projet %s : %s"
                                   % (f.name, motif)))
                else:
                    non_mesures.append((nom, "garde du projet %s : %s"
                                        % (f.name, motif)))
            if not detail and propres:
                mauvais = [v for v in derives if v[0] in ("dérivé", "absent")]
                inconnus = [v for v in derives if v[0] == "pas mesuré"]
                detail = ("%d garde(s) propre(s) au projet — %d dérivé(s), "
                          "%d non mesuré(s)"
                          % (len(propres), len(mauvais), len(inconnus)))
                if mauvais:
                    detail = "%s%s%s" % (R, detail, X)
            lignes.append((nom, "paquet", detail))
            continue
        if not cmds:
            comptes["aucun"] = comptes.get("aucun", 0) + 1
            lignes.append((nom, "aucun hook", ""))
            continue
        c, cible = canal(cmds[0])
        detail = ""
        if c == "local" and isinstance(cible, str):
            cible = resous(cible, base)
        if isinstance(cible, pathlib.Path) and cible.name == "briefing.py":
            if not cible.is_file():
                detail = "le fichier appelé n'existe pas : %s" % cible
                ecarts.append((nom, detail))
            elif MARQUE not in cible.read_text(encoding="utf-8", errors="replace"):
                n = len(cible.read_text(encoding="utf-8", errors="replace").splitlines())
                detail = ("appelle un briefing PÉRIMÉ (%d l., sans `%s`) : %s"
                          % (n, MARQUE, cible))
                ecarts.append((nom, detail))
        comptes[c] = comptes.get(c, 0) + 1
        lignes.append((nom, c, detail))

    print("\n  %sPAR OÙ PART LE HOOK%s  —  %d agent(s) examiné(s)\n"
          % (B, X, len(fichiers)))
    for nom, c, detail in lignes:
        coul = G if c == "paquet" else (D if c == "aucun hook" else J)
        print("  %s%-14s%s %s" % (coul, c, X, nom))
        if detail:
            print("      %s%s%s" % (R, detail, X))

    print("\n  " + " · ".join("%s : %d" % (k, v) for k, v in sorted(comptes.items())))

    # CE QU'ON N'A PAS PU MESURER SE DIT, il ne se tait pas. Un garde hors
    # dépôt git n'est pas un garde vérifié bon — et les deux se ressemblaient
    # jusqu'ici, parce que le seul mot de la fin était « ✓ ».
    if non_mesures:
        print("\n  %s%d garde(s) du projet NON MESURÉ(S) — ni bons ni mauvais :%s"
              % (J, len(non_mesures), X))
        for nom, motif in non_mesures:
            print("      %s%s · %s%s" % (D, nom, motif, X))

    if ecarts:
        print("\n  %s%d écart(s) : du code périmé est appelé%s" % (R, len(ecarts), X))
        for nom, motif in ecarts:
            print("      %s%s · %s%s" % (R, nom, motif, X))
        return 1

    # LA PHRASE NE PORTE PLUS PLUS LOIN QUE LA MESURE. Jusqu'au 16/09/2026 elle
    # disait « tout le code appelé » alors que les gardes propres au projet
    # n'étaient que comptés. Elle dit maintenant ce qui a été confronté.
    print("  %s✓%s canal du paquet conforme, et chaque garde propre au projet "
          "confronté à l'arbre principal de son dépôt" % (G, X)
          + ("" if not non_mesures else
             " — %s%d réserve(s) ci-dessus%s" % (J, len(non_mesures), X)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
