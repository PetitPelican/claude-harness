"""LES TÉMOINS FIGÉS — ce que Python rendait, le jour où il existait encore.

Un contrôle différentiel compare deux programmes vivants. Le jour où l'un des
deux disparaît, il ne compare plus rien — et **on ne peut plus jamais le
régénérer** : l'interpréteur parti, la sortie de référence n'existe nulle part.

Ce module fige cette sortie AVANT la disparition, sous forme de données, et
retourne le contrôle : il ne demande plus à Python ce qu'il rendrait, il lit ce
qu'il a rendu.

**Trois exigences, et aucune n'est décorative.**

1. **La provenance.** Un témoin dit le commit du dépôt ET l'empreinte de chaque
   fichier Python qui l'a produit. Les hooks vivent dans `~/.claude/hooks/`,
   qui n'est versionné nulle part : sans leur empreinte, le témoin ne dirait
   pas de quel code il vient.

2. **Le contre-exemple.** Deux programmes qui ne font rien se comparent égaux —
   c'est la maladie de cet atelier. Chaque témoin nomme donc DEUX cas dont les
   sorties doivent DIFFÉRER. Si elles sont égales, le témoin est aveugle et le
   contrôle échoue au lieu de rassurer. La vérification se fait des deux côtés :
   dans le témoin figé, et dans ce que le programme vient de produire.

3. **Le corpus est fabriqué, jamais l'état du jour.** Un différentiel joué sur
   l'atelier vivant ne prouve que les chemins que ce jour-là empruntait. Un
   témoin figé sur l'état du jour serait pire : il périmerait en silence à la
   première migration. Les cas se fabriquent.

**Les chemins de bac à sable ne se figent pas.** Ils changent à chaque
exécution. `masque` remplace ces morceaux variables par un jeton avant de
figer, et le même masque s'applique avant de comparer.
"""
import datetime, hashlib, json, os, pathlib, subprocess, sys

ICI = pathlib.Path(__file__).resolve().parent
DOSSIER = ICI / "temoins"
DEPOT = ICI.parent


