#!/bin/bash
# LA GARDE DES FAITS DES AGENTS EXPERTS (B16) — un fait oublié exprès fait refuser la fin de tour.
#
#     bash controles/faits-experts.sh [programme]
#
# Demandé par le commanditaire le 12/10/2026 : « un agent expert oublie un fait exprès, et la fin de
# tour est refusée ». Le juge (un modèle) n'est JAMAIS appelé ici : un faux
# `claude` tient sa place, qui journalise ce qu'on lui envoie et rend le verdict
# du scénario. On éprouve donc la PLOMBERIE — qui est jugé, quand, avec quoi, et
# ce que la fin de tour fait du verdict. La justesse du juge lui-même se mesure à
# part, sur le vrai modèle (voir la trace de publication).
#
# Treize garanties — douze numérotées, plus le témoin (la 0.12.8, qui doit se
# faire prendre) :
#   1. un fait oublié      → refusé (code 2), le fait est nommé, la consigne dit date + source
#   2. le même état        → une seule fois (le second passage laisse partir)
#   3. le fait noté        → la fin de tour part (code 0)
#   4. un fait qui identifie quelqu'un, rangé dans une fiche partagée → refusé
#   5. un registre local que git suit → refusé ; ignoré → accepté
#   6. un « ok » de l'humain → le juge n'est pas appelé
#   7. un message de pair  → n'est pas un message de l'humain
#   8. juge muet           → la fin de tour part, et le journal le dit (B16-muet)
#   9. ce que le juge reçoit : le message, les fiches, le registre ; Sonnet ; aucun outil ;
#      HARNAIS_JUGE posé ; lancé hors du dossier de l'agent
#  10. profil développeur  → rien ne change : aucun juge, aucun refus
#  11. un expert enregistre ses faits sans ` # fact-ok` ; un développeur, non (témoin)
#  12. le briefing d'un expert annonce son profil, ses fiches libres et son registre
# TÉMOIN : la 0.12.8 Rust, sur le scénario 1, laisse partir — le scénario voit.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
B="${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}"
S="$(mktemp -d)"; S="$(cd "$S" && pwd -P)"
ANCIEN="$S/harnais-0.12.8"
git -C "$DEPOT" show 635e400:bin/harnais-darwin-arm64 > "$ANCIEN" 2>/dev/null
chmod 755 "$ANCIEN" 2>/dev/null; "$ANCIEN" version >/dev/null 2>&1 || ANCIEN=""
trap 'rm -rf "$S"' EXIT

P="$S/expert"; H="$S/maison"; J="$S/juge.log"
mkdir -p "$H/.local/bin"
# LE FAUX JUGE : il garde ce qu'il reçoit (arguments, entrée, dossier, variables)
# et rend le verdict posé par le scénario dans $S/verdict.
cat > "$H/.local/bin/claude" <<FIN
#!/bin/sh
{ echo "ARGS: \$*"; echo "CWD: \$(pwd)"; echo "JUGE: \${HARNAIS_JUGE:-}"; echo "---"; cat; echo; echo "=== FIN"; } >> "$J"
[ -f "$S/muet" ] && exit 1
cat "$S/verdict"
FIN
chmod 755 "$H/.local/bin/claude"

