# harnais — le paquet de l'atelier agentique

Ce qui faisait tourner l'atelier vivait dans `~/.claude/hooks` et `~/.local/bin`,
**versionné nulle part**, recopié à la main d'un projet à l'autre. Les copies
dérivaient en silence : une correction faite ici n'atteignait jamais les autres.

Un paquet règle les trois : une version, une commande pour installer, un chemin
de mise à jour. Pour comprendre ce qu'il fait et pourquoi, lire
[`COMMENT-CA-MARCHE.md`](COMMENT-CA-MARCHE.md).

## Ce qu'il embarque

| | |
|---|---|
| `hooks/hooks.json` | les quatorze déclencheurs — briefing d'entrée (deux), garde de commit, garde de la Production, verrou des consignes, garde du coffre et son témoin, garde des sous-agents, journal, compteur d'usage de la mémoire (deux), la note d'un refus du mode auto, la fin de tour qui porte les seize gardes, et celle des tâches Notion (éteinte sauf réglage). Chacun lance le lanceur, rien d'autre |
| `bin/harnais` | le lanceur, un script `sh` : il cherche un vrai Python, lance `py/main.py`, et **dit** quand il n'en trouve pas |
| `py/` | le programme : du Python (3.9 au moins), bibliothèque standard seule, rien à compiler ni à installer d'autre que Python lui-même |
| `skills/` | les compétences : `agentic-adopte`, `agentic-agents`, `agentic-team`, `agentic-clean`, `agentic-init`, `project-init`, `publish-docs`, `caveman` |
| `rechutes.md` | la liste de contrôle rejouée **avant d'affirmer**. C'est une **amorce** : dès que l'agent écrit la sienne, elle vit dans les données et celle-ci n'est plus lue |
| `criteres-*.md` | les critères des deux juges — livrés avec le paquet, pour que l'agent jugé ne puisse pas les changer sans laisser de trace |

Et dans le même dépôt, sans être chargé par les agents : `tests/` (les tests
unitaires, `python3 -m unittest discover tests`), `controles/` (ce qui prouve que
ça marche — voir son [`LISEZMOI.md`](controles/LISEZMOI.md)), `rappels/` (un petit
programme Swift qui écrit dans les Rappels ; le harnais ne s'en sert plus depuis
le 08/10/2026, il reste pour le gardien du poste du CTO). `atelier/` n'est pas au
paquet : ce sont les outils du poste, tenus à part.

## Python, et pourquoi on y est revenu

Le programme a été du Python, puis du Rust jusqu'à la 0.12.8, et **il est de
nouveau du Python depuis le 12/10/2026** (décision du commanditaire). Le Rust ne gagnait que
~20 s par séance (mesuré les 09 et 10/09/2026) ; son coût était ailleurs : la
compilation — à la main, parce que la chaîne GitHub était bloquée — et un poste
Windows resté en 0.11.1. Ce que le Rust achetait, « rien à installer sous
Windows », redevient une précondition.

| | |
|---|---|
| **Ce que ça coûte** | un hook chaud prend 21 ms en Python contre 5 ms en Rust — environ 12 s de plus par séance (mesuré le 12/10/2026) |
| **Ce que ça rapporte** | plus de compilation, plus de chaîne qui construit Mac et Windows, plus de binaire qui peut être en retard sur son source : le programme **est** le source |
| **Ce qu'il faut** | un vrai Python 3.9 au moins sur chaque poste. macOS : `brew install python`. Windows : python.org ou `winget install Python.Python.3.13`, en cochant « Add to PATH ». Éprouvé sous Windows par la CI (3.9 et 3.13) depuis la 0.19.0 ; pas encore sur un vrai poste |
| **Retour arrière** | l'étiquette `v0.12.8` garde la dernière version Rust |

Le lanceur évite deux pièges : le faux `python.exe` du Microsoft Store, qui ouvre
le Store au lieu d'exécuter, et le relais `/usr/bin/python3` des outils Xcode
(62 ms à démarrer contre 14 ms pour un vrai Python, mesuré le 12/10/2026), qu'il
ne prend qu'en dernier recours. Quand il n'y a aucun Python, il **l'écrit** sur la
sortie d'erreur, avec le code que le hook aurait de toute façon : 2 pour le garde
de commit (qui refuse), 1 pour les autres.

`harnais version` rend deux mots : la version du paquet et l'empreinte de `py/`.

## Monter un atelier sur une machine neuve (Mac ou Windows)

> **À l'agent qui lit ceci sur une machine neuve** : suis ces étapes dans l'ordre ;
> à chacune, dis ce qui est vérifié bon, vérifié mauvais ou pas mesuré, et arrête-toi
> au premier échec pour le rapporter. Ne pose rien avant que le banc (étape 3) soit vert.

