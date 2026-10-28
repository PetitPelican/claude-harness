#!/bin/bash
# LA MÉMOIRE PARTAGÉE ENTRE DEUX PERSONNES — deux copies, un distant nu.
#
#     bash controles/synchro.sh [binaire]
#
# Demandé par le CTO le 09/10/2026 (des agents experts servent deux personnes,
# chacune sur sa machine). Les deux personnes sont simulées par deux
# copies du même agent sur ce poste, chacune avec son esprit (« Expert A »,
# « Expert B »), et un `brain/` qui a son propre dépôt, cloné d'un distant
# nu. Le dépôt de l'agent, lui, n'a pas de distant : il ne doit jamais bouger.
#
# Cinq preuves, au programme réel, par les deux hooks qui les portent :
#   1. ce qu'écrit A est lu par B à son démarrage suivant ;
#   2. deux séances simultanées sur des fichiers différents fusionnent seules ;
#   3. le même passage modifié des deux côtés s'arrête : renvoi nommé, rien de
#      perdu, rien d'envoyé, l'arbre propre ;
#   4. hors ligne : le tour finit, et le retard se dit au message suivant ;
#   5. sans le réglage, rien ne part — même avec un distant ;
#   6. la course : l'autre envoie entre notre récupération et notre envoi —
#      jamais écrasé (son témoin est un sabotage : un envoi forcé y échoue) ;
#   7. le dépôt de l'agent : du nouveau sur son distant se dit, jamais ne se tire.
# TÉMOIN : la 0.12.7, sur le même banc, doit échouer 1, 2 et 3.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
B="${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}"
S="$(mktemp -d)"; S="$(cd "$S" && pwd -P)"
ANCIEN="$S/harnais-0.12.7"
git -C "$DEPOT" show 7bf63c1:bin/harnais-darwin-arm64 > "$ANCIEN" 2>/dev/null && chmod 755 "$ANCIEN" || ANCIEN=""
trap 'rm -rf "$S"' EXIT

# poste <x> <nom de l'esprit> — un clone du distant comme cerveau, dans un
# dépôt d'agent qui l'ignore.
poste() {
  local p="$S/$1"; mkdir -p "$p/agents/$2"
  git -C "$p" init -q -b main; git -C "$p" config user.name "$1"; git -C "$p" config user.email "$1@x"
  printf 'brain/\n' > "$p/.gitignore"; printf 'x\n' > "$p/agents/$2/.garde"
  git -C "$p" add -A; git -C "$p" commit -q -m agent
  git clone -q "$S/distant.git" "$p/brain" 2>/dev/null
  git -C "$p/brain" config user.name "$1"; git -C "$p/brain" config user.email "$1@x"
  mkdir -p "$S/data-$1"
}
monte() {
  rm -rf "$S/distant.git" "$S/a" "$S/b" "$S/semis" "$S"/data-*
  git init -q --bare -b main "$S/distant.git"
  local s="$S/semis"; git clone -q "$S/distant.git" "$s" 2>/dev/null
  git -C "$s" config user.name s; git -C "$s" config user.email s@x
  mkdir -p "$s/fact" "$s/workspace"
  printf -- '---\ncap: un cap\n---\n\n## Nature\nx\n' > "$s/fact/base.md"
  printf 'l1\nl2\nl3\nl4\nl5\nl6\nl7\nl8\n' > "$s/workspace/commun.md"
  for n in "Expert A" "Expert B"; do
    mkdir -p "$s/mind/$n"
    printf -- '---\nmaj: %s\nsante: verte\njalon: J\n---\n' "$(date +%Y-%m-%d)" > "$s/mind/$n/state.md"
    printf '# À faire\n\n- [ ] !moyen **Relire le contrat**\n      fini quand → relu.\n' > "$s/mind/$n/todo.md"
  done
  git -C "$s" checkout -q -b main 2>/dev/null; git -C "$s" add -A; git -C "$s" commit -q -m socle
  git -C "$s" push -q -u origin main 2>/dev/null
  poste a "Expert A"; poste b "Expert B"
}
esprit() { [ "$1" = a ] && echo "Expert A" || echo "Expert B"; }
# hook <binaire> <poste> <attente|briefing> <évènement> [synchro]
hook() {
  local ag="$S/$2/agents/$(esprit "$2")"
  (cd "$ag" && printf '{"session_id":"s-%s-%s","hook_event_name":"%s","prompt":"bonjour"}' "$2" "$RANDOM" "$4" \
    | env -u CLAUDE_PLUGIN_ROOT -u HARNAIS_JUGE -u HARNAIS_CANAL -u HARNAIS_SYNCHRO \
      ${5:+HARNAIS_SYNCHRO=$5} CLAUDE_PLUGIN_DATA="$S/data-$2" CLAUDE_PROJECT_DIR="$ag" \
      CLAUDE_CODE_ENTRYPOINT=cli HARNAIS_RELECTURE_SIMULEE=1 \
      "$1" "$3" > "$S/out" 2> "$S/err"; echo $? > "$S/code")
}
fin() { sleep 1.1; hook "$1" "$2" attente Stop "${3-git}"; }
entre() { hook "$1" "$2" briefing SessionStart "${3-git}"; }
message() { hook "$1" "$2" briefing UserPromptSubmit "${3-git}"; }
ecris() { printf '%s' "$3" > "$S/$1/brain/$2"; }
code() { cat "$S/code"; }
tete() { git -C "$1" rev-parse HEAD; }