monte() {
  rm -rf "$P" "$S/data"; mkdir -p "$P/brain/fact" "$P/brain/mind" "$S/data"; : > "$J"; rm -f "$S/muet"
  git -C "$P" init -q -b main; git -C "$P" config user.name M; git -C "$P" config user.email m@x
  printf -- '---\ncap: le droit de la société\n---\n\n## Nature\nLe juriste.\n' > "$P/brain/fact/base.md"
  printf '# Alpha SAS — le dossier de la société\n\n## Identité\n- Siège à Lyon · 08/10/2026 · dit\n' > "$P/brain/fact/societe.md"
  printf -- '---\nmaj: %s\nsante: verte\njalon: J\n---\n' "$(date +%Y-%m-%d)" > "$P/brain/mind/state.md"
  printf '# À faire\n\n- [ ] !moyen **Relire le pacte**\n      fini quand → relu.\n' > "$P/brain/mind/todo.md"
  git -C "$P" add -A; git -C "$P" commit -q -m socle
}
# journal <texte de l'humain> [enveloppe pair]
journal() {
  python3 -I - "$S/transcript.jsonl" "$1" "${2:-}" <<'PY'
import json, sys
f, texte, pair = sys.argv[1], sys.argv[2], sys.argv[3]
if pair:
    texte = '<cross-session-message from="x" from-name="CTO">\n' + texte + '\n</cross-session-message>'
l = [{"type": "user", "uuid": "u1", "message": {"role": "user", "content": "bonjour"}},
     {"type": "assistant", "uuid": "a1", "message": {"role": "assistant", "content": [{"type": "text", "text": "Bonjour."}]}},
     {"type": "user", "uuid": "u2", "message": {"role": "user", "content": texte}},
     {"type": "assistant", "uuid": "a2", "message": {"role": "assistant", "content": [{"type": "text", "text": "Compris."}]}}]
open(f, "w").write("\n".join(json.dumps(x, ensure_ascii=False) for x in l) + "\n")
PY
}
verdict() { printf '%s' "$1" > "$S/verdict"; }
# fin <programme> <session> [profil]
fin() {
  sleep 1.1
  (cd "$P" && printf '{"session_id":"%s","transcript_path":"%s"}' "$2" "$S/transcript.jsonl" \
    | env -u CLAUDE_PLUGIN_ROOT -u HARNAIS_JUGE -u HARNAIS_CANAL -u HARNAIS_SYNCHRO -u HARNAIS_PROFIL \
      -u HARNAIS_FAITS_SIMULE ${3:+HARNAIS_PROFIL=$3} HOME="$H" CLAUDE_PLUGIN_DATA="$S/data" \
      CLAUDE_PROJECT_DIR="$P" CLAUDE_CODE_ENTRYPOINT=cli HARNAIS_RELECTURE_SIMULEE=aucun \
      "$1" attente > "$S/out" 2> "$S/err"; echo $? > "$S/code")
}
code() { cat "$S/code"; }
appels() { n=$(grep -c '^ARGS:' "$J" 2>/dev/null); echo "${n:-0}"; }

ecarts=0
ok() { echo "  ✓ $1"; }
ko() { echo "  ✗ $1"; ecarts=$((ecarts+1)); }
OUBLI='{"faits":[{"fait":"Le capital social est de 10 000 euros","note":"nulle-part","identifiant":false}]}'
NOTE='{"faits":[{"fait":"Le capital social est de 10 000 euros","note":"partage","identifiant":false}]}'
MAL='{"faits":[{"fait":"La date de naissance du président","note":"partage","identifiant":true}]}'
FAIT="Le capital d'Alpha SAS est de 10 000 euros, réparti à parts égales."

echo "— le programme jugé"
monte; journal "$FAIT"; verdict "$OUBLI"; fin "$B" s1 expert
[ "$(code)" = 2 ] && grep -q "capital social" "$S/err" && grep -q "\*\*dit\*\*" "$S/err" \
  && ok "1. un fait oublié est refusé, nommé, avec la consigne date + source" \
  || ko "1. le fait oublié passe (code $(code)) : $(tr '\n' ' ' < "$S/err" | cut -c1-140)"
fin "$B" s1 expert
[ "$(code)" = 0 ] && ok "2. le même état ne renvoie qu'une fois" || ko "2. le même état renvoie encore (code $(code))"

monte; journal "$FAIT"; verdict "$OUBLI"; fin "$B" s3 expert
verdict "$NOTE"; fin "$B" s3 expert
[ "$(code)" = 0 ] && [ "$(appels)" = 2 ] && ok "3. une fois le fait noté, la fin de tour part — et le juge a RELU (2 appels)" \
  || ko "3. après la note : code $(code), $(appels) appel(s) au juge"

monte; journal "Le président est né le 3 mars 1990."; verdict "$MAL"; fin "$B" s4 expert
[ "$(code)" = 2 ] && grep -q "IDENTIFIENT" "$S/err" && ok "4. un fait identifiant dans une fiche partagée est refusé" \
  || ko "4. le fait identifiant mal rangé passe (code $(code))"

monte; mkdir -p "$P/brain/local"; echo "- registre" > "$P/brain/local/registre.md"; journal "ok"; verdict "$NOTE"
fin "$B" s5 expert; c1=$(code); grep -q "SUIVI par le dépôt" "$S/err"; m1=$?
echo "brain/local/" > "$P/.gitignore"; fin "$B" s5b expert; c2=$(code)
[ "$c1" = 2 ] && [ "$m1" = 0 ] && [ "$c2" = 0 ] && ok "5. un registre local suivi par git est refusé ; ignoré, il est accepté" \
  || ko "5. registre local : suivi → $c1, ignoré → $c2"

monte; journal "ok merci"; verdict "$OUBLI"; fin "$B" s6 expert
[ "$(code)" = 0 ] && [ "$(appels)" = 0 ] && ok "6. un « ok » de l'humain n'appelle pas le juge" \
  || ko "6. « ok » : code $(code), $(appels) appel(s)"

