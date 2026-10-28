#!/usr/bin/env python3
"""LA FORME DES PROJETS VIVANTS — et surtout, aucun ne doit être à cheval.

POURQUOI CE CONTRÔLE EXISTE. Le déménagement vers `brain/` est PROGRESSIF : au
10/09/2026, sept projets sont passés et deux restent en v1. Une flotte mixte
n'est pas un défaut, c'est l'état normal d'une migration — donc on ne peut pas
juger sur « tout le monde est-il en v2 ».

Ce qui SE JUGE, c'est l'état qu'aucun projet ne doit atteindre :

  ① AMBIGU — l'ancien arbre et le neuf coexistent. Le résolveur le nomme, et
     refuse alors de choisir : le briefing se tait, la serrure des faits perd
     son préfixe, et rien n'a l'air cassé. C'est l'état qu'une migration
     interrompue laisse derrière elle.
  ② RÉSIDU — un projet en `brain/` qui porte encore un `.fact/` ou un `.mind/`
     sur le disque. Le résolveur ne le verrait PAS comme ambigu si le résidu
     est vide, et deux mémoires cohabiteraient, l'une lue, l'autre écrite.

CE QU'IL NE JUGE PAS : qu'un projet soit encore en v1. Ça se compte, ça ne se
refuse pas.

IL EST EN LECTURE SEULE. On peut le lancer n'importe quand.
"""
import json, pathlib, subprocess, sys
import os

HOME = pathlib.Path.home()
ATELIER = HOME / "Agentic"
DEPOT = pathlib.Path(__file__).resolve().parent.parent
H = pathlib.Path(os.environ.get("HARNAIS_BIN") or DEPOT / "bin" / "harnais")

G, J, R, D, B, X = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def resolution(p):
    r = subprocess.run([str(H), "resolution", str(p)],
                       capture_output=True, text=True, timeout=10)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return json.loads(r.stdout)


def juge(p):
    """(forme, [motifs de refus]) pour un dossier de projet."""
    res = resolution(p)
    if res is None:
        return "?", ["le programme n'a pas répondu"]
    f, maux = res["forme"], []
    if f == "AMBIGUE":
        maux.append("l'ancien arbre et `brain/` coexistent — migration interrompue ?")
    if f == "brain":
        for vieux in (".fact", ".mind"):
            if (p / vieux).exists():
                maux.append("porte encore `%s/` à côté de `brain/`" % vieux)
    return f, maux


def main():
    if not H.exists():
        print("  %s⚠ le programme %s est introuvable — rien n'a été jugé%s" % (R, H, X))
        return 2

    # LE TÉMOIN, ET IL EST POSÉ AVANT DE JUGER QUOI QUE CE SOIT. Un contrôle qui
    # ne trouve jamais rien et un contrôle aveugle rendent tous les deux zéro.
    # On lui donne donc un arbre à CHEVAL, fabriqué exprès, et on exige qu'il le
    # voie. S'il ne le voit pas, le verdict sur les vrais projets ne vaut rien.
    # DEUX MÉTIERS, DONC DEUX TÉMOINS — plus un cas sain, sans quoi un juge qui
    # crie sur tout passerait les deux premiers.
    #
    # Mesuré le 10/09/2026 par l'audit (P2) : ce témoin n'exerçait que le cas
    # AMBIGU. Le cas RÉSIDU — un `brain/` qui traîne encore un `.mind/` — est
    # précisément celui que le RÉSOLVEUR ne signale pas et délègue ici : il rend
    # `brain` sans un mot, et c'est voulu, la forme se décide sur les FAITS.
    # Cette branche est donc la seule chose qui sépare un résidu vu d'un résidu
    # invisible, et rien ne la vérifiait.
    import tempfile
    epreuves = [
        ("AMBIGU — l'ancien arbre et `brain/` coexistent",
         (".fact", ".mind", "brain/fact", "brain/mind"), True),
        ("RÉSIDU — `brain/` porte encore un `.mind/`",
         ("brain/fact", "brain/mind", ".mind"), True),
        ("SAIN — `brain/` seul, rien ne doit être signalé",
         ("brain/fact", "brain/mind"), False),
    ]
    for quoi, dossiers, doit_crier in epreuves:
        with tempfile.TemporaryDirectory() as tmp:
            t = pathlib.Path(tmp)
            subprocess.run(["git", "init", "-q", "-b", "main", str(t)], capture_output=True)
            for d in dossiers:
                (t / d).mkdir(parents=True, exist_ok=True)
            _, maux = juge(t)
            if bool(maux) != doit_crier:
                print("  %s⚠ témoin RATÉ — %s : le contrôle %s. Son verdict sur les "
                      "vrais projets ne vaut rien.%s"
                      % (R, quoi, "n'a rien vu" if doit_crier else "crie sur un arbre sain", X))
                return 2

    projets = sorted([d for d in ATELIER.iterdir()
                      if d.is_dir() and not d.name.startswith(".")])
    if not projets:
        print("  %s⚠ aucun projet trouvé sous %s%s" % (R, ATELIER, X))
        return 2

    comptes, ecarts = {}, []
    print("\n  %sLA FORME DES PROJETS VIVANTS%s  —  %d examiné(s)\n"
          % (B, X, len(projets)))
    for p in projets:
        f, maux = juge(p)
        comptes[f] = comptes.get(f, 0) + 1
        coul = G if f == "brain" else (R if maux else (D if f in ("hors-depot", "sans-memoire") else J))
        print("  %s%-11s%s %s" % (coul, f, X, p.name))
        for m in maux:
            print("      %s%s%s" % (R, m, X))
            ecarts.append((p.name, m))

    print("\n  " + " · ".join("%s : %d" % (k, v) for k, v in sorted(comptes.items())))
    if ecarts:
        print("\n  %s%d projet(s) dans un état qu'aucun ne doit atteindre%s"
              % (R, len(ecarts), X))
        return 1
    v1 = comptes.get("en-place", 0) + comptes.get("deportee", 0)
    print("  %s✓%s aucun projet à cheval%s" % (G, X,
          (" — %d encore sur l'ancien arbre, ce n'est pas un défaut" % v1) if v1 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
