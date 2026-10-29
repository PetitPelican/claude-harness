# Démarrer — de zéro à une équipe de trois agents

Ce guide est pour quelqu'un qui n'a jamais vu le harnais. À la fin, vous aurez
sur votre ordinateur :

```
Agentic/                  la racine de votre atelier
├── CTO/                  l'agent qui monte et entretient l'atelier
└── MonProjet/            la mémoire partagée de votre équipe
    └── agents/
        ├── OPS/          serveur, infrastructure, mise en Production
        ├── PO/           le produit et les applications (il code)
        └── QA/           qualité, audits, plans, pilotage de l'équipe
```

Chaque agent est une session Claude ouverte dans **son** dossier. Il y trouve
son rôle, ses droits, sa mémoire et sa propre copie du code. Le harnais (ce
dépôt) est le paquet que chacun charge au démarrage : il lui donne sa mémoire,
ses gardes et sa façon de rendre compte.

**Vous ne tapez aucune commande.** Vous ouvrez des dossiers dans l'app Claude et
vous collez des messages, appelés ici des *prompts*. Les agents font les gestes
eux-mêmes et vous demandent votre accord quand il le faut.

Comptez une heure. La plus grande partie, c'est l'agent qui travaille.

---

## Étape 0 — Ce qu'il vous faut

- Un ordinateur **Mac** ou **Windows**, sur lequel vous pouvez installer des logiciels.
- Un **abonnement Claude** qui donne accès à Claude Code (Pro ou Max), ou un
  compte d'organisation qui l'inclut.
- Si le code de votre projet est sur GitHub : un **compte GitHub** qui y a accès.

## Étape 1 — Installer l'app Claude

1. Téléchargez l'app depuis **claude.ai/download** et installez-la.
2. Ouvrez-la et connectez-vous avec votre compte Claude.
3. Repérez l'onglet **Code** : c'est là qu'on ouvre un dossier de votre ordinateur
   et qu'on y fait travailler un agent.

## Étape 2 — Créer le dossier de l'atelier

Créez un dossier vide nommé **`Agentic`** dans votre dossier personnel :

- **Mac** : dans le Finder, ouvrez votre dossier personnel (la petite maison), puis
  Fichier → Nouveau dossier → `Agentic`.
- **Windows** : dans l'Explorateur, ouvrez `C:\Users\<votre nom>`, puis clic droit →
  Nouveau → Dossier → `Agentic`.

## Étape 3 — Installer tout, avec le prompt n° 1

1. Dans l'app, onglet **Code**, ouvrez une nouvelle session et choisissez le
   dossier **`Agentic`**. Si l'app vous demande de faire confiance à ce dossier,
   acceptez.
2. Collez ce message en remplaçant `<PRÉNOM>`, puis envoyez :

```text
Tu vas installer un atelier agentique sur cet ordinateur. Je ne connais pas
l'outil : fais les gestes toi-même, explique chacun en une phrase, et ne me
demande que ce que toi seul ne peux pas faire.

Mon prénom : <PRÉNOM>
Le dossier ouvert est la racine de l'atelier.

1. Vérifie, et installe ce qui manque : Claude Code en ligne de commande,
   Python 3.9 ou plus (sous Windows, le vrai Python, pas celui du Microsoft
   Store), Git (sous Windows, Git pour Windows).
2. Lis le README du dépôt https://github.com/PetitPelican/claude-harness,
   section « Monter un atelier sur une machine neuve », et suis-la dans
   l'ordre : le paquet, le banc d'essai, l'atelier à blanc puis pour de bon,
   l'inscription du paquet dans le dossier du CTO.
3. Remplis avec moi ce qui est marqué « À REMPLIR » (la machine et le cap du
   CTO) : pose-moi les questions une par une, en mots simples.
4. À chaque étape, dis « vérifié bon », « vérifié mauvais » ou « pas mesuré ».
   Arrête-toi au premier échec et explique-le-moi simplement.
5. Ne monte aucun projet. À la fin, donne-moi le chemin exact du dossier à
   ouvrir ensuite.
```

**Ce qui va se passer :**
- l'agent vous demande l'autorisation avant chaque geste : lisez la phrase qui
  l'explique, puis autorisez ;
- sous Windows, l'installation de Python ou de Git peut ouvrir une fenêtre
  « Voulez-vous autoriser cette application… » : répondez oui ;
- il vous pose quelques questions sur votre machine et sur ce que vous voulez
  faire de l'atelier ;
- **à la fin**, il vous donne le chemin du dossier `CTO`. Le banc d'essai doit
  avoir rendu `0 en échec`. Sinon, ne continuez pas : demandez-lui ce qui a échoué.

## Étape 4 — Rencontrer le CTO

Fermez cette première session : elle a servi à installer, elle ne sert plus.

1. Ouvrez une **nouvelle** session dans le dossier **`Agentic/CTO`**. C'est
   important : le CTO n'existe que dans son dossier. Ouvert ailleurs, c'est un
   Claude ordinaire, sans rôle ni mémoire.
2. Collez :