1. **Prérequis** — Claude Code connecté ; un vrai Python 3.9 ou plus (sous Windows :
   pas le `python.exe` de `WindowsApps`, qui ouvre le Store) ; Git (sous Windows, Git
   pour Windows : il fournit le `sh` qui lance les hooks) ; l'accès à ce dépôt privé.
2. **Le paquet, pour l'utilisateur** :
   ```bash
   claude plugin marketplace add PetitPelican/claude-harness
   claude plugin install harnais@atelier
   ```
   Sa version (`.claude-plugin/plugin.json` du paquet installé) : 0.19.0 ou plus.
3. **Le banc**, avant de rien poser :
   `python <dossier du paquet>/controles/banc-deploiement.py`. Il monte un atelier, un
   projet seul et une équipe dans un dossier jetable et éprouve briefing, verrou des
   consignes et garde de la Production. Attendu : `35 vérification(s), 0 en échec`.
4. **L'atelier**, à blanc puis pour de bon :
   ```bash
   sh <dossier du paquet>/bin/harnais atelier-monte --racine ~/Agentic --utilisateur <Prénom>
   sh <dossier du paquet>/bin/harnais atelier-monte --racine ~/Agentic --utilisateur <Prénom> --go
   ```
   Il pose la machine (`~/.claude/CLAUDE.md`, à remplir), les consignes communes
   (`~/Agentic/CLAUDE.md`) et le poste du CTO (`~/Agentic/CTO`). Il n'écrase rien.
5. **Remplir** l'étage 1 (système, mémoire vive, comment l'humain entre sur la
   machine) et le cap du CTO (`~/Agentic/CTO/brain/fact/base.md`).
6. **Inscrire le paquet dans le dossier du CTO** : dans `~/Agentic/CTO`,
   `claude plugin install harnais@atelier --scope project`.
7. **Rendre la main** : l'humain ouvre une nouvelle session DANS `~/Agentic/CTO` ; la
   preuve est le briefing d'entrée au démarrage. C'est le CTO qui monte ensuite les
   projets (compétences `/agentic-adopte`, `/agentic-agents`).

Le détail est dans la compétence `/agentic-init`.

## Poser le harnais sur un projet

```bash
claude plugin marketplace add <organisation>/<dépôt> --scope project
claude plugin install harnais@atelier --scope project
harnais adopte          # dit ce qu'il poserait, n'écrit rien
harnais adopte --go     # pose la mémoire brain/ et déclare le paquet
```

**L'installation se fait dans CHAQUE dossier d'où un agent démarre** — la racine
en mono, chaque `agents/<nom>/` à plusieurs. Mesuré le 11/09/2026 sous Claude
Code 2.1.268 : un dossier qui déclare le paquet sans y être inscrit ne le charge
pas, et rien ne le dit. Le briefing d'un projet sans mémoire donne le chemin
exact du programme.

## La mémoire d'un projet

| | |
|---|---|
| `brain/fact/` | les faits du projet — quatre fichiers, plus `workflow.md` (commun à tous les agents) et `roles.md` à plusieurs ; un agent **expert** y tient des fiches libres |
| `brain/mind/` | l'état d'un agent — `state.md` et `todo.md` ; à plusieurs, un jeu par agent dans `brain/mind/<nom>/` |
| `docs/` | les traces datées, sans plafond |

**Deux profils d'agent** (12/10/2026) : le **développeur** (défaut ; QA, OPS, PO,
Harness) a les fichiers ci-dessus. L'**expert** (`HARNAIS_PROFIL=expert`
dans les réglages de l'agent ; un juriste, un comptable, le CTO) a un socle — nature, sources,
règles, façon de procéder — puis des fiches au nom de son métier, et une garde de
fin de tour qui exige qu'un fait donné par l'humain soit noté. Voir
[`COMMENT-CA-MARCHE.md`](COMMENT-CA-MARCHE.md), §6 bis.

L'organisation d'avant — `.fact/` et `.mind/` à la racine, ou déportés dans
`memoire/` — est encore servie à l'identique ; `harnais mise-a-niveau` la passe en
`brain/` sans rien perdre (fichiers, historique, droits des agents), et complète ce
qui manque, mono comme équipe. `--atelier` dit quels projets en ont besoin. Les deux à la fois, jamais : le harnais refuse de choisir laquelle
fait foi, et le dit.

## Aucune clé à l'écran

