---
name: agentic-team
description: >
  Lit la mémoire et les réglages de tous les projets d'un atelier et en rend
  deux vues : un DIAGNOSTIC en terminal (projet par projet et agent par agent :
  la mémoire, le paquet déclaré, inscrit, servi, et quoi faire) et une PAGE HTML autonome, qui s'ouvre d'un double-clic sur n'importe
  quelle machine, sans serveur. Cette page s'appelle **agentic-team**.
  Strictement en lecture.
  Trigger: /agentic-team, « ouvre la page agentic-team », « agentic team »,
  « /equipe » (ancien nom), « la vue
  d'équipe », « le tableau de l'atelier », « où en sont les projets »,
  « diagnostique ce projet », « qu'est-ce qui m'attend ».
---

# Équipe

> **Deux questions, une seule lecture.** « Dans quel état est ce projet, et que
> faut-il y faire ? » et « où en est toute l'équipe ? » se répondent avec les
> mêmes fichiers : la mémoire de chaque projet et les réglages de chaque agent.
> Un seul analyseur, deux sorties — deux analyseurs finiraient par diverger, et
> personne ne le verrait.

**Strictement en lecture.** Ce skill n'écrit que la page HTML qu'on lui demande.
Il ne touche à aucun projet : il dit ce qu'il faut lancer, il ne le lance pas.

## Les trois usages

```bash
# 1. Diagnostic de tout l'atelier, en terminal
harnais equipe-vue --racine ~/Agentic

# 2. Un seul projet, en détail — « va voir ce projet-là »
harnais equipe-vue --racine ~/Agentic --projet <NomDuProjet>

# 3. La page autonome
harnais equipe-vue --racine ~/Agentic --html ~/agentic-team.html
```

Le programme est celui du paquet, le même sur Mac et sur Windows — le
briefing d'un projet en donne le chemin exact.

**Sa lecture a été refaite le 11/09/2026.** Porté à l'octet du script d'avant,
il ne lisait que l'organisation d'avant et des réglages vides de sens depuis le
paquet : mesuré ce jour-là, 12 projets sur 13 classés « sans mémoire », dont
deux servis sous nos yeux, et des conseils vers deux compétences supprimées. Un
tableau de bord qui désigne presque tout l'atelier comme à refaire apprend à ne
plus le lire.

## La page

**Autonome au sens strict** : aucun serveur, aucun CDN, aucune police distante,
aucun fichier joint. Tout est dans le fichier. Elle s'ouvre d'un double-clic,
hors ligne, sur macOS comme sur Windows — et se copie sur une clé si besoin.

Elle ouvre sur **ce qui attend une décision**, avant les cartes de projet : c'est
la seule colonne qui ne se délègue pas. Puis une carte par projet avec le `cap:`,
la fraîcheur, l'état du harnais et l'avancement des tâches. Thème clair et sombre
selon le réglage de la machine.

Régénérer, c'est relancer la commande : la page est un **relevé daté**, pas un
tableau de bord vivant. Elle porte sa date en tête.

## Ce que le diagnostic lit

- **La mémoire, par la même règle que le briefing** : `brain/`, l'organisation
  d'avant (`.fact/` et `.mind/` en place, ou déportés dans `memoire/`), et les
  projets à cheval entre les deux. À plusieurs agents, l'état de chacun est
  cherché là où il vit — `brain/mind/<nom>/`, ou `agents/<nom>/` dans la forme
  « un dossier par agent » (0.18.0).
- **Ce qui s'éparpille** (forme « un dossier par agent ») : une copie du code hors
  des dossiers d'agents (`git worktree list`), ou un `brain/`, `agents/`, `docs/`
  réapparu dans une copie du code. Verdict `disperse`.
- **Le paquet, dans chaque dossier d'où un agent se lance** : la racine en mono,
  chaque `agents/<nom>/` à plusieurs — les réglages ne s'héritent pas, ceux de
  la racine sont inertes. Trois choses séparées, parce que chacune peut manquer
  seule et en silence : le paquet **déclaré** (les réglages), le dossier
  **inscrit** (sans quoi Claude Code 2.1.268 ne le charge pas), et la **trace
  d'entrée** qui prouve qu'il a servi, avec la version qui l'a écrite — copies
  de travail comprises, car un agent peut se lancer depuis l'une d'elles.

## Les verdicts

Pour chaque projet, dans cet ordre — le premier problème rencontré donne le
verdict, parce que les suivants n'ont pas de sens tant qu'il n'est pas réglé :

