# Les contrôles — et les témoins figés

26 contrôles, lancés d'un seul geste — plus deux vérifications du lanceur
lui-même (ses propres témoins, et le programme livré qui répond à `version`) :

    python3 controles/tous-les-controles.py /tmp/controles

**Les contrôles jugent le programme désigné par `HARNAIS_BIN`**, et à défaut le
lanceur du paquet, `bin/harnais`. Depuis le retour en Python (12/10/2026) c'est
du Python lu à chaque lancement : il n'y a plus de binaire à construire, ni de
binaire livré qui puisse être en retard sur son source.

**Ce qu'ils ont rendu la dernière fois est dans `verdict.txt`** — daté, avec
l'état exact du source jugé (`py/`, `hooks/`, `skills/`), et une ligne par
contrôle. Ce fichier ne dit pas « tout passe » : il dit QUAND et SUR QUOI. Il
n'y a plus de chaîne de construction pour le lire et refuser : l'ordre de
publication le demande — monter la version, rejouer tous les contrôles,
enregistrer le verdict, étiqueter —, et c'est désormais une discipline, pas une
porte (dit, pas mesuré). Un verdict sur des modifications non enregistrées se
déclare « NON ENREGISTRÉ » : il ne vaut pas preuve.

Une limite, dite : trois contrôles (canal de déploiement, formes réelles,
conversion en équipe) jugent l'état réel de l'atelier ou le programme livré par
nature ; ils disent ce qui tourne chez les agents, pas seulement ce que le dépôt
contient.