monte; journal "$FAIT" pair; verdict "$OUBLI"; fin "$B" s7 expert
[ "$(code)" = 0 ] && [ "$(appels)" = 0 ] && ok "7. un message de pair n'est pas un message de l'humain" \
  || ko "7. message de pair : code $(code), $(appels) appel(s)"

monte; journal "$FAIT"; : > "$S/muet"; fin "$B" s8 expert
[ "$(code)" = 0 ] && grep -q "B16-muet" "$S/data/attente/blocages.log" 2>/dev/null \
  && ok "8. juge muet : la fin de tour part, et le journal le dit" \
  || ko "8. juge muet : code $(code), journal : $(tail -1 "$S/data/attente/blocages.log" 2>/dev/null)"

monte; journal "$FAIT"; verdict "$OUBLI"; fin "$B" s9 expert
grep -q -- "--model claude-sonnet-5" "$J" && grep -q -- "--disallowedTools Bash Edit Write" "$J" \
  && grep -q "^JUGE: 1" "$J" && grep -q "réparti à parts égales" "$J" && grep -q "Siège à Lyon" "$J" \
  && ! grep -q "^CWD: $P" "$J" \
  && ok "9. le juge reçoit le message et les fiches ; Sonnet, sans outil, HARNAIS_JUGE, hors du dossier de l'agent" \
  || ko "9. ce que reçoit le juge ne va pas : $(head -3 "$J" | tr '\n' ' ' | cut -c1-160)"

monte; journal "$FAIT"; verdict "$OUBLI"; fin "$B" s10
[ "$(code)" = 0 ] && [ "$(appels)" = 0 ] && ok "10. profil développeur : aucun juge, aucun refus" \
  || ko "10. développeur : code $(code), $(appels) appel(s)"

monte; echo "- Capital : 10 000 € · 12/10/2026 · dit" >> "$P/brain/fact/societe.md"; git -C "$P" add -A
GARDE() { (cd "$P" && printf '{"tool_name":"Bash","tool_input":{"command":"git commit -m faits"}}' \
  | env -u HARNAIS_PROFIL ${1:+HARNAIS_PROFIL=$1} HOME="$H" CLAUDE_PLUGIN_DATA="$S/data" CLAUDE_PROJECT_DIR="$P" \
    "$B" mind-guard 2>/dev/null | grep -q '"permissionDecision": "deny"' && echo refus || echo passe); }
# Le garde de commit refuse par sa RÉPONSE (`permissionDecision: deny`), pas par
# son code de sortie : lire le code aurait déclaré « passe » un refus.
ge=$(GARDE expert); gd=$(GARDE "")
[ "$ge" = passe ] && [ "$gd" = refus ] && ok "11. un expert enregistre ses faits sans « fact-ok » ; un développeur est refusé" \
  || ko "11. garde de commit : expert → $ge, développeur → $gd"

monte; mkdir -p "$P/brain/local"; echo "- x" > "$P/brain/local/registre.md"
BR=$(cd "$P" && printf '{"hook_event_name":"SessionStart","session_id":"b"}' | env HARNAIS_PROFIL=expert HOME="$H" \
     CLAUDE_PLUGIN_DATA="$S/data" CLAUDE_PROJECT_DIR="$P" "$B" briefing)
echo "$BR" | grep -q "profil : expert" && echo "$BR" | grep -q "societe.md" \
  && echo "$BR" | grep -q "registre local" && echo "$BR" | grep -q "sources.md *ABSENT" \
  && ok "12. le briefing expert annonce le profil, la fiche libre, le registre et le socle manquant" \
  || ko "12. briefing expert incomplet : $(echo "$BR" | grep -E 'profil|societe|registre|sources' | tr '\n' ' ' | cut -c1-160)"

echo "— TÉMOIN : la 0.12.8 Rust, sur le scénario 1"
if [ -z "$ANCIEN" ]; then ko "témoin introuvable"; else
  monte; journal "$FAIT"; verdict "$OUBLI"; fin "$ANCIEN" t1 expert
  [ "$(code)" = 0 ] && ok "elle laisse partir le fait oublié : le scénario voit" \
    || ko "la 0.12.8 refuse aussi (code $(code)) — le scénario ne sépare rien"
fi

echo
if [ "$ecarts" = 0 ]; then echo "ÉCARTS : AUCUN sur 13 garanties"; else echo "$ecarts écart(s)"; fi
exit $([ "$ecarts" = 0 ] && echo 0 || echo 1)
