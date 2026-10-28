#!/bin/bash
# LA CONVERSION EN ÉQUIPE RELUE CONTRE LE TÉMOIN FIGÉ DU PYTHON.
#
#     bash controles/equipe.sh [binaire]      compare le Rust au témoin
#     bash controles/equipe.sh --figer        (une fois) fige ce que rend le Python
#
# Le même scénario joue les deux côtés : seule la commande change. Le témoin
# (`temoins/equipe/`) a été figé le 11/09/2026 depuis `agentic-agents.py`,
# AVANT son retrait — voir `provenance.txt`.
#
# Tout se joue sous une MAISON FABRIQUÉE (HOME) : la conversion déplace la
# mémoire automatique rangée sous `~/.claude/projects/`, et ancre ses refus sur
# `~/` — la jouer sur la vraie maison déplacerait la vraie mémoire.
#
# Cas, chacun avec ce qu'il sépare :
#   brain-mono   brain/ + réglages avec hooks + .mcp.json + mémoire auto
#                → esprit descendu d'un cran, réglages repris, hooks retirés,
#                  deny ancrés sur ~/, mémoire auto déplacée et l'ancienne marquée
#   brain-multi  le même, UN agent de plus               → n'emporte rien, ajoute
#   ancien-mono  .fact/ + .mind/                         → esprit dans agents/<nom>/.mind
#   sans-faits   ni brain/fact ni .fact                  → REFUS, rien d'écrit
#   collision    « Q A » et « Q-A »                      → REFUS, même mémoire auto
# Pour chacun : la sortie, l'arbre après, et le contenu des fichiers posés.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
T="$ICI/temoins/equipe"
if [ "${1:-}" = "--figer" ]; then
  MODE=figer; CMD=(python3 "$DEPOT/skills/agentic-agents/scripts/agentic-agents.py")
else
  MODE=compare; B="${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}"; CMD=("$B" equipe)
fi
# Le chemin RÉSOLU : les deux programmes résolvent la racine du projet, et
# /var/folders est un lien vers /private/var/folders — sans ça la maison ne se
# neutraliserait pas dans leurs sorties.
M="$(cd "$(mktemp -d)" && pwd -P)/maison"; mkdir -p "$M/.claude/projects"; S="$(mktemp -d)"
JOUR=$(date +%Y-%m-%d); JOURC=$(date +%Y%m%d)
slug() { printf '%s' "$1" | sed 's/[^A-Za-z0-9]\{1,\}/-/g'; }
# La maison se retrouve aussi SLUGIFIÉE dans les adresses de mémoire auto.
neutre() { sed -e "s|$M|<MAISON>|g" -e "s|$(slug "$M")|<MAISON-SLUG>|g" \
  -e "s|$JOUR|<JOUR>|g" -e "s|$JOURC|<JOURC>|g" -e "s|$(date +%Y-%m)|<MOIS>|g"; }
depot() { git -C "$1" init -q -b main; git -C "$1" config user.email e@x; git -C "$1" config user.name e; }
commit() { git -C "$1" add -A >/dev/null; git -C "$1" commit -qm c >/dev/null; }
reglages='{"permissions":{"allow":["Bash(ls:*)"],"deny":["Edit(~/x/agents/vieux/**)"]},"hooks":{"Stop":[{"hooks":[{"type":"command","command":"a"},{"type":"command","command":"b"}]}]}}'

# ── brain-mono ─────────────────────────────────────────────────────────
P="$M/Agentic/brain-mono"; mkdir -p "$P/brain/fact" "$P/brain/mind" "$P/.claude"; depot "$P"
printf -- '---\ncap: essai\n---\n' > "$P/brain/fact/base.md"
printf -- '---\nmaj: 2026-01-01\n---\n# état\n' > "$P/brain/mind/state.md"; printf '# à faire\n' > "$P/brain/mind/todo.md"
printf '%s\n' "$reglages" > "$P/.claude/settings.json"; printf '{"mcpServers":{}}\n' > "$P/.mcp.json"
commit "$P"
A="$M/.claude/projects/$(slug "$P")"; mkdir -p "$A/memory"; printf '{}\n' > "$A/f1.jsonl"; printf 'n\n' > "$A/memory/n.md"

# ── ancien-mono ────────────────────────────────────────────────────────
Q="$M/Agentic/ancien-mono"; mkdir -p "$Q/.fact" "$Q/.mind"; depot "$Q"
printf -- '---\ncap: essai\n---\n' > "$Q/.fact/base.md"; printf '# état\n' > "$Q/.mind/state.md"; printf '# à faire\n' > "$Q/.mind/todo.md"
commit "$Q"

# ── sans-faits, collision ──────────────────────────────────────────────
R="$M/Agentic/sans-faits"; mkdir -p "$R/src"; depot "$R"; printf 'x\n' > "$R/src/a"; commit "$R"
C="$M/Agentic/collision"; mkdir -p "$C/brain/fact" "$C/brain/mind"; depot "$C"
printf -- '---\ncap: c\n---\n' > "$C/brain/fact/base.md"; printf '# é\n' > "$C/brain/mind/state.md"; commit "$C"

