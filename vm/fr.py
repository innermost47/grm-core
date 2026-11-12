# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The interface in French: the English template -> its French text (the same {fields})."""

FR = {
    # ---------------------------------------------------------------- help, tour
    "  The GRM machine is programmed with relations, not steps: a program is a network. Enter alone: one tick.":
        "  La machine GRM se programme avec des relations, pas des étapes : un programme est un réseau. Entrée "
        "seule : un tick.",
    "  help WORD: one word, with an example.  tour: a guided tour.  +/- can be written for ±.":
        "  help MOT : un mot, avec un exemple.  tour : une visite guidée.  +/- s'écrit à la place de ±.",
    " or ": " ou ",
    "#! name: {name}\n#! does: (what it does, in a few words)\n#! try: use programs/{name}.grm ; ask y\n#\n"
    "# A program is a network: write relations, not steps. Each line is a statement (help WORD for one).\n\n"
    "input x = 2\nrelate model: y = 3 * x +/- 0.1\noutput y\n":
        "#! name: {name}\n#! does: (ce qu'il fait, en quelques mots)\n#! try: use programs/{name}.grm ; ask y\n#\n"
        "# Un programme est un réseau : écrire des relations, pas des étapes. Chaque ligne est une instruction "
        "(help MOT pour l'une d'elles).\n\ninput x = 2\nrelate model: y = 3 * x +/- 0.1\noutput y\n",
    "'{n}' is a new node; did you mean {like}?": "'{n}' est un nouveau nœud ; vouliez-vous dire {like} ?",
    "'{word}' is not a word of the machine (help)": "'{word}' n'est pas un mot de la machine (help)",
    "'{word}' is not a word of the machine (help: the list)": "'{word}' n'est pas un mot de la machine (help : la liste)",
    "'{word}' is not a word of the machine; did you mean {like}?":
        "'{word}' n'est pas un mot de la machine ; vouliez-vous dire {like} ?",
    "(0: now; 240 ticks kept)": "(0 : maintenant ; 240 ticks gardés)",
    "A measured node: the network moves the others to fit it. +/- 1% for a positive quantity, +/- 0.1 in its own "
    "unit for a signed one.":
        "Un nœud mesuré : le réseau ajuste les autres pour s'y accorder. +/- 1% pour une grandeur positive, +/- 0.1 "
        "dans son unité pour une grandeur signée.",
    "A network, not steps": "Un réseau, pas des étapes",
    "A relation holds both ways. Give the height, forget the time, ask it:":
        "Une relation marche dans les deux sens. Donnez la hauteur, oubliez le temps, demandez-le :",
    "A relation holds both ways: give any of its nodes and the others are found. Products, powers and sums; +/- "
    "says how exact it is (none: exact).":
        "Une relation marche dans tous les sens : donnez n'importe lesquels de ses nœuds, les autres sont trouvés. "
        "Produits, puissances et sommes ; +/- dit à quel point elle est exacte (rien : exacte).",
    "A tick: the writes (set), then the network settles (every relation answers what is new, round after round).":
        "Un tick : les écritures (set), puis le réseau se stabilise (chaque relation répond à ce qui est nouveau, "
        "tour après tour).",
    "A variable is held until written again; set writes it at each tick. Enter alone is a tick. Type, then press "
    "Enter a few times:":
        "Une variable est gardée jusqu'à être réécrite ; set l'écrit à chaque tick. Entrée seule est un tick. Tapez, "
        "puis appuyez quelques fois sur Entrée :",
    "A weight (learn) keeps what it learns from the inputs. Type:":
        "Un poids (learn) garde ce qu'il apprend des entrées. Tapez :",
    "A weight: it keeps what each row of data taught it (load), and remembers it at the next session.":
        "Un poids : il garde ce que chaque ligne de données lui a appris (load), et s'en souvient à la session "
        "suivante.",
    "Ask": "Demander",
    "B was A under another name": "B était A sous un autre nom",
    "GRM machine": "Machine GRM",
    "GRM programs": "Programmes GRM",
    "Give it what is known (obs is short for observe, +/- for ±). Type:":
        "Donnez-lui ce qui est connu (obs abrège observe, +/- remplace ±). Tapez :",
    "Given from outside at each moment (put, load). Its surprise is what the network did not expect.":
        "Donnée de l'extérieur à chaque instant (put, load). Sa surprise est ce que le réseau n'attendait pas.",
    "Help": "Aide",
    "In the GRM machine you write relations between quantities; the network finds what is missing, in every "
    "direction. Type:":
        "Dans la machine GRM, on écrit des relations entre des grandeurs ; le réseau trouve ce qui manque, dans "
        "tous les sens. Tapez :",
    "In the middle of the window, the network: a round per node, a square per relation. Put the mouse on the square "
    "`fall`, or type:":
        "Au milieu de la fenêtre, le réseau : un rond par nœud, un carré par relation. Passez la souris sur le carré "
        "`fall`, ou tapez :",
    "Inside": "À l'intérieur",
    "JSON data: a list of records, {{name: [values]}} or {{name: value}}":
        "Données JSON : une liste d'enregistrements, {{nom: [valeurs]}} ou {{nom: valeur}}",
    "Learning": "Apprendre",
    "Look at it": "Le regarder",
    "Measurements": "Des mesures",
    "Opens a program in the programs window, a tab per program. tab N to go to one, edit to write in it, Ctrl+F to "
    "search, F5 to run it.":
        "Ouvre un programme dans la fenêtre des programmes, un onglet par programme. tab N pour y aller, edit pour y "
        "écrire, Ctrl+F pour chercher, F5 pour l'exécuter.",
    "Programs": "Les programmes",
    "Programs are files of statements. List them, open one in a tab (tab N to change), run it (F5 in its tab):":
        "Les programmes sont des fichiers d'instructions. Listez-les, ouvrez-en un dans un onglet (tab N pour "
        "changer), exécutez-le (F5 dans son onglet) :",
    "Talk to it in its words (relate, observe, var, set, learn, input, output...); Enter alone: one tick; Tab "
    "completes; help: the words; tour: a guided tour; lang fr / lang en.":
        "Parlez-lui avec ses mots (relate, observe, var, set, learn, input, output...) ; Entrée seule : un tick ; "
        "Tab complète ; help : les mots ; tour : une visite guidée ; lang fr / lang en.",
    "The lines up to `end` are a network that can be called, as a function: {p} in them is replaced by what the "
    "call gives.":
        "Les lignes jusqu'à `end` sont un réseau qu'on peut appeler, comme une fonction : {p} y est remplacé par ce "
        "que donne l'appel.",
    "The network has settled: ask what you did not give. Type:":
        "Le réseau s'est stabilisé : demandez ce que vous n'avez pas donné. Tapez :",
    "The other way": "Dans l'autre sens",
    "The tab can be written; Ctrl+S saves, F5 runs it (an error turns its line red), Esc comes back here.":
        "L'onglet devient modifiable ; Ctrl+S enregistre, F5 l'exécute (une erreur met sa ligne en rouge), Échap "
        "revient ici.",
    "Time": "Le temps",
    "What it feels (pleasure, flourishing), its master equation, what is wrong:":
        "Ce qu'il ressent (plaisir, épanouissement), son équation maîtresse, ce qui ne va pas :",
    "Written at the next tick, from the values before the tick: all the writes of a tick at once (loops, counters, "
    "choices with `when`).":
        "Écrit au tick suivant, à partir des valeurs d'avant le tick : toutes les écritures d'un tick à la fois "
        "(boucles, compteurs, choix avec `when`).",
    "help WORD for any word, help on / off for the menu while typing, lang fr / lang en. The tour is over: tour 1 "
    "to see it again.":
        "help MOT pour n'importe quel mot, help on / off pour le menu pendant la frappe, lang fr / lang en. La "
        "visite est finie : tour 1 pour la revoir.",
    "help on / off: the menu of words while typing (the line of help under the prompt stays).":
        "help on / off : le menu des mots pendant la frappe (la ligne d'aide sous le prompteur reste).",
    "pygrm's master invariant: the equation the network holds or implies that ties the widest span of scales.":
        "L'invariant maître de pygrm : l'équation que le réseau tient ou implique et qui relie le plus grand écart "
        "d'échelles.",
    "tour": "visite",
    "tour end: the end of the tour": "tour end : la fin de la visite",
    "tour: the next step": "tour : l'étape suivante",
    "the tour is over (tour 1: again)": "la visite est finie (tour 1 : à nouveau)",
    "type a statement or a command (Tab completes; help; tour: a guided tour)":
        "tapez une instruction ou une commande (Tab complète ; help ; tour : une visite guidée)",
    "typing help (a menu of words under the prompt)": "aide à la saisie (un menu de mots sous le prompteur)",
    "typing help off": "aide à la saisie désactivée",
    "typing help on": "aide à la saisie activée",
    "for example": "par exemple",
    "short": "abrégé",
    "usage": "usage",
    "{n} word(s): {words}": "{n} mot(s) : {words}",
    # groups of words
    "the network": "le réseau",
    "running": "exécuter",
    "looking": "regarder",
    "inside": "à l'intérieur",
    "programs": "programmes",
    "memory": "mémoire",
    "help": "aide",
    # what each word is (DOCS)
    "a quantity": "une grandeur",
    "a relation: products, powers, sums": "une relation : produits, puissances, sommes",
    "a measurement": "une mesure",
    "drop a measurement": "retirer une mesure",
    "a contact: a bound held": "un contact : une borne tenue",
    "a network to call (a function)": "un réseau à appeler (une fonction)",
    "put a network in, with its values": "insérer un réseau, avec ses valeurs",
    "every statement of a file": "toutes les instructions d'un fichier",
    "the end of a network": "la fin d'un réseau",
    "a variable, held until written again": "une variable, gardée jusqu'à être réécrite",
    "written at each tick: loops, choices": "écrit à chaque tick : boucles, choix",
    "a weight: it keeps what it learns": "un poids : il garde ce qu'il apprend",
    "an input, given at each moment": "une entrée, donnée à chaque instant",
    "an output: shown, drawn, heard": "une sortie : affichée, dessinée, entendue",
    "n ticks (Enter alone: one)": "n ticks (Entrée seule : un)",
    "give an input its value": "donner sa valeur à une entrée",
    "a file (no file: the open tab)": "un fichier (sans fichier : l'onglet ouvert)",
    "data row by row: it learns": "des données ligne par ligne : il apprend",
    "ticks by themselves (0: stop)": "des ticks tout seuls (0 : arrêt)",
    "a node's value": "la valeur d'un nœud",
    "the outputs and the surprise": "les sorties et la surprise",
    "what the network is": "ce qu'est le réseau",
    "what a node or a relation holds": "ce que contient un nœud ou une relation",
    "the master equation, now or n ticks ago": "l'équation maîtresse, maintenant ou il y a n ticks",
    "everything wrong now": "tout ce qui ne va pas maintenant",
    "pleasure, flourishing, room": "plaisir, épanouissement, place",
    "the links it may hold": "les liens qu'il peut tenir",
    "forget now what a night would": "oublier maintenant ce qu'oublierait une nuit",
    "to its memory": "dans sa mémoire",
    "back from its memory": "retour depuis sa mémoire",
    "forget everything": "tout oublier",
    "the programs and what they do": "les programmes et ce qu'ils font",
    "a program, in the answers": "un programme, dans les réponses",
    "a program in a tab": "un programme dans un onglet",
    "go to a tab": "aller à un onglet",
    "close a tab": "fermer un onglet",
    "a new program, in a tab": "un nouveau programme, dans un onglet",
    "write in a tab (Esc: back here)": "écrire dans un onglet (Échap : retour ici)",
    "save the tab (Ctrl+S)": "enregistrer l'onglet (Ctrl+S)",
    "search the tab (Ctrl+F)": "chercher dans l'onglet (Ctrl+F)",
    "hear the outputs": "entendre les sorties",
    "the language of the machine": "la langue de la machine",
    "help on a word; the typing help on or off": "l'aide sur un mot ; l'aide à la saisie activée ou non",
    "a guided tour, a step at a time": "une visite guidée, une étape à la fois",
    "to sleep, and goodbye": "au lit, et au revoir",
    # roles and kinds
    "a variable": "une variable",
    "a weight it learns": "un poids qu'il apprend",
    "an input": "une entrée",
    "an output": "une sortie",
    "input": "entrée",
    "output": "sortie",
    "var": "variable",
    "learn": "poids",
    "fixed": "fixe",
    "signed": "signé",
    "positive": "positif",
    "weight": "poids",
    "base": "base",
    "set": "écriture",
    "node": "nœud",
    "relation": "relation",
    "the base it was born with": "la base avec laquelle il est né",
    "written to it": "écrit par l'humain",
    "found by itself": "trouvé tout seul",
    "products and powers": "produits et puissances",
    "a sum": "une somme",
    "a logarithm": "un logarithme",
    "a contact": "un contact",
    "the same values, row by row": "les mêmes valeurs, ligne par ligne",
    "its inverse, row by row": "son inverse, ligne par ligne",
    "time": "temps",
    "none measured": "rien de mesuré",
    # ---------------------------------------------------------------- the language
    "not a number: '{text}'": "pas un nombre : '{text}'",
    "an empty side of a relation": "un côté vide dans une relation",
    "a product relation multiplies positive quantities: '{base}'":
        "une relation produit multiplie des grandeurs positives : '{base}'",
    "cannot read '{part}'": "impossible de lire '{part}'",
    "cannot read the condition '{c}' (node in lo .. hi)": "impossible de lire la condition '{c}' (nœud in bas .. haut)",
    "a dimension is [M L T Q K]: five powers": "une dimension s'écrit [M L T Q K] : cinq puissances",
    "relate NAME: left = right [+/- sigma] [when node in lo .. hi and ...]":
        "relate NOM: gauche = droite [+/- sigma] [when nœud in bas .. haut and ...]",
    "ln({y}): {y} is signed; a logarithm takes a positive quantity":
        "ln({y}) : {y} est signé ; un logarithme prend une grandeur positive",
    "{L} = ln({y}): {L} must be signed (a logarithm can be negative)":
        "{L} = ln({y}) : {L} doit être signé (un logarithme peut être négatif)",
    "relation {name}: {L} = ln({y}) (the converter between a quantity and its exponent)":
        "relation {name} : {L} = ln({y}) (le convertisseur entre une grandeur et son exposant)",
    "a relation needs at least one node": "une relation demande au moins un nœud",
    "relation {name} (a sum, kept as a product of exponentials): {text}":
        "relation {name} (une somme, gardée comme un produit d'exponentielles) : {text}",
    "relation {name}: {text}": "relation {name} : {text}",
    "{n} is signed: a product relation needs positive quantities":
        "{n} est signé : une relation produit demande des grandeurs positives",
    "keep NAME: node >= value [when node in lo .. hi and ...]":
        "keep NOM: nœud >= valeur [when nœud in bas .. haut and ...]",
    "contact {name}: {text}": "contact {name} : {text}",
    "network {name}({params}): {n} lines": "réseau {name}({params}) : {n} lignes",
    "node NAME [= value] [fixed] [signed]": "node NOM [= valeur] [fixed] [signed]",
    "a node is a positive quantity (solved in log10): say `signed` for a signed one":
        "un nœud est une grandeur positive (résolue en log10) : dites `signed` pour une grandeur signée",
    "node {name} = {value}": "nœud {name} = {value}",
    "observe NAME = value [+/- 1% | +/- 0.004 dex]": "observe NOM = valeur [+/- 1% | +/- 0.004 dex]",
    "a measurement needs a positive sigma": "une mesure demande un sigma positif",
    "observed {name} = {value} ± {s}": "mesuré {name} = {value} ± {s}",
    "observed {name} = {value} ± {s} dex": "mesuré {name} = {value} ± {s} dex",
    "{name} is a positive quantity: say `node {name} signed` first for a signed one":
        "{name} est une grandeur positive : dites d'abord `node {name} signed` pour une grandeur signée",
    "forgot the measurement of {name}": "mesure de {name} oubliée",
    "{name} is not measured": "{name} n'est pas mesuré",
    "network NAME(param, param...) ... end": "network NOM(param, param...) ... end",
    "call NETWORK(param=value, ...): no network '{name}'": "call RÉSEAU(param=valeur, ...) : pas de réseau '{name}'",
    "call {name}: missing {missing}": "call {name} : il manque {missing}",
    "called {name}({given})": "appelé {name}({given})",
    "no file {name}": "pas de fichier {name}",
    "in {file}, line {n}: {line}": "dans {file}, ligne {n} : {line}",
    "used {file}: {n} statements": "{file} lu : {n} instructions",
    "fuse A B [inverse]: B becomes A (or its inverse)": "fuse A B [inverse] : B devient A (ou son inverse)",
    "no node {name}": "pas de nœud {name}",
    "{name} is already one node": "{name} est déjà un seul nœud",
    "fuse {keep} {gone}: keep the positive one ({gone}) and fuse the signed one into it":
        "fuse {keep} {gone} : gardez le positif ({gone}) et fusionnez le signé dedans",
    "fuse {keep} {gone}: {gone} has been {v}, {keep} is positive":
        "fuse {keep} {gone} : {gone} a valu {v}, {keep} est positif",
    "fused: {gone} is {keep} (one node)": "fusionné : {gone} est {keep} (un seul nœud)",
    "fuse {keep} {gone} inverse: {n} has been {v}: an inverse is positive":
        "fuse {keep} {gone} inverse : {n} a valu {v} : un inverse est positif",
    "fuse {keep} {gone} inverse: {gone} is in {r}": "fuse {keep} {gone} inverse : {gone} est dans {r}",
    "fuse {keep} {gone} inverse: {gone} is written at each tick":
        "fuse {keep} {gone} inverse : {gone} est écrit à chaque tick",
    "fuse {keep} {gone} inverse: {gone} is a condition of {r}":
        "fuse {keep} {gone} inverse : {gone} est une condition de {r}",
    "fused: {gone} is {keep}^-1 (one node, its inverse included)":
        "fusionné : {gone} est {keep}^-1 (un seul nœud, son inverse compris)",
    "{word} NAME [= value] [positive] [M L T Q K]": "{word} NOM [= valeur] [positive] [M L T Q K]",
    "{name} is positive: its value must be above 0": "{name} est positif : sa valeur doit être au-dessus de 0",
    "set NAME = expression [when node in lo .. hi and ...]": "set NOM = expression [when nœud in bas .. haut and ...]",
    "at each tick {target} <- {expr}": "à chaque tick {target} <- {expr}",
    # ---------------------------------------------------------------- the runtime
    "fixed node {n} must be positive (or signed)": "le nœud fixe {n} doit être positif (ou signé)",
    "relation {name}: a term of a sum holds one free node, to the power 1 (give a product its own node: relate p: "
    "p = a * b)":
        "relation {name} : un terme de somme tient un seul nœud libre, à la puissance 1 (donnez à un produit son "
        "propre nœud : relate p: p = a * b)",
    "{name} is not a free node": "{name} n'est pas un nœud libre",
    "{path} is not a sleeping grm network": "{path} n'est pas un réseau grm endormi",
    "the sleeping state does not match its network": "l'état endormi ne correspond pas à son réseau",
    # ---------------------------------------------------------------- the machine
    "woke from {file} (tick {tick})": "réveillée depuis {file} (tick {tick})",
    "{file} not usable ({error}): ": "{file} inutilisable ({error}) : ",
    "born with its base ({n} points of the world)": "née avec sa base ({n} points du monde)",
    "a blank machine": "une machine vierge",
    "{note}.": "{note}.",
    "{name} is a positive quantity": "{name} est une grandeur positive",
    "network loaded: {nodes} nodes, {relations} relations": "réseau chargé : {nodes} nœuds, {relations} relations",
    "{n} left out": "{n} laissés de côté",
    "{n} rows learned": "{n} lignes apprises",
    "an oscillation: period {p} moments, {d} left each moment":
        "une oscillation : période {p} instants, {d} restant à chaque instant",
    "a decay: half-life {h} moments": "une décroissance : demi-vie {h} instants",
    "a growth: doubles in {d} moments": "une croissance : double en {d} instants",
    "found by itself: {text} (relation {name}, r² {r2} over {rows} rows{extra})":
        "trouvé tout seul : {text} (relation {name}, r² {r2} sur {rows} lignes{extra})",
    "a node nobody mentioned: {h} = {value} in {rel} (it kept missing the data on the same side: {t} sigma over "
    "{rows} rows)":
        "un nœud que personne n'a cité : {h} = {value} dans {rel} (elle manquait les données toujours du même côté : "
        "{t} sigma sur {rows} lignes)",
    "a node nobody mentioned, that changes: {h} in {rel} (its misses followed each other: each one {rho} of the one "
    "before, over {rows} rows)":
        "un nœud que personne n'a cité, qui change : {h} dans {rel} (ses écarts se suivaient : chacun {rho} du "
        "précédent, sur {rows} lignes)",
    "{gone} looks like {keep} ({why}) but stays apart: {error}":
        "{gone} ressemble à {keep} ({why}) mais reste à part : {error}",
    "fused by itself: {gone} is {keep}": "fusionné tout seul : {gone} est {keep}",
    "{mean} held still, {a} is {va}, {t} sigma apart": "{mean} immobile, {a} vaut {va}, à {t} sigma",
    # ---------------------------------------------------------------- the shell
    "tick {tick}: {rounds} rounds": "tick {tick} : {rounds} tours",
    "{n} ticks (now {tick}): {rounds} rounds": "{n} ticks (maintenant {tick}) : {rounds} tours",
    "{s} inside": "{s} à l'intérieur",
    "surprise": "surprise",
    "{s} sigma (how far the last inputs were from what it expected)":
        "{s} sigma (à quel point les dernières entrées s'écartaient de ce qu'il attendait)",
    "{nodes} nodes, {relations} relations, {sets} writes at each tick, {networks} networks":
        "{nodes} nœuds, {relations} relations, {sets} écritures à chaque tick, {networks} réseaux",
    "{p} processors, tick {tick}, round {round}": "{p} processeurs, tick {tick}, tour {round}",
    "asleep in {path}": "endormie dans {path}",
    "awake at tick {tick}": "réveillée au tick {tick}",
    "blank": "vierge",
    "sound on": "son activé",
    "sound off": "son coupé",
    "clock {hz} Hz": "horloge {hz} Hz",
    "now": "maintenant",
    "tick {tick}": "tick {tick}",
    "master equation, {when}{tick}: {text}": "équation maîtresse, {when}{tick} : {text}",
    "ties {span} decades of scale, residual {residual}": "relie {span} décades d'échelle, résidu {residual}",
    "implied by the network": "impliquée par le réseau",
    "written as one of its relations": "écrite comme l'une de ses relations",
    "pleasure": "plaisir",
    "displeasure": "déplaisir",
    "calm": "calme",
    "dopamine": "dopamine",
    "expects": "attend",
    "{s} sigma of surprise": "{s} sigma de surprise",
    "nothing yet (no input has surprised it)": "rien encore (aucune entrée ne l'a surpris)",
    "flourishing": "épanouissement",
    "accuracy": "justesse",
    "room": "place",
    "progress": "progrès",
    "how much its surprise is falling": "à quel point sa surprise baisse",
    "links": "liens",
    "{n} of {cap}": "{n} sur {cap}",
    "set by hand": "fixé à la main",
    "rent": "loyer",
    "{p} bits per link per tick": "{p} bits par lien et par tick",
    "{n} links of {cap}": "{n} liens sur {cap}",
    "rent: {p} bits per link per tick": "loyer : {p} bits par lien et par tick",
    "nothing measured on this host: {n} by default": "rien de mesuré sur cet hôte : {n} par défaut",
    "the host's budget: {parts}; limited by {limit}": "le budget de l'hôte : {parts} ; limité par {limit}",
    "nothing to forget": "rien à oublier",
    "no problem found": "aucun problème trouvé",
    "no node or relation {name}; did you mean {like}?": "pas de nœud ni de relation {name} ; vouliez-vous dire {like} ?",
    "no node or relation {name}": "pas de nœud ni de relation {name}",
    "no node {name}; did you mean {like}?": "pas de nœud {name} ; vouliez-vous dire {like} ?",
    "no program in {folder}": "aucun programme dans {folder}",
    "in": "entrées",
    "out": "sorties",
    "networks": "réseaux",
    "open NAME: in a tab; read NAME: here; run NAME: run it":
        "open NOM : dans un onglet ; read NOM : ici ; run NOM : l'exécuter",
    "no program {name}; did you mean {like}?": "pas de programme {name} ; vouliez-vous dire {like} ?",
    "no program {name} (programs: the list)": "pas de programme {name} (programs : la liste)",
    "{word}: in the window only (python vm/grm_vm.py --window); read NAME shows a program here":
        "{word} : seulement dans la fenêtre (python vm/grm_vm.py --window) ; read NOM affiche un programme ici",
    "open in tab {n}: {path}": "ouvert dans l'onglet {n} : {path}",
    "no tab open": "aucun onglet ouvert",
    "no tab {tab} (tab: the list)": "pas d'onglet {tab} (tab : la liste)",
    "no tab to close": "aucun onglet à fermer",
    "{path} already exists: open {name}": "{path} existe déjà : open {name}",
    "new program: {path}": "nouveau programme : {path}",
    "no tab open: edit NAME": "aucun onglet ouvert : edit NOM",
    "{n} found": "{n} trouvé(s)",
    "language: {lang}": "langue : {lang}",
    # ---------------------------------------------------------------- diagnose, mind
    "warning": "attention",
    "error": "erreur",
    "not a number: {names}": "pas un nombre : {names}",
    "in {names}": "dans {names}",
    "still moving: {names}": "bouge encore : {names}",
    "its values stand still but its messages keep growing more certain: exact relations that say the same thing "
    "twice around a loop, or contradict each other":
        "ses valeurs ne bougent plus mais ses messages deviennent toujours plus sûrs : des relations exactes qui "
        "disent deux fois la même chose dans une boucle, ou qui se contredisent",
    "around {names}": "autour de {names}",
    "the network did not settle in the rounds it was given": "le réseau ne s'est pas stabilisé dans les tours donnés",
    "swinging back and forth: {names}": "oscille d'avant en arrière : {names}",
    "relation {name} does not hold: {s} sigma ({text}). Two relations that contradict each other, or data that "
    "disagree with it.":
        "la relation {name} ne tient pas : {s} sigma ({text}). Deux relations qui se contredisent, ou des données "
        "en désaccord avec elle.",
    "{file}, line {n}, in {name}": "{file}, ligne {n}, dans {name}",
    "error inside the machine": "erreur à l'intérieur de la machine",
    "curiosity (surprised by {s} sigma, no longer learning)": "curiosité (surpris de {s} sigma, n'apprend plus)",
    "relation {name}": "relation {name}",
    "node {name}": "nœud {name}",
    "no room: {n} links for {cap}, and nothing left that may be forgotten":
        "plus de place : {n} liens pour {cap}, et plus rien qui puisse être oublié",
    "forgot {n} relation(s): {names}": "{n} relation(s) oubliée(s) : {names}",
    "and {names}": "et {names}",
    "only the last {n} ticks are kept (t - 0 .. t - {last})": "seuls les {n} derniers ticks sont gardés (t - 0 .. t - {last})",
    "cannot compute it: {error}": "impossible de la calculer : {error}",
    "unused": "inutilisée",
    "it no longer paid its rent": "elle ne payait plus son loyer",
    "no room left": "plus de place",
    "no master equation without pygrm": "pas d'équation maîtresse sans pygrm",
    "no relation yet": "pas encore de relation",
    "no closed relation found": "aucune relation fermée trouvée",
    # ---------------------------------------------------------------- the window, the cards
    "outputs": "sorties",
    "by hand": "à la main",
    "host: {limit}": "hôte : {limit}",
    "links {n} of {cap} ({limit})": "liens {n} sur {cap} ({limit})",
    "rent {p} bit a link a tick": "loyer {p} bit par lien et par tick",
    "tick {tick}   {p} processors   round {round}": "tick {tick}   {p} processeurs   tour {round}",
    "master equation ({when}{tick})": "équation maîtresse ({when}{tick})",
    "{span} decades of scale, residual {residual}": "{span} décades d'échelle, résidu {residual}",
    "holds": "tient",
    "strained": "tendue",
    "does not hold": "ne tient pas",
    "drag: move · wheel: zoom · double-click: back": "glisser : déplacer · molette : zoom · double-clic : retour",
    "cannot read it: {error}": "illisible : {error}",
    "tab N · edit · Ctrl+S save · F5 run · Ctrl+F find · Ctrl+Tab next · Esc back to the prompt":
        "tab N · edit · Ctrl+S enregistrer · F5 exécuter · Ctrl+F chercher · Ctrl+Tab suivant · Échap retour au "
        "prompteur",
    "no tab {tab}": "pas d'onglet {tab}",
    "closed {name}": "{name} fermé",
    "not saved": "non enregistré",
    "saved {path}": "enregistré : {path}",
    "ran {name}: {n} statements": "{name} exécuté : {n} instructions",
    "value": "valeur",
    "its unit inside": "son unité à l'intérieur",
    "last move": "dernier mouvement",
    "moving": "bouge",
    "dimension": "dimension",
    "measured": "mesuré",
    "also called": "aussi appelé",
    "its inverse": "son inverse",
    "in {n} relation(s)": "dans {n} relation(s)",
    "comes from": "vient de",
    "use": "usage",
    "learned under": "appris sous",
    "no relation {name}": "pas de relation {name}",
    "{s} sigma from holding": "à {s} sigma de tenir",
    "hold: it acts": "tiennent : elle agit",
    "do not hold: it is silent": "ne tiennent pas : elle se tait",
    "conditions": "conditions",
    "swings": "oscillations",
    "damped": "amortie",
    "weights": "poids",
    "last surprise": "dernière surprise",
    "{s} sigma ({n} moments kept)": "{s} sigma ({n} instants gardés)",
    "found by itself at tick {tick}: r² {r2} over {rows} rows": "trouvée toute seule au tick {tick} : r² {r2} sur "
                                                                 "{rows} lignes",
    "information": "information",
    "{bits} bits a tick; rent {rent} ({n} links)": "{bits} bits par tick ; loyer {rent} ({n} liens)",
    "pays its rent": "paie son loyer",
    "does not pay its rent": "ne paie pas son loyer",
}
