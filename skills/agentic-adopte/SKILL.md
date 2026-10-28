---
name: agentic-adopte
description: >
  Pose le harnais sur N'IMPORTE QUEL projet, en un seul geste. Seul : la mémoire
  (`brain/fact/`, `brain/mind/`), le CLAUDE.md du projet, `docs/` et les deux clés
  qui branchent le paquet. En équipe (`--equipe A,B,C [--modeles ops,po,qa]
  [--code DÉPÔT]`) : l'équipe NAÎT « un dossier par agent » — la racine est le
  dépôt de la mémoire, chaque agent a son rôle, ses droits, son état et SA copie
  du code. Purement additif, à blanc par défaut, `--go` pour écrire.
  Trigger: /agentic-adopte, « mettre ce projet au harnais », « adopter ce
  projet », « installer le harnais ici », « démarrer un projet agentique »,
  « monter une équipe ».
---

# agentic-adopte — la porte d'entrée

**Un geste, pas huit.** Avant le 10/09/2026, monter un projet demandait huit
gestes dont deux qu'aucun document ne mentionnait, et rien n'avertissait qu'on
fabriquait le projet dans l'organisation d'avant. Un atelier qui ne se monte que
par quelqu'un qui l'a déjà monté n'est pas un outil, c'est un savoir-faire.

## Le geste

```bash
harnais adopte                     # dit ce qu'il poserait, n'écrit rien
harnais adopte --go                # écrit
# une équipe, dans un dossier VIDE qui deviendra sa mémoire :
harnais adopte --equipe OPS,PO,QA --modeles ops,po,qa --code <dépôt du code> --go
```

Le programme est celui du paquet — le briefing d'un projet sans mémoire en donne
le chemin exact, parce qu'il change à chaque version et qu'un mode d'emploi faux
est pire qu'absent. C'est du Python (3.9 au moins) lancé par `bin/harnais` : sur
un poste sans vrai Python, le lanceur le dit et rien ne se pose (voir le
`README.md` du paquet).

## Ce qu'il pose

**Seul** (dans le dépôt du code) :

| | |
|---|---|
| `brain/fact/` | `base` (le cap), `stack`, `architecture`, `rules`, `workflow`, « À REMPLIR » |
| `brain/mind/` | `state.md`, `todo.md` |
| `CLAUDE.md` | les règles du projet (étage 3), « À REMPLIR » |
| `docs/decisions.md` | le pourquoi de chaque choix, daté |
| `.claude/settings.json` | le marché, et le paquet activé |

**En équipe** (0.19 — dans un dossier vide, qui devient le dépôt de la mémoire) :

```
<projet>/                 dépôt de la MÉMOIRE (.gitignore : agents/*/code*/, secrets)
  CLAUDE.md               règles communes de l'équipe (gabarit type si --modeles)
  fact/                   base, stack, architecture, rules, workflow, roles
  docs/  shared/  assets/ le daté, le carnet d'équipe, les livrables
  agents/<nom>/           CLAUDE.md (rôle) · .claude/settings.json · state.md · todo.md
    code/                 SA copie du code : clone de --code chez le premier,
                          copie git (branche à son nom) chez les autres
```

Chaque badge déclare le paquet, ferme les dossiers des autres agents (`deny`
ancré sur `~/`), interdit la copie isolée de Claude Code (elle copierait la
mémoire, pas le code) et ouvre la racine de l'équipe (`additionalDirectories`).
Il pose le périmètre type d'un agent DEV : `bypassPermissions`, `allow`
`Bash(*)` et `Read(*)` — l'agent lit tout et agit sans demander, il n'écrit que
son lot. Un agent de type `qa` a sa copie du code fermée : il prescrit, il ne
corrige pas. La maison entière n'est pas ouverte en `additionalDirectories` :
mesuré le 27/10/2026, un fichier hors de l'arbre se lit sans elle.
Avec un agent de type `ops`, la Production naît fermée : l'en-tête de
`fact/rules.md` porte `production:` et `production-agent:` (voir le garde de la
Production dans `/agentic-agents`). Il refuse un dossier qui n'est pas vide :
une équipe ne naît pas par-dessus un code.

**Il pose un `workflow.md` de départ**, le fichier des faits commun à tous les
agents (comment procéder : les gestes qu'on ne redécouvre pas), marqué
« À REMPLIR » : tant que la marque y est — ou que le fichier est vide — le briefing
l'annonce **À RENSEIGNER**. Son contenu vient du travail, pas du gabarit : il
s'écrit puis se tient à jour comme les autres faits, à la demande de l'humain
(` # fact-ok`) ; la garde de commit l'accepte sans ` # fact-neuf`. Un fichier
existant n'est jamais écrasé.

## Ce qu'il ne fait pas, et le dit

Écrire le cap, découper un `CLAUDE.md` existant, répartir les périmètres : ce
sont des jugements, ils demandent d'avoir lu le projet. La commande les NOMME en
fin de rapport. **Un script qui décide à la place de l'agent décide sans avoir
lu.**

## Trois garanties, chacune tenue par un essai

- **Purement additif** — un fichier qui existe est annoncé comme déjà là et
  laissé tel quel ; les réglages sont fusionnés clé à clé, donc un projet qui a
  déjà ses permissions les garde.
- **Le blanc n'écrit rien** — après un passage sans `--go`, aucun des fichiers
  annoncés n'existe. Son témoin négatif est l'essai qui exige que `--go` écrive
  vraiment : sans lui, une commande qui n'écrit jamais passerait le premier.
- **Relancer ne change rien** — un outil d'installation qu'on n'ose pas relancer
  n'est pas un outil, c'est un pari.

## Deux profils : développeur par défaut

`adopte` pose la mémoire d'un **développeur**. Un agent qui ne code pas (un juriste,
un comptable) est un **expert** : il se déclare à part, en posant `HARNAIS_PROFIL=expert`
dans la clé `env` des réglages de l'agent (comme `HARNAIS_CANAL`). Ses faits ne
sont alors pas ceux d'un projet : un socle — nature (`base.md`), sources
(`sources.md`), règles (`rules.md`), `workflow.md` — puis des fiches libres au nom
du métier, un registre local ignoré par git pour ce qui identifie quelqu'un, et
une garde de fin de tour qui exige qu'un fait donné par l'humain soit noté. L'adoption
ne choisit pas ce profil à la place de l'agent : c'est un jugement, et il se
demande à l'humain. Le détail est dans `COMMENT-CA-MARCHE.md`, §6 bis.

## Ce qu'il refuse

Un projet **à cheval sur deux organisations de mémoire** : poser des fichiers
dessus, c'est choisir en silence lequel des deux arbres fait foi. Il renvoie
vers `harnais mise-a-niveau`, qui dit quoi trancher avant de terminer.

Un projet dans l'organisation d'avant, ou adopté avant la 0.17.0 (trois faits
manquants) : `harnais mise-a-niveau`, à blanc d'abord.

## Après

Ouvre une session dans le dossier — en équipe, DANS `agents/<nom>/` : le
briefing d'entrée s'affiche. Inscrire le paquet dans chaque dossier de lancement
(`claude plugin install harnais@atelier --scope project`). Ajouter ou retirer un
agent : `harnais equipe --agents NOM` / `--retire NOM` (`/agentic-agents`).
