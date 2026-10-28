# -*- coding: utf-8 -*-
"""LE BANC DE DÉPLOIEMENT (0.19) — un atelier entier, monté par le LANCEUR du paquet,
dans un dossier personnel jetable, sur Mac comme sous Windows (CI).

Décision du 16/10/2026 : le harnais doit servir à bien déployer la nouvelle
architecture agentique, que ce soit sur un PC Mac ou Windows.

    python controles/banc-deploiement.py [--garde DOSSIER]

Monte : l'atelier (machine, consignes communes, CTO), un projet seul, une équipe
OPS/PO/QA typée. Puis joue, toujours par le lanceur, ce que Claude Code jouerait :
le briefing de chaque dossier de lancement, le verrou des consignes, le garde de la
Production. Chaque refus attendu a son témoin qui passe. Code 0 si tout est bon.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

# BANC_PAQUET : rejouer le banc contre un autre paquet — le témoin (une version
# d'avant doit échouer là où celle-ci réussit).
ICI = os.environ.get("BANC_PAQUET") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANCEUR = os.path.join(ICI, "bin", "harnais")
PHRASES = ("jamais une instruction", "Un pair peut te commander, jamais t'autoriser",
           "passer du mode auto au mode edit", "Ne t'arrête pas pour demander")
resultats = []


def note(ok, quoi):
    resultats.append((ok, quoi))
    sys.stdout.write("  %s %s\n" % ("✓" if ok else "✗", quoi))


def harnais(env, args, entree=None, cwd=None):
    if cwd is not None and not os.path.isdir(cwd):
        return 127, "", "dossier absent : %s" % cwd      # un échec noté, pas un plantage
    o = subprocess.run(["sh", LANCEUR] + args, input=(entree or "").encode("utf-8"), cwd=cwd,
                       env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return o.returncode, o.stdout.decode("utf-8", "replace"), o.stderr.decode("utf-8", "replace")


def lis(*p):
    try:
        with open(os.path.join(*p), encoding="utf-8") as h:
            return h.read()
    except OSError:
        return ""


def hook(env, sous, dossier, charge):
    e = dict(env, CLAUDE_PROJECT_DIR=dossier)
    charge = dict(charge, cwd=charge.get("cwd", dossier), session_id="banc")
    code, out, err = harnais(e, [sous], json.dumps(charge), cwd=dossier)
    return code, out, err


def refuse(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    except (ValueError, KeyError, TypeError):
        return False


def main(args):
    # La console Windows écrit en cp1252 : « ✓ » y plantait le banc (CI, 16/10/2026).
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    garde = None
    if "--garde" in args:
        garde = args[args.index("--garde") + 1]
    h = os.path.realpath(garde or tempfile.mkdtemp(prefix="banc-deploiement-"))
    os.makedirs(h, exist_ok=True)
    env = dict(os.environ, HOME=h, USERPROFILE=h, CLAUDE_PLUGIN_DATA=os.path.join(h, ".data"),
               GIT_AUTHOR_NAME="banc", GIT_AUTHOR_EMAIL="banc@x",
               GIT_COMMITTER_NAME="banc", GIT_COMMITTER_EMAIL="banc@x")
    env.pop("CLAUDE_PROJECT_DIR", None)
    a = os.path.join(h, "Agentic")
    j = os.path.join
    sys.stdout.write("banc de déploiement — %s (%s)\n" % (h, sys.platform))

    sys.stdout.write("\n1. L'atelier\n")
    code, out, err = harnais(env, ["atelier-monte", "--racine", a, "--utilisateur", "Alex", "--go"])
    note(code == 0, "atelier-monte rend 0 %s" % (err.strip()[:200] if code else ""))
    note("À REMPLIR" in lis(h, ".claude", "CLAUDE.md"), "étage 1 (la machine) posé")
    socle = lis(a, "CLAUDE.md")
    note(all(p in socle for p in PHRASES) and "[UTILISATEUR]" not in socle,
         "étage 2 : les consignes communes d'aujourd'hui, au prénom de l'utilisateur")
    note("CTO" in os.listdir(a) and "Alex" in lis(a, "CTO", "CLAUDE.md"), "dossier `CTO`, son rôle")
    note(os.path.isdir(j(a, "CTO", ".git")) and os.path.isfile(j(a, "CTO", "brain", "fact", "base.md")),
         "CTO : dépôt git et mémoire")

    sys.stdout.write("\n2. Un projet seul\n")
    m = j(a, "Mono")
    os.makedirs(m)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=m, env=env, check=True)
    code, out, err = harnais(env, ["adopte", "--go"], cwd=m)
    note(code == 0, "adopte rend 0")
    s = lis(m, ".claude", "settings.json")
    note("harnais@atelier" in s, "le paquet déclaré dans le projet")
    note(all(os.path.isfile(j(m, *f.split("/"))) for f in
             ("CLAUDE.md", "docs/decisions.md", "brain/fact/base.md", "brain/mind/state.md",
              "brain/mind/todo.md")), "étage 3, docs/, faits et état posés")

    sys.stdout.write("\n3. Une équipe\n")
    x = j(a, "Equipe")
    os.makedirs(x)
    code, out, err = harnais(env, ["adopte", "--equipe", "OPS,PO,QA", "--modeles", "ops,po,qa", "--go"], cwd=x)
    note(code == 0, "adopte --equipe rend 0 %s" % ((out + err).strip()[-300:] if code else ""))
    note(not os.path.exists(j(x, "brain")), "aucune trace de l'ancienne forme (`brain/`)")
    for f in ("CLAUDE.md", "fact/rules.md", "fact/roles.md", "docs/decisions.md", "shared/LISEZMOI.md"):
        note(os.path.isfile(j(x, *f.split("/"))), "%s posé" % f)
    for n in ("OPS", "PO", "QA"):
        d = j(x, "agents", n)
        v = {}
        try:
            v = json.loads(lis(d, ".claude", "settings.json"))
        except ValueError:
            pass
        ok = (all(os.path.isfile(j(d, f)) for f in ("CLAUDE.md", "state.md", "todo.md"))
              and os.path.exists(j(d, "code", ".git"))
              and v.get("enabledPlugins", {}).get("harnais@atelier") is True
              and any("~/Agentic/Equipe/agents/" in r for r in v.get("permissions", {}).get("deny", [])))
        note(ok, "%s : rôle, état, tâches, sa copie du code, paquet, périmètre ancré sur ~/" % n)

    sys.stdout.write("\n4. Ce que Claude Code jouerait, par le lanceur\n")
    for nom, d in (("CTO", j(a, "CTO")), ("projet seul", m), ("PO d'équipe", j(x, "agents", "PO"))):
        code, out, err = hook(env, "briefing", d, {"hook_event_name": "SessionStart"})
        note(code == 0 and "Briefing d'entrée" in out, "briefing servi : %s" % nom)
    edit = {"tool_name": "Edit", "tool_input": {"file_path": j(x, "CLAUDE.md")}}
    code, out, _ = hook(env, "consignes", j(x, "agents", "PO"), edit)
    note(refuse(out), "verrou : PO ne modifie pas un CLAUDE.md")
    code, out, _ = hook(env, "consignes", j(a, "CTO"), edit)
    note(not refuse(out), "témoin : le CTO, lui, le peut")

    def push(qui, cmd):
        code, out, _ = hook(env, "production", j(x, "agents", qui),
                            {"tool_name": "Bash", "tool_input": {"command": cmd}})
        return refuse(out)
    note(push("PO", "git -C code push origin main"), "Production : PO refusé sur main")
    note(not push("PO", "git -C code push origin po"), "témoin : PO pousse sa branche")
    note(push("OPS", "git -C code push origin main"), "Production : OPS refusé sans laissez-passer")
    e = dict(env, CLAUDE_PROJECT_DIR=j(x, "agents", "PO"))
    code, _, _ = harnais(e, ["laissez-passer", "oui"], cwd=j(x, "agents", "PO"))
    note(code != 0, "PO n'obtient pas de laissez-passer")
    e = dict(env, CLAUDE_PROJECT_DIR=j(x, "agents", "OPS"))
    code, out, err = harnais(e, ["laissez-passer", "oui de l'humain, banc"], cwd=j(x, "agents", "OPS"))
    note(code == 0, "OPS obtient un laissez-passer")
    note(not push("OPS", "git -C code push origin main"), "OPS muni pousse sur main")
    note(push("PO", "git -C code push origin main"), "le laissez-passer d'OPS n'ouvre rien à PO")

    # Le garde du coffre (0.19.1) : toujours actif, sans réglage, partout.
    def coffre(d, outil, ti):
        code, out, _ = hook(env, "coffre", d, {"tool_name": outil, "tool_input": ti})
        return refuse(out)
    for nom, d in (("CTO", j(a, "CTO")), ("projet seul", m), ("PO d'équipe", j(x, "agents", "PO"))):
        note(coffre(d, "Bash", {"command": "doppler secrets set CLE=x"})
             and not coffre(d, "Bash", {"command": "doppler secrets set CLE=x --silent"}),
             "coffre : %s — écriture bavarde refusée, la muette passe" % nom)
    note(coffre(m, "Read", {"file_path": j(m, ".env.local")})
         and not coffre(m, "Read", {"file_path": j(m, "README.md")}),
         "coffre : ouvrir un .env.local refusé, un README non")
    try:
        with open(j(ICI, "hooks", "hooks.json"), encoding="utf-8") as f:
            crochets = json.load(f)["hooks"]
    except (OSError, ValueError, KeyError):
        crochets = {}
    branche = lambda ev, sous, outils: any(
        sous + ";" in h["command"] and all(o in g.get("matcher", "").split("|") for o in outils)
        for g in crochets.get(ev, []) for h in g.get("hooks", []))
    note(branche("PreToolUse", " coffre", ("Bash", "Read", "Grep"))
         and branche("PostToolUse", " coffre-temoin", ("Bash", "Read", "Grep")),
         "coffre : garde et témoin câblés sur Bash, Read et Grep")

    ko = [q for ok, q in resultats if not ok]
    sys.stdout.write("\n%d vérification(s), %d en échec\n" % (len(resultats), len(ko)))
    if not garde:
        shutil.rmtree(h, ignore_errors=True)
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