Neuf d'entre eux **comparaient** deux programmes vivants (un hook Python et un
hook Rust) ; depuis le 10/09/2026 ils comparent à un **témoin figé** — ce que le
programme de référence rendait, gardé sous forme de données dans `temoins/`. C'est
ce qui a rendu le retour en Python possible sans refaire les preuves : le juge ne
dépend d'aucun langage. Les autres jugent autre chose : le relecteur, la conversion
en équipe, le canal de déploiement, la forme des projets réels, la fin de tour
muette, la mémoire partagée à deux, **la garde des faits des experts**
(`faits-experts.sh`, nouveau le 12/10/2026 : douze garanties et un témoin, avec
un faux juge — le vrai modèle n'est jamais appelé dans un contrôle), **la forme
« un dossier par agent »** de bout en bout par le lanceur (`equipe-v3.py`,
nouveau le 14/10/2026 : déménagement, garde de commit, garde des copies, page
d'équipe — chaque garantie avec son témoin), et la documentation elle-même
(`doc-code.sh`).

## Les deux passes, avant de demander une publication

Les contrôles jugent le code. Deux passes jugent le reste — ce qui est branché,
et ce qu'on en affirme. Aucune n'est dans le lanceur : elles ne se lancent pas
toutes seules, et c'est pourquoi elles sont nommées ici (jusqu'au 26/09/2026
elles ne l'étaient nulle part, et la première était cassée depuis que le banc
de fin de tour avait gagné une garde, sans que personne le voie).

    python3 controles/passe-mecanique.py /chemin/absolu/jetable
    python3 controles/passe-jugee.py [AAAA-MM-JJ] [N]

- **La passe mécanique** — six questions sans jugement : les contrôles passent
  depuis un dossier vide, les deux programmes livrés viennent du même code,
  toute sous-commande a un appelant ou un mode d'emploi, une déclaration sans
  programme le dit, chaque voie du code est déclarée, le paquet installé est le
  dépôt. Elle relance tous les contrôles, donc réécrit `verdict.txt`. Chemin
  ABSOLU : un argument qui commence par un tiret est pris pour un dossier.
- **La passe jugée** — tire au sort, par empreinte, les affirmations chiffrées
  du jour (messages d'enregistrement du paquet, lignes ajoutées à l'état, au
  todo et aux décisions du projet Harness) et les soumet à des juges neufs en
  lecture seule. `N = 0` ne lance aucun juge et dit seulement combien
  d'affirmations l'extraction trouve : c'est son témoin.

Ce qu'elles ne voient pas, écrit plutôt que supposé : la passe mécanique juge
le programme Windows par son empreinte seulement — elle ne peut pas le lancer
sur ce poste.

## Pourquoi on a figé

Le jour où le programme de référence disparaît, un différentiel ne compare plus
rien. Le gel est donc le premier geste d'un chantier qui change de langage, pas le
dernier. Il a servi deux fois : Python vers Rust (10/09/2026), puis Rust vers
Python (12/10/2026).

**Une nuance, mesurée le 12/09/2026, et elle corrige ce qui était écrit ici.**
On lisait « on ne peut plus JAMAIS le régénérer ». C'est faux : le programme de
référence est dans l'HISTOIRE du dépôt, au commit qui l'efface, avec l'empreinte
exacte que le témoin enregistre. Il se ressort et il tourne encore. Deux
conditions, vérifiées ce jour-là et non négociables : il faut ressortir TOUT son
dossier, pas le seul fichier — il importe ses voisins et, ne les trouvant pas,
il sort sans rien faire, ce qui figerait un corpus de sorties vides comme un
témoin parfaitement vert ; et il appelle un outil de poste, lui aussi retiré,
qu'il faut ressortir avec. Sans les deux, la régénération rend un témoin aveugle
au lieu d'échouer. C'est possible, donc, mais ce n'est pas un geste anodin : un
re-gel réécrit tous les cas d'un coup et ne se relit qu'en comparant l'ancien
témoin au neuf.

Il vaut aussi pour la suite. Un code et son juge qui partagent un langage et un
auteur héritent des mêmes défauts. Les témoins referment cette faiblesse : produits
par un programme de référence qui n'est plus celui qu'on juge, ils ne peuvent pas
hériter de ses défauts. Au retour en Python, ce sont eux qui ont dit si le
nouveau programme rendait la même chose.

## Refaire les témoins — tant que c'est encore possible

    python3 controles/geler-les-temoins.py

C'est le **seul** programme qui appelle encore les hooks de `~/.claude/hooks/`.
Quand ils auront disparu, il échouera bruyamment. C'est voulu : il ne doit pas
exister de façon discrète de perdre la référence.

Chaque témoin **refuse de se figer** si le côté Python ne tient pas ses propres
témoins positifs et négatifs. Un témoin produit par un programme qui ne fait
rien vaut moins que pas de témoin : il rassure.

## Ce qu'un témoin porte

| champ | ce qu'il dit |
|---|---|
| `commit_depot` | l'état du dépôt au moment du gel |
| `sources` | chaque fichier Python qui a produit la sortie, avec son empreinte — ils ne sont versionnés nulle part |
| `origine` | `python` pour un vrai témoin de transition ; `rust` dans un seul cas, ci-dessous |
| `contre_exemple` | deux cas dont les sorties doivent DIFFÉRER |
| `cas` | l'entrée fabriquée et la sortie attendue |

**Le contre-exemple n'est pas décoratif.** Deux programmes qui ne font rien se
comparent égaux. On exige donc que deux cas nommés rendent des sorties
différentes — dans le témoin figé ET dans ce que le programme vient de
produire. Si le rendu confond les deux cas, le contrôle échoue même sans écart.

**Deux témoins sont d'origine `rust`**, et pour la même raison : Python y
était FAUX et ne sera pas corrigé. Figer sa version aurait gravé l'erreur. Ce ne
sont pas des preuves d'équivalence, ce sont des clichés de référence :

- `briefing-chemins.json` — Python annonçait aux agents en mémoire déportée des
  chemins qui ne s'ouvrent pas. Sans lui, plus aucun contrôle ne regarderait les
  chemins annoncés.
- `vue-equipe/` (11/09/2026) — le script du tableau de bord ne lisait que
  l'organisation d'avant et des réglages vides de sens depuis le paquet : sur le
  vrai atelier, 12 projets sur 13 classés « sans mémoire », et des conseils vers
  deux compétences supprimées. Le script est retiré. Ce qui tient ici lieu de
  référence indépendante : **chaque projet du corpus doit rendre le verdict pour
  lequel il a été fabriqué**, vérifié avant toute comparaison — et le gel refuse
  de figer sinon.

## Le corpus est fabriqué, jamais l'état du jour

Trois contrôles lisaient l'atelier vivant — le carnet réel d'un projet, les
arbres réels de la flotte. Un différentiel sur l'état vivant ne prouve que les
chemins que le jour emprunte ; un **témoin** figé sur l'état vivant est pire :
il périme en silence à la première migration, et il recopie la mémoire d'un
autre agent dans ce dépôt-ci.

Leur corpus est donc fabriqué, forme par forme, en reproduisant les formes
relevées dans le vrai. Et **les seuils sont joués des deux côtés, à l'unité** :
48 h / 50 h pour la fenêtre du résumé, 29 j / 31 j pour l'oubli de la confiance,
trois rechutes qui mordent et une quatrième qui passe.

## Ce qui a été vérifié le 10/09/2026, et comment

(Relevé daté, du temps du Rust : les gestes valent encore, les chiffres sont ceux
de ce jour.)

- **Les quinze passent sans aucun Python de hook** : `~/.claude/hooks/` déplacé,
  suite relancée, quinze verts. C'est le geste à rejouer avant de supprimer ce
  dossier pour de bon.
- **Un octet changé dans un module du programme fait échouer au moins un témoin** :
  quatre sabotages joués, quatre attrapés — le plafond du registre d'usage
  (40→39), la note dormante du briefing (30→31 j), la garde des rechutes (3→4),
  l'affichage de la confiance au carnet (2→3 mouvements).
- **Trois passages consécutifs rendent le même verdict.** Un contrôle qui
  clignote, on apprend à l'ignorer.

## Trois pièges rencontrés en figeant, et leur forme générale

1. **Restaurer un fichier par `mv` lui rend sa DATE**, donc `cargo` ne
   reconstruit pas — et le contrôle « le binaire correspond au source » ne le
   voit pas, puisqu'il compare le COMMIT, pas le contenu construit. Un binaire
   saboté a ainsi survécu à sa propre restauration. Toujours `touch` après avoir
   restauré. (Piège du temps du Rust : sans compilation, il n'existe plus, mais
   la forme reste — un cache qui se fie à une date.)
2. **Masquer APRÈS avoir trié range les clés dans l'ordre du haché.** Les noms
   deviennent stables, l'ordre non — le témoin clignote. On masque d'abord, on
   trie ensuite ; et on ne trie JAMAIS une liste sur une empreinte.
3. **Une empreinte se calcule sur le texte que le LECTEUR recompose**, pas sur
   celui qu'on croit avoir écrit : une transmission sur deux lignes laisse sa
   seconde ligne dans le texte.
