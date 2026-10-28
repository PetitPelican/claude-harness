"""CONTRÔLE — la conversion d'un projet mono en équipe, et ce qu'elle produit.

Pas un contrôle différentiel : il n'y a rien à comparer, la conversion n'a
jamais existé en deux versions. Ce qu'on vérifie, c'est qu'elle produit un
projet où le harnais MARCHE — pas seulement des dossiers au bon endroit.

LE TÉMOIN QUI COMPTE EST LE DERNIER : un agent né de la conversion reçoit-il
son briefing ? Tout le reste peut être juste et le dispositif rester muet, et
c'est exactement ce qui arrivait au carnet d'équipe — lu partout, créé nulle
part, pendant des semaines.
"""
import json, os, pathlib, shutil, subprocess, sys

R = pathlib.Path(__file__).resolve().parent.parent
S = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp") / "conversion"
RS = pathlib.Path(os.environ.get("HARNAIS_BIN") or R / "bin" / "harnais")
# LA CONVERSION EST DANS LE PROGRAMME depuis le 11/09/2026 (`harnais equipe`,
# portée du script Python retiré, témoin figé dans `equipe.sh`). On juge le
# programme LIVRÉ s'il la porte ; sinon — entre le portage et sa publication —
# celui qu'on vient de construire, et on le DIT dans la preuve.
def _conv():
    r = subprocess.run([str(RS), "equipe", "--help"], capture_output=True, text=True)
    if "harnais equipe" in r.stdout:
        return RS, "livré"
    return R / "harnais" / "target" / "release" / "harnais", "construit ici, pas encore livré"
CONV, CONV_QUI = _conv()

def projet_mono(ou):
    ou.mkdir(parents=True)
    for d in (".fact", ".mind", "docs", ".claude"):
        (ou / d).mkdir()
    (ou / "CLAUDE.md").write_text("# Projet\n")
    (ou / ".fact/base.md").write_text("Nature\n")
    (ou / ".mind/state.md").write_text("---\nmaj: 2026-09-10\nsante: vert\njalon: rien\n---\n\n# État\n\nrien.\n")
    (ou / ".mind/todo.md").write_text("# À faire\n\n- [ ] rien\n")
    (ou / ".claude/settings.json").write_text(json.dumps({
        "permissions": {"defaultMode": "bypassPermissions"},
        "hooks": {"Stop": [{"hooks": [{"type": "command",
                                       "command": "python3 .claude/hooks/attente.py"}]}]}}) + "\n")
    subprocess.run(["git", "init", "-q", "."], cwd=ou, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=ou, capture_output=True)
    subprocess.run(["git", "-c", "user.email=x@y", "-c", "user.name=x",
                    "commit", "-qm", "socle"], cwd=ou, capture_output=True)

shutil.rmtree(S, ignore_errors=True)
p = S / "projet"
projet_mono(p)

ecarts = []
sec = subprocess.run([str(CONV), "equipe", "--project-root", str(p),
                      "--agents", "PO,QA,OPS"], capture_output=True, text=True)
if "Dry-run" not in sec.stdout:
    ecarts.append("TÉMOIN RATÉ — le blanc n'annonce pas qu'il est un blanc")
if (p / "agents").exists():
    ecarts.append("TÉMOIN RATÉ — le blanc a ÉCRIT : agents/ existe après un dry-run")

r = subprocess.run([str(CONV), "equipe", "--project-root", str(p),
                    "--agents", "PO,QA,OPS", "--apply"], capture_output=True, text=True)
if r.returncode != 0:
    ecarts.append("la conversion a échoué (rc=%d)\n%s" % (r.returncode, r.stdout[-600:]))

# ── ce que la conversion doit avoir produit ──────────────────────────────────
for n in ("PO", "QA", "OPS"):
    d = p / "agents" / n
    f = d / ".claude/settings.json"
    if not f.exists():
        ecarts.append("agents/%s : pas de réglages" % n); continue
    j = json.loads(f.read_text())
    if "hooks" in j:
        ecarts.append("agents/%s : des hooks à la main SUBSISTENT — deux jeux sur le "
                      "même événement, personne ne saurait lequel a parlé" % n)
    if not j.get("enabledPlugins", {}).get("harnais@atelier"):
        ecarts.append("agents/%s : le paquet n'est pas déclaré" % n)
    if "atelier" not in j.get("extraKnownMarketplaces", {}):
        ecarts.append("agents/%s : le catalogue n'est pas déclaré" % n)
    deny = j.get("permissions", {}).get("deny", [])
    autres = [x for x in ("PO", "QA", "OPS") if x != n]
    for a in autres:
        if not any(("/agents/%s/" % a) in x and x.startswith("Edit(") for x in deny):
            ecarts.append("agents/%s : rien n'interdit d'écrire chez %s" % (n, a))
    if any(("/agents/%s/" % n) in x for x in deny):
        ecarts.append("agents/%s : il s'interdit SON PROPRE dossier" % n)
    if not (d / ".mind/state.md").exists():
        ecarts.append("agents/%s : pas d'état" % n)

if (p / ".claude/settings.json").exists():
    ecarts.append("les réglages de la racine n'ont pas été retirés — quelqu'un les "
                  "éditera un jour en croyant agir sur tous les agents")
if not (p / ".mind").exists() and not (p / "agents/PO/.mind/state.md").exists():
    ecarts.append("le premier nommé n'a pas hérité de l'état existant")
if not (p / ".fact/roles.md").exists():
    ecarts.append("pas de fiche des rôles")

# ── LE CARNET D'ÉQUIPE : le mécanisme qui n'était créé nulle part ────────────
carnet = p / "equipe"
if not (carnet / ".etat").is_dir():
    ecarts.append("LE CARNET N'EST PAS AMORCÉ — les entrées d'équipe, les chiffres de "
                  "confiance et le résumé du briefing resteront muets, sans que rien "
                  "ne l'explique. C'est le défaut que ce contrôle existe pour attraper.")

# ── LE TÉMOIN QUI COMPTE : le harnais parle-t-il depuis un dossier d'agent ? ──
charge = json.dumps({"session_id": "conv", "cwd": str(p / "agents/QA"),
                     "hook_event_name": "SessionStart"})
b = subprocess.run([str(RS), "briefing"], input=charge, capture_output=True, text=True)
sert = "additionalContext" in (b.stdout or "")
if not sert:
    ecarts.append("TÉMOIN RATÉ — un agent né de la conversion ne reçoit AUCUN briefing")

# ── témoin négatif : sur un projet déjà multi, on AJOUTE, on ne reconvertit pas
avant = sorted(x.name for x in (p / "agents").iterdir())
r2 = subprocess.run([str(CONV), "equipe", "--project-root", str(p),
                     "--agents", "DOC", "--apply"], capture_output=True, text=True)
apres = sorted(x.name for x in (p / "agents").iterdir())
if apres != sorted(avant + ["DOC"]):
    ecarts.append("sur un projet déjà multi, l'ajout n'a pas ajouté : %s -> %s"
                  % (avant, apres))

print("programme de conversion : %s" % CONV_QUI)
print("témoins : blanc muet, %d agents montés, carnet %s, briefing servi depuis un "
      "dossier d'agent : %s" % (len(apres), "amorcé" if (carnet/".etat").is_dir() else "ABSENT", sert))
print()
print("\n\n".join(ecarts) or "ÉCARTS : AUCUN — conversion, périmètres, carnet et briefing")
sys.exit(1 if ecarts else 0)