| Verdict | Ce qui a été constaté | Ce qu'il faut faire |
|---|---|---|
| `GIT` | pas de dépôt git | `git init` — sans dépôt, aucune mémoire n'est cherchée |
| `NEUF` | aucune mémoire | `harnais adopte`, à blanc puis `--go` |
| `TRI` | taxonomie d'avant le 02/09/2026, ou tout dans `.mind/` | le tri à la main, puis `harnais adopte` ou `harnais mise-a-niveau` |
| `AMBI` | `brain/` et l'organisation d'avant à la fois | `harnais mise-a-niveau` dit quoi trancher |
| `AGT?` | des faits, aucun état d'agent | `harnais adopte --go` en `brain/` |
| `MANQ` | un fichier de la mémoire manque | `harnais adopte --go` en `brain/` ; à la main sinon |
| `BRCH` | rien ne déclare le paquet | `harnais adopte --go` |
| `HOOK` | câblé par des hooks locaux d'avant le paquet | déclarer le paquet, puis retirer les hooks locaux |
| `INSC` | déclaré, pas inscrit : il ne se charge pas | `claude plugin install harnais@atelier --scope project`, dans le dossier |
| `????` | les inscriptions n'ont pas pu être lues | rien n'est conclu — ce n'est pas un « inscrit » |
| `SERV` | aucune trace d'entrée | démarrer l'agent, puis relire |
| `TROP` | un fichier que la mémoire ne prévoit pas | le déplacer vers `docs/` |
| `DENY` | aucune règle `deny` | déclarer ce qui doit être refusé |
| `MAJ` | inscrit dans une version plus vieille que le programme | `claude plugin update harnais@atelier --scope project`, dans le dossier |
| `RETD` | la session tourne sur une version plus vieille que l'inscrite | rien : elle la prendra à son prochain démarrage |
| `V1` | servi, dans l'organisation d'avant | `harnais mise-a-niveau`, quand on le décide |
| `OK` | servi, mémoire complète | rien |

**Chaque commande de ce tableau existe** — un essai du programme relit tous
les conseils et échoue sur une commande ou une compétence absente. C'est le
défaut d'origine : un conseil qui envoie vers une commande morte apprend à ne
plus lire les conseils.

Le `CLAUDE.md` qui nomme (ou non) la mémoire, `@imports` compris, reste affiché
comme une information : depuis le briefing, le harnais sert l'index de la
mémoire à l'entrée, qu'il la nomme ou non.

Il lit aussi l'en-tête de `state.md` (`maj`, `sante`, `jalon`), le `cap:` dans
les faits du projet, et rend trois états de fraîcheur, jamais deux : **à
jour**, **tiède** (plus de 7 jours), **périmé** (plus de 4 semaines) — et
**illisible**, qui est le cas grave : un en-tête cassé fait disparaître le
projet des tableaux de bord sans un mot.

## Formater un projet existant — la marche à suivre

Le diagnostic dit **quoi** faire. Le faire demande deux précautions.

**1. Travailler depuis le dossier du projet.** Le *jugement* — écrire le cap,
trier une mémoire, réconcilier `CLAUDE.md` — demande d'être dans le projet :
c'est là que Claude Code charge son `CLAUDE.md` et ses réglages. Une session
ouverte ailleurs ne les voit pas.

**2. Le tri de mémoire n'est jamais automatique.** Le diagnostic signale une
taxonomie ancienne, il ne la migre pas : trier demande de lire le contenu, et le
contenu appartient au projet.

Puis vérifier, dans cet ordre : le dépôt est un dépôt git · le paquet est
déclaré **et inscrit** dans chaque dossier de lancement · **il sert vraiment**,
ce qui se voit au briefing d'entrée. Relancer `harnais equipe-vue --projet
<nom>` doit alors rendre `OK`.

## Le contrat de lecture

L'analyseur suit **le même contrat que le tableau de bord de la machine**, et
c'est une contrainte, pas un détail : deux analyseurs qui divergent, c'est deux
vérités et aucun signal.

- en-tête `---` … `---` en tête de `state.md`, champs `maj cap sante jalon`
- tâches `- [ ]` `- [>]` `- [~]` `- [x]`, **dans tout le fichier**, toutes
  sections confondues
- marqueurs `!haut` `!moyen` `!bas` et `@<qui>`, dont `@dehors` réservé

> Ne pas se borner à une section « Chantiers ». Les fichiers réels s'organisent
> librement — « Attend une décision », « Outillage », « Technique ». Une version
> antérieure de cet analyseur ne lisait que ce qui suivait un titre
> « Chantiers » : elle rendait **zéro tâche sur dix projets pleins**, sans rien
> signaler. Le titre reste reconnu pour les anciens `pilotage.md` qui bornaient
> réellement leur section.

## Règles

- **Lecture seule.** Ne jamais modifier un projet depuis ce skill.
- **Ne rien voir n'est pas un succès.** Zéro tâche `@<qui>` sur tout un atelier
  se vérifie avant d'être annoncé — c'est plus souvent un analyseur cassé qu'un
  atelier serein.
- Ne pas recopier l'état d'un projet ailleurs : la page est un relevé daté, la
  vérité reste dans la mémoire de chaque projet.