joue() {  # nom projet agents [--apply]
  local nom="$1" p="$2" ag="$3"; shift 3
  ( cd /tmp && HOME="$M" "${CMD[@]}" --project-root "$p" --agents "$ag" "$@" ) > "$S/$nom.sortie" 2>&1
  echo "rc=$?" >> "$S/$nom.sortie"
}
etat() {  # nom projet — l'arbre, puis chaque fichier posé
  local nom="$1" p="$2"
  { (cd "$p" && find . -path ./.git -prune -o -print | LC_ALL=C sort)
    echo "── mémoire auto"; (cd "$M/.claude/projects" && find . | LC_ALL=C sort)
    for f in $(cd "$p" && find . -path ./.git -prune -o -type f \( -name '*.md' -o -name '*.json' \) -print | LC_ALL=C sort); do
      echo "── $f"; cat "$p/$f"; done
  } > "$S/$nom.etat" 2>&1
}
joue brain-mono-blanc "$P" PO,QA;          etat brain-mono-blanc "$P"
joue brain-mono "$P" PO,QA --apply;        etat brain-mono "$P"
joue brain-multi "$P" OPS --apply;         etat brain-multi "$P"
joue ancien-mono "$Q" A,B --apply;         etat ancien-mono "$Q"
joue sans-faits "$R" A,B --apply;          etat sans-faits "$R"
joue collision "$C" "Q A,Q-A" --apply;     etat collision "$C"

ecarts=0
# L'ÉCART DÉCLARÉ du 11/09/2026. La fiche des rôles que pose la conversion
# nommait `.fact/` même dans un projet en `brain/` — le Python l'écrivait ainsi,
# et c'était faux : l'agent qui la lit cherche ses faits là où ils ne sont pas.
# Le programme nomme désormais la maison réelle. Le témoin reste celui du
# Python : l'écart est appliqué à SON côté, sur les deux lignes de la fiche, et
# pour les seuls cas en `brain/` — le cas `.fact/` doit rester identique.
fiche() {
  case "$1" in
    brain-mono.etat|brain-multi.etat)
      sed -e 's|^> Il appartient à `\.fact/` parce qu|> Il appartient à `brain/fact/` parce qu|' \
          -e 's|^`\.fact/`, `docs/`, `\.logs/` et la racine du dépôt|`brain/fact/`, `docs/`, `.logs/` et la racine du dépôt|' ;;
    *) cat ;;
  esac
}
# L'ÉCART DÉCLARÉ du 24/09/2026. La conversion DÉPLAÇAIT la mémoire auto vers
# l'adresse du dossier d'agent. Or Claude Code la range à la racine du DÉPÔT,
# que `agents/<nom>/` ne quitte pas : le déplacement l'envoyait là où Claude
# Code ne lit jamais, et il recommençait un carnet vide à la racine. Mesuré sur
# un projet converti le 04/09 : 13 notes parties chez un agent, 103 écrites
# depuis dans un carnet neuf que rien n'entretenait. Tous les projets de ce banc
# sont des dépôts : la mémoire y reste, sous son nom, sans marque `.migre`.
memoire() {
  case "$1" in
    *.sortie) sed -e 's|^  → mémoire auto : .* ; l.ancien sera marqué \.migre-<JOURC>$|  · mémoire auto : même dépôt, même adresse — rien à migrer|' \
                  -e 's|^  · aucune mémoire auto à migrer (.* absent)$|  · mémoire auto : même dépôt, même adresse — rien à migrer|' ;;
    *.etat) sed -e '/-Agentic-brain-mono-agents-PO/d' -e 's|-Agentic-brain-mono\.migre-<JOURC>|-Agentic-brain-mono|' ;;
    *) cat ;;
  esac
}
attendu() { fiche "$1" < "$T/$1" | memoire "$1"; }
for f in "$S"/*; do
  n=$(basename "$f")
  if [ "$MODE" = figer ]; then mkdir -p "$T"; neutre < "$f" > "$T/$n"; continue; fi
  if neutre < "$f" | cmp -s - <(attendu "$n"); then echo "  ✓ $n"
  else echo "  ✗ $n"; neutre < "$f" | diff <(attendu "$n") - | head -14; ecarts=$((ecarts+1)); fi
done
# Un écart déclaré qui ne change plus rien est périmé : il masquerait le jour
# où le témoin serait refigé sans lui.
if [ "$MODE" = compare ]; then
  for n in brain-mono.etat brain-multi.etat; do
    k=$(diff "$T/$n" <(fiche "$n" < "$T/$n") | grep -c '^>')
    if [ "$k" = 2 ]; then echo "  ✓ l'écart déclaré de la fiche mord sur $n (2 lignes)"
    else echo "  ✗ l'écart déclaré de la fiche change $k ligne(s) de $n au lieu de 2 — à revoir"; ecarts=$((ecarts+1)); fi
  done
  for n in brain-mono.sortie brain-mono-blanc.sortie ancien-mono.sortie brain-mono.etat; do
    k=$(diff "$T/$n" <(memoire "$n" < "$T/$n") | grep -c '^[<>]')
    if [ "$k" -gt 0 ]; then echo "  ✓ l'écart déclaré de la mémoire mord sur $n ($k lignes)"
    else echo "  ✗ l'écart déclaré de la mémoire ne change rien à $n — périmé ?"; ecarts=$((ecarts+1)); fi
  done
fi
if [ "$MODE" = figer ]; then
  { git -C "$DEPOT" rev-parse HEAD; (cd "$DEPOT" && shasum skills/agentic-agents/scripts/agentic-agents.py); } > "$T/provenance.txt"
  echo "figé : $(ls "$T" | wc -l | tr -d ' ') fichiers dans $T"; exit 0
fi
# le contre-exemple : un témoin d'une autre conversion ne doit pas passer
if neutre < "$S/ancien-mono.sortie" | cmp -s - "$T/brain-mono.sortie"; then
  echo "  ✗ contre-exemple : deux conversions différentes rendent pareil"; ecarts=$((ecarts+1))
else echo "  ✓ contre-exemple : deux conversions différentes se distinguent"; fi
echo "$ecarts écart(s)"
[ "$ecarts" = 0 ]