ecarts=0
ok() { echo "  ✓ $1"; }
ko() { echo "  ✗ $1"; ecarts=$((ecarts+1)); }

# Chaque scénario rend 0 s'il tient — le témoin s'y juge à l'envers.
s1() {   # A écrit, B le lit à son entrée
  monte
  ecris a "mind/Expert A/state.md" "$(printf -- '---\nmaj: %s\nsante: verte\njalon: J2\n---\nclause 4 relue\n' "$(date +%Y-%m-%d)")"
  ecris a "workspace/note-a.md" "vu avec A"
  fin "$1" a; entre "$1" b
  grep -q "clause 4 relue" "$S/b/brain/mind/Expert A/state.md" 2>/dev/null \
    && [ -f "$S/b/brain/workspace/note-a.md" ]
}
s2() {   # deux séances, deux fichiers, en même temps
  monte
  ecris a "workspace/a.md" "A"; ecris b "workspace/b.md" "B"
  fin "$1" a; local ca; ca=$(code); fin "$1" b; local cb; cb=$(code); entre "$1" a
  [ "$ca" = 0 ] && [ "$cb" = 0 ] && [ -f "$S/a/brain/workspace/b.md" ] && [ -f "$S/b/brain/workspace/a.md" ] \
    && git --git-dir="$S/distant.git" show main:workspace/a.md >/dev/null 2>&1 \
    && git --git-dir="$S/distant.git" show main:workspace/b.md >/dev/null 2>&1
}
s3() {   # le même passage des deux côtés
  monte
  ecris a "workspace/commun.md" "$(printf 'l1\nl2\nl3\nl4 de A\nl5\nl6\nl7\nl8\n')"
  ecris b "workspace/commun.md" "$(printf 'l1\nl2\nl3\nl4 de B\nl5\nl6\nl7\nl8\n')"
  fin "$1" a
  local distant; distant=$(git --git-dir="$S/distant.git" rev-parse main)
  fin "$1" b
  S3_CODE=$(code); S3_ERR=$(tr '\n' ' ' < "$S/err" | cut -c1-160)
  [ "$S3_CODE" = 2 ] && grep -q "commun.md" "$S/err" \
    && grep -q "l4 de B" "$S/b/brain/workspace/commun.md" \
    && git -C "$S/b/brain" log -1 --format=%s | grep -q "Mémoire" \
    && [ "$(git --git-dir="$S/distant.git" rev-parse main)" = "$distant" ] \
    && [ -z "$(git -C "$S/b/brain" status --porcelain)" ]
}

echo "— le programme jugé"
s1 "$B" && ok "1. ce qu'écrit A est lu par B à son démarrage suivant" || ko "1. B ne lit pas ce qu'A a écrit"
grep -q "intégré" "$S/out" && ok "   et le briefing de B le dit" || ko "   le briefing de B ne dit rien de l'intégration"
[ "$(git -C "$S/b" log --oneline | wc -l | tr -d ' ')" = 1 ] && ok "   le dépôt de l'agent n'a pas bougé" \
  || ko "   le dépôt de l'agent a bougé"
s2 "$B" && ok "2. deux séances sur deux fichiers fusionnent seules, et le distant porte les deux" \
  || ko "2. la fusion à deux ne tient pas (code $(code)) : $(tr '\n' ' ' < "$S/err" | cut -c1-120)"
s3 "$B" && ok "3. le même passage s'arrête : renvoi qui nomme le fichier, rien perdu, rien envoyé, arbre propre" \
  || ko "3. le conflit ne s'arrête pas proprement (code $S3_CODE) : $S3_ERR"

# 6. LA COURSE : l'autre envoie entre notre récupération et notre envoi. Un
# faux `git` en tête du chemin fait pousser A juste avant le premier envoi de
# B. Sans ce scénario, un envoi forcé passait le banc : le conflit s'arrête
# AVANT l'envoi, et aucun autre scénario n'envoie sur un distant qui a bougé
# (sabotage du 09/10). Un crochet d'avant-envoi ne suffit pas : le distant
# compare la référence qu'il a annoncée, et refuse même un envoi forcé.
VRAI_GIT="$(command -v git)"
mkdir -p "$S/course-bin"
cat > "$S/course-bin/git" <<FIN
#!/bin/sh
for x in "\$@"; do
  if [ "\$x" = push ] && [ ! -f "$S/course.fait" ]; then
    : > "$S/course.fait"; "$VRAI_GIT" -C "$S/a/brain" push -q >/dev/null 2>&1
  fi
