#!/bin/bash
# LE MÉNAGE EN RUST RELU CONTRE LE TÉMOIN FIGÉ DU PYTHON.
#
#     bash controles/menage.sh [binaire]
#
# Le témoin (`temoins/menage/`) a été produit par `agentic-clean.py` le
# 11/09/2026, AVANT son retrait — voir `provenance.txt`. Le script Python
# n'existe plus : ce témoin est la seule mémoire de ce qu'il rendait.
#
# Quatre régimes : tout l'atelier à blanc, un projet à mémoire, un projet
# sans rien à dire, et un `--apply` dont on compare AUSSI l'arbre restant —
# un ménage qui annonce juste et efface faux passerait sans ce dernier.
# Et un contre-exemple : le même rapport, un octet changé, DOIT différer.
set -u
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(dirname "$ICI")"
B="${1:-${HARNAIS_BIN:-$DEPOT/bin/harnais}}"
T="$ICI/temoins/menage"; C="$(mktemp -d)/corpus"; S="$(mktemp -d)"
ecarts=0
compare() {  # nom attendu produit
  if cmp -s "$2" "$3"; then echo "  ✓ $1"; else echo "  ✗ $1"; diff "$2" "$3" | head -12; ecarts=$((ecarts+1)); fi
}
bash "$ICI/corpus-menage.sh" "$C" > /dev/null
"$B" menage --racine "$C" > "$S/racine.txt" 2>&1
"$B" menage --projet "$C/memoire" > "$S/memoire.txt" 2>&1
"$B" menage --projet "$C/propre" > "$S/propre.txt" 2>&1
"$B" menage --projet "$C/pnpm" --apply > "$S/pnpm-apply.txt" 2>&1
(cd "$C/pnpm" && find . -path ./.git -prune -o -print | sort) > "$S/pnpm-apres.txt"
for f in racine memoire propre pnpm-apply pnpm-apres; do compare "$f" "$T/$f.txt" "$S/$f.txt"; done
# le contre-exemple : un seul caractère de moins doit se voir
sed '1s/.$//' "$S/racine.txt" > "$S/sabote.txt"
if cmp -s "$T/racine.txt" "$S/sabote.txt"; then
  echo "  ✗ contre-exemple : un rapport saboté passe — la comparaison ne voit rien"; ecarts=$((ecarts+1))
else echo "  ✓ contre-exemple : un rapport saboté est vu"; fi
echo "$ecarts écart(s)"
[ "$ecarts" = 0 ]
