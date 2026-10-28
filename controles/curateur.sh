#!/bin/bash
# LE CURATEUR DU PAQUET RELU CONTRE LE TÉMOIN FIGÉ DE L'OUTIL DU POSTE.
#
#     bash controles/curateur.sh                     # juge harnais curateur
#     bash controles/curateur.sh --figer <cmd...>    # fige le témoin
#
# Le curateur vivait dans le binaire des outils du poste (`claude-memoire`),
# donc sur ce Mac seulement. Il entre dans le paquet le 11/09/2026, décidé par
# le commanditaire, pour exister aussi sur le PC. Le témoin (`temoins/curateur/`) a été
# produit par l'outil du poste AVANT le déplacement — voir `provenance.txt`.
#
# LE CORPUS EST DATÉ PAR RAPPORT À AUJOURD'HUI. Ses dates d'usage sont écrites
# au 10/09/2026 ; on les décale d'autant de jours qu'il s'en est écoulé, sinon
# une note « servie hier » deviendrait dormante dans un mois et le témoin
# rougirait sans que rien n'ait changé.
#
# Cinq régimes : le rapport sous ses deux formes d'option, l'épingle, le geste
# qui déplace (dont on compare AUSSI l'arbre restant), et un projet inconnu.
# Et un contre-exemple : le même rapport, un octet changé, DOIT différer.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
T="$ICI/temoins/curateur"; CORPUS="$DEPOT/atelier/controles/corpus-memoire"
FIGER=0
if [ "${1:-}" = "--figer" ]; then FIGER=1; shift; fi
# Comme les autres contrôles : un argument, c'est un PROGRAMME, et on lui
# demande sa sous-commande. Le 11/09, rejoué sur le programme livré avec le
# seul chemin, il rendait « 5 écarts sur 5 » : c'était l'instrument, pas le
# programme. Seul `--figer` prend une commande complète.
if [ "$FIGER" = 1 ]; then CMD=("$@")
else CMD=("${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}" curateur); fi
[ -d "$CORPUS" ] || { echo "corpus introuvable : $CORPUS"; exit 1; }

ref=$(date -j -f '%Y-%m-%d %H' '2026-09-10 12' +%s)
now=$(date -j -f '%Y-%m-%d %H' "$(date +%Y-%m-%d) 12" +%s)
decal=$(( (now - ref) / 86400 ))

