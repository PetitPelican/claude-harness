"""CONTRÔLE DIFFÉRENTIEL — le compteur d'usage de la mémoire.

Refait : le premier avait été joué AVANT qu'un réglage partagé (l'ordre des
clés demandé par le carnet) ne change la façon dont ce hook écrit son fichier.
Une preuve datée d'avant un changement de dépendance ne prouve plus rien.

Le hook tourne après CHAQUE lecture de fichier : c'est le plus fréquent du
harnais, donc celui où une divergence coûte le plus.

FIGÉ LE 10/09/2026 (lot 0). Il ne lance plus Python : il compare le Rust au
témoin de `temoins/usage.json`, produit par le hook Python pendant qu'il
existait encore. `--gel` reproduit ce témoin — et ne peut plus l'être une fois
l'interpréteur parti.

ÉTENDU LE 10/09/2026 À LA VOIE DU SHELL, parce qu'elle était la seule empruntée.
Neuf heures après la mise en service, le registre portait six épingles et zéro
lecture : le hook n'écoutait que l'outil de lecture, et cet agent lit ses notes
avec `cat`. Les quatre chemins de cette voie sont donc joués ET COMPTÉS ici —
la lecture, l'écriture qui ne compte pas, le chemin qui n'apparaît que dans la
sortie, et l'inventaire qu'on refuse. Un contrôle qui ne les énumère pas
retomberait dans le silence qu'il vient de lever.
"""
import json, os, shutil, subprocess, pathlib, sys, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import temoins

S = pathlib.Path(sys.argv[1])/"usage"
shutil.rmtree(S, ignore_errors=True); S.mkdir(parents=True)
PY = str(pathlib.Path.home()/".claude/hooks/memoire-usage.py")
RS = os.environ.get("HARNAIS_BIN") or str(pathlib.Path.home()/"Agentic/claude-harnais/bin/harnais")
# Le programme comparé doit avoir DÉMARRÉ avant qu'on juge quoi que ce soit :
# un lanceur mort rend une sortie qu'on confondrait avec un verdict (23/09/2026).
temoins.exige_que_ca_demarre([RS])

def bac(cote):
    d = S/cote/".claude"/"projects"/"un-projet"/"memory"
    d.mkdir(parents=True)
    return d

CHARGES = []
def lu(chemin, sess="s1", cle="file_path", cote="reponse"):
    o = {"path" if cle == "path" else "file_path": chemin}
    return {"tool_name": "Read", "session_id": sess,
            ("tool_response" if cote == "reponse" else "tool_input"): o}

def cas(mem):
    m = str(mem)
    return [
      lu(m + "/une-note.md"),
      lu(m + "/une-note.md"),                       # relue : le compteur monte
      lu(m + "/une-note.md", cote="entree"),        # lue par l'autre porte
      lu(m + "/AUTRE-note.md"),
      lu(m + "/MEMORY.md"),                         # l'index n'est PAS une note
      lu(m + "/memory.MD"),                         # ni sa variante de casse
      lu(m + "/une-note.txt"),                      # ni un fichier qui n'en est pas
      lu("/ailleurs/une-note.md"),                  # ni hors de la mémoire
      lu(m + "/accentuée-é.md"),                    # les accents : \\u ou pas ?
      lu(m + "/dans-une-autre-session.md", sess="s2"),
      {"tool_name": "Read"},                        # charge sans chemin
      {"pas": "du json attendu"},
    ]

def joue(argv, mem):
    for c in cas(mem):
        subprocess.run(argv, input=json.dumps(c), capture_output=True, text=True)
    f = mem/".usage.json"
    return f.read_bytes() if f.exists() else b""

# LE PLAFOND DU REGISTRE : quarante, et la quarante-et-unième chasse la première.
def joue_plafond(argv, mem):
    for i in range(45):
        subprocess.run(argv, input=json.dumps(lu(str(mem) + "/n%02d.md" % i)),
                       capture_output=True, text=True)
    return (mem/".usage.json").read_bytes()

# ── LA VOIE DU SHELL, ses quatre chemins et leurs témoins ──────────────────
def sh(cmd, sortie="", sess="s1"):
    return {"tool_name": "Bash", "session_id": sess,
            "tool_input": {"command": cmd},
            "tool_response": {"stdout": sortie}}

