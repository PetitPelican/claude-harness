#!/bin/bash
# LE DERNIER PROGRAMME QUI PARLAIT AUX RAPPELS, ressorti de l'histoire du dépôt.
#
#     source controles/ancien-harnais.sh   →   $ANCIEN (chemin d'un exécutable)
#
# Le témoin négatif des contrôles « plus rien vers les Rappels » (08/10/2026).
# Un piège qui ne journalise rien ne prouve rien tant qu'on ne l'a pas vu
# prendre : on lui présente donc la 0.12.6 — macOS, enregistrée au commit
# d3167ea —, qui DOIT s'y faire prendre. Si elle ne s'y prend pas, c'est le
# piège qui est aveugle, et le vert du programme neuf ne vaut rien.
ANCIEN="$(mktemp -t harnais-0.12.6)"
git -C "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" show d3167ea:bin/harnais-darwin-arm64 > "$ANCIEN" \
  && chmod 755 "$ANCIEN" || { echo "témoin introuvable : la 0.12.6 n'a pas pu être ressortie"; ANCIEN=""; }
