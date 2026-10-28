#!/bin/bash
# LA DOCUMENTATION SOUS GARDE — ce qu'elle fait taper doit exister, et ce
# qu'elle décrit doit être l'organisation d'aujourd'hui.
#
#     bash controles/doc-code.sh [binaire]
#
# Quatorze gardes surveillent le todo, les faits, le carnet, les constats ; rien
# ne surveillait les fichiers qui expliquent le système (audit du 11/09/2026).
# Le même jour, en vérifiant l'audit : `harnais menage`, `harnais adopte`…
# cités par six fiches et huit messages des hooks, ne s'ouvraient chez aucun
# agent. Trois questions, chacune mesurable sans rien interpréter :
#
#   1. chaque `harnais <mot>` cité est une sous-commande que le programme
#      annonce dans son aide ;
#   2. aucune fiche livrée ne porte encore le bandeau « organisation d'avant » ;
#   3. le nombre de contrôles annoncé par le mode d'emploi est celui du lanceur.
#
# ET TROIS DE PLUS, le 11/09/2026 au soir. Le CTO du PC Windows a trouvé ce que
# ces trois-là laissaient passer : le mode d'emploi, le document d'explication
# et le fichier de méthode qu'une installation recopie ne nommaient JAMAIS
# `brain/`, des fiches renvoyaient à `/agentic-upgrade` et `/agentic-sync`,
# supprimées, et à un script retiré. La question 1 ne regardait que les
# `harnais <mot>` — ni les compétences, ni les chemins, ni l'organisation :
#
#   4. chaque compétence citée (`/nom`) est un dossier de `skills/` — ou une
#      commande de Claude Code lui-même ;
#   5. chaque chemin du dépôt cité (`skills/…`, `controles/…`, `bin/…`) existe ;
#   6. aucune fiche ne nomme l'organisation d'avant plus souvent que l'actuelle,
#      et les quatre textes d'entrée nomment `brain/`.
#
# ET UNE SEPTIÈME, le 26/09/2026. La garde B13 tournait chez tous les agents
# depuis deux jours, et le document d'explication annonçait toujours « douze
# gardes », sans elle, pendant que le banc affichait « 12/12 » — un douze qui
# n'était pas le même (il laisse de côté les deux gardes sans banc) :
#
#   7. chaque « N gardes » annoncé par une fiche est le nombre de gardes du
#      code, et le tableau du document d'explication les nomme toutes.
#
# Et deux contre-exemples : une fiche fabriquée qui porte chaque défaut doit
# mordre partout — sinon ce contrôle est aveugle et le dit ; une fiche saine ne
# doit mordre nulle part — sinon il refuse tout.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
B="${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}"
ecarts=0
ko() { echo "  ✗ $1"; ecarts=$((ecarts+1)); }

# Ce que le programme annonce : les lignes de l'aide qui ouvrent sur un nom.
CONNUES=" $("$B" aide | sed -n 's/^  \([a-z][a-z-]*\) .*/\1/p' | tr '\n' ' ')version "
case "$CONNUES" in *" adopte "*" curateur "*) ;; *)
  echo "  ✗ l'aide du programme ne se lit plus — ce contrôle serait aveugle"; exit 1 ;; esac