def cas_shell(mem):
    m = str(mem)
    return [
      ("lecture-commande", sh("cat %s/une-note.md" % m)),
      ("lecture-commande", sh("sed -n 1,5p %s/une-note.md" % m)),   # relue
      ("ecriture-ecartee", sh("cat > %s/jamais-lue.md <<EOF" % m)),
      ("ecriture-ecartee", sh("echo x >> %s/jamais-lue.md" % m)),
      ("chemin-en-sortie", sh('grep -l x "$M"/*.md',
                              "%s/AUTRE-note.md\n%s/accentuée-é.md" % (m, m))),
      ("inventaire-refuse", sh("ls %s/" % m,
                               "\n".join("%s/n%02d.md" % (m, i) for i in range(6)))),
      ("index-jamais", sh("cat %s/MEMORY.md" % m)),
      ("hors-memoire", sh("cat /ailleurs/une-note.md")),
      ("note-inexistante", sh("cat %s/fantome.md" % m)),
      ("sans-commande", {"tool_name": "Bash", "session_id": "s1"}),
    ]

def joue_shell(argv, mem):
    for _, c in cas_shell(mem):
        subprocess.run(argv, input=json.dumps(c), capture_output=True, text=True)
    f = mem/".usage.json"
    return f.read_bytes() if f.exists() else b""

def peuple(mem):
    for n in ("une-note", "AUTRE-note", "accentuée-é", "jamais-lue", "MEMORY"):
        (mem/(n + ".md")).write_text("---\nname: %s\n---\n" % n)
    for i in range(6):
        (mem/("n%02d.md" % i)).write_text("x")

GEL = temoins.gel_demande()
COTE = ["python3", PY] if GEL else [RS, "usage"]
cote = "py" if GEL else "rs"

peuple(bac(cote + "0"))  # le bac 0 n'est pas joué : il tient les fichiers modèles
m1 = bac(cote + "1"); a1 = joue(COTE, m1)
m2 = bac(cote + "2"); a2 = joue_plafond(COTE, m2)
m3 = bac(cote + "3"); peuple(m3); a3 = joue_shell(COTE, m3)

MASQUE = [(str(S), "<bac>")]
CAS = [("douze-charges",  [c for c in cas(pathlib.Path("<mem>"))], a1),
       ("plafond-45",     "45 lectures de n00.md a n44.md", a2),
       ("voie-du-shell",  [n for n, _ in cas_shell(pathlib.Path("<mem>"))], a3)]

if GEL:
    f = temoins.fige("usage", CAS, ("douze-charges", "voie-du-shell"),
                     [PY], MASQUE)
    print("témoin figé :", f)
    sys.exit(0)

ecarts, ligne = temoins.compare("usage", {n: v for n, _, v in CAS}, MASQUE)

# LES PROPRIÉTÉS DE LA VOIE DU SHELL, exigées sur ce que le RUST vient d'écrire.
# Le témoin dit l'octet ; celles-ci disent le SENS, et elles mordent même le
# jour où le témoin et le rendu se tromperaient ensemble.
d3 = json.loads(a3) if a3 else {}
d2 = json.loads(a2) if a2 else {}
n_plafond = len(d2.get("_encours", {}).get("s1", []))
props = [
  ("le registre plafonne à 40", n_plafond == 40),
  ("la lecture par la commande compte deux fois",
   d3.get("une-note", {}).get("n") == 2),
  ("le chemin vu dans la SORTIE compte",
   d3.get("AUTRE-note", {}).get("n") == 1 and "accentuée-é" in d3),
  ("ce que la commande ÉCRIT ne compte pas", "jamais-lue" not in d3),
  ("l'inventaire de six notes ne compte rien",
   not any(k.startswith("n0") for k in d3)),
  ("l'index n'est pas une note", "MEMORY" not in d3),
  ("une note qui n'existe pas ne compte pas", "fantome" not in d3),
  ("le registre de session porte les trois lues",
   sorted(d3.get("_encours", {}).get("s1", [])) == ["AUTRE-note", "accentuée-é", "une-note"]),
]
rates = [t for t, ok in props if not ok]
if rates:
    ecarts.append("PROPRIÉTÉS RATÉES :\n  - " + "\n  - ".join(rates))

print("%s · registre plafonné à %d · %d/%d propriétés"
      % (ligne, n_plafond, len(props) - len(rates), len(props)))
print()
print("\n\n".join(ecarts) or "ÉCARTS : AUCUN — le Rust rend le témoin à l'octet")
sys.exit(1 if ecarts else 0)