def exige_que_ca_demarre(argv):
    """REFUSER TOUT DE SUITE SI LE PROGRAMME COMPARÉ NE DÉMARRE PAS.

    POURQUOI, mesuré le 23/09/2026. Un différentiel lancé DIRECTEMENT — hors du
    point d'entrée, qui repose le repli Python — appelait un fichier absent.
    `python3 <fichier absent>` rend le code 2, et l'un des différentiels compte
    un code 2 comme un BLOCAGE : cinquante « fichier introuvable » s'y lisaient
    comme cinquante refus réussis. L'échec du lanceur avait exactement la forme
    de son succès.

    Par le point d'entrée le défaut ne se voyait PAS — la restauration a lieu,
    et sept témoins sur neuf se figeaient. C'est donc une trappe qui n'attend
    que deux choses : qu'on lance un différentiel à la main, ou que la
    restauration échoue en silence.

    Un contrôle ne doit jamais juger une référence dont il ignore si elle a
    seulement démarré. Deux formes, deux vérifications :
    · `["python3", chemin]` — le fichier doit exister ;
    · un programme — il doit répondre à `version`.
    """
    import subprocess, pathlib
    if not argv:
        raise SystemExit("CONTRÔLE IMPOSSIBLE : aucun programme à comparer.")
    if argv[0].endswith("python3") and len(argv) > 1:
        p = pathlib.Path(argv[1])
        if not p.is_file():
            raise SystemExit(
                "CONTRÔLE IMPOSSIBLE : la référence à comparer n'existe pas "
                "(%s). Rien n'a été jugé, et surtout rien n'a été figé — un "
                "fichier absent rend un code de sortie qu'on confondrait avec "
                "un verdict. Par le point d'entrée `geler-les-temoins.py` elle "
                "est reposée depuis l'historique ; lancé à la main, il faut la "
                "poser soi-même." % p)
        return
    r = subprocess.run([argv[0], "version"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit(
            "CONTRÔLE IMPOSSIBLE : le programme de référence ne répond pas à "
            "`version` (%s). Rien n'a été jugé ni figé." % argv[0])


def gel_demande():
    """Le mode qui produit le témoin, au lieu de le lire."""
    return "--gel" in sys.argv[1:]


def _commit():
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(DEPOT),
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "(inconnu)"


def _chemin_public(chemin):
    """Le chemin d'une source, sans le nom du poste : relatif au home (`~/…`)
    ou, à défaut, au dépôt. La provenance dit QUEL fichier, pas OÙ il vit."""
    p = pathlib.Path(chemin).resolve()
    for base, pre in ((pathlib.Path.home(), "~/"), (DEPOT, "")):
        try:
            return pre + p.relative_to(base.resolve()).as_posix()
        except ValueError:
            pass
    return p.name


def _empreinte(chemin):
    p = pathlib.Path(chemin)
    if not p.exists():
        return "(absent)"
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _jour_de_reference(t, ref):
    """LE JOUR OÙ ÇA TOURNE N'EST PAS LE MÊME DES DEUX CÔTÉS.

    Un témoin figé le 10 et rejoué le 11 échoue sur chaque message qui porte la
    date du jour : cinq contrôles sont passés au rouge à minuit sans qu'une
    ligne ait bougé. Et comme les témoins ne se refont qu'avec un interpréteur
    qui n'existe plus, un témoin fragile à la date est un témoin qui meurt de
    sa propre vieillesse.

    Le piège, et c'est lui qui rend l'argument `ref` obligatoire : le masque ne
    peut pas être posé au gel une fois pour toutes, parce que le témoin porte
    le jour DU GEL et le programme celui d'AUJOURD'HUI. Un seul « maintenant »
    appliqué aux deux les décale d'un cran au lieu de les aligner. Chaque côté
    se relativise donc à SON jour — le témoin au sien, qu'il porte dans
    `gele_le`, le programme au nôtre — et les deux se rejoignent sur `<auj>`.

    **ET SEULEMENT CE JOUR-LÀ.** Premier essai : une fenêtre de quatre jours,
    `<auj-1>`, `<auj-2>`, `<auj-3>`. Elle a cassé le témoin du briefing, qui
    était vert — son corpus fabrique une cible datée du 08/09, une date FIXE,
    la même des deux côtés. La fenêtre la traduisait `<auj-2>` côté témoin et
    `<auj-3>` côté programme : deux noms pour une seule date. Une date fixe du
    corpus n'a pas à devenir relative ; seule celle qui vient de l'horloge le
    doit. Le masque ne touche donc qu'un jour, et c'est le seul qu'on sache
    différent des deux côtés.

    Deux formes, parce que l'atelier rend les deux : `2026-09-11` et `11/09`.
    Ce qu'on perd, et il faut le savoir : un corpus qui contiendrait
    littéralement `11/09` — une fraction, un rapport — serait masqué d'un côté
    seulement. Le cas ne se présente pas ici ; s'il se présentait, il se verrait
    comme un écart, pas comme un faux vert.
    """
    return t.replace(ref.isoformat(), "<auj>").replace(ref.strftime("%d/%m"), "<auj-jm>")


def _texte(v, masque):
    """Une sortie devient du texte comparable, quel que soit son type.

    ON MASQUE AVANT DE TRIER, et l'ordre des deux gestes n'est pas un détail.
    Une clé masquée peut être une EMPREINTE — un haché de la date, donc une
    valeur neuve à chaque exécution. Trier d'abord range les clés dans l'ordre
    du haché ; le masque rend ensuite des noms stables, mais dans un ordre qui
    change à chaque passage. Le témoin devient alors intermittent : vert deux
    fois, rouge la troisième, sans qu'une ligne de code ait bougé — et un
    contrôle qui clignote, on apprend à l'ignorer.

    Mesuré le 10/09/2026 sur le carnet, en jouant la suite hooks Python
    retirés : la seule différence était l'ordre des clés de `confiances`.
    """
    if isinstance(v, bytes):
        try:
            v = v.decode("utf-8")
        except UnicodeDecodeError:
            v = "hex:" + v.hex()
    brut_json = not isinstance(v, str)
    if brut_json:
        v = json.dumps(v, ensure_ascii=False)
    for a, jeton in (masque or []):
        v = v.replace(str(a), jeton)
    if brut_json:
        try:
            v = json.dumps(json.loads(v), ensure_ascii=False, sort_keys=True)
        except ValueError:
            # Un masque a cassé le JSON : on garde la forme masquée telle
            # quelle plutôt que de rendre une comparaison silencieusement
            # différente des deux côtés.
            pass
    return v


def fige(nom, cas, contre, sources, masque=None, origine="python"):
    """ÉCRIT LE TÉMOIN. `cas` est une liste ordonnée de (nom, entrée, sortie).

    `contre` nomme deux cas dont les sorties doivent différer. `sources` liste
    les fichiers qui ont produit ces sorties.

    `origine` vaut `python` pour un vrai témoin de transition. Il vaut `rust`
    dans un seul cas, et il faut le dire : quand Python était FAUX sur ce point
    et ne sera pas corrigé — le repli est condamné. On fige alors la sortie
    corrigée du jour où elle a été écrite, pour qu'une régression future se
    voie. Ce n'est pas la même preuve, et ça ne doit pas se lire comme telle.
    """
    a, b = contre
    noms = [n for n, _, _ in cas]
    for n in (a, b):
        if n not in noms:
            raise SystemExit("GEL REFUSÉ — le contre-exemple nomme « %s », "
                             "qui n'est pas un cas de ce témoin" % n)
    sorties = {n: _texte(s, masque) for n, _, s in cas}
    if sorties[a] == sorties[b]:
        raise SystemExit("GEL REFUSÉ — le contre-exemple ne sépare rien : « %s » "
                         "et « %s » rendent la MÊME sortie. Un témoin qui ne "
                         "distingue pas deux cas ne prouve rien." % (a, b))
    DOSSIER.mkdir(exist_ok=True)
    doc = {
        "controle": nom,
        # LA DATE DE GEL SE MESURE, ELLE NE SE TAPE PAS. Elle était en dur —
        # « 2026-09-10 » — et un re-gel le 11 a produit un témoin qui
        # annonçait la veille tout en portant les dates du jour. `compare` s'en
        # sert pour relativiser : elle a donc relativisé de travers, et trois
        # contrôles verts sont passés au rouge à cause du champ censé les
        # protéger. Une provenance fausse est pire qu'une provenance absente.
        "gele_le": datetime.date.today().isoformat(),
        "commit_depot": _commit(),
        "origine": origine,
        "sources": {_chemin_public(s): _empreinte(s) for s in sources},
        "contre_exemple": [a, b],
        "cas": [{"nom": n, "entree": e, "sortie": sorties[n]} for n, e, _ in cas],
    }
    f = DOSSIER / (nom + ".json")
    f.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return f


def charge(nom):
    f = DOSSIER / (nom + ".json")
    if not f.exists():
        raise SystemExit("TÉMOIN ABSENT — %s. Le figer d'abord : %s --gel"
                         % (f, pathlib.Path(sys.argv[0]).name))
    return json.loads(f.read_text())


def _ou_ca_diverge(a, b, fenetre=140):
    """DIRE OÙ, PAS MONTRER LE DÉBUT. Deux sorties de dix kilo-octets qui
    diffèrent au sept-millième caractère se ressemblent parfaitement sur les
    huit cents premiers — et le contrôle rend alors deux blocs identiques en
    annonçant un écart, ce qui est la pire chose qu'un instrument puisse faire :
    avoir raison et paraître fou. Mesuré le 10/09/2026 sur le carnet.
    """
    k = 0
    for k in range(min(len(a), len(b))):
        if a[k] != b[k]:
            break
    else:
        k = min(len(a), len(b))
    d, f = max(0, k - fenetre // 2), k + fenetre
    return ("  écart au caractère %d (témoin %d o., rendu %d o.)\n"
            "  témoin …%s…\n  rendu  …%s…" % (k, len(a), len(b), a[d:f], b[d:f]))


def compare(nom, produit, masque=None, normalise=None):
    """COMPARE CE QUE LE PROGRAMME VIENT DE RENDRE AU TÉMOIN FIGÉ.

    `produit` : dict nom-de-cas -> sortie. Rend (écarts, ligne de témoin).

    `normalise(texte, côté)`, facultatif, s'applique aux DEUX côtés après les
    masques — `côté` vaut "temoin" ou "produit", parce qu'un contrôle peut
    vérifier une valeur du jour sur ce qu'il vient de produire, et pas sur ce
    qui a été figé un autre jour. Il sert à nommer par leur identité les
    valeurs qui dépendent de l'heure où l'on joue.
    """
    t = charge(nom)
    gele = datetime.date.fromisoformat(t["gele_le"])
    auj = datetime.date.today()
    attendu = {c["nom"]: _jour_de_reference(c["sortie"], gele) for c in t["cas"]}
    vu = {n: _jour_de_reference(_texte(v, masque), auj) for n, v in produit.items()}
    if normalise:
        attendu = {n: normalise(x, "temoin") for n, x in attendu.items()}
        vu = {n: normalise(x, "produit") for n, x in vu.items()}
    ecarts = []

    manquants = [n for n in attendu if n not in vu]
    surnumeraires = [n for n in vu if n not in attendu]
    if manquants:
        ecarts.append("CAS NON JOUÉS — le témoin en porte %d que le programme "
                      "n'a pas produits : %s" % (len(manquants), ", ".join(sorted(manquants))))
    if surnumeraires:
        ecarts.append("CAS INCONNUS DU TÉMOIN — %s. Le corpus a bougé depuis le "
                      "gel : refiger, ou corriger le corpus."
                      % ", ".join(sorted(surnumeraires)))
    for n in sorted(set(attendu) & set(vu)):
        if attendu[n] != vu[n]:
            ecarts.append("« %s »\n%s" % (n, _ou_ca_diverge(attendu[n], vu[n])))

    a, b = t["contre_exemple"]
    if a in vu and b in vu and vu[a] == vu[b]:
        ecarts.append("CONTRE-EXEMPLE MORT — « %s » et « %s » devaient rendre des "
                      "sorties DIFFÉRENTES et rendent la même. Le programme a "
                      "cessé de distinguer ces deux cas." % (a, b))

    ligne = ("témoin %s · %d cas figés au commit %s (origine %s) · "
             "contre-exemple %s ≠ %s"
             % (nom, len(attendu), t["commit_depot"][:8],
                t.get("origine", "python"), a, b))
    return ecarts, ligne