prepare() {  # dossier → une copie du corpus, datée par rapport à aujourd'hui
  mkdir -p "$1"; cp -R "$CORPUS/" "$1/"
  local u="$1/-projet-essai/memory/.usage.json" d n
  for d in $(grep -o '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "$u" | sort -u); do
    n=$(date -j -v+"${decal}"d -f '%Y-%m-%d' "$d" +%Y-%m-%d)
    sed -i '' "s/\"$d\"/\"@$n\"/g" "$u"
  done
  sed -i '' 's/"@/"/g' "$u"
}
joue() {  # dossier args... → la sortie
  local d="$1"; shift
  CLAUDE_MEMOIRE_RACINE="$d" "${CMD[@]}" "$@" 2>&1
}
etat() {  # dossier → l'arbre et les fichiers qui restent
  local m="$1/-projet-essai/memory"
  (cd "$m" && find . -type f | sort)
  echo "── MEMORY.md"; cat "$m/MEMORY.md"
  echo "── .usage.json"; cat "$m/.usage.json"
}

S="$(mktemp -d)"
for r in egal espace epingle appliquer; do prepare "$S/$r"; done
joue "$S/egal" --du=-projet-essai            > "$S/rapport-egal.txt"
joue "$S/espace" --du -projet-essai          > "$S/rapport-espace.txt"
joue "$S/epingle" --du=-projet-essai --epingle a-archiver > "$S/epingle.txt"
etat "$S/epingle"                           >> "$S/epingle.txt"
joue "$S/appliquer" --du=-projet-essai --appliquer > "$S/appliquer.txt"
etat "$S/appliquer"                         >> "$S/appliquer.txt"
joue "$S/egal" --du=-inconnu                 > "$S/inconnu.txt"
# Le décalage du jour ne doit pas entrer dans le témoin : on remet les dates
# du corpus d'origine avant de figer ou de comparer.
for f in epingle appliquer; do
  for d in $(grep -o '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "$S/$f.txt" | sort -u); do
    o=$(date -j -v-"${decal}"d -f '%Y-%m-%d' "$d" +%Y-%m-%d)
    sed -i '' "s/$d/@$o/g" "$S/$f.txt"
  done
  sed -i '' 's/@\(20[0-9][0-9]-\)/\1/g' "$S/$f.txt"
done

REGIMES="rapport-egal rapport-espace epingle appliquer inconnu"
if [ "$FIGER" = 1 ]; then
  # UN TÉMOIN QUI N'EXERCE RIEN NE SE FIGE PAS : le rapport doit traverser
  # toutes ses bandes, sinon on garderait une page presque vide.
  for attendu in "à archiver" "à endormir" "démenties" "doublons probables"; do
    grep -q "$attendu" "$S/rapport-egal.txt" || { echo "refus de figer : le corpus n'exerce pas « $attendu »"; exit 1; }
  done
  grep -q "archive/a-archiver.md" "$S/appliquer.txt" || { echo "refus de figer : --appliquer n'a rien déplacé"; exit 1; }
  mkdir -p "$T"
  for f in $REGIMES; do cp "$S/$f.txt" "$T/$f.txt"; done
  {
    echo "figé le $(date '+%d/%m/%Y %H:%M') par : $(basename "${CMD[0]}") ${CMD[*]:1}"
    echo "binaire : $(shasum -a 256 "$(command -v "${CMD[0]}" || echo "${CMD[0]}")" | cut -c1-16)"
    echo "dépôt : $(git -C "$DEPOT" rev-parse --short HEAD)"
    echo "corpus : atelier/controles/corpus-memoire, dates décalées de $decal j puis remises"
  } > "$T/provenance.txt"
  echo "témoin figé : $REGIMES"; exit 0
fi

# ── LE SEUL CHANGEMENT DÉCLARÉ DEPUIS LE GEL : les trois natures (11/09/2026)
#
# Ce témoin a été figé par l'outil du poste AVANT que le curateur n'entre dans
# le paquet : c'est ce qui en fait une référence indépendante du programme
# qu'il juge. Le refiger sur ce programme la rendrait circulaire. On garde
# donc le témoin tel quel et on lui applique le changement décidé — énoncé
# ICI, sans une ligne du programme — avant de comparer :
#   · une ligne « natures » après le compte des notes, PRÉDITE depuis le
#     corpus : une note « supposé » est une croyance, les autres des faits ;
#   · l'explication des seuils, qui range la supposition sur l'axe de la nature ;
#   · la marque d'une supposition, qui dit sa nature.
# LE CLASSEMENT N'EST PAS TOUCHÉ par cet oracle. S'il bougeait, ce serait un
# écart, et c'est voulu : la nature ne devait rien changer à ce corpus.
attendu() {  # témoin → ce que le programme doit rendre depuis le 11/09/2026
  python3 - "$1" "$2" "$CORPUS/-projet-essai/memory" <<'PY'
import sys, re, pathlib
src, dst, mem = sys.argv[1:4]
t = pathlib.Path(src).read_text(encoding="utf-8")
notes = [p for p in pathlib.Path(mem).glob("*.md") if p.stem.upper() != "MEMORY"]
niv = re.compile(r"(?m)^> \*\*(mesuré|observé|supposé|dit)\*\* · (\d\d/\d\d)/\d{4}")
debut = lambda p: p.read_text(encoding="utf-8")[:900]
sup = sum(1 for p in notes if (m := niv.search(debut(p))) and m.group(1) == "supposé")
if any(re.search(r"(?m)^\s*nature\s*:", debut(p)) for p in notes):
    sys.exit("l'oracle ne sait pas prédire une nature DÉCLARÉE : le corpus en porte une — l'étendre")
D, Z = "\x1b[2m", "\x1b[0m"
avant = (f"  {D}par note : × niveau (supposé 0,5 · observé 0,7 · mesuré 1 · dit 1,5){Z}\n"
         f"  {D}× (1 + log(lectures)) × 2 si un résultat l'a déjà éprouvée{Z}\n")
apres = (f"  {D}par note : × nature (croyance 0,5 · fait 1 · expérience 1,5 — une supposition est une croyance){Z}\n"
         f"  {D}× niveau (observé 0,7 · mesuré 1 · dit 1,5) × (1 + log(lectures)) × 2 si un résultat l'a déjà éprouvée{Z}\n")
t = t.replace(avant, apres)
if "natures :" not in t:
    t = re.sub(r"(?m)^(  \d+ notes · mesure d'usage en place depuis \d+ j\n)",
               lambda m: m.group(1) + f"  natures : {len(notes) - sup} fait · {sup} croyance · "
                         f"0 expérience {D}— 0 déclarée(s) par la note{Z}\n", t)
t = t.replace("[supposé]", "[supposé · croyance]")
pathlib.Path(dst).write_text(t, encoding="utf-8")
PY
}

ecarts=0
for f in $REGIMES; do
  attendu "$T/$f.txt" "$S/attendu-$f.txt" || exit 1
  if cmp -s "$S/attendu-$f.txt" "$S/$f.txt"; then echo "  ✓ $f"
  else echo "  ✗ $f"; diff "$S/attendu-$f.txt" "$S/$f.txt" | head -12; ecarts=$((ecarts+1)); fi
done
# L'ORACLE PORTE SON TÉMOIN DE PÉREMPTION : s'il ne change plus rien au rapport
# figé, le témoin a été refigé depuis le 11/09 et ce bloc est mort — un bloc
# mort qui passe se lit comme une vérification.
if cmp -s "$T/rapport-egal.txt" "$S/attendu-rapport-egal.txt"; then
  echo "  ✗ l'oracle des natures ne change plus rien au témoin : il a été refigé — retirer ce bloc"
  ecarts=$((ecarts+1))
fi
sed '3s/.$//' "$S/rapport-egal.txt" > "$S/sabote.txt"
if cmp -s "$S/attendu-rapport-egal.txt" "$S/sabote.txt"; then
  echo "  ✗ contre-exemple : un rapport saboté passe — la comparaison ne voit rien"; ecarts=$((ecarts+1))
else echo "  ✓ contre-exemple : un rapport saboté est vu"; fi
echo "témoin : $ecarts écart(s) sur 5 régimes"
[ "$ecarts" = 0 ]