done
exec "$VRAI_GIT" "\$@"
FIN
chmod 755 "$S/course-bin/git"
s6() {
  monte
  ecris a "workspace/course-a.md" "A"; git -C "$S/a/brain" add -A; git -C "$S/a/brain" commit -q -m "A en course"
  rm -f "$S/course.fait"
  ecris b "workspace/course-b.md" "B"
  PATH="$S/course-bin:$PATH" fin "$1" b
  S6_CODE=$(code)
  [ -f "$S/course.fait" ] && git --git-dir="$S/distant.git" show main:workspace/course-a.md >/dev/null 2>&1 \
    && [ "$S6_CODE" = 0 ]
}
s6 "$B" && ok "6. course : l'envoi de l'autre arrivé entre-temps est gardé, et le tour finit" \
  || ko "6. course : l'envoi de l'autre est perdu ou le tour bloque (code $S6_CODE)"
fin "$B" b
git --git-dir="$S/distant.git" show main:workspace/course-b.md >/dev/null 2>&1 \
  && git --git-dir="$S/distant.git" show main:workspace/course-a.md >/dev/null 2>&1 \
  && ok "   au tour suivant, les deux sont sur le distant" || ko "   au tour suivant, il manque un envoi"

# 7. le dépôt de l'agent a du nouveau ailleurs : dit, jamais tiré
monte
git init -q --bare -b main "$S/agent.git"
git -C "$S/a" remote add origin "$S/agent.git"; git -C "$S/a" push -q -u origin main 2>/dev/null
git clone -q "$S/agent.git" "$S/autre" 2>/dev/null
printf 'fiche\n' > "$S/autre/fiche.md"; git -C "$S/autre" add -A
git -C "$S/autre" -c user.name=o -c user.email=o@x commit -q -m fiche; git -C "$S/autre" push -q 2>/dev/null
avant=$(tete "$S/a"); entre "$B" a
grep -q "dépôt de l'agent : 1 enregistrement" "$S/out" && ok "7. le dépôt de l'agent a du nouveau ailleurs : le briefing le dit" \
  || ko "7. le briefing ne dit rien du nouveau sur le dépôt de l'agent"
[ "$(tete "$S/a")" = "$avant" ] && [ ! -f "$S/a/fiche.md" ] && ok "   et rien n'est tiré" || ko "   le dépôt de l'agent a été tiré"

# 4. hors ligne
monte; mv "$S/distant.git" "$S/parti.git"
ecris a "workspace/hors.md" "x"; fin "$B" a
[ "$(code)" = 0 ] && ok "4. hors ligne, le tour finit (code 0)" || ko "4. hors ligne, le tour est bloqué (code $(code))"
message "$B" a
grep -q "pas encore envoyé" "$S/out" && ok "   et le message suivant dit le retard" \
  || ko "   le message suivant ne dit rien du retard : $(cut -c1-160 "$S/out")"
mv "$S/parti.git" "$S/distant.git"; fin "$B" a
git --git-dir="$S/distant.git" show main:workspace/hors.md >/dev/null 2>&1 \
  && ok "   revenu en ligne, l'envoi part tout seul" || ko "   revenu en ligne, rien n'est parti"

# 5. sans le réglage
monte; ecris a "workspace/sans.md" "x"; avant=$(git --git-dir="$S/distant.git" rev-parse main)
fin "$B" a ""; entre "$B" a ""
[ "$(git --git-dir="$S/distant.git" rev-parse main)" = "$avant" ] \
  && ok "5. sans le réglage, rien ne part — même avec un distant" || ko "5. sans le réglage, le distant a bougé"
git -C "$S/a/brain" log -1 --format=%s | grep -q "Mémoire" \
  && ok "   mais le cerveau autonome s'enregistre quand même" || ko "   le cerveau autonome ne s'enregistre pas"

echo "— TÉMOIN : la 0.12.7, sur le même banc"
if [ -z "$ANCIEN" ]; then ko "témoin introuvable"; else
  s1 "$ANCIEN" && ko "1. la 0.12.7 passe aussi — le scénario est aveugle" || ok "1. la 0.12.7 n'y arrive pas : le scénario voit"
  s2 "$ANCIEN" && ko "2. la 0.12.7 passe aussi — le scénario est aveugle" || ok "2. la 0.12.7 n'y arrive pas : le scénario voit"
  s3 "$ANCIEN" && ko "3. la 0.12.7 passe aussi — le scénario est aveugle" || ok "3. la 0.12.7 n'y arrive pas : le scénario voit"
  # La 0.12.7 n'envoie rien : la course n'a pas lieu, et ce que A a poussé
  # lui-même reste. Le témoin de la course est donc le sabotage, pas elle.
fi

echo
if [ "$ecarts" = 0 ]; then echo "ÉCARTS : AUCUN sur 19 garanties"; else echo "$ecarts écart(s)"; fi
exit $([ "$ecarts" = 0 ] && echo 0 || echo 1)
