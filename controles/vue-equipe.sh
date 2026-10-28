#!/bin/bash
# LA VUE D'ÉQUIPE RELUE CONTRE SON TÉMOIN FIGÉ.
#
#     bash controles/vue-equipe.sh [binaire]            compare au témoin
#     bash controles/vue-equipe.sh --figer [binaire]    refige depuis le programme
#
# TÉMOIN D'ORIGINE `rust` — le second, et le LISEZMOI dit pourquoi. Le premier,
# figé le 11/09/2026 depuis `agentic-team.py` avant son retrait, gravait une
# lecture FAUSSE : l'organisation d'avant seule, des réglages qui ne disent plus
# rien depuis le paquet, et des conseils vers deux compétences disparues. Mesuré
# le même jour sur le vrai atelier : 12 projets sur 13 « sans mémoire », dont
# deux servis sous nos yeux. Le script n'existe plus : refiger depuis lui
# graverait l'erreur. Ce témoin est donc un CLICHÉ DE RÉFÉRENCE, pas une preuve
# d'équivalence. Ce qui prouve que la lecture est JUSTE : les essais du module
# (un par verdict, chacun avec son témoin négatif) et, ici même, le verdict
# ATTENDU de chaque projet, vérifié avant toute comparaison — et avant de figer.
#
# VERSION NEUTRALISÉE : le corpus inscrit et trace la version que le programme
# annonce, et la sortie la remplace par <V>. Sinon chaque montée de version
# changerait le témoin — et un témoin qu'on refige à chaque fois ne garde rien.
#
# L'âge d'un état se compte en jours depuis AUJOURD'HUI : les dates du corpus
# sont posées RELATIVEMENT au jour du passage (J-3, J-10, J-40). L'heure du
# relevé, en tête de page, est neutralisée.
#
# Ce que le corpus sépare — un projet par verdict, et les pièges du lecteur :
#   conforme       brain/ servi ; CLAUDE.md qui IMPORTE le fichier nommant brain/
#   equipe         agents/A et agents/B, l'état dans brain/mind/<nom> : la santé
#                  ROUGE l'emporte, tâches réunies
#   v1             .fact/ .mind/ en place, servi — informatif
#   ancien         taxonomie d'avant (.memory/charter.md), état périmé (J-40)
#   ambigu         brain/ ET .fact/ : le harnais ne sert rien
#   non-branche    rien ne déclare le paquet
#   hooks-locaux   l'ancien câblage, sans le paquet
#   non-inscrit    déclaré, absent des inscriptions : il ne se charge pas
#   jamais-servi   déclaré, inscrit, aucune trace d'entrée
#   en-retard      trace d'une version d'avant ; retard-ancien : trace sans version
#   inscription-vieille  inscrit plus vieux que le programme
#   sans-agent · incomplet · surplus · sans-deny · neuf · sans-git
#   claude-starter, claude-harnais  ignorés ; .cache  caché, jamais lu
# Et un passage aux inscriptions ILLISIBLES : « non mesuré », jamais « inscrit ».
# Tâches : @user !haut, @dehors (n'attend personne ici), root@serveur (pas un
# destinataire), [x] fait, [>] en cours.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
T="$ICI/temoins/vue-equipe"
MODE=compare; if [ "${1:-}" = "--figer" ]; then MODE=figer; shift; fi
B="${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}"; CMD=("$B" equipe-vue)
V="$("$B" --version 2>/dev/null | awk '{print $1}')"
if [ -z "$V" ]; then echo "  ✗ le programme ne dit pas sa version : rien n'est comparable"; echo "1 écart(s)"; exit 1; fi
H="$(cd "$(mktemp -d)" && pwd -P)"; R="$H/atelier"; S="$(mktemp -d)"; mkdir -p "$R"
I="$H/inscriptions.json"; maintenant=$(date +%s)
jour() { date -v-"$1"d +%Y-%m-%d 2>/dev/null || date -d "-$1 day" +%Y-%m-%d; }
ecr() { mkdir -p "$(dirname "$1")"; printf '%b' "$2" > "$1"; }
etat() { ecr "$1" "---\nmaj: $2\nsante: $3\njalon: $4\n---\n\n# état\n"; }
declare_='{"enabledPlugins":{"harnais@atelier":true},"permissions":{"deny":["Bash(rm:*)"],"defaultMode":"bypassPermissions"}}'
locaux='{"permissions":{"deny":["Bash(rm:*)"]},"hooks":{"PreToolUse":[{"hooks":[{"command":"mind-guard"}]}],"PostToolUse":[{"hooks":[{"command":"journal"}]}]}}'
nu='{"permissions":{"deny":["Bash(rm:*)"]}}'
sansdeny='{"enabledPlugins":{"harnais@atelier":true}}'
INS=()
faits() { for f in base architecture stack rules; do ecr "$1/brain/fact/$f.md" "---\ncap: le cap de $2\n---\n"; done; git -C "$1" init -q; }
brain() { faits "$1" "$2"; etat "$1/brain/mind/state.md" "$(jour 2)" verte "avancer"; ecr "$1/brain/mind/todo.md" "\n"; }
regle() { ecr "$1/.claude/settings.json" "$2\n"; }
trace() { local v=""; [ -n "$2" ] && v=", \"version\": \"$2\""
  ecr "$1/.claude/.briefing.json" "{\"derniere\": $maintenant, \"evenement\": \"SessionStart\"$v}\n"; }
