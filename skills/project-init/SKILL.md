---
name: project-init
description: >
  Remplit la mémoire d'un projet qu'on vient de mettre au harnais : scanne tous
  les fichiers (code, specs, PDF, Word, tableurs), détecte la stack, suggère
  MCPs/CLIs, pose 7 questions, puis pré-remplit les faits (cap, stack,
  architecture, règles) et PROPOSE le CLAUDE.md du projet et les rôles. Seul ou
  en équipe. La structure, elle, se pose par `harnais adopte` (plus de clone du
  starter). Reprenable. `/project-init --verifier` = état, lecture seule.
  Trigger: /project-init ou "initialise ce projet"
---

# project-init — de « À REMPLIR » à une mémoire juste

> **0.19 (16/10/2026).** Ce skill ne pose plus aucune structure : plus de clone du
> starter, plus de `.claude/` copié, plus de hooks locaux (ils doubleraient ceux du
> paquet). La structure vient de **`harnais adopte`** — seul, ou `--equipe` pour une
> équipe « un dossier par agent » (`/agentic-adopte`). Ce skill fait ce qu'aucune
> commande ne peut faire : **lire le projet** et remplir ce qui est « À REMPLIR ».

## Phase 0 — Le harnais est-il posé ?

```bash
harnais resolution          # la forme : brain (seul) · equipe · sans-memoire
```

- **Sans mémoire** → `harnais adopte` (à blanc), puis `--go`. Une équipe :
  demander d'abord Q0 ci-dessous, puis `harnais adopte --equipe A,B --modeles …
  [--code <dépôt>] --go` dans un dossier vide.
- **Forme d'avant** (`.fact/`, `.mind/`, `memoire/`) → `harnais mise-a-niveau`.

Où écrire ensuite :

| | seul | en équipe |
|---|---|---|
| les faits | `brain/fact/` | `fact/` |
| l'état de l'agent | `brain/mind/` | `agents/<nom>/` |
| le daté | `docs/` | `docs/` |

## Reprise

Chaque phase teste d'abord si elle est faite — la vérité vient des fichiers :

| Phase | Faite quand |
|---|---|
| 0 — harnais | `harnais resolution` ne dit plus `sans-memoire` |
| 2 — questions | `docs/decisions.md` porte le bloc `## Initialisation` |
| 3 — faits | plus aucun « À REMPLIR » dans les faits ni dans l'état |
| 3 — consignes | le CLAUDE.md du projet ne porte plus « À REMPLIR » |

`/project-init --verifier` affiche ce tableau, sans rien écrire.

## Phase 1 — Scan

Lis **tout** ce qui décrit le projet ; les fichiers métier passent avant le code.

- **Stack** : `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`,
  `Cargo.toml`, `pom.xml`, `build.gradle`, `dbt_project.yml`, `Dockerfile`,
  `docker-compose.yml`, `.github/workflows/`, `.mcp.json`, `.env.example` (les
  NOMS des variables, jamais de valeur).
- **Métier** : README, specs, cahiers des charges, PRD, business plans — tout
  fichier dont le nom contient `spec`, `brief`, `cahier`, `requirements`,
  `roadmap`, `business`.
- **Binaires** : `.docx` (pandoc, puis python-docx), `.pdf` (pdftotext, puis
  pdfminer ou pymupdf), `.xlsx`/`.csv` (openpyxl, `head`). Si rien n'extrait :
  « `<nom>` non extractible — résume-le-moi en quelques phrases », et attendre.
- **CLIs** : `command -v` (Windows : `where`) pour `git`, `gh`, `vercel`, `eas`,
  `supabase`, `stripe`, `dbt`, `kubectl`, `terraform`, `aws`, `gcloud`, `az`.

Rapport court : stack, services externes, CLIs, MCPs déjà là, et ce que tu as
compris du projet en trois phrases.

## Phase 2 — Questions (7), une par une

