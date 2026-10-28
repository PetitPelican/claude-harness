---
name: agentic-agents
description: >
  La forme d'une équipe d'agents. Une équipe NEUVE naît « un dossier par agent »
  (`harnais adopte --equipe A,B,C --modeles ops,po,qa --code DÉPÔT`) ; sur une
  équipe de cette forme, ajoute ou retire un agent en une commande (dossier,
  badge, état, sa copie du code). Rôles types (OPS seul en Production, PO, QA
  guichet des questions, NXT), règles communes d'équipe, garde de la Production
  avec laissez-passer. Une équipe `brain/` d'avant passe à cette forme par
  `harnais demenage`. Dry-run par défaut.
  Trigger: /agentic-agents, « passer ce projet en multi-agents », « ajouter un
  agent », « monter une équipe », « découper ce projet en lots », « ce projet a
  besoin de deux agents ».
---

# agentic-agents — un projet, plusieurs agents

**Un seul skill, deux comportements, et c'est la forme du projet qui décide.**
Sur un projet mono il convertit ; sur un projet déjà multi il ajoute. Les deux
sont la même opération à une étape près.

> **Avant de découper, lire [`references/roles.md`](references/roles.md).** Ce
> skill pose la mécanique ; il ne choisit pas les rôles, et c'est ce choix qui
> décide de tout le reste. On y trouve les trois rôles types et leurs
> frontières, pourquoi découper par couche technique (back/front) est presque
> toujours faux, ce que le modèle **ne** couvre pas, le seuil au-delà duquel un
> agent seul ne suffit plus, et ce que le multi-agents coûte réellement.
>
> Deux points qui se paient longtemps s'ils sont ratés ici : **le nom d'un rôle
> façonne le comportement de l'agent qui le porte**, et **chaque agent ajouté
> augmente ce qui remonte vers l'humain** — qui reste le seul à pouvoir
> débloquer un lot au profit d'un autre.

À ne pas confondre avec son voisin :

| | |
|---|---|
| `agentic-team` | la **vue** de l'atelier — lecture seule, ne modifie rien |
| **`agentic-agents`** | la **forme** du projet — combien d'agents y travaillent |

Et `agents/` à la racine du projet n'est **pas** `.claude/agents/`, qui est la
convention Claude Code pour les définitions de sous-agents. Plusieurs projets
ont déjà le second ; les deux cohabitent sans se gêner, mais ne pas les mélanger
dans une phrase.

## Quand un projet mérite plusieurs agents

Quand deux lots ont des **rythmes** différents et des **contextes disjoints** —
typiquement fiabilité/infra d'un côté, produit/apps de l'autre. Chacun mérite
alors sa santé, son jalon, sa todo. Un seul agent qui alterne entre les deux
garde une fenêtre à moitié hors sujet.

Ce n'est **pas** une réponse à « le projet est gros ». Un projet gros mais d'un
seul tenant se tient très bien à un agent, et la forme mono coûte moins cher.

## La forme « un dossier par agent » (0.18.0, décision du 14/10/2026)

Le dossier du projet **est** la mémoire de l'équipe, avec son propre dépôt ; chaque
agent a UN dossier, qui porte tout ce qui le concerne :

```
<Projet>/                  la mémoire (dépôt git, ignore agents/*/code*/)
  CLAUDE.md                consignes communes
  fact/  shared/  docs/  assets/
  agents/<nom>/            CLAUDE.md (rôle) · .claude/settings.json (droits) · state.md · todo.md
    code/                  SA copie du code (worktree) — une de plus : code-<sujet>/
```

L'agent démarre dans `agents/<nom>/` et enregistre son code par `git -C code commit`
(un `git commit` tapé dans son dossier viserait la mémoire : le harnais le refuse).

