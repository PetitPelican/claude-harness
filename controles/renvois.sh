#!/bin/bash
# LES RENVOIS DE FIN DE TOUR NE FONT PLUS RÉPÉTER — rejoué sur le cas réel.
#
#     bash controles/renvois.sh [binaire]
#
# Le 27/09/2026 à 0 h 43, un agent PO a réécrit quatre fois de suite la même
# conclusion : quatre renvois d'affilée, dont deux à tort (une question bien
# formée, mais dont la ligne `- fini quand →` portait un tiret de liste), et
# chacun lui demandait de reposer ses questions dans son message. Sur la flotte,
# la même semaine : 107 renvois sur 777 fins de tour, 19 tours en chaîne.
#
# Trois garanties, chacune avec son contraire :
#   1. une question bien formée À TIRETS, posée dans le message, ne renvoie pas
#      pour sa forme ;
#   2. après un premier renvoi (`stop_hook_active`), aucune garde de FORME ne
#      renvoie une seconde fois — même devant une ligne encore mal écrite ;
#      mais la même ligne, SANS renvoi préalable, renvoie bien (témoin) ;
#   3. une garde d'ÉTAT (du code bougé sans todo) renvoie encore, même après un
#      premier renvoi : on n'a pas éteint le hook ;
#   et tout renvoi dit de ne pas recopier le message.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
B="${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}"
S="$(mktemp -d)"; LISTE="renvois-$$"; P="$S/$LISTE"; DATA="$S/data"
VERROU="$HOME/.claude/rappels-verrous/$LISTE.verrou"
nettoie() { rm -rf "$S"; rm -f "$VERROU"; }
trap nettoie EXIT

mkdir -p "$P/brain/fact" "$P/brain/mind" "$DATA"
git -C "$P" init -q -b main; git -C "$P" config user.name M; git -C "$P" config user.email m@x
printf -- '---\ncap: un cap\n---\n\n## Nature\nx\n' > "$P/brain/fact/base.md"
printf -- '---\nmaj: %s\nsante: verte\njalon: J\n---\n' "$(date +%Y-%m-%d)" > "$P/brain/mind/state.md"
printf '# À faire\n\n## Travail\n\n- [ ] !haut @user **Une vieille question ? oui / non**\n      oui → on fait ceci.\n      non → on fait cela.\n      fini quand → tu vois la page en ligne.\n' > "$P/brain/mind/todo.md"
git -C "$P" add -A; git -C "$P" commit -q -m socle
printf '[]' > "$DATA/rappels.json"

# fin <stop_hook_active> <dernier message>  → code dans $S/code, message dans $S/err
fin() {
  # UNE SECONDE ENTRE DEUX PASSAGES : la fin de tour ne relit pas un todo dont
  # la date, à la seconde, n'a pas bougé. Depuis qu'elle n'appelle plus les
  # Rappels (08/10/2026) un passage dure quelques millisecondes, et deux
  # retouches tombaient dans la même seconde — le banc mesurait sa propre hâte.
  sleep 1.1
  python3 -c 'import json,sys; print(json.dumps({"session_id":"s1","stop_hook_active":sys.argv[1]=="1","last_assistant_message":sys.argv[2]}))' "$1" "$2" > "$S/in"
  (cd "$P" && env -u CLAUDE_PLUGIN_ROOT -u HARNAIS_JUGE \
     PATH="$ICI/faux-bin:$PATH" CLAUDE_PLUGIN_DATA="$DATA" CLAUDE_PROJECT_DIR="$P" \
     CLAUDE_CODE_ENTRYPOINT=cli FAUX_RAPPELS="$DATA/rappels.json" \
     FAUX_JOURNAL="$DATA/appels.log" HARNAIS_RELECTURE_SIMULEE=1 \
     "$B" attente < "$S/in" > "$S/out" 2> "$S/err"; echo $? > "$S/code")
}
code() { cat "$S/code"; }
garde() { tr "\n" " " < "$S/err" | sed -n "s/.*attente : \(.\{0,90\}\).*/\1/p"; }
ecarts=0
ok() { echo "  ✓ $1"; }
ko() { echo "  ✗ $1 — code $(code) : $(garde)"; ecarts=$((ecarts+1)); }
todo_ajoute() { printf '%s\n' "$1" >> "$P/brain/mind/todo.md"; }

fin 0 "Rien de neuf."                       # première rencontre : l'arriéré est amnistié
fin 0 "Rien de neuf."

# 1. La question de PO, telle qu'il l'a écrite, et posée dans son message.
todo_ajoute ""
todo_ajoute "- [ ] !moyen @user **Je prépare une version 11 ? 1 non, la version 10 a déjà tout / 2 oui, il manque quelque chose**"
todo_ajoute "  - 1 → rien ne part : tu installes la version 10 depuis le test interne."
todo_ajoute "  - 2 → tu m'écris ce qui manque, je le fais, OPS construit la version 11."
todo_ajoute "  - fini quand → ta version montre les cartes d'avant."
MSG="Tes apps sont à jour. **Je prépare une version 11 ? 1 non, la version 10 a déjà tout / 2 oui, il manque quelque chose**"
fin 0 "$MSG"
case "$(garde)" in *CONSTATS*) ko "1. une question à tirets bien formée est prise pour un constat" ;;
  *) ok "1. une question à tirets bien formée n'est pas renvoyée pour sa forme ($( [ "$(code)" = 0 ] && echo "aucun renvoi" || echo "renvoi : $(garde)"))" ;; esac
premier="$(code)"
fin 1 "J'ai relu, rien ne mord."
[ "$(code)" = 0 ] && ok "1 bis. après ce renvoi, la ligne d'une phrase passe (pas de reprise de la question)" \
  || ko "1 bis. une ligne d'une phrase est renvoyée alors que la question a été posée dans ce tour"

# 2. Une ligne mal écrite (un constat) : renvoyée une fois, pas deux.
todo_ajoute ""
todo_ajoute "- [ ] !haut @user **Le serveur de préproduction est tombé cette nuit**"
fin 1 "Le serveur est tombé, je te le signale."
[ "$(code)" = 0 ] && ok "2. déjà renvoyé dans ce tour : la forme ne renvoie pas une seconde fois" \
  || ko "2. une garde de forme renvoie une seconde fois dans le même tour"
todo_ajoute ""
todo_ajoute "- [ ] !haut @user **La base de données a débordé hier soir**"
fin 0 "La base a débordé."
case "$(garde)" in *CONSTATS*) ok "2 témoin. sans renvoi préalable, la même faute est bien renvoyée" ;;
  *) ko "2 témoin. une ligne mal écrite n'est pas renvoyée du tout — la garde est éteinte" ;; esac
grep -q "ne le recopie pas" "$S/err" && ok "   et le renvoi dit de ne pas recopier le message" \
  || ko "   le renvoi ne dit pas de ne pas recopier"

# 3. Une garde d'état renvoie encore après un premier renvoi.
printf 'x = 1\n' > "$P/code.py"; git -C "$P" add code.py; git -C "$P" commit -q -m code
printf 'x = 2\n' > "$P/code.py"
fin 1 "J'ai changé le code."
case "$(code):$(garde)" in 2:*) ok "3. une garde d'état renvoie encore après un premier renvoi ($(garde | cut -c1-40)…)" ;;
  *) ko "3. plus rien ne renvoie après un premier renvoi — le hook est éteint" ;; esac

echo "renvois : $ecarts écart(s)"
[ "$ecarts" = 0 ]
