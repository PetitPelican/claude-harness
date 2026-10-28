#!/bin/bash
# PLUS RIEN VERS LES RAPPELS — ni écrit, ni lu.
#
#     bash controles/sans-rappels.sh [binaire]
#
# Demandé par le commanditaire le 08/10/2026 : « supprime dans le harnais tout le fait
# que les agents mono ou multi mettent des notes dans mes rappels ios, je ne
# veux plus que la todo qui est tenue ». Ce contrôle remplace celui de la fin
# de tour muette (11/09/2026), qui gardait un canal désormais retiré.
#
# Trois preuves, et chacune a son témoin dans la 0.12.6, qui s'y fait prendre :
#   1. au fonctionnement : un faux `osascript` en tête du chemin journalise
#      tout appel ; le faux téléphone porte des réponses, une coche et une
#      demande de l'humain, de quoi tenter un programme qui lirait encore ;
#   2. à l'octet : le programme ne contient plus ni `osascript`, ni le nom de
#      l'app Rappels, ni celui du petit programme Swift qui lui parlait ;
#   3. à la porte : la sous-commande qui lisait une liste n'existe plus.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
B="${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}"
source "$ICI/ancien-harnais.sh"
S="$(mktemp -d)"; LISTE="sans-rappels-$$"; P="$S/$LISTE"
nettoie() { rm -rf "$S"; rm -f "$ANCIEN" "$HOME/.claude/rappels-verrous/$LISTE.verrou"; }
trap nettoie EXIT

monte() {   # un bac neuf par programme jugé : aucun état ne passe de l'un à l'autre
  rm -rf "$P" "$S/data"; mkdir -p "$P/brain/fact" "$P/brain/mind" "$S/data"
  git -C "$P" init -q -b main; git -C "$P" config user.name M; git -C "$P" config user.email m@x
  printf -- '---\ncap: un cap\n---\n\n## Nature\nx\n' > "$P/brain/fact/base.md"
  printf -- '---\nmaj: %s\nsante: verte\njalon: J\n---\n' "$(date +%Y-%m-%d)" > "$P/brain/mind/state.md"
  printf '# À faire\n\n## Travail\n\n- [ ] !haut @user **Une question ? oui / non**\n      oui → on fait ceci.\n      non → on fait cela.\n      fini quand → tu vois la page en ligne.\n' > "$P/brain/mind/todo.md"
  git -C "$P" add -A; git -C "$P" commit -q -m socle
  : > "$S/data/appels.log"
  printf '%s' '{"faits": ["🔴 Une question ? oui / non · Ta réponse : oui"], "ouverts": ["achète du café"]}' > "$S/data/rappels.json"
}
fin() {   # fin <binaire> <session> — le journal des appels court sur tout le bac
  (cd "$P" && printf '{"session_id":"%s"}' "$2" | env -u CLAUDE_PLUGIN_ROOT -u HARNAIS_JUGE -u HARNAIS_CANAL \
     PATH="$ICI/faux-bin:$PATH" CLAUDE_PLUGIN_DATA="$S/data" CLAUDE_PROJECT_DIR="$P" \
     CLAUDE_CODE_ENTRYPOINT=cli FAUX_RAPPELS="$S/data/rappels.json" \
     FAUX_JOURNAL="$S/data/appels.log" HARNAIS_RELECTURE_SIMULEE=1 \
     "$1" attente > "$S/out" 2> "$S/err"; echo $? > "$S/code")
}
appels() { awk 'END{print NR}' "$S/data/appels.log" 2>/dev/null || echo 0; }
code() { cat "$S/code"; }
# Le programme Python est un lanceur plus ses sources : on lit les deux. Un
# binaire (le témoin Rust) se lit par `strings`.
source_de() { if file -b "$1" | grep -q text; then cat "$1" "$(dirname "$1")"/../py/*.py 2>/dev/null; else strings "$1"; fi; }
traces() { source_de "$1" | grep -c -E 'osascript|Reminders|rappels-darwin-arm64'; }

ecarts=0
ok() { echo "  ✓ $1"; }
ko() { echo "  ✗ $1"; ecarts=$((ecarts+1)); }

echo "— le programme jugé"
monte; fin "$B" s1; fin "$B" s2
[ "$(appels)" = 0 ] && ok "1. aucun appel au téléphone, même avec une réponse, une coche et une demande qui attendent" \
  || ko "1. $(appels) appel(s) aux Rappels"
grep -q "Rappels" "$S/err" "$S/out" && ko "   un message parle encore des Rappels : $(tr '\n' ' ' < "$S/err" | cut -c1-120)" \
  || ok "   et aucun message ne parle de Rappels"
[ "$(code)" = 0 ] && ok "   le tour finit (code 0)" || ko "   le tour est renvoyé (code $(code)) : $(tr '\n' ' ' < "$S/err" | cut -c1-120)"
[ "$(traces "$B")" = 0 ] && ok "2. le programme ne contient plus aucune trace du canal" \
  || ko "2. $(traces "$B") trace(s) du canal dans le programme"
# Témoin de la lecture : sur un lanceur, zéro trace ne vaut que si les sources
# ont bien été lues (un chemin faux lirait zéro octet, donc zéro trace).
L=$(source_de "$B" | grep -c 'def attente\|def garde'); [ "$L" -gt 0 ] && ok "   lecture vérifiée : $L définition(s) du garde lues" \
  || ko "   les sources du programme n'ont pas été lues — la recherche à l'octet est aveugle"
# Une sous-commande inconnue rend 0 (le programme ne bloque jamais un hook pour
# une porte qui manque) : c'est donc ce qu'il DIT qui se juge, pas son code.
"$B" rappels --listes 2>&1 | grep -q "sous-commande inconnue" \
  && ok "3. la sous-commande qui lisait une liste n'existe plus" \
  || ko "3. la sous-commande qui lisait une liste répond encore"

echo "— TÉMOIN : la 0.12.6, sur le même banc"
if [ -z "$ANCIEN" ]; then ko "témoin introuvable"; else
  monte; fin "$ANCIEN" s1; fin "$ANCIEN" s2
  [ "$(appels)" -gt 0 ] && ok "1. elle appelle le téléphone ($(appels) appel(s)) : le piège voit" \
    || ko "1. même la 0.12.6 n'appelle rien — le piège est aveugle"
  [ "$(traces "$ANCIEN")" -gt 0 ] && ok "2. elle porte $(traces "$ANCIEN") trace(s) du canal : la recherche à l'octet voit" \
    || ko "2. aucune trace dans la 0.12.6 — la recherche à l'octet est aveugle"
  "$ANCIEN" rappels >/dev/null 2>&1; [ $? = 2 ] && ok "3. sa sous-commande répond (usage) : la porte se voyait" \
    || ko "3. la 0.12.6 n'a pas de sous-commande Rappels — le test de la porte est aveugle"
fi

echo
if [ "$ecarts" = 0 ]; then echo "ÉCARTS : AUCUN sur 9 garanties"; else echo "$ecarts écart(s)"; fi
exit $([ "$ecarts" = 0 ] && echo 0 || echo 1)