```text
Présente-toi en cinq lignes : qui tu es, ce que tu tiens, ce que tu ne
touches pas. Puis prouve que ton harnais est chargé : cite la ligne « cap »
de ton briefing d'entrée et la version du paquet.
```

Il doit citer son cap (ce que vous avez rempli à l'étape 3) et une version du
paquet. S'il dit qu'il n'a pas de briefing, le paquet n'est pas chargé : voir
« Si ça coince ».

## Étape 5 — Monter le projet et ses trois agents

Toujours dans la session du CTO, collez ce message en remplaçant `<NOM>` et
l'adresse du code :

```text
Monte mon projet <NOM> en équipe de trois agents, OPS, PO et QA (types ops,
po, qa), avec la compétence /agentic-adopte.
- Dossier de l'équipe : <NOM>, dans la racine de l'atelier. Il doit être neuf.
- Le code : <adresse du dépôt git, par exemple https://github.com/mon-orga/mon-projet>
  (ou : « pas encore de code »).
Fais-le d'abord à blanc et montre-moi ce qui sera créé, en mots simples.
Après mon accord : pour de bon. Puis inscris le paquet dans le dossier de
chaque agent, et dis-moi quels dossiers ouvrir, et dans quel ordre.
```

**Ce qui va se passer :**
- il vous montre ce qu'il va créer, puis attend votre « oui » ;
- si le code est sur GitHub et privé, il peut vous demander de vous connecter à
  GitHub une fois : suivez ce qu'il dit ;
- à la fin, il vous donne trois chemins : `Agentic/<NOM>/agents/OPS`, `…/PO` et `…/QA`.

## Étape 6 — Réveiller les trois agents

Chaque agent a **sa** session, ouverte dans **son** dossier. Ouvrez-en une par
agent : vous les garderez côte à côte.

**D'abord QA**, qui remplit la mémoire commune de l'équipe. Ouvrez une session
dans `Agentic/<NOM>/agents/QA`, puis collez :

```text
/project-init
```

Il lit le code et les documents du projet, puis vous pose quelques questions :
le but du projet, pour qui, les outils, les contraintes… Répondez simplement. Il écrit
la mémoire partagée par les trois agents.

**Ensuite OPS et PO**, chacun dans sa session et son dossier
(`…/agents/OPS`, puis `…/agents/PO`) :

```text
Lis ton rôle et la mémoire du projet. Dis-moi en trois lignes ce que tu
tiens, ce que tu ne touches pas, et la première tâche que tu proposes.
```

Votre équipe est en place.

## Ensuite, au quotidien

- **Un agent = une session = un dossier.** N'ouvrez jamais un agent à la racine
  du projet ou dans le dossier d'un autre.
- **Vous décidez du quoi et du pourquoi**, eux du comment. Quand ils ont besoin
  de vous, ils posent une question fermée en fin de message : vous répondez par
  le numéro.
- **QA est le guichet** : les autres lui adressent leurs questions, et il ne vous
  remonte que celles qui comptent.
- **La Production est fermée par défaut** : seul OPS peut y aller, et seulement
  sur votre « oui » au moment du geste.
- **Mettre le harnais à jour** : demandez-le au CTO (« mets le harnais à jour
  partout »). Chaque agent prend la nouvelle version à son prochain démarrage.
- **Ajouter un agent** : demandez-le au CTO (compétence `/agentic-agents`).

## Si ça coince

| Ce que vous voyez | Ce qu'il faut faire |
|---|---|
| L'agent dit qu'il n'a ni rôle ni briefing | La session n'est pas ouverte dans le bon dossier. Rouvrez-la dans celui de l'agent. |
| Le CTO ne cite pas de cap ni de version | Le paquet n'est pas inscrit dans son dossier. Dans une session à la racine `Agentic`, demandez : « inscris le paquet harnais@atelier dans le dossier CTO ». |
| « Python introuvable » ou le Microsoft Store s'ouvre | Le vrai Python manque. Demandez à l'agent de l'installer depuis python.org, avec « Add to PATH ». |
| Le banc d'essai a des échecs | Ne montez rien. Demandez à l'agent de vous expliquer le premier échec, puis signalez-le sur ce dépôt (onglet *Issues*). |
| Un agent demande l'autorisation pour chaque petite chose | Normal pour le premier passage. Une fois l'équipe montée, chaque agent agit seul dans son périmètre. |

## Ce que ce guide ne monte pas

Le CTO de ce dépôt monte l'atelier, les projets et les agents. Il ne fournit pas
d'outils de surveillance : relance automatique des agents, tableau de bord de la
machine, veille de nuit. Votre CTO pourra vous en proposer, adaptés à votre poste.

**Éprouvé** : l'installation du paquet depuis ce dépôt public, sans aucun compte
ni réglage préalable (sur Mac), et le banc d'essai, rejoué sous Mac et sous
Windows à chaque version. **Pas encore
éprouvé** : ce parcours complet, de bout en bout, par quelqu'un qui découvre,
sur un PC Windows neuf. Si une étape ne se passe pas comme écrit ici, dites-le :
c'est ce qui rendra ce guide juste.
