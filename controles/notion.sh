#!/bin/bash
# LE CANAL NOTION — plus rien vers les Rappels, et une question sans sa ligne
# dans la base Décisions ne laisse pas finir le tour (garde B14).
#
#     bash controles/notion.sh [binaire]
#
# Demandé par le commanditaire le 30/09/2026 (« contrôle : 1 » :
# le lien de la ligne, pas une lecture de Notion). Chaque garantie a son
# contraire : sans le réglage, B14 se tait — et les Rappels ne sont pas appelés
# non plus, depuis le 08/10/2026 ; l'ancien programme, lui, s'y fait prendre ;
# avec un lien, le tour passe ; sans lien, il ne passe pas, même après un
# premier renvoi — mais pas indéfiniment.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
B="${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}"
source "$ICI/ancien-harnais.sh"
S="$(mktemp -d)"; LISTE="notion-$$"; P="$S/$LISTE"; DATA="$S/data"
VERROU="$HOME/.claude/rappels-verrous/$LISTE.verrou"
nettoie() { rm -rf "$S"; rm -f "$VERROU" "$ANCIEN"; }
trap nettoie EXIT
mkdir -p "$P/brain/fact" "$P/brain/mind" "$DATA"
# Le banc ne lit jamais le carnet des rechutes réel de la machine (0.18.1 : la
# garde le lit désormais dans ~/.claude) : un carnet vide, posé ici, fait foi.
: > "$DATA/rechutes.md"
git -C "$P" init -q -b main; git -C "$P" config user.name M; git -C "$P" config user.email m@x
printf -- '---\ncap: un cap\n---\n\n## Nature\nx\n' > "$P/brain/fact/base.md"
printf -- '---\nmaj: %s\nsante: verte\njalon: J\n---\n' "$(date +%Y-%m-%d)" > "$P/brain/mind/state.md"
printf '# À faire\n\n## Travail\n' > "$P/brain/mind/todo.md"
git -C "$P" add -A; git -C "$P" commit -q -m socle
printf '{}' > "$DATA/rappels.json"
ID=0f0f0f0f0f0f4f0f8f0f0f0f0f0f0f0f

# fin <canal> <stop_hook_active> <session>
fin() {
  : > "$DATA/appels.log"
  python3 -c 'import json,sys; print(json.dumps({"session_id":sys.argv[2],"stop_hook_active":sys.argv[1]=="1","last_assistant_message":"Question posée."}))' "$2" "$3" > "$S/in"
  (cd "$P" && env -u CLAUDE_PLUGIN_ROOT -u HARNAIS_JUGE -u HARNAIS_CANAL ${1:+HARNAIS_CANAL=$1} \
     PATH="$ICI/faux-bin:$PATH" CLAUDE_PLUGIN_DATA="$DATA" CLAUDE_PROJECT_DIR="$P" \
     CLAUDE_CODE_ENTRYPOINT=cli FAUX_RAPPELS="$DATA/rappels.json" \
     FAUX_JOURNAL="$DATA/appels.log" HARNAIS_RELECTURE_SIMULEE=1 \
     "$B" attente < "$S/in" > "$S/out" 2> "$S/err"; echo $? > "$S/code")
}
code() { cat "$S/code"; }
b14() { grep -q "ligne dans la base" "$S/err"; }
rappels() { awk 'END{print NR}' "$DATA/appels.log" 2>/dev/null || echo 0; }
ecarts=0
ok() { echo "  ✓ $1"; }
ko() { echo "  ✗ $1 — code $(code), appels Rappels $(rappels)"; ecarts=$((ecarts+1)); }
# Le motif (0.19.5) : sans lui, la garde des questions refuse avant B14.
question() { sleep 1.1; printf '\n- [ ] !haut @user **%s ? 1 / 2**\n      1 → a.\n      2 → b.\n      motif → périmètre\n      fini quand → tu vois c.\n%s' "$1" "${2:+      ↳ $2
}" >> "$P/brain/mind/todo.md"; }

fin notion 0 s0; fin notion 0 s0                     # premières rencontres
question "Je publie la page A" ""
fin notion 0 s1
[ "$(code)" = 2 ] && b14 && ok "1. une question sans ligne Décisions ne laisse pas finir" || ko "1. une question sans ligne passe"
[ "$(rappels)" = 0 ] && ok "   et rien n'est parti vers les Rappels" || ko "   les Rappels ont été appelés en canal Notion"
fin notion 1 s1
[ "$(code)" = 2 ] && b14 && ok "2. même après un premier renvoi, elle renvoie encore (garde d'état)" || ko "2. elle se tait après un premier renvoi"
fin notion 1 s1; fin notion 1 s1
[ "$(code)" = 0 ] && grep -q "sans ligne dans" "$S/out" && ok "3. au 4e passage elle laisse finir et le dit au commanditaire" || ko "3. elle tourne en rond, ou se tait"
python3 - "$P/brain/mind/todo.md" "$ID" <<'PY'
import sys; p, i = sys.argv[1], sys.argv[2]; t = open(p).read()
t = t.replace("      fini quand → tu vois c.\n", "      fini quand → tu vois c.\n      ↳ https://www.notion.so/espace/Page-A-%s\n" % i, 1); open(p, "w").write(t)
PY
sleep 1.1; fin notion 0 s2
[ "$(code)" = 0 ] && ! b14 && ok "4. avec le lien de sa ligne, le tour finit" || ko "4. une question avec sa ligne est renvoyée"
[ "$(rappels)" = 0 ] && ok "   toujours rien vers les Rappels" || ko "   les Rappels ont été appelés"
question "Je publie la page B" "voir la ligne dans Notion"
fin notion 0 s3
[ "$(code)" = 2 ] && b14 && ok "5. « voir Notion » sans l'adresse de la page ne suffit pas" || ko "5. un faux lien passe"
sleep 1.1; touch "$P/brain/mind/todo.md"; fin "" 0 s4
! b14 && ok "6 témoin. sans le réglage, B14 se tait…" || ko "6 témoin. B14 mord hors canal Notion"
[ "$(rappels)" = 0 ] && ok "   …et sans le réglage non plus, rien vers les Rappels" || ko "   sans le réglage, les Rappels sont encore appelés"
B0="$B"; B="$ANCIEN"; sleep 1.1; touch "$P/brain/mind/todo.md"; fin "" 0 s5; B="$B0"
[ -n "$ANCIEN" ] && [ "$(rappels)" -gt 0 ] && ok "7 témoin. la 0.12.6, sur ce banc, appelle les Rappels ($(rappels) appel(s)) : le piège voit" \
  || ko "7 témoin. même la 0.12.6 n'appelle pas les Rappels ici — le piège est aveugle"
echo "notion : $ecarts écart(s)"
[ "$ecarts" = 0 ]