Le garde du coffre refuse toute commande qui afficherait une valeur de secret : les
lectures des coffres et des outils en ligne de commande courants (gestionnaire de
secrets, plateformes d'hébergement, de base de données, de paiement, GitHub, le
trousseau du système), un lanceur qui imprime son environnement, la lecture brute
d'un `.env*`, d'un `.mcp.json` ou d'un dossier caché `.…secrets`. La même commande passe si sa
sortie est jetée, écrite dans un fichier, capturée dans une variable, ou réduite aux
noms (`--only-names`, `grep -oE '^[A-Z_][A-Z0-9_]*='`, `jq keys`, `wc -l`). Le refus
dit laquelle employer. Son témoin, après coup, signale une clé de forme connue
passée en clair (les formats courants : fournisseurs d'IA, de cloud, de paiement,
de base de données, GitHub, GitLab, Slack, npm, jeton JWT hors clé `anon`) : elle est à refaire. Il en garde la sorte et une empreinte, jamais la valeur.

## Pas de sous-agent qui lit des images sans l'accord de l'humain

Le 18/10/2026, un sous-agent a lu 2 273 images dans une seule conversation (43 M
de jetons, la semaine bloquée deux jours). La garde des sous-agents refuse le
lancement d'un sous-agent (`Agent`, `Task`, `Workflow`) dont la consigne lui fait
REGARDER du visuel — un verbe qui voit suivi d'une image, d'une capture d'écran,
d'une diapositive, d'un PDF ou d'un fichier de ces formats ; la rédaction de textes
alternatifs ; l'OCR — ou lui confie plus de 30 images, captures ou PDF (« les 2 273
images »). Un audit qui parle d'images sans les regarder passe, et un lot de
texte aussi, quelle que soit sa taille : le coupe-circuit du poste le couvre. Le refus dit quoi faire : poser à l'humain la question
majeure, avec le volume et le découpage ; sur son oui, `harnais laissez-passer-lot
"<son oui, cité>"` laisse partir le visuel pendant 120 minutes, chaque lancement
journalisé. Au-delà de 30 médias, le refus tient même muni : un sous-agent neuf par lot.

## Les tâches Notion restent à jour (sur réglage)

Éteinte par défaut ; un projet l'allume en posant `HARNAIS_TACHES` dans les
réglages de ses agents (un objet JSON : la base des tâches, le nom du secret de
lecture, les valeurs qui disent « fini », la propriété qui porte la preuve).
Alors, dans la copie du code d'une équipe, chaque commit cite sa tâche :
`Tâche: <identifiant>`, `Tâche: <identifiant> fait` ou `Tâche: aucune` — sans
cette ligne, la garde de commit refuse et dit quoi écrire. En fin de tour, chaque
tâche citée par les commits du tour est lue dans Notion : citée « fait », elle
doit en porter les valeurs et sa preuve ; citée seule, elle doit avoir été
modifiée depuis le commit ; un identifiant inconnu ou hors de la base est refusé.
Notion injoignable ou secret absent : un avertissement, jamais un blocage. Le
secret, lu dans l'environnement ou au coffre, n'est jamais affiché.

## Savoir ce qui tourne vraiment

    harnais equipe-vue --racine ~/Agentic

Pour chaque projet et chaque agent : la forme de la mémoire, le paquet
**déclaré**, **inscrit**, et **servi** — la trace d'entrée qu'il laisse à chaque
démarrage, avec la version qui l'a écrite. `--html` pour une page autonome.

## Mettre à jour

Le cache est épinglé par le **numéro de version**, jamais par le contenu :
publier une correction sans monter le numéro laisse la machine sur l'ancien code,
et l'outil répond « déjà à jour ». **Monter la version fait partie de la
correction.** Publier, c'est : monter la version, rejouer les contrôles et
enregistrer le verdict, étiqueter et pousser, rafraîchir le marché, puis mettre à
jour l'inscription de chaque projet — rien à compiler. Dans chaque dossier de
lancement :

    claude plugin update harnais@atelier --scope project

Un agent prend la version **à son prochain démarrage**, et seulement alors.

## Les deux variables qui décident de tout

- **`CLAUDE_PLUGIN_ROOT`** — où le code est posé. Chemin **absolu**, ce qui
  ferme le piège du chemin relatif : sur un clone Windows, un lien symbolique
  devient un fichier texte et les hooks disparaissent sans bruit.
- **`CLAUDE_PLUGIN_DATA`** — un dossier qui **survit aux mises à jour**. Les
  témoins, le journal des blocages et la liste des rechutes y vivent : le code
  se remplace, pas ce qu'il a appris. Le code Python compilé (`pycache/`) y va
  aussi : le paquet reste tel que livré.

## Pas de repli

Chaque déclencheur vérifie que le lanceur existe, et le lanceur vérifie qu'il
trouve un Python. Sinon, il n'y a pas de version de secours : il le dit, avec le
remède, et le garde de commit **refuse** la commande plutôt que de la laisser
passer sans contrôle.

## Essayer sans rien installer

    claude --plugin-dir ~/Agentic/claude-harnais

Le drapeau charge le paquet depuis ce dépôt, pour cette session seulement.
