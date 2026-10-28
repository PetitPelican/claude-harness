#!/bin/bash
# UN ATELIER FABRIQUÉ POUR LE MÉNAGE — chaque dossier sépare un cas.
#
#     bash corpus-menage.sh <dossier>
#
# Écrit en shell, pas en Python : il sert à figer ce que rendait le script
# Python AVANT qu'il parte, puis à juger le Rust qui le remplace. Tailles
# fixes (octets de zéros) : le rapport en Mo doit être le même à chaque
# montage, sinon le témoin clignote.
#
#   pnpm        deux node_modules qui partagent un inode (lien dur) → compté UNE fois
#   pnpm        un .turbo vide                        → ligne « moins de 1 Mo »
#   pnpm        dist/ à côté d'un package.json         → « npm run build »
#   pyinst      dist/ à côté d'un .spec                → « pyinstaller »
#   pyinst      __pycache__                            → commande fixe
#   suivi       node_modules SUIVI par git             → pas supprimé, .gitignore
#   horsgit     build/ hors dépôt                      → nom ambigu, pas supprimé
#   horsgit     .venv hors dépôt                       → supprimable (nom sans ambiguïté)
#   memoire     .fact/ + docs/ : state.md, charter.md, finances.md, rapport.pdf,
#               archive/ (overview.md + note), journal.md de 600 lignes datées,
#               notes.md.bak                           → familles 2 et 3
#   ancien      .memory/ sans .fact/ : rules.md        → la mémoire d'avant
#   cerveau     brain/fact + docs/state.md             → forme actuelle
#   propre      rien à signaler                        → absent du rapport
#   .cache      dossier caché à la racine             → jamais visité en --racine
set -e
R="$1"
[ -n "$R" ] || { echo "usage : corpus-menage.sh <dossier>" >&2; exit 2; }
rm -rf "$R"; mkdir -p "$R"
zero() { mkdir -p "$(dirname "$1")"; head -c "$2" /dev/zero > "$1"; }
depot() { git -C "$1" init -q; git -C "$1" config user.email essai@exemple; git -C "$1" config user.name essai; }
commit() { git -C "$1" add -A >/dev/null; git -C "$1" commit -qm corpus >/dev/null; }

P="$R/pnpm"; mkdir -p "$P"; depot "$P"
printf 'node_modules/\n.turbo/\ndist/\n' > "$P/.gitignore"; printf '{}\n' > "$P/package.json"
zero "$P/node_modules/a/gros.bin" 3145728
mkdir -p "$P/app/node_modules/a"; ln "$P/node_modules/a/gros.bin" "$P/app/node_modules/a/gros.bin"
zero "$P/app/node_modules/b/propre.bin" 2097152
mkdir -p "$P/.turbo"; mkdir -p "$P/app/.turbo"
zero "$P/dist/index.js" 1572864
commit "$P"

Y="$R/pyinst"; mkdir -p "$Y/packaging"; depot "$Y"
printf 'dist/\n__pycache__/\n' > "$Y/.gitignore"; printf '# spec\n' > "$Y/packaging/app.spec"
zero "$Y/packaging/dist/app" 2621440
zero "$Y/src/__pycache__/m.pyc" 1048576
commit "$Y"

S="$R/suivi"; mkdir -p "$S"; depot "$S"
zero "$S/node_modules/x/v.js" 1310720
commit "$S"

H="$R/horsgit"
zero "$H/build/out.o" 1048576
zero "$H/.venv/lib/site.py" 2097152

M="$R/memoire"; mkdir -p "$M/.fact" "$M/docs/archive"; depot "$M"
printf '# état\n' > "$M/docs/state.md"; printf '# charte\n' > "$M/docs/charter.md"
printf '# finances\n' > "$M/docs/finances.md"; zero "$M/docs/rapport.pdf" 2048
printf '# vue\n' > "$M/docs/archive/overview.md"; printf 'note\n' > "$M/docs/archive/note.txt"
{ for i in $(seq 1 600); do
    if [ "$i" = 17 ]; then echo "- 2026-03-04 la plus ancienne"
    elif [ "$i" = 300 ]; then echo "- 12/05/2026 au milieu"
    else echo "ligne $i"; fi
  done; } > "$M/docs/journal.md"
printf 'vieux\n' > "$M/docs/notes.md.bak"
commit "$M"

A="$R/ancien"; mkdir -p "$A/.memory"; printf '# règles\n' > "$A/.memory/rules.md"

C="$R/cerveau"; mkdir -p "$C/brain/fact" "$C/docs"; printf '# état\n' > "$C/docs/state.md"

mkdir -p "$R/propre/src"; printf 'rien\n' > "$R/propre/src/main.txt"
zero "$R/.cache/node_modules/z.bin" 1048576
echo "corpus monté : $R"
