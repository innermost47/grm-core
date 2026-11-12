# GRML : le langage du Global Relational Model

*[In English](GRML.md)*

GRML est le langage de la machine GRM (`vm/`). Un programme GRML ne dit pas quoi faire pas à pas : il dit ce qui est
lié à quoi. Les grandeurs sont des nœuds, les liens sont des relations, et la machine trouve toutes les valeurs qui
s'accordent avec toutes les relations à la fois, avec leur incertitude. Le temps, la mémoire, les choix et
l'apprentissage s'écrivent de la même façon.

Chaque exemple de cette page est un fichier de `vm/programs/` et il est exécuté par les tests (`vm/test_vm.py`) : ce
qui est écrit ici est ce que fait le langage.

Les mots du langage (`node`, `relate`, `observe`...) restent en anglais : un programme tourne partout, quelle que soit
la langue de l'interface. L'interface, elle, parle français avec `lang fr`.

- [Démarrage rapide](#démarrage-rapide)
- [Tutoriel](#tutoriel) : dix étapes, d'une relation à une machine qui apprend et se souvient
- [Référence](#référence) : chaque mot
- [Ce que la machine fait toute seule](#ce-que-la-machine-fait-toute-seule) : nœuds, relations, fusions
- [Les programmes](#les-programmes) : les fichiers, leur en-tête, la fenêtre des programmes
- [Le tick](#le-tick) : ce qui se passe à chaque battement de l'horloge
- [Les commandes de la machine](#les-commandes-de-la-machine), son aide et ses deux langues
- [Pièges](#pièges)
- [Limites](#limites)

## Démarrage rapide

```bash
python vm/grm_vm.py --blank
```
```
grm> lang fr
grm> observe distance = 100 ± 1%
grm> observe time = 9.58 ± 0.1%
grm> relate run: speed * time = distance
grm> ask speed
  speed = 10.4384  (± 0.00434 à l'intérieur)
```

Personne n'a dit à la machine de diviser : elle a trouvé la vitesse qui fait tenir la relation.

`±` peut s'écrire `+/-` (il n'est pas sur tous les claviers), et chaque mot a une forme abrégée (`obs`, `rel`,
`t`...) : `obs distance = 100 +/- 1%` est la même ligne. `help` liste les mots, `help MOT` en explique un avec un
exemple, et `tour` est une visite guidée en dix étapes.

## Tutoriel

### 1. Nœuds et relations (`programs/hello.grm`)

```
observe distance = 100 ± 1%     # m
observe time = 9.58 ± 0.1%      # s
relate run: speed * time = distance
output speed
```

Un **nœud** est une grandeur. Sauf indication contraire, il est **positif** et la machine le résout en log10 : une
relation produit (`*`, `/`, puissances `^`) devient alors une droite, et les valeurs peuvent aller de 1e-44 à 1e122
dans le même réseau. `speed` n'a jamais été déclaré : une relation qui nomme un nœud le crée.

Une **relation** sans `±` est exacte. Avec `± 1%` (ou `± 0.004 dex`), elle a droit à cet écart. Une **mesure**
(`observe`) est une donnée avec son incertitude, pas un point de départ : la machine la pèse face aux relations.

### 2. Les unités (`programs/fall.grm`)

```
input g positive [0 1 -2 0 0]        # m/s^2
input t positive [0 0 1 0 0]         # s
output height positive [0 1 0 0 0]   # m
relate fall: 2 * height = g * t^2
observe g = 9.81 ± 0.1%
observe t = 2 ± 0.1%
```

`[M L T Q K]` est la dimension d'un nœud : les puissances de la masse, de la longueur, du temps, de la charge et de
la température. Les valeurs sont données et lues en SI (`height` vaut 19.62). À l'intérieur, la machine compte dans
ses propres unités, où c, ħ, G et k_B valent 1 (pygrm.units, les « ticks ») : g y vaut 1.8e-51. Les constantes
fondamentales sont dans la façon dont la machine compte, pas dans des nœuds.

### 3. Grandeurs signées et sommes

```
var x = -3
relate shift: y = x + 10
```

Un nœud **signé** (`node x signed`, et tout `var`, `input`, `output`, `learn` sauf si `positive` est dit) peut être
négatif ou nul. Une relation avec `+` ou `-`, ou avec un nœud signé, est une **somme**. Les sommes sont des
multiplications : un x signé est l'exposant d'un e^x positif, et `y = x + 10` est e^y = e^x · e^10, le genre de
relation que la machine résout en log. Quand une somme nomme un nœud positif (`v1 = v0 - g * dt`, g positif), un
**convertisseur** lie g à son jumeau signé `~g` : la seule relation entre le monde des produits et celui des
exposants.

Un terme de somme peut multiplier plusieurs nœuds ou en élever un à une puissance (`z = x * y + x^2`) : une telle
relation est redessinée, toute seule, en droite autour de l'endroit où se trouvent ses nœuds, à chaque tour.

### 4. Une boucle (`programs/count.grm`)

```
var n = 0
output n
set n = n + 1 when n in -inf .. 9.5
```

Une **variable** (`var`) est une valeur que le réseau garde jusqu'à ce qu'elle soit réécrite. `set` l'écrit au
**tick** suivant (Entrée seule, `tick n`, l'horloge, une ligne de fichier). Ici n augmente de un à chaque tick et
s'arrête à 10 : la condition arrête la boucle.

### 5. Toutes les écritures d'un tick à la fois (`programs/fibonacci.grm`)

```
var a = 0
var b = 1
output b
set a = b
set b = a + b
```

Tous les `set` d'un tick sont calculés à partir des valeurs d'avant le tick, puis écrits ensemble : pas besoin de
variable temporaire. Après 10 ticks, b = 89.

### 6. Des choix (`programs/thermostat.grm`)

```
input outside = 5
var room = 15
var heater = 0
output room
output heater
set heater = 1 when room in -inf .. 19
set heater = 0 when room in 21 .. inf
set room = room + 3 * heater - 0.1 * room + 0.1 * outside
```

`when` fait qu'un `set`, ou n'importe quelle relation, ne tient que tant que ses conditions tiennent. Ici le
chauffage s'allume sous 19 et s'éteint au-dessus de 21, et garde son état entre les deux. Comme les écritures d'un
tick utilisent les valeurs d'avant, le chauffage réagit avec un tick de retard : la pièce oscille entre environ 17
et 23.

### 7. Un réseau appelé deux fois : une fonction (`programs/circles.grm`)

```
network circle(id, radius)
  observe r_{id} = {radius}
  relate area_{id}: area_{id} = pi * r_{id}^2
  output area_{id}
end
call circle(id=small, radius=1)
call circle(id=big, radius=3)
```

`network ... end` écrit un réseau qui n'est pas encore là. `call` l'insère, chaque `{param}` remplacé par ce que donne
l'appel : `area_small` et `area_big` sont deux réseaux dans le réseau. Un appel peut faire un peu d'arithmétique sur
les nombres (`{right}+0.25`). `use fichier.grm` dit toutes les instructions d'un fichier, et ses réseaux deviennent
appelables.

### 8. Apprendre (`programs/mean.grm`, `programs/fit.grm`)

```
learn mu = 0
input x
relate seen: x = mu ± 1
```
```
grm> load programs/numbers.csv
  200 lignes apprises
    mu: 0 -> 12.5113  (± 0.0707)
```

Un **poids** (`learn`) garde ce qu'il apprend. `load` donne chaque ligne d'un fichier aux entrées (une colonne est un
nœud), un tick par ligne. Avant qu'une nouvelle ligne soit entendue, les poids gardent ce que la ligne d'avant leur a
appris : chaque ligne compte une fois. Ici mu est la moyenne des 200 valeurs, et son incertitude vaut 1/√200 du ± 1
donné à chaque ligne.

Des poids qui partagent une relation apprennent ensemble, liens compris :

```
learn k = 0
learn c = 0
input x
input y
output y
relate model: y = k * x + c ± 0.5
```

Sur 100 points bruités de y = 3x + 2 (`programs/measures.csv`), cela donne exactement les moindres carrés (k =
2.99943, c = 2.02211). Ensuite `forget y`, `put x = 10`, `ask y` : la machine utilise ce qu'elle a appris.

### 9. Une machine de Minsky (`programs/double.grm`)

```
var s = 0          # l'état
input a = 5
var b = 0
set a = a - 1 when s in -0.5 .. 0.5 and a in 0.5 .. inf
set s = 1     when s in -0.5 .. 0.5 and a in 0.5 .. inf
set s = 9     when s in -0.5 .. 0.5 and a in -0.5 .. 0.5
set b = b + 1 when s in 0.5 .. 1.5
set s = 2     when s in 0.5 .. 1.5
set b = b + 1 when s in 1.5 .. 2.5
set s = 0     when s in 1.5 .. 2.5
```

Des compteurs, « ajouter un », « retirer un ou sauter si zéro » : une machine de Minsky, et les machines de Minsky
calculent tout ce que calcule un ordinateur. GRML est Turing-complet ; `vm/test_vm.py` écrit n'importe quel programme
de Minsky en GRML et exécute une addition et une multiplication.

### 10. Des relations que personne n'a écrites (`programs/falling.csv`)

```
grm> load programs/falling.csv
  40 lignes apprises
    trouvé tout seul : h = 4.90618 * t^2 (relation found_1, r² 0.999999 sur 40 lignes)
grm> forget h
grm> put t = 3
grm> ask h
  h = 44.1556
```

Une machine vierge, un fichier de hauteurs et de temps d'une chute, et aucune relation écrite : la machine trouve
h = K t² toute seule, avec K comme poids qui continue d'apprendre, et s'en sert. Rien n'est demandé à l'utilisateur :
voir [Ce que la machine fait toute seule](#ce-que-la-machine-fait-toute-seule).

### 11. La mémoire

`quit` endort la machine dans `vm/memory.json` : chaque nœud, relation, mesure, poids appris, et chaque message entre
eux. Le démarrage suivant repart de là, sans rien résoudre à nouveau. La nuit, la machine fusionne aussi ce qui est
une seule chose sous deux noms et relâche un peu ce qu'elle a appris (voir `vm/README.md`).

## Référence

### Lignes, noms, nombres
- Une instruction par ligne ; `#` commence un commentaire.
- Un nom : une lettre ou `_`, puis des lettres, des chiffres, des `_` (`speed`, `r_small`, `M_earth`). Les noms avec
  `__` ou qui commencent par `~` appartiennent à la machine (l'aide d'un `set`, le jumeau signé d'un nœud positif).
- Un nombre : `3`, `-2.5`, `6.674e-11`, `pi`, `e`, `tau`, `inf`, et un peu d'arithmétique (`3-0.25`, `2*pi`).
- `+/-` vaut `±`, n'importe où dans une ligne.
- Le premier mot d'une ligne peut s'écrire en abrégé :

  | abrégé | mot | abrégé | mot |
  |---|---|---|---|
  | `nd` | `node` | `cl` | `call` |
  | `rel` | `relate` | `lrn` | `learn` |
  | `obs` | `observe` | `inp` | `input` |
  | `fgt` | `forget` | `out` | `output` |
  | `kp` | `keep` | `net` | `network` |

  (`var`, `set`, `use`, `end`, `fuse` sont déjà courts.) Dans un fichier comme au prompteur : `rel fall: 2 * height =
  g * t^2 +/- 0.1%` est `relate fall: 2 * height = g * t^2 ± 0.1%`.

### Nœuds

| instruction | ce qu'elle crée |
|---|---|
| `node NOM [= valeur] [fixed] [signed] [[M L T Q K]]` | un nœud : positif (log10) sauf avec `signed` ; `fixed` ne bouge pas |
| `var NOM [= valeur] [positive] [[dim]]` | une variable : gardée jusqu'à ce qu'un `set` l'écrive |
| `input NOM [= valeur] [positive] [[dim]]` | un nœud que l'extérieur mesure (`put`, fichiers) |
| `output NOM [positive] [[dim]]` | un nœud que l'extérieur lit (affiché et entendu) |
| `learn NOM [= valeur] [positive]` | un poids : ce qu'il apprend reste |

`var`, `input`, `output` et `learn` sont signés sauf si `positive` est dit. Tout nœud peut prendre une dimension :
donné et lu en SI, compté à l'intérieur dans les unités de la machine (un nœud positif par un décalage de son log,
un nœud signé par une échelle).

**Ce qu'est un nœud, comme dans le cerveau.** Un nœud positif est tenu par son logarithme : son incertitude est
relative (loi de Weber : une différence se ressent en proportion de la taille), et son inverse est le même nœud (1/x
est -log x : une période et une fréquence sont un seul nœud). Un nœud signé est tenu par sa valeur ; donnée sans son
incertitude, elle est connue au millième d'elle-même (et jamais mieux qu'au millième d'une unité), relative elle
aussi. Là où le cerveau porte une grandeur signée sur deux canaux opposés (cellules ON et OFF, muscles agonistes et
antagonistes), le corps de la machine fait de même pour un humain : chaque sortie est vue et entendue comme deux
canaux opposés autour de zéro.

### Relations

```
relate NOM: GAUCHE = DROITE [± SIGMA] [when CONDITIONS]
```

- **Produit** : les deux côtés sont des produits de nombres et de nœuds avec des puissances (`*`, `/`, `^`), tous
  positifs. `± 1%` ou `± 0.004 dex` (ou un nombre seul : des dex). Exacte sans `±` (tenue à 1e-6 dex).
- **Somme** : un `+` ou un `-` entre des termes, un côté `0`, ou un nœud signé. `± 0.5` est dans l'unité propre de
  la relation (pas de %). Exacte sans `±` (tenue à 1e-6). Chaque terme : un nombre, des nœuds fixes et des nœuds
  libres ; un seul nœud libre à la puissance 1 fait un terme droit, davantage font que la relation se redessine.
- **Logarithme** : `relate NOM: L = ln(y)`, y positif, L signé : le convertisseur entre une grandeur et son exposant
  (une exponentielle y = A e^(k x) s'écrit `L = ln(y)` et `L = k * x + lnA`).
- `relate` à nouveau avec le même nom remplace la relation.

### Conditions

```
when NŒUD in BAS .. HAUT [and NŒUD in BAS .. HAUT ...]
```

`BAS` et `HAUT` sont des nombres (`-inf`, `inf` permis), écrits sans espaces. Une relation, un `set` ou un contact
avec des conditions ne tient que tant qu'elles tiennent toutes ; les conditions sont lues sur les valeurs actuelles.

### Mesures

| instruction | |
|---|---|
| `observe NOM = VALEUR [± SIGMA]` | nœud positif : `± 1%` ou `± 0.004 dex` (par défaut 0.01 dex) ; signé : `± 0.1` dans son unité ou `± 1%` de la valeur (par défaut 0.001) |
| `forget NOM` | la mesure s'en va |

### Contacts

```
keep NOM: NŒUD >= BORNE [when CONDITIONS]
keep NOM: NŒUD <= BORNE [when CONDITIONS]
```

Un contact pousse, en tenant le nœud à la borne, seulement tant que ses conditions tiennent et que ce que disent du
nœud ses autres relations dépasse la borne (un sol qui retient un corps qui tombe, pas un sol qui l'attire).

### Le temps

| instruction | |
|---|---|
| `set NOM = EXPRESSION [when CONDITIONS]` | à chaque tick, NOM prend la valeur d'EXPRESSION (un nœud, ou n'importe quelle somme ou produit) |

### Réseaux et fichiers

| instruction | |
|---|---|
| `network NOM(p1, p2, ...)` ... `end` | un réseau qu'on peut appeler ; `{p1}` dans ses lignes est remplacé à l'appel |
| `call NOM(p1=..., p2=...)` | les instructions du réseau, dites avec les valeurs données |
| `use FICHIER.grm` | toutes les instructions d'un fichier (relatif au fichier qui le dit) |

### Fusion

| instruction | |
|---|---|
| `fuse A B` | B était A sous un autre nom : chaque relation de B passe sur A, l'ancien nom atteint toujours A |
| `fuse A B inverse` | B était l'inverse de A (une période et une fréquence) : B est A^-1 partout, un seul nœud |

La machine fusionne aussi toute seule (après un fichier, la nuit) : deux entrées qui s'accordent ligne à ligne ; une
entrée qui est l'inverse d'une autre ligne à ligne ; une entrée qui reste immobile à la valeur d'un nœud connu à 1 %.

## Ce que la machine fait toute seule

Après chaque fichier qu'elle charge et la nuit, avec ce qu'elle a vu (les entrées de chaque instant, dans l'ordre,
et l'écart de chaque relation à tenir), la machine :
- **fusionne** ce qui est une seule chose sous deux noms : deux entrées qui s'accordent ligne à ligne ; une entrée qui
  est l'inverse d'une autre (elle devient ce nœud à la puissance -1) ; une entrée immobile à la valeur d'un nœud
  connu à 1 %. L'ancien nom atteint toujours le nœud.
- **écrit les relations que personne n'a écrites** (pygrm.discover), seulement entre des entrées que le réseau ne lie
  pas encore (ce qu'il dit déjà n'est pas dit deux fois), la plus simple qui tienne sur les lignes (r² d'au moins
  0.999) :
  - lois de puissance entre entrées positives : y = K x^p, y = K x^p z^q, avec des puissances simples (1, 2, 1/2, -1,
    3/2...) ; une loi en t^1.8 n'est pas transformée en t^2 ;
  - droites : y = a x + b ;
  - exponentielles et logarithmes : y = A e^(k x), y = a ln(x) + b (à travers un convertisseur `ln`) ;
  - sommes bâties sur des produits, quand rien de plus simple ne tient : E = a m v^2 + b m h + c. Chaque produit
    devient son propre nœud (`m_v2`, `h_m`), trouvé une fois et utilisé par chaque relation qui en a besoin ; la
    somme lie ces nœuds. Des produits, puis des sommes : les deux mondes de la machine, empilés ;
  - ce qui porte une entrée d'un instant au suivant : x(t) = a x(t-1) + c (une croissance ou une décroissance, avec
    son temps de doublement ou sa demi-vie) ou x(t) = a x(t-1) + b x(t-2) + c (une oscillation, avec sa période et
    son amortissement). Le passé devient des variables (`x_before`, `x_before2`) écrites à chaque tick, si bien que la
    machine poursuit la loi quand les données s'arrêtent : donnée une onde amortie, elle la continue toute seule.

  Les constantes de chaque relation trouvée sont des poids : elles continuent d'apprendre.
- **fait apparaître un nœud** là où une relation manque sans cesse les données :
  - si ses écarts se suivent (chacun annonce le suivant), un nœud qui change d'un instant à l'autre : une variable
    cachée avec sa propre loi, drift = rho drift_before, rho appris. La relation suit ce qu'elle ne pouvait pas voir
    (sur une droite qui cache une lente dérive : une surprise d'environ 0.3 sigma au lieu de 26) ;
  - sinon, s'ils restent du même côté bien au-delà du hasard (plus de 3 fois leur incertitude et plus de 1 sigma),
    un nœud constant avec la valeur qui manquait.

  Quand rien ne manque, rien n'est inventé.

Elle dit ce qu'elle a fait, en mots, après le fichier ou quand elle s'endort.

Les constantes qu'elle écrit (`K_1`, `a_2`...) portent la dimension qui équilibre leur relation : h = K t² avec t en
secondes donne K en s^-2. À l'intérieur, la machine compte dans ses propres unités (c = hbar = G = kB = 1), et une
relation dont les deux côtés ont des dimensions différentes y serait fausse de dizaines de décades.

Elle aussi :
- **ressent** : moins surprise qu'elle ne s'y attendait, c'est du plaisir ; plus, du déplaisir ; trouver quelque chose
  toute seule est une bouffée de plaisir, une erreur une bouffée de déplaisir. Ce qui marche sous le plaisir est
  gardé plus longtemps, et les poids qui ont appris sous lui gardent davantage de leur précision à travers la nuit
  (`mood`) ;
- **oublie** : sa place vient de l'hôte (le temps qu'un tick peut prendre à l'horloge où elle tourne, la mémoire
  disponible, divisés par ce que coûte un lien sur cette machine) ; chaque relation paie un loyer en bits par lien et
  par tick, dont le prix monte quand la place se fait rare, face à l'information qu'elle apporte (à quel point elle
  resserre ses nœuds) ; chaque nœud et chaque relation a aussi une trace de son usage. La nuit, ce qu'elle a trouvé
  et n'utilise plus, ou qui ne paie plus son loyer, s'en va ; au-delà de sa capacité, ce qui paie le moins part en
  premier. Jamais sa base, ses entrées, ses sorties (`prune` fait maintenant ce que fait une nuit ; `capacity N` fixe
  la place à la main, `capacity auto` la rend à l'hôte) ;
- **va chercher** : quand elle reste surprise et a cessé d'apprendre, elle cherche des relations et des nœuds
  manquants toute seule, sans attendre la nuit (curiosité), et dit ce qu'elle a trouvé ;
- **tend à s'épanouir** : la justesse (ses entrées ne la surprennent plus) fois la place (les liens qui restent), et
  le progrès de son apprentissage (`mood`).

## Les programmes

Un programme est un fichier d'instructions, `NOM.grm`, dans `vm/programs/` (ou ailleurs, donné par son chemin). Il
peut commencer par un en-tête, des lignes qui commencent par `#!` :

```
#! name: fall
#! does: a fall from rest, with units: the height from g and t
#! try: use programs/fall.grm ; ask height
```

`does` (ou `about`) dit ce qu'il fait, `try` ce qu'il faut taper pour le voir. Ce qu'il prend et ce qu'il donne n'est
pas écrit dans l'en-tête : `programs` le lit dans le programme lui-même (ses instructions `input`, `output` et
`network`). Sans en-tête, son premier commentaire dit ce qu'il fait. Les clés de l'en-tête restent en anglais, comme
les mots du langage ; ce qui suit les deux-points s'écrit dans la langue qu'on veut.

| commande | abrégé | |
|---|---|---|
| `programs` | `progs` | chaque programme, ce qu'il fait, ses entrées, sorties et réseaux |
| `read NOM` | `rd` | le programme ici, ses lignes numérotées |
| `run [NOM]` | | l'exécuter (sans nom : le programme de l'onglet courant) |
| `new NOM` | | un nouveau programme dans `programs/`, depuis un court modèle, ouvert pour être écrit |

Dans la fenêtre (`--window`), les programmes s'ouvrent dans une fenêtre à eux, un onglet par programme, colorés
pendant la frappe, et tout se fait au clavier :

| commande | abrégé | touche, dans la fenêtre des programmes | |
|---|---|---|---|
| `open NOM` | `o` | | un programme dans un nouvel onglet |
| `tab N` / `tab NOM` | | Ctrl+Tab : le suivant | aller à un onglet (`tab` seul : la liste) |
| `edit [NOM]` | `ed` | | écrire dans l'onglet |
| `save [FICHIER.grm]` | `sv` | Ctrl+S | enregistrer l'onglet (sous FICHIER) |
| `run` | | F5 | exécuter l'onglet, ligne par ligne : une ligne qui échoue passe en rouge |
| `find MOTS` | | Ctrl+F, puis Entrée / Maj+Entrée, Échap | chercher dans l'onglet |
| `close [N \| NOM]` | | Ctrl+W | fermer un onglet |
| | | Échap | retour au prompteur |

Une erreur dans un fichier (`use`, `run`) dit le fichier et la ligne ; quand ce fichier est ouvert, sa ligne passe
en rouge.

## Le tick

À chaque tick :
1. Si les entrées ont changé depuis le tick d'avant (ou si une ligne de fichier est donnée), les poids gardent ce
   que les entrées d'avant leur ont appris.
2. Le réseau se stabilise : chaque nœud et chaque relation qui a entendu quelque chose de nouveau répond, tour après
   tour, jusqu'à ce que plus rien de nouveau ne soit dit.
3. La machine mesure sa surprise : l'écart de chaque relation qui entend les entrées à tenir, en ses sigmas.
4. Chaque `set` dont les conditions tiennent est écrit, tous à la fois, à partir des valeurs de l'étape 2.

## Les commandes de la machine

Tapées au prompteur de `python vm/grm_vm.py` (ou dans la fenêtre, `--window`), à côté des instructions. Plusieurs
peuvent s'écrire sur une ligne, séparées par `;`.

| commande | abrégé | |
|---|---|---|
| Entrée | | un tick |
| `tick [n]` | `t` | n ticks |
| `put NOM = VALEUR [± SIGMA]` | | une entrée (en SI si elle a une dimension) |
| `load FICHIER.csv` / `FICHIER.json` | `ld` | des données, une ligne par tick ; les poids apprennent (JSON : des enregistrements, `{nom: [valeurs]}`, `{nom: valeur}`, un store grm-core) |
| `ask NŒUD` | | sa valeur |
| `outputs` | `outs` | les sorties et la surprise |
| `show` | | ce qu'est le réseau |
| `inspect NOM` | `ins` | ce que contient un nœud ou une relation (ce que la fenêtre montre sous la souris) |
| `master [n]` | `ms` | l'équation maîtresse maintenant, ou il y a n ticks (les 240 derniers sont gardés) |
| `check` | `chk` | tout ce qui ne va pas maintenant |
| `mood` | | le plaisir, ce qu'elle attend, l'épanouissement, le progrès, les liens, le loyer |
| `capacity [N \| auto]` | `cap` | les liens qu'elle peut tenir (auto : le budget de l'hôte) ; au-delà, elle oublie ce qui paie le moins |
| `prune` | | oublier maintenant ce qu'oublierait une nuit |
| `sleep [FICHIER]`, `wake [FICHIER]` | | la mémoire |
| `blank` | | tout oublier |
| `sound on` / `off` | | une voix par sortie |
| `clock HZ` | `clk` | des ticks tout seuls (fenêtre) |
| `programs`, `read`, `open`, `tab`, `edit`, `save`, `find`, `close`, `new`, `run` | | voir [Les programmes](#les-programmes) |
| `help [MOT]` | `h` | les mots de la machine par groupe ; un mot, avec sa forme et un exemple |
| `help on` / `off` | | le menu des mots sous le prompteur, pendant la frappe (fenêtre) |
| `tour [N \| end]` | | une visite guidée, une étape à la fois |
| `lang fr` / `lang en` | | la langue de l'interface |
| `quit` | `q` | la nuit : fusions, relations trouvées, oubli, puis le sommeil dans `vm/memory.json` |

Tab complète (instructions, commandes, nœuds, relations, fichiers, programmes, réseaux) ; dans la fenêtre, ce qui est
tapé est coloré, et Haut et Bas reviennent sur ce qui a été tapé. Les erreurs sont dites avec l'endroit où elles
sont : la ligne d'un fichier, un nom qui ressemble à un nom connu, un réseau qui ne se stabilise pas, des relations
qui se contredisent.

**L'aide pendant la frappe (fenêtre).** Sous le prompteur, une ligne dit ce qui est en train d'être tapé : le mot, ce
qu'il est en quelques mots, et sa forme (`rel = relate — une relation : produits, puissances, sommes   relate NAME:
left = right [+/- sigma] [when ...]`). En dessous, un menu : les mots de la machine dès la première lettre tapée
(avec leurs formes abrégées), puis les noms des nœuds et des relations dès la deuxième lettre, quand il n'y en a pas
plus de douze. Haut et Bas choisissent, Tab ou Entrée prend, Échap ferme. Le menu peut être désactivé (la case en
dessous, ou `help off`) ; la ligne reste.

**Deux langues.** L'interface parle anglais ou français : `lang fr`, `lang en`. La première fois, elle suit la
langue du système. Les mots de GRML (`node`, `relate`, `observe`...) restent en anglais dans les deux, si bien qu'un
programme écrit dans l'une tourne dans l'autre. Le choix, et celui du menu, sont gardés dans `vm/settings.json`, à
côté de la mémoire.

## Pièges

- **Dire deux fois la même chose.** Une relation qui découle d'autres (S · E_quant = E_stock écrite à côté des sept
  relations dont elle vient) n'apporte rien de nouveau, et autour de la boucle qu'elle ferme, les messages de la
  machine oscillent. Les relations qui le voient se calment ; le réseau se stabilise, plus lentement. Écrire ce qui
  est nouveau.
- **Un pourcentage sur une somme** : `± 1%` est pour les relations produit et les mesures ; une somme prend son sigma
  dans sa propre unité.
- **Des espaces dans les conditions** : `x in 3-0.25 .. 8` et non `x in 3 - 0.25 .. 8`.
- **`e`, `pi`, `tau`, `inf` sont des constantes en minuscules seulement** : `E` est un nom (une énergie), `e` est le
  nombre d'Euler.
- **Une faute de frappe est un nouveau nœud** : `relate r: heigt = g * t` crée un nœud `heigt`. La machine le dit
  (`attention : 'heigt' est un nouveau nœud ; vouliez-vous dire 'height' ?`). Il n'y a pas encore d'instruction pour
  retirer un nœud : `blank`, et redire le programme.
- **Après un tick, la machine est déjà à l'instant suivant** : une variable écrite par `set` (un compteur, le passé
  d'une oscillation) a sa nouvelle valeur, et ce qui en dépend suit. `ask` après un tick répond pour l'instant qui
  commence.

## Limites

- Sur des réseaux avec des boucles, les incertitudes données par la machine ne sont pas fiables ; les valeurs, si.
- Une fusion ne se défait pas encore ; les données d'un fichier sont prises comme exactes.
- L'apprentissage est exact pour les poids qui entrent droit dans leurs relations ; approché sinon.
- Les relations trouvées toute seule : parmi les formes ci-dessus, entre jusqu'à trois entrées (une somme : jusqu'à
  trois produits). La recherche regarde chaque entrée ; avec beaucoup d'entrées, il faudra regarder d'abord près de
  ce qui bouge ensemble.
- Un nœud signé est tenu par une seule valeur dans la machine ; les deux canaux opposés du cerveau sont dans son
  corps (ce qu'un humain voit et entend), pas dans ses processeurs.

## Exemples

| fichier | ce qu'il montre |
|---|---|
| `vm/programs/hello.grm` | des mesures, une relation, une inconnue trouvée |
| `vm/programs/fall.grm` | les unités : données et lues en SI |
| `vm/programs/count.grm` | une boucle qui s'arrête |
| `vm/programs/fibonacci.grm` | les écritures d'un tick, toutes à la fois |
| `vm/programs/thermostat.grm` | des choix, un état, une boucle avec l'extérieur |
| `vm/programs/circles.grm` | un réseau appelé deux fois |
| `vm/programs/universe.grm` | les constantes de l'univers et les sept relations de la chaîne : l'équation maîtresse que la machine fait remonter est S · Equant = Estock, sur 175 décades, jamais écrite (pygrm ≥ 0.5.1 ; `vm/test_universe_unbiased.py` la vérifie de sept façons) |
| `vm/programs/mean.grm` + `numbers.csv` | apprendre une moyenne |
| `vm/programs/fit.grm` + `measures.csv` | des poids qui apprennent ensemble |
| `vm/programs/double.grm` | une machine de Minsky |
| `vm/programs/falling.csv` | des données seulement : la machine trouve h = K t² toute seule |
| `vm/programs/wave.csv` | des données seulement : la machine trouve une oscillation (période 25) et la poursuit |
| `vm/base.grm` | la base avec laquelle la machine naît |
| `talk/universe.grm` | les constantes, les sept relations de la chaîne, `network` et `call` |
| `talk/examples/equation.grm` | S × E_quant = E_stock |