inscris() { INS+=("$1|$2"); }
servi() { regle "$1" "$declare_"; trace "$1" "$V"; inscris "$1" "$V"; }

P="$R/conforme"; brain "$P" conforme; servi "$P"
etat "$P/brain/mind/state.md" "$(jour 3)" verte "livrer la v2"
ecr "$P/brain/mind/todo.md" "# À faire\n\n- [ ] !haut @user **Je publie ? oui / non**\n- [ ] @dehors attendre le fournisseur\n- [ ] copier sur root@serveur\n- [x] déjà fait\n- [>] !moyen en cours\n"
ecr "$P/CLAUDE.md" "@docs/guide.md\n"; ecr "$P/docs/guide.md" "La mémoire est dans brain/\n"
ecr "$P/.logs/2026-09-01.md" "x\n"; ecr "$P/.logs/2026-09-02.md" "x\n"

Q="$R/equipe"; faits "$Q" equipe; ecr "$Q/brain/fact/roles.md" "# rôles\n"; ecr "$Q/CLAUDE.md" "voir brain/\n"
for a in A B; do ecr "$Q/agents/$a/CLAUDE.md" "# $a\n"; servi "$Q/agents/$a"; done
etat "$Q/brain/mind/A/state.md" "$(jour 10)" rouge "réparer"
ecr "$Q/brain/mind/A/todo.md" "- [ ] !bas @user **Tu valides ?**\n"
etat "$Q/brain/mind/B/state.md" "$(jour 1)" verte "avancer"
ecr "$Q/brain/mind/B/todo.md" "- [>] travail de B\n- [ ] !moyen @Zoe **Zoe tranche ?**\n"

P="$R/v1"; for f in base architecture stack rules; do ecr "$P/.fact/$f.md" "---\ncap: le cap de v1\n---\n"; done
etat "$P/.mind/state.md" "$(jour 5)" orange "migrer un jour"; ecr "$P/.mind/todo.md" "\n"; git -C "$P" init -q; servi "$P"

A="$R/ancien"; for f in state todo stack architecture rules; do ecr "$A/.mind/$f.md" "x\n"; done
etat "$A/.mind/state.md" "$(jour 40)" orange "vieux"; ecr "$A/.memory/charter.md" "# charte\n"; git -C "$A" init -q

P="$R/ambigu"; brain "$P" ambigu; ecr "$P/.fact/base.md" "---\ncap: l'ancien\n---\n"; servi "$P"
P="$R/non-branche"; brain "$P" x; regle "$P" "$nu"; trace "$P" "$V"; inscris "$P" "$V"
P="$R/hooks-locaux"; brain "$P" x; regle "$P" "$locaux"; trace "$P" "$V"; inscris "$P" "$V"
P="$R/non-inscrit"; brain "$P" x; regle "$P" "$declare_"; trace "$P" "$V"
P="$R/jamais-servi"; brain "$P" x; regle "$P" "$declare_"; inscris "$P" "$V"
P="$R/en-retard"; brain "$P" x; regle "$P" "$declare_"; trace "$P" 0.0.1; inscris "$P" "$V"
P="$R/retard-ancien"; brain "$P" x; regle "$P" "$declare_"; trace "$P" ""; inscris "$P" "$V"
P="$R/inscription-vieille"; brain "$P" x; regle "$P" "$declare_"; trace "$P" 0.0.1; inscris "$P" 0.0.1
P="$R/sans-deny"; brain "$P" x; regle "$P" "$sansdeny"; trace "$P" "$V"; inscris "$P" "$V"
P="$R/sans-agent"; faits "$P" seul; servi "$P"
P="$R/incomplet"; brain "$P" x; rm "$P/brain/mind/todo.md"; servi "$P"
P="$R/surplus"; brain "$P" x; ecr "$P/brain/fact/journal.md" "x\n"; servi "$P"
mkdir -p "$R/neuf/src"; git -C "$R/neuf" init -q
for f in base architecture stack rules; do ecr "$R/sans-git/brain/fact/$f.md" "x\n"; done
mkdir -p "$R/claude-starter/.mind" "$R/claude-harnais/brain" "$R/.cache/.mind"

{ printf '{"version": 2, "plugins": {"harnais@atelier": ['; sep=""
  for e in "${INS[@]}"; do
    printf '%s{"scope": "project", "projectPath": "%s", "version": "%s"}' "$sep" "${e%%|*}" "${e#*|}"; sep=", "
  done; printf ']}}\n'; } > "$I"

joue() { local nom="$1" ins="$2"; shift 2
  ( cd /tmp && HARNAIS_INSCRIPTIONS="$ins" "${CMD[@]}" "$@" ) > "$S/$nom" 2>&1; echo "rc=$?" >> "$S/$nom"; }