| Geste | Commande (à blanc d'abord, `--apply` pour écrire) |
|---|---|
| **monter une équipe neuve** | `harnais adopte --equipe OPS,PO,QA,NXT --modeles ops,po,qa,nxt [--code <dépôt du code>]`, dans un dossier vide — la forme ci-dessus d'un coup ; rôles types, règles communes d'équipe dans le CLAUDE.md du projet, Production fermée (voir plus bas) |
| ajouter un agent | `harnais equipe --agents NOM` — dossier, badge (paquet, périmètre type DEV : lit tout, agit sans demander ; QA : code fermé), état, copie du code ; une ligne `deny` ajoutée chez chacun des autres |
| retirer un agent | `harnais equipe --retire NOM` — refuse s'il reste du travail non enregistré dans ses copies |
| passer une équipe `brain/` à cette forme | `harnais demenage <projet>` — agents arrêtés, synchronisation coupée, puis `--apply --agents-arretes` |

### Le garde de la Production (0.19)

Rien ne part en Production sans le oui de l'humain AU MOMENT du geste. Le paquet
refuse `git push` vers une branche de production (toutes formes : `HEAD:main`,
`+main`, motifs, `--all`, push nu depuis la branche), `gh pr merge` et l'API
GitHub en écriture, sauf à l'agent nommé, muni d'un laissez-passer daté :

```
harnais laissez-passer "l'humain : « oui, mets en ligne »"     # seul l'agent nommé l'obtient
```

Il vaut `production-duree` minutes ; chaque dépôt et chaque usage sont
journalisés dans le dossier de données du paquet. Rien n'est fermé sans réglage :
l'en-tête des règles du projet (`fact/rules.md`, ou `brain/fact/rules.md` seul) —

```
---
production: main, master, production
production-agent: OPS
production-duree: 15
---
```

Une équipe avec un agent de type `ops` naît fermée ainsi. C'est un fait : il
ne s'assouplit qu'à la demande de l'humain (` # fact-ok`). Les gardes propres à
un produit (base de données, paiements, magasins) restent dans le projet.

Ce qui ne se fait pas : poser une copie du code hors de `agents/<nom>/` — le harnais
refuse `git worktree add` ailleurs (` # copie-ok` si l'humain l'a demandé), et la page
d'équipe signale toute copie hors des agents.

## Convertir un projet d'AVANT (forme `brain/`)

- **Une équipe `brain/` dont la mémoire a son propre dépôt** (une équipe d'avant le
  14/10) : `harnais demenage <projet>` la porte à « un dossier par agent ».
- **Un projet seul qui passe à plusieurs** : pas encore en une commande
  (`demenage` refuse une mémoire logée dans le dépôt du code — mesuré le
  16/10/2026). Le chemin sûr : monter l'équipe neuve à côté, `harnais adopte
  --equipe … --code <dépôt du projet>`, puis y reporter à la main les faits, les
  `docs/` et l'état de l'agent d'avant ; agents arrêtés.
- `harnais equipe` sur un projet seul fait encore la conversion d'avant, dans
  la forme `brain/` (ci-dessous) — elle n'est gardée que pour les projets
  qui y sont déjà. Ce qu'elle fait :

```
brain/mind/{state,todo}.md  ->  brain/mind/<premier>/       l'agent qui était là garde sa mémoire
.claude/settings.json       ->  agents/<premier>/.claude/   le PAQUET déclaré, pas de hooks
~/.claude/projects/<slug>/  ->  copié vers le slug du dossier d'agent
agents/<autres>/            ->  créés, avec rôle et réglages ; leur état neuf dans brain/mind/<nom>/
brain/fact/roles.md         ->  qui tient quoi, et les zones partagées
brain/workspace/            ->  le carnet d'équipe, AMORCÉ
```

Dans l'organisation d'avant, la même opération range l'état dans
`agents/<nom>/.mind/`, `roles.md` dans `.fact/` et le carnet dans `equipe/`.

**Ce que le paquet supprime, et c'était l'étape la plus fragile.** Avant, chaque
agent recevait une copie des déclarations de hooks, dont chaque chemin devait
être repointé vers la source commune deux crans plus haut. **Cette étape
n'existe plus** : les hooks viennent du paquet, par un chemin absolu que l'outil
fournit lui-même. Plus de chemin relatif, plus de lien symbolique, et plus la
panne muette d'un clone Windows qui transforme le lien en fichier texte. Il ne
reste à écrire que deux faits : **quel paquet**, et **ce que cet agent n'a pas
le droit de toucher**.

Les déclarations de hooks présentes sont **retirées** au passage. Deux jeux sur
le même événement, ce sont deux briefings et deux poussées vers le téléphone, et
personne ne verrait lequel a parlé.

**Le carnet d'équipe est amorcé ici, et nulle part ailleurs.** Mesuré le
10/09/2026 : il était LU partout — entrées, chiffres de confiance, résumé servi
au briefing — et CRÉÉ nulle part. Il n'existait que chez le seul projet où il
avait été monté à la main ; un projet neuf passé en multi-agents avait donc un
dispositif muet sans que rien ne l'explique. Ce n'est délibérément pas un hook
qui le crée : un projet mono n'a pas d'équipe, et lui fabriquer un carnet vide à
chaque tour donnerait un dispositif qui a l'air monté sans que personne l'ait
décidé.

Les faits, `docs/`, `.logs/`, le code : **rien ne bouge** — seul `roles.md`
s'ajoute aux faits (`workflow.md`, commun à tous les agents, reste à écrire s'il
manque : le briefing de chaque agent l'annonce ABSENT, ou À RENSEIGNER s'il est
vide). Aucun n'appartient à un agent.

Le `settings.json` de la racine est **supprimé**. Il ne s'exécute plus — les
réglages ne s'héritent pas, seul celui du dossier de lancement compte — et le
laisser produirait un fichier que quelqu'un éditera un jour en croyant agir sur
tous les agents. Depuis le paquet, la racine ne garde **rien** : il n'y a plus
de source commune à héberger.

## Le piège qu'il existe pour éviter

**La mémoire auto est classée par CHEMIN.** Convertir déplace le `cwd` de
l'agent de `<projet>/` vers `<projet>/agents/<nom>/`, donc change son slug :
adresse neuve et vide, `--resume` qui ne retrouve rien. Au 04/09/2026 ça
représentait 428 Mo et 20 fils pour <projet>, 58 Mo et 31 mémoires pour <cto>. Le
script migre, ou il refuse.

Il refuse aussi deux noms qui se **slugifient pareil** (`<projet> OPS` et
`<projet>-OPS`) : ils partageraient une seule mémoire auto, en silence, et c'est
irrattrapable une fois installé.

Et il refuse si le projet porte encore des hooks locaux d'avant le 04/09/2026 :
leur `briefing`, à une seule remontée, ne verrait jamais les faits depuis un
dossier d'agent. Les retirer et déclarer le paquet d'abord (`harnais adopte
--go`). Sous le paquet la question ne se pose plus — c'est le paquet qui porte
la version — mais un projet peut encore arriver avec ses anciens hooks à la
main, et ce sont eux qui sont testés.

## Marche à suivre

```bash
# 1. le projet doit déjà avoir ses faits (brain/fact/ ou .fact/) — sinon :
harnais adopte --go

# 2. à blanc, toujours — le premier nommé hérite de l'état existant
harnais equipe --project-root . --agents "OPS,PO"

# 3. appliquer
harnais equipe --project-root . --agents "OPS,PO" --apply
```

Le programme est celui du paquet, le même sur Mac et sur Windows — le
briefing d'un projet en donne le chemin exact. Depuis le 12/10/2026 c'est du
Python (3.9 au moins), lancé par `bin/harnais` ; l'ancien script qui échouait en
silence sur un Windows sans interpréteur avait laissé place à un binaire Rust
(11/09/2026), puis le programme est revenu en Python. La différence avec le script
d'avant : le lanceur, lui, **dit** quand il ne trouve pas de Python au lieu de se
taire.

## Les choses qui restent à la main

1. **Découper le `CLAUDE.md`** — la seule étape qui ne s'automatise pas. Le
   commun reste en haut, le rôle descend. Contrôle de sortie : **aucune phrase
   du bas ne resterait vraie pour un autre agent**. Le `CLAUDE.md` du projet est
   chargé à chaque démarrage de chaque agent : une phrase répétée est payée deux
   fois par session.
2. **Écrire les périmètres en dossiers** dans chaque `settings.json`. Le script
   ne pose que les frontières entre dossiers d'agents ; qui tient quel dossier
   de code est une décision. Trois faits mesurés le 04/09/2026, à ne pas
   redécouvrir : seules les règles `Edit(...)` sont évaluées (`Write(...)` est
   inerte) ; un motif **relatif** (`Edit(../autre/**)`) **ne mord pas** ; un
   motif ancré sur le home mord, y compris en `bypassPermissions`.
3. **Inscrire le paquet dans chaque dossier d'agent.** Le script le déclare ;
   depuis Claude Code 2.1.268, un dossier qui le déclare sans y être inscrit ne
   le charge pas, sans un mot. Dans chaque `agents/<nom>/` : `claude plugin
   install harnais@atelier --scope project`. Témoin : démarrer un agent et
   regarder si son **briefing d'entrée** arrive ; `harnais equipe-vue --projet
   <nom>` dit, agent par agent, déclaré · inscrit · servi.
4. **Déclarer le profil de chaque agent qui n'est pas un développeur.** Le
   défaut est le profil développeur. Un agent expert (juriste, comptable, CTO) reçoit
   `HARNAIS_PROFIL=expert` dans la clé `env` de SES réglages
   (`agents/<nom>/.claude/settings.json`) : les réglages ne s'héritent pas, le
   profil se pose donc agent par agent. C'est un jugement à demander à l'humain.
5. **Relancer les sessions tmux dans les dossiers d'agents**, sous des noms
   slugifiés. L'ancienne session à la racine n'a plus d'agent — le briefing
   l'avertira au lieu de se taire, mais elle ne sert plus à rien.