**Q0 — Seul ou en équipe ?** *(d'abord : elle décide de la structure)*
Seul par défaut — huit projets sur dix, et moins cher. Une équipe se justifie
quand deux lots ont des **rythmes** différents et des **contextes disjoints**
(infra/fiabilité d'un côté, produit de l'autre), pas parce que le projet est
gros. En équipe : les noms (deux noms qui se slugifient pareil partageraient une
mémoire auto) et un rôle type par agent (`ops`, `po`, `qa`, `nxt` — voir
`/agentic-agents`).

**Q1 — Nom et description** en une phrase : ce que le projet fait, et pour qui.

**Q2 — Rôle de l'agent** : CTO/Tech Lead, Data Engineer, Data Scientist,
développeur senior, assistant technique, autre.

**Q3 — Type** (seulement les options cohérentes avec le scan) : web, mobile,
fullstack, API, SaaS multi-tenant, pipeline, ML, entrepôt de données, script.

**Q4 — Domaines actifs** : frontend · backend · mobile · base de données ·
authentification · paiements · pipeline · SQL · Python/ML · orchestration · API.

**Q5 — Outils** : « J'ai détecté X, Y, Z. Complet ? » Suggérer le MCP d'un
service détecté qui n'est pas dans `.mcp.json` (base de données, paiements, gestion de projet,
GitHub, Slack, Linear…). `.mcp.json` porte des accès : jamais sur GitHub.

**Q6 — Contraintes** : multi-tenant · RBAC · RGPD · SOC2 · budget · on-premise ·
Production à fermer (quelle branche, quel agent) · autre.

Consigner les sept réponses dans `docs/decisions.md` sous `## Initialisation`
(daté) : une reprise ne les redemande pas.

## Phase 3 — Remplir

**Les faits** (commit avec ` # fact-ok` : ils s'écrivent à la demande de
l'humain, et c'est lui qui vient de répondre) :
- `base.md` : le `cap:` (ce que le projet doit produire — son but, pas son
  domaine), sa nature, le prochain jalon, ce qu'il n'est pas.
- `stack.md` : outils et versions ; les accès = OÙ trouver les identifiants,
  jamais leur valeur.
- `architecture.md` : les grandes pièces et leurs frontières.
- `rules.md` : ce qu'on ne franchit pas, et ce que chaque règle protège. Si Q6
  ferme la Production, son en-tête porte `production:` / `production-agent:`
  (le garde du paquet le lit).
- `workflow.md` : les gestes qu'on ne redécouvre pas (commandes, ordre, pièges).
- en équipe, `roles.md` : qui tient quoi, et surtout les zones partagées.

**L'état** : `state.md` (en-tête `maj` / `sante` / `jalon` — un en-tête cassé
fait sortir le projet du tableau de bord sans un mot) et `todo.md`.

**Les consignes — proposées, pas écrites.** Le CLAUDE.md du projet (étage 3) et
les rôles d'agents (étage 4) ne se modifient que par le CTO : le paquet refuse
les autres. Rédiger le texte proposé (rôle Q2, règles retenues ci-dessous), le
déposer dans `docs/` et l'adresser au CTO dans `todo.md`.

Règles à proposer, seulement si elles s'appliquent :

| Règle | Si |
|---|---|
| Git : commit libre ; envoi sur les branches de travail si les contrôles passent ; la Production sur demande explicite | projet versionné |
| TypeScript strict | TypeScript |
| Python typé (mypy/pyright), logs structurés | Python |
| Pipelines idempotents | pipeline (Q4) |
| RLS / RBAC côté serveur | multi-tenant ou RBAC (Q6) |
| Clés restreintes en Production | paiements (Q4) |

`operations.md` (privé) : seulement OÙ vivent secrets et hébergement, sans
valeur ; jamais ouvert, cité, résumé ni publié ensuite.

## Fin

1. Ce qui a été rempli, ce qui reste « À REMPLIR », ce qui attend le CTO.
2. Le MCP ou le CLI à installer, avec sa commande.
3. La preuve : ouvrir une session dans le dossier de lancement (en équipe,
   `agents/<nom>/`) et voir le briefing servir le cap qu'on vient d'écrire.

## Règles

- Ne jamais écraser un fichier qui ne porte plus « À REMPLIR ».
- Ne jamais écrire une valeur de secret, ni ce qui identifie quelqu'un, dans un
  fichier suivi par git.
- Le site de doc est une proposition (`/publish-docs`), jamais un préalable.