joue terminal.txt "$I" --racine "$R"
joue un-projet.txt "$I" --racine "$R" --projet EQUIPE
joue introuvable.txt "$I" --racine "$R" --projet personne
joue illisible.txt "$H/absent.json" --racine "$R" --projet conforme
joue page.sortie "$I" --racine "$R" --html "$S/page.html"
joue watch-sans-html.txt "$I" --racine "$R" --watch 60
joue watch-trop-court.txt "$I" --racine "$R" --html "$S/x.html" --watch 3
VRE="$(printf '%s' "$V" | sed 's/[.]/\\./g')"
# LES DATES DU CORPUS SONT RELATIVES AU JOUR DU PASSAGE, donc elles changent
# toutes les nuits : le témoin figé le 11/09 échouait le 12/09 sur « maj :
# 2026-09-01 » devenu « 2026-09-02 ». L'âge en jours, lui, ne bouge pas — c'est
# lui qu'on compare. Défaut de ce contrôle, trouvé par la suite le lendemain.
DATES=""
for d in 1 2 3 5 10 40; do DATES="$DATES -e s|$(jour $d)|<J-$d>|g"; done
neutre() { sed -E $DATES -e "s|$R|<ATELIER>|g" -e "s|$S|<SORTIE>|g" -e "s|$VRE|<V>|g" \
  -e 's|relevé du [0-9]{2}/[0-9]{2}/[0-9]{4} à [0-9]{2}:[0-9]{2}|relevé du <DATE>|' \
  -e 's|\([0-9]+ projets, [0-9]+ Ko\)|(<N> projets, <K> Ko)|' \
  -e 's|^usage: .*|usage: <USAGE>|'; }

# LE SENS, AVANT LES OCTETS : chaque projet rend le verdict pour lequel il a été
# fabriqué. C'est ce qui empêche de figer une lecture fausse une seconde fois.
ecarts=0
attendu() { local ligne; ligne="$(grep -F -- "── $1 " "$S/$3" | head -1)"
  if [[ "$ligne" == *"[$2]"* ]]; then echo "  ✓ $1 → [$2]"
  else echo "  ✗ $1 : attendu [$2], rendu : ${ligne:-<absent>}"; ecarts=$((ecarts+1)); fi; }
for c in "conforme:OK  " "equipe:OK  " "v1:V1  " "ancien:TRI " "ambigu:AMBI" "non-branche:BRCH" \
         "hooks-locaux:HOOK" "non-inscrit:INSC" "jamais-servi:SERV" "en-retard:RETD" "retard-ancien:RETD" \
         "inscription-vieille:MAJ " "sans-deny:DENY" "sans-agent:AGT?" "incomplet:MANQ" "surplus:TROP" \
         "neuf:NEUF" "sans-git:GIT "; do attendu "${c%%:*}" "${c#*:}" terminal.txt; done
attendu conforme "????" illisible.txt
for n in claude-starter claude-harnais .cache; do
  if grep -qF -- "── $n " "$S/terminal.txt"; then echo "  ✗ $n devait être ignoré"; ecarts=$((ecarts+1))
  else echo "  ✓ $n ignoré"; fi
done
if grep -qE '/agentic-(upgrade|sync)|agentic-team\.py' "$S/terminal.txt" "$S/page.html"; then
  echo "  ✗ un conseil renvoie à une commande disparue"; ecarts=$((ecarts+1))
else echo "  ✓ aucun conseil ne renvoie à une commande disparue"; fi

for f in "$S"/*; do
  n=$(basename "$f")
  if [ "$MODE" = figer ]; then continue; fi
  if neutre < "$f" | cmp -s - "$T/$n"; then echo "  ✓ $n"
  else echo "  ✗ $n"; neutre < "$f" | diff "$T/$n" - | head -14; ecarts=$((ecarts+1)); fi
done
if [ "$MODE" = figer ]; then
  if [ "$ecarts" != 0 ]; then echo "REFUS de figer : $ecarts verdict(s) faux"; exit 1; fi
  rm -rf "$T"; mkdir -p "$T"
  for f in "$S"/*; do neutre < "$f" > "$T/$(basename "$f")"; done
  { echo "origine: rust — la lecture d'avant était fausse, et son script est retiré (voir l'en-tête)"
    git -C "$DEPOT" rev-parse HEAD; echo "programme: $V"; (cd "$DEPOT" && shasum py/vue.py); } > "$T/provenance.txt"
  echo "figé : $(ls "$T" | wc -l | tr -d ' ') fichiers"; exit 0
fi
if neutre < "$S/un-projet.txt" | cmp -s - "$T/terminal.txt"; then
  echo "  ✗ contre-exemple : un projet seul rend l'atelier entier"; ecarts=$((ecarts+1))
else echo "  ✓ contre-exemple : un projet seul et l'atelier se distinguent"; fi
echo "$ecarts écart(s)"
[ "$ecarts" = 0 ]