# Les sous-commandes citées : `harnais x` partout ; `harnais x` en tête de
# ligne DANS un bloc de code seulement — en prose, « harnais qui… » est un mot.
cites() {
  awk '/^[ \t]*```/ { f = !f; next }
       { l = $0
         while (match(l, /`harnais [a-z][a-z-]*/)) {
           print substr(l, RSTART + 9, RLENGTH - 9); l = substr(l, RSTART + RLENGTH) }
         if (f && match($0, /^[ \t]*harnais [a-z][a-z-]*/)) {
           s = substr($0, RSTART, RLENGTH); sub(/^[ \t]*harnais /, "", s); print s } }' "$1"
}
inconnues() {  # fichier → les citations qui ne s'ouvrent pas
  cites "$1" | sort -u | while read -r m; do
    case "$CONNUES" in *" $m "*) ;; *) echo "$m" ;; esac
  done
}

# 4. Une compétence se cite entre accents graves, suivie d'un accent ou d'un
#    argument : `/tmp/x` est un chemin, pas une compétence.
NATIVES=" loop compact clear resume plugin config help model memory agents hooks permissions status init "
competences_mortes() {
  grep -oE '`/[a-z][a-z0-9-]*[` ]' "$1" | sed -E 's/^`\/([a-z0-9-]+).$/\1/' | sort -u | while read -r s; do
    [ -f "$DEPOT/skills/$s/SKILL.md" ] && continue
    case "$NATIVES" in *" $s "*) ;; *) echo "/$s" ;; esac
  done
}
# 5. Les chemins du dépôt. `.claude/skills/x` est la copie qu'une installation
#    posait dans le projet : elle se lit `skills/x`. Un gabarit (`<plateforme>`,
#    `*`) n'est pas un chemin.
chemins_morts() {
  grep -oE '(^|[` (])(\.claude/skills|skills|controles|hooks|bin|py|rappels|\.claude-plugin)/[A-Za-z0-9._/<>*-]+' "$1" \
    | sed -E 's/^[` (]//' | grep -v '[<>*]' | sort -u | while read -r p; do
      q="${p/#.claude\/skills/skills}"; q="${q%/}"
      [ -e "$DEPOT/$q" ] || echo "$p"
    done
}
# 6. Une fiche qui nomme l'organisation d'avant plus souvent que l'actuelle la
#    présente comme actuelle. Compté en lignes : un paragraphe de migration
#    peut citer l'ancienne, pas s'y installer.
avant_actuelle() {
  local a c; a=$(grep -cE '\.(fact|mind)/' "$1"); c=$(grep -c 'brain/' "$1")
  [ "$a" -gt "$c" ] && echo "$a ligne(s) sur l'organisation d'avant, $c sur brain/"
}

DOCS=("$DEPOT"/README.md "$DEPOT"/COMMENT-CA-MARCHE.md "$ICI"/LISEZMOI.md \
      "$DEPOT"/skills/*/SKILL.md "$DEPOT"/skills/*/templates/*.md "$DEPOT"/skills/*/references/*.md)

# 1. Les citations
n=0
for f in "${DOCS[@]}" "$DEPOT"/py/*.py; do
  [ -f "$f" ] || continue
  n=$((n + $(cites "$f" | wc -l)))
  for m in $(inconnues "$f"); do ko "${f#$DEPOT/} cite « harnais $m », que le programme n'a pas"; done
done
[ "$n" -gt 20 ] || ko "seulement $n citation(s) trouvée(s) — le relevé est aveugle"

# 2. Les bandeaux
for f in $(grep -l "ORGANISATION D.AVANT" "$DEPOT"/skills/*/SKILL.md 2>/dev/null); do
  ko "${f#$DEPOT/} décrit encore l'organisation d'avant"
done

# 3. Le compte du mode d'emploi
annonce=$(sed -n "s/^\([0-9][0-9]*\) contrôles, lancés d.un seul geste.*/\1/p" "$ICI/LISEZMOI.md")
reel=$(grep -cE '\("[^"]+", +"[^"]+\.(py|sh)"\)' "$ICI/tous-les-controles.py")
[ -n "$annonce" ] && [ "$annonce" = "$reel" ] || ko "le mode d'emploi annonce « ${annonce:-rien} » contrôles, le lanceur en porte $reel"

# 4 vaut aussi pour le code : un message du programme est une fiche que l'agent
#   lit au moment où il bute. Trouvé le 11/09/2026 : le refus de la conversion
#   en équipe renvoyait encore à une compétence supprimée.
for f in "$DEPOT"/py/*.py; do
  for s in $(competences_mortes "$f"); do ko "${f#$DEPOT/} cite « $s », qu'aucune compétence ne porte"; done
done

# 4, 5, 6 — fiche par fiche
ns=0; np=0
for f in "${DOCS[@]}"; do
  [ -f "$f" ] || continue
  ns=$((ns + $(grep -oE '`/[a-z][a-z0-9-]*[` ]' "$f" | wc -l)))
  np=$((np + $(grep -oE '(^|[` (])(\.claude/skills|skills|controles|hooks|bin|py|rappels|\.claude-plugin)/' "$f" | wc -l)))
  for s in $(competences_mortes "$f"); do ko "${f#$DEPOT/} cite « $s », qu'aucune compétence ne porte"; done
  for p in $(chemins_morts "$f"); do ko "${f#$DEPOT/} cite « $p », qui n'existe pas"; done
  x=$(avant_actuelle "$f"); [ -n "$x" ] && ko "${f#$DEPOT/} présente l'organisation d'avant comme actuelle : $x"
done
[ "$ns" -gt 10 ] || ko "seulement $ns compétence(s) citée(s) — le relevé est aveugle"
[ "$np" -gt 5 ] || ko "seulement $np chemin(s) cité(s) — le relevé est aveugle"
for f in README.md COMMENT-CA-MARCHE.md skills/agentic-init/templates/foundation-CLAUDE.md \
         skills/agentic-init/templates/cto-CLAUDE.md; do
  grep -q 'brain/' "$DEPOT/$f" || ko "$f ne nomme jamais brain/, l'organisation actuelle"
done

# 7. Les gardes de fin de tour. Le code les nomme `"B<n>-<quoi>"` ; une garde
#    peut porter deux noms (B4-demande, B4-cible) : on compte les NUMÉROS.
NOMBRES=(zero un deux trois quatre cinq six sept huit neuf dix onze douze treize \
         quatorze quinze seize dix-sept dix-huit dix-neuf vingt)
GARDES=$(cat "$DEPOT/py/attente.py" "$DEPOT/py/experts.py" | grep -oE '"B[0-9]+-' | tr -dc '0-9\n' | sort -un | tr '\n' ' ')
NG=$(echo $GARDES | wc -w | tr -d ' ')
gardes_mal_comptees() {  # fichier → chaque « N gardes » qui n'est pas NG
  grep -oiE "\b([0-9]+|$(IFS='|'; echo "${NOMBRES[*]:2}")) gardes\b" "$1" | while read -r n _; do
    m=$(echo "$n" | tr 'A-Z' 'a-z')
    for i in "${!NOMBRES[@]}"; do [ "${NOMBRES[$i]}" = "$m" ] && m=$i; done
    [ "$m" = "$NG" ] || echo "« $n gardes »"
  done
}
gardes_absentes() {  # fichier → les numéros du code que son tableau ne nomme pas
  for g in $GARDES; do grep -qE "^\| \*\*B$g\*\* \|" "$1" || echo "B$g"; done
}
[ "$NG" -ge 10 ] || ko "seulement $NG garde(s) relevée(s) dans le code — le relevé est aveugle"
for f in "${DOCS[@]}"; do
  [ -f "$f" ] || continue
  for x in "$(gardes_mal_comptees "$f")"; do [ -n "$x" ] && ko "${f#$DEPOT/} annonce ${x//$'\n'/, } — le code en porte $NG"; done
done
x=$(gardes_absentes "$DEPOT/COMMENT-CA-MARCHE.md" | tr '\n' ' ')
[ -z "$x" ] || ko "COMMENT-CA-MARCHE.md ne décrit pas la ou les gardes : $x"

# Les contre-exemples
T=$(mktemp); printf 'lancer `harnais inexistant` puis :\n```\nharnais fantome --x\n```\nle harnais qui passe\n' > "$T"
[ "$(inconnues "$T" | tr '\n' ' ')" = "fantome inexistant " ] \
  || ko "contre-exemple : une fiche qui cite deux commandes fausses n'est pas vue telle quelle"
printf 'lancer `/agentic-upgrade` puis `/agentic-sync --x`, puis `/agentic-adopte`\n' > "$T"
printf 'python3 skills/agentic-team/scripts/agentic-team.py, ou `bin/harnais-<plateforme>`\n' >> "$T"
printf 'la mémoire est dans `.mind/`\net les faits dans `.fact/`\n' >> "$T"
[ "$(competences_mortes "$T" | tr '\n' ' ')" = "/agentic-sync /agentic-upgrade " ] \
  || ko "contre-exemple : deux compétences supprimées ne sont pas vues telles quelles"
[ "$(chemins_morts "$T")" = "skills/agentic-team/scripts/agentic-team.py" ] \
  || ko "contre-exemple : un script retiré n'est pas vu, ou un gabarit est pris pour un chemin"
[ -n "$(avant_actuelle "$T")" ] || ko "contre-exemple : une fiche toute d'avant passe pour actuelle"
printf 'lancer `/agentic-adopte`, lire `skills/agentic-adopte/SKILL.md`\nla mémoire est dans `brain/mind/`, jadis `.mind/`\n' > "$T"
[ -z "$(competences_mortes "$T")$(chemins_morts "$T")$(avant_actuelle "$T")" ] \
  || ko "contre-exemple : une fiche saine est refusée"
printf 'les %s gardes, puis %s gardes, puis Les %s gardes\n| **B1** | x |\n' \
  "${NOMBRES[$((NG-1))]}" "$((NG+1))" "${NOMBRES[$NG]}" > "$T"
[ "$(gardes_mal_comptees "$T" | tr '\n' ' ')" = "« ${NOMBRES[$((NG-1))]} gardes » « $((NG+1)) gardes » " ] \
  || ko "contre-exemple : deux annonces fausses, en lettres et en chiffres, ne sont pas vues telles quelles"
[ -n "$(gardes_absentes "$T")" ] || ko "contre-exemple : un tableau amputé passe pour complet"
printf "les $NG gardes\n" > "$T"; for g in $GARDES; do printf '| **B%s** | x |\n' "$g" >> "$T"; done
[ -z "$(gardes_mal_comptees "$T")$(gardes_absentes "$T")" ] \
  || ko "contre-exemple : une fiche au bon compte est refusée"
rm -f "$T"

echo "témoin : $n citation(s), $ns compétence(s), $np chemin(s) relevés, $NG gardes, 7 questions, $ecarts écart(s)"
[ "$ecarts" = 0 ]
