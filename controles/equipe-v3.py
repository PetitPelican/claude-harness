#!/usr/bin/env python3
"""« UN DOSSIER PAR AGENT » — LE PROGRAMME LIVRÉ, DE BOUT EN BOUT (0.18.0).

    python3 controles/equipe-v3.py <dossier de travail>

Décision du 14/10/2026, plan validé par QA. Les essais unitaires
importent `py/` ; ce contrôle passe par le LANCEUR (`HARNAIS_BIN`), comme un
hook ou un agent : une équipe `brain/` fabriquée — code en copie principale,
mémoire imbriquée à dépôt propre, une copie par agent hors du projet, une copie
de Production, une copie posée par Claude Code dans le principal, un `.env.local`
ignoré — est déménagée, puis jugée.

Chaque garantie a son TÉMOIN : le même geste, dans l'autre sens, doit rendre
l'autre verdict. Un garde qui refuse tout et un garde qui laisse tout passer
rendent le même verdict sur un seul cas.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

R = pathlib.Path(__file__).resolve().parent.parent
B = os.environ.get("HARNAIS_BIN") or str(R / "bin" / "harnais")
S = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/equipe-v3").resolve() / "v3"
shutil.rmtree(S, ignore_errors=True)
S.mkdir(parents=True)
S = pathlib.Path(os.path.realpath(S))
MAISON = S / "maison"
(MAISON / ".claude" / "projects").mkdir(parents=True)
INS = MAISON / "installed.json"
ENV = dict(os.environ, HOME=str(MAISON), HARNAIS_INSCRIPTIONS=str(INS),
           CLAUDE_PLUGIN_DATA=str(MAISON / "data"), GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
ENV.pop("CLAUDE_PROJECT_DIR", None)


def git(d, *a):
    o = subprocess.run(["git"] + list(a), cwd=str(d), env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if o.returncode:
        raise SystemExit("banc cassé : git %s : %s" % (" ".join(a), o.stderr.decode()))
    return o.stdout.decode()


def ecris(p, t):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t, encoding="utf-8")


def harnais(args, cwd, entree=None, projet=None):
    e = dict(ENV)
    if projet:
        e["CLAUDE_PROJECT_DIR"] = str(projet)
    o = subprocess.run(["sh", B] + list(args), cwd=str(cwd), env=e, input=(entree or "").encode(),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return o.returncode, o.stdout.decode("utf-8", "replace") + o.stderr.decode("utf-8", "replace")


def garde(cmd, cwd, projet):
    _, out = harnais(["mind-guard"], cwd, json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}), projet)
    return "deny" if '"deny"' in out else "allow"


# ── le banc ─────────────────────────────────────────────────────────────────
P, WT = S / "Projet", S / ".worktrees"
P.mkdir()
git(P, "init", "-q", "-b", "main")
ecris(P / ".gitignore", "brain/\n.env*\n")
ecris(P / "apps" / "app.ts", "export {}\n")
ecris(P / "docs" / "decisions.md", "# Décisions\n")
ecris(P / "CLAUDE.md", "# Consignes communes\n")
for n in ("OPS", "PO"):
    ecris(P / "agents" / n / "CLAUDE.md", "# %s\n" % n)
    ecris(P / "agents" / n / ".claude" / "settings.json", json.dumps({
        "enabledPlugins": {"harnais@atelier": True},
        "permissions": {"deny": ["Edit(%s/**)" % (P / "brain" / "mind" / ("OPS" if n == "PO" else "PO"))]},
        "hooks": {"Stop": [{"hooks": [{"command": "${CLAUDE_PROJECT_DIR}/../../.claude/hooks/g.py"}]}]}}))
git(P, "add", "-A")
git(P, "commit", "-qm", "code")
ecris(P / ".env.local", "CLE=1\n")
BR = P / "brain"
BR.mkdir()
git(BR, "init", "-q", "-b", "main")
ecris(BR / "fact" / "base.md", "---\ncap: le banc\n---\n")
for n in ("OPS", "PO"):
    ecris(BR / "mind" / n / "state.md", "---\nmaj: 2026-10-14\nsante: vert\njalon: x\n---\n")
    ecris(BR / "mind" / n / "todo.md", "# todo\n")
ecris(BR / "workspace" / "carnet.md", "x\n")
git(BR, "add", "-A")
git(BR, "commit", "-qm", "memoire")
git(P, "worktree", "add", "-q", "-b", "po", str(WT / "po"))
git(P, "worktree", "add", "-q", "--detach", str(WT / "prod"))
git(P, "worktree", "add", "-q", "-b", "isole", str(P / ".claude" / "worktrees" / "a1"))
ecris(P / "agents" / "OPS" / ".claude" / ".briefing.json", '{"derniere": 1}')
ecris(WT / "po" / "agents" / "PO" / ".claude" / ".briefing.json", '{"derniere": 2}')
ecris(INS, json.dumps({"plugins": {"harnais@atelier": [
    {"scope": "project", "projectPath": str(WT / "po" / "agents" / "PO"), "version": "0.17.0"}]}}))

ecarts, n = [], 0


def exige(nom, vrai, detail=""):
    global n
    n += 1
    if not vrai:
        ecarts.append("%s%s" % (nom, (" — " + detail[:300]) if detail else ""))


# 1. À BLANC : rien ne bouge — et l'apply SANS `--agents-arretes` non plus.
c, out = harnais(["demenage", str(P), "--en-plus", "OPS:prod=%s" % (WT / "prod")], S)
exige("à blanc rend 0 et n'écrit rien", c == 0 and (P / "brain").is_dir(), out)
c, out = harnais(["demenage", str(P), "--en-plus", "OPS:prod=%s" % (WT / "prod"), "--apply"], S)
exige("sans --agents-arretes : refus, rien d'écrit", c == 1 and (P / "brain").is_dir(), out)

# 2. LE DÉMÉNAGEMENT.
c, out = harnais(["demenage", str(P), "--en-plus", "OPS:prod=%s" % (WT / "prod"),
                  "--apply", "--agents-arretes"], S)
exige("déménagement rend 0", c == 0, out)
OPS, PO = P / "agents" / "OPS", P / "agents" / "PO"
exige("brain/ a disparu, fact/ est à la racine", not (P / "brain").exists() and (P / "fact" / "base.md").is_file())
exige("l'état de PO dans son dossier", (PO / "state.md").is_file() and (PO / "CLAUDE.md").is_file())
exige("fichier ignoré du principal conservé", (OPS / "code" / ".env.local").read_text() == "CLE=1\n")
exige("copie de PO sur sa branche", git(PO / "code", "rev-parse", "--abbrev-ref", "HEAD").strip() == "po")
liste = git(OPS / "code", "worktree", "list", "--porcelain")
exige("4 copies, toutes chez un agent",
      liste.count("worktree ") == 4 and str(WT) not in liste, liste)
s = (PO / ".claude" / "settings.json").read_text()
exige("droits réécrits (mémoire, crochets)", str(OPS) in s and "/code/.claude/hooks" in s and "brain" not in s, s)
exige("inscription suivie",
      json.loads(INS.read_text())["plugins"]["harnais@atelier"][0]["projectPath"] == str(PO))
exige("mémoire enregistrée et propre", git(P, "status", "--porcelain") == "")

# 3. LA RÉSOLUTION, par le lanceur.
c, out = harnais(["resolution", str(PO / "code" / "apps")], S)
exige("résolu en équipe depuis le fond de la copie", '"equipe"' in out.replace(" ", ""), out)

# 3 bis. LA MISE À NIVEAU COMPLÈTE SANS RECRÉER `brain/`.
c, out = harnais(["mise-a-niveau", str(P), "--apply"], S)
exige("mise à niveau d'une équipe : faits posés dans fact/, aucun brain/",
      c == 0 and (P / "fact" / "rules.md").is_file() and not (P / "brain").exists(), out)
git(P, "add", "-A")
git(P, "commit", "-qm", "faits")

# 4. LE GARDE DE COMMIT — chaque refus a son passage.
ecris(PO / "todo.md", "# todo\n- [ ] x\n")
git(PO, "add", "todo.md")
exige("commit tapé dans la mémoire : refusé", garde("git commit -m x", PO, PO) == "deny")
exige("TÉMOIN — avec memoire-ok : passe", garde("git commit -m x # memoire-ok", PO, PO) == "allow")
git(PO, "reset", "-q")
exige("copie hors du dossier : refusée", garde("git -C code worktree add %s" % (S / "ailleurs"), PO, PO) == "deny")
exige("TÉMOIN — copie dans le dossier : passe", garde("git -C code worktree add ../code-essai", PO, PO) == "allow")

# 5. LA PAGE D'ÉQUIPE.
c, out = harnais(["equipe-vue", "--racine", str(S), "--projet", "Projet"], S)
exige("la page nomme la forme", "un dossier par agent" in out, out)
git(OPS / "code", "worktree", "add", "-q", "-b", "sauvage", str(S / "sauvage"))
c, out = harnais(["equipe-vue", "--racine", str(S), "--projet", "Projet"], S)
exige("TÉMOIN — une copie sauvage est signalée", "éparpille" in out, out)

print("témoin : banc équipe brain/ → un dossier par agent, %d garanties" % n)
print()
print("\n".join("✗ " + e for e in ecarts) or "ÉCARTS : AUCUN sur %d garanties" % n)
sys.exit(1 if ecarts else 0)
