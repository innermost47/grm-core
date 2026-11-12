# GRML: the Global Relational Model Language

*[En français](GRML.fr.md)*

GRML is the language of the GRM machine (`vm/`). A GRML program does not say what to do step by step: it says what
is tied to what. Quantities are nodes, ties are relations, and the machine finds every value that agrees with all of
them at once, with its uncertainty. Time, memory, choices and learning are written the same way.

Every example of this page is a file of `vm/programs/` and is run by the tests (`vm/test_vm.py`): what is written
here is what the language does.

- [Quick start](#quick-start)
- [Tutorial](#tutorial): ten steps, from one relation to a machine that learns and remembers
- [Reference](#reference): every word
- [What the machine does by itself](#what-the-machine-does-by-itself): nodes, relations, fusions
- [Programs](#programs): files, their header, the programs window
- [The tick](#the-tick): what happens at each beat of the clock
- [The machine's commands](#the-machines-commands), its help and its two languages
- [Pitfalls](#pitfalls)
- [Limits](#limits)

## Quick start

```bash
python vm/grm_vm.py --blank
```
```
grm> observe distance = 100 ± 1%
grm> observe time = 9.58 ± 0.1%
grm> relate run: speed * time = distance
grm> ask speed
  speed = 10.4384  (± 0.00434 inside)
```

Nothing told the machine to divide: it found the speed that makes the relation hold.

`±` can be written `+/-` (it is not on every keyboard), and every word has a short form (`obs`, `rel`, `t`...):
`obs distance = 100 +/- 1%` is the same line. `help` lists the words, `help WORD` explains one with an example, and
`tour` is a guided tour of ten steps. `lang fr` puts the machine's interface in French (the words of the language stay
English, so a program runs anywhere).

## Tutorial

### 1. Nodes and relations (`programs/hello.grm`)

```
observe distance = 100 ± 1%     # m
observe time = 9.58 ± 0.1%      # s
relate run: speed * time = distance
output speed
```

A **node** is a quantity. Unless it is said otherwise, it is **positive** and the machine solves it in log10: a
product relation (`*`, `/`, powers `^`) is then a straight line, and the values can go from 1e-44 to 1e122 in the
same network. `speed` was never declared: a relation that names a node creates it.

A **relation** without `±` is exact. With `± 1%` (or `± 0.004 dex`) it is allowed that much. A **measurement**
(`observe`) is data with its uncertainty, not a starting point: the machine weighs it against the relations.

### 2. Units (`programs/fall.grm`)

```
input g positive [0 1 -2 0 0]        # m/s^2
input t positive [0 0 1 0 0]         # s
output height positive [0 1 0 0 0]   # m
relate fall: 2 * height = g * t^2
observe g = 9.81 ± 0.1%
observe t = 2 ± 0.1%
```

`[M L T Q K]` is the dimension of a node: the powers of mass, length, time, charge and temperature. Values are given
and read in SI (`height` reads 19.62). Inside, the machine counts in its own units, where c, ħ, G and k_B are 1
(pygrm.units, "ticks"): there, g is 1.8e-51. The fundamental constants are in how the machine counts, not in nodes.

### 3. Signed quantities and sums

```
var x = -3
relate shift: y = x + 10
```

A **signed** node (`node x signed`, and every `var`, `input`, `output`, `learn` unless `positive` is said) can be
negative or zero. A relation with `+` or `-`, or with a signed node, is a **sum**. Sums are multiplications: a signed
x is the exponent of a positive e^x, and `y = x + 10` is e^y = e^x · e^10, the kind of relation the machine solves
in log. When a sum names a positive node (`v1 = v0 - g * dt`, g positive), a **converter** ties g to its signed twin
`~g`: the one relation between the world of products and the world of exponents.

A term of a sum may multiply several nodes or raise one to a power (`z = x * y + x^2`): such a relation is redrawn,
by itself, as a straight one around where its nodes stand, at each round.

### 4. A loop (`programs/count.grm`)

```
var n = 0
output n
set n = n + 1 when n in -inf .. 9.5
```

A **variable** (`var`) is a value the network holds until it is written again. `set` writes it at the next
**tick** (Enter alone, `tick n`, the clock, a row of a file). Here n grows by one at each tick and stops at 10: the
condition stops the loop.

### 5. All the writes of a tick at once (`programs/fibonacci.grm`)

```
var a = 0
var b = 1
output b
set a = b
set b = a + b
```

All the `set` of a tick are computed from the values before the tick, then written together: no temporary
variable is needed. After 10 ticks, b = 89.

### 6. Choices (`programs/thermostat.grm`)

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

`when` makes a `set`, or any relation, hold only while its conditions hold. Here the heater goes on under 19 and off
above 21, and keeps its state in between. Because the writes of a tick use the values before it, the heater reacts
one tick late: the room swings between about 17 and 23.

### 7. A network called twice: a function (`programs/circles.grm`)

```
network circle(id, radius)
  observe r_{id} = {radius}
  relate area_{id}: area_{id} = pi * r_{id}^2
  output area_{id}
end
call circle(id=small, radius=1)
call circle(id=big, radius=3)
```

`network ... end` writes a network that is not there yet. `call` puts it in, with every `{param}` replaced by what
the call gives: `area_small` and `area_big` are two networks in the network. A call can do arithmetic on numbers
(`{right}+0.25`). `use file.grm` says every statement of a file, so its networks become callable.

### 8. Learning (`programs/mean.grm`, `programs/fit.grm`)

```
learn mu = 0
input x
relate seen: x = mu ± 1
```
```
grm> load programs/numbers.csv
  200 rows learned
    mu: 0 -> 12.5113  (± 0.0707)
```

A **weight** (`learn`) keeps what it learns. `load` gives each row of a file to the inputs (a column is a node), one
tick a row. Before a new row is heard, the weights keep what the row before taught them: every row counts once.
Here mu is the mean of the 200 values, and its uncertainty 1/√200 of the ± 1 each row was given.

Weights that share a relation learn together, links included:

```
learn k = 0
learn c = 0
input x
input y
output y
relate model: y = k * x + c ± 0.5
```

On 100 noisy points of y = 3x + 2 (`programs/measures.csv`) this gives exactly the least squares (k = 2.99943,
c = 2.02211). Then `forget y`, `put x = 10`, `ask y`: the machine uses what it has learned.

### 9. A Minsky machine (`programs/double.grm`)

```
var s = 0          # the state
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

Counters, "add one", "take one away or jump if zero": a Minsky machine, and Minsky machines compute everything a
computer computes. GRML is Turing complete; `vm/test_vm.py` writes any Minsky program in GRML and runs addition and
multiplication.

### 10. Relations nobody wrote (`programs/falling.csv`)

```
grm> load programs/falling.csv
  40 rows learned
    found by itself: h = 4.90618 * t^2 (relation found_1, r² 0.999999 over 40 rows)
grm> forget h
grm> put t = 3
grm> ask h
  h = 44.1556
```

A blank machine, a file of heights and times of a fall, and no relation written: the machine finds h = K t² by
itself, with K as a weight that goes on learning, and uses it. Nothing is asked of the user: see
[What the machine does by itself](#what-the-machine-does-by-itself).

### 11. Memory

`quit` puts the machine to sleep in `vm/memory.json`: every node, relation, measurement, learned weight, and every
message between them. The next start goes on from there, without solving anything again. At night the machine also
fuses what is one thing under two names and loosens a little what it has learned (see `vm/README.md`).

## Reference

### Lines, names, numbers
- One statement per line; `#` starts a comment.
- A name: a letter or `_`, then letters, digits, `_` (`speed`, `r_small`, `M_earth`). Names with `__` or starting with
  `~` are the machine's own (the helper of a `set`, the signed twin of a positive node).
- A number: `3`, `-2.5`, `6.674e-11`, `pi`, `e`, `tau`, `inf`, and a little arithmetic (`3-0.25`, `2*pi`).
- `+/-` is `±`, anywhere in a line.
- The first word of a line can be written short:

  | short | word | short | word |
  |---|---|---|---|
  | `nd` | `node` | `cl` | `call` |
  | `rel` | `relate` | `lrn` | `learn` |
  | `obs` | `observe` | `inp` | `input` |
  | `fgt` | `forget` | `out` | `output` |
  | `kp` | `keep` | `net` | `network` |

  (`var`, `set`, `use`, `end`, `fuse` are short already.) In a file as at the prompt: `rel fall: 2 * height = g *
  t^2 +/- 0.1%` is `relate fall: 2 * height = g * t^2 ± 0.1%`.

### Nodes

| statement | what it makes |
|---|---|
| `node NAME [= value] [fixed] [signed] [[M L T Q K]]` | a node: positive (log10) unless `signed`; `fixed` does not move |
| `var NAME [= value] [positive] [[dim]]` | a variable: held until a `set` writes it |
| `input NAME [= value] [positive] [[dim]]` | a node the outside measures (`put`, files) |
| `output NAME [positive] [[dim]]` | a node the outside reads (shown and heard) |
| `learn NAME [= value] [positive]` | a weight: what it learns stays |

`var`, `input`, `output` and `learn` are signed unless `positive` is said. Every node can take a dimension: given
and read in SI, counted inside in the machine's units (a positive node by a shift of its log, a signed one by a
scale).

**What a node is, as in the brain.** A positive node is held by its logarithm: its uncertainty is relative (Weber's
law: a difference is felt in proportion to the size), and its inverse is the same node (1/x is -log x: a period and
a frequency are one node). A signed node is held by its value; said without its uncertainty, it is known to a
thousandth of itself (and never better than a thousandth of a unit), relative too. Where the brain carries a signed
quantity on two opposed channels (ON and OFF cells, agonist and antagonist muscles), the machine's body does the same
for a human: each output is seen and heard as two opposed channels around zero.

### Relations

```
relate NAME: LEFT = RIGHT [± SIGMA] [when CONDITIONS]
```

- **Product**: both sides are products of numbers and nodes with powers (`*`, `/`, `^`), all positive.
  `± 1%` or `± 0.004 dex` (or a bare number: dex). Exact without `±` (held to 1e-6 dex).
- **Sum**: a `+` or `-` between terms, a `0` side, or a signed node. `± 0.5` is in the relation's own unit (no %).
  Exact without `±` (held to 1e-6). Each term: a number, fixed nodes, and free nodes; one free node to the power 1
  is a straight term, more make the relation redraw itself.
- **Logarithm**: `relate NAME: L = ln(y)`, y positive, L signed: the converter between a quantity and its exponent
  (an exponential y = A e^(k x) is `L = ln(y)` and `L = k * x + lnA`).
- `relate` again with the same name replaces the relation.

### Conditions

```
when NODE in LOW .. HIGH [and NODE in LOW .. HIGH ...]
```

`LOW` and `HIGH` are numbers (`-inf`, `inf` allowed), written without spaces. A relation, a `set` or a contact with
conditions holds only while they all hold; the conditions are read on the current values.

### Measurements

| statement | |
|---|---|
| `observe NAME = VALUE [± SIGMA]` | positive node: `± 1%` or `± 0.004 dex` (default 0.01 dex); signed: `± 0.1` in its unit or `± 1%` of the value (default 0.001) |
| `forget NAME` | the measurement goes |

### Contacts

```
keep NAME: NODE >= BOUND [when CONDITIONS]
keep NAME: NODE <= BOUND [when CONDITIONS]
```

A contact pushes, holding the node at the bound, only while its conditions hold and what the node's other
relations say of it is beyond the bound (a floor that holds a falling body, not one that pulls it down).

### Time

| statement | |
|---|---|
| `set NAME = EXPRESSION [when CONDITIONS]` | at each tick, NAME takes the value of EXPRESSION (a node or any sum or product) |

### Networks and files

| statement | |
|---|---|
| `network NAME(p1, p2, ...)` ... `end` | a network that can be called; `{p1}` in its lines is replaced at the call |
| `call NAME(p1=..., p2=...)` | the network's statements, said with the values given |
| `use FILE.grm` | every statement of a file (relative to the file that says it) |

### Fusion

| statement | |
|---|---|
| `fuse A B` | B was A under another name: every relation of B is moved to A, the old name keeps reaching A |
| `fuse A B inverse` | B was the inverse of A (a period and a frequency): B is A^-1 everywhere, one node |

The machine also fuses by itself (after a file, at night): two inputs that agree row by row; an input that is the
inverse of another row by row; an input that holds still at the value of a node known to 1 %.

## What the machine does by itself

After every file it loads and at night, with what it has seen (the inputs of each moment, in order, and how far each
relation was from holding), the machine:
- **fuses** what is one thing under two names: two inputs that agree row by row; an input that is the inverse of
  another (it becomes that node to the power -1); an input that holds still at the value of a node known to 1 %.
  The old name keeps reaching the node.
- **writes the relations nobody wrote** (pygrm.discover), only between inputs the network does not tie yet (what it
  already says is not said twice), the simplest that holds on the rows (r² at least 0.999):
  - power laws between positive inputs: y = K x^p, y = K x^p z^q, with simple powers (1, 2, 1/2, -1, 3/2...); a
    law in t^1.8 is not made into t^2;
  - straight lines: y = a x + b;
  - exponentials and logarithms: y = A e^(k x), y = a ln(x) + b (through a `ln` converter);
  - sums built on products, when nothing simpler holds: E = a m v^2 + b m h + c. Each product becomes its own node
    (`m_v2`, `h_m`), found once and used by every relation that needs it; the sum ties those nodes. Products, then
    sums: the two worlds of the machine, stacked;
  - what carries an input from one moment to the next: x(t) = a x(t-1) + c (a growth or a decay, with its doubling
    time or half-life) or x(t) = a x(t-1) + b x(t-2) + c (an oscillation, with its period and its damping). The past
    becomes variables (`x_before`, `x_before2`) written at each tick, so the machine carries the law on when the
    data stops: given a damped wave, it goes on with it by itself.

  The constants of every relation found are weights: they go on learning.
- **makes a node appear** where a relation keeps missing the data:
  - if its misses follow each other (each one tells the next), a node that changes from moment to moment: a hidden
    variable with its own law, drift = rho drift_before, rho learned. The relation follows what it could not see (on a
    line hiding a slow drift: a surprise of about 0.3 sigma instead of 26);
  - otherwise, if they stay on the same side far beyond chance (more than 3 times their uncertainty and more than 1
    sigma), a constant node with the value that was missing.

  When nothing is missing, nothing is invented.

It says what it did, in words, after the file or when it goes to sleep.

The constants it writes (`K_1`, `a_2`...) carry the dimension that balances their relation: h = K t² with t in
seconds gives K in s^-2. Inside, the machine counts in its own units (c = hbar = G = kB = 1), and a relation whose
two sides have different dimensions would be off by tens of decades there.

It also:
- **feels**: less surprised than it expected is pleasure, more is displeasure; finding something by itself is a burst
  of pleasure, an error a burst of displeasure. What works under pleasure is kept longer, and the weights that learned
  under it keep more of their precision through the night (`mood`);
- **forgets**: its room comes from the host (the time a tick may take at the clock it runs at, the memory
  available, divided by what a link costs there); every relation pays a rent in bits per link and per tick, whose
  price grows as room runs out, against the information it brings (how much it narrows its nodes); every node and
  relation also has a trace of its use. At night, what it found and no longer uses or no longer pays its rent goes;
  beyond its capacity, what pays the least goes first. Never its base, its inputs, its outputs (`prune` does now
  what a night does; `capacity N` sets the room by hand, `capacity auto` gives it back to the host);
- **goes looking**: when it stays surprised and has stopped learning, it looks for relations and missing nodes by
  itself, without waiting for the night (curiosity), and says what it found;
- **tends to flourish**: accuracy (its inputs no longer surprise it) times room (links left), and the progress of its
  learning (`mood`).

## Programs

A program is a file of statements, `NAME.grm`, in `vm/programs/` (or anywhere, given by its path). It may begin with
a header, lines starting with `#!`:

```
#! name: fall
#! does: a fall from rest, with units: the height from g and t
#! try: use programs/fall.grm ; ask height
```

`does` (or `about`) says what it does, `try` what to type to see it. What it takes and gives is not written in the
header: `programs` reads it from the program itself (its `input`, `output` and `network` statements). Without a
header, its first comment says what it does.

| command | short | |
|---|---|---|
| `programs` | `progs` | every program, what it does, its inputs, outputs and networks |
| `read NAME` | `rd` | the program here, its lines numbered |
| `run [NAME]` | | run it (no name: the program of the current tab) |
| `new NAME` | | a new program in `programs/`, from a short template, open to be written |

In the window (`--window`), programs open in a window of their own, a tab per program, coloured as they are typed,
and everything is done from the keyboard:

| command | short | key, in the programs window | |
|---|---|---|---|
| `open NAME` | `o` | | a program in a new tab |
| `tab N` / `tab NAME` | | Ctrl+Tab: the next one | go to a tab (`tab` alone: the list) |
| `edit [NAME]` | `ed` | | write in the tab |
| `save [FILE.grm]` | `sv` | Ctrl+S | save the tab (as FILE) |
| `run` | | F5 | run the tab, line by line: a line that fails turns red |
| `find WORDS` | | Ctrl+F, then Enter / Shift+Enter, Esc | search the tab |
| `close [N \| NAME]` | | Ctrl+W | close a tab |
| | | Esc | back to the prompt |

An error in a file (`use`, `run`) says the file and the line; when that file is open, its line turns red.

## The tick

At each tick:
1. If the inputs have changed since the tick before (or a file row is given), the weights keep what the inputs
   before taught them.
2. The network settles: every node and relation that has heard something new answers, round after round, until
   nothing new is said.
3. The machine measures its surprise: how far each relation that hears the inputs is from holding, in its sigmas.
4. Every `set` whose conditions hold is written, all at once, from the values of step 2.

## The machine's commands

Typed at the prompt of `python vm/grm_vm.py` (or in the window, `--window`), next to the statements. Several can be
written on one line, separated by `;`.

| command | short | |
|---|---|---|
| Enter | | one tick |
| `tick [n]` | `t` | n ticks |
| `put NAME = VALUE [± SIGMA]` | | an input (in SI if it has a dimension) |
| `load FILE.csv` / `FILE.json` | `ld` | data, one row a tick; the weights learn (JSON: records, `{name: [values]}`, `{name: value}`, a grm-core store) |
| `ask NODE` | | its value |
| `outputs` | `outs` | the outputs and the surprise |
| `show` | | what the network is |
| `inspect NAME` | `ins` | what a node or a relation holds (what the window shows under the mouse) |
| `master [n]` | `ms` | the master equation now, or n ticks ago (the last 240 are kept) |
| `check` | `chk` | everything that is wrong now |
| `mood` | | pleasure, what it expects, flourishing, progress, links, rent |
| `capacity [N \| auto]` | `cap` | the links it may hold (auto: the host's budget); beyond, it forgets what pays the least |
| `prune` | | forget now what a night would forget |
| `sleep [FILE]`, `wake [FILE]` | | memory |
| `blank` | | forget everything |
| `sound on` / `off` | | a voice per output |
| `clock HZ` | `clk` | ticks by themselves (window) |
| `programs`, `read`, `open`, `tab`, `edit`, `save`, `find`, `close`, `new`, `run` | | see [Programs](#programs) |
| `help [WORD]` | `h` | the words of the machine by group; one word, with its form and an example |
| `help on` / `off` | | the menu of words under the prompt, while typing (window) |
| `tour [N \| end]` | | a guided tour, a step at a time |
| `lang fr` / `lang en` | | the language of the interface |
| `quit` | `q` | the night: fusions, relations found, forgetting, then sleep in `vm/memory.json` |

Tab completes (statements, commands, nodes, relations, files, programs, networks); in the window, what is typed is
coloured, and Up and Down go back through it. Errors are said with where they are: a file's line, a name that looks
like a known one, a network that does not settle, relations that contradict each other.

**Help while typing (window).** Under the prompt, one line says what is being typed: the word, what it is in a few
words, and its form (`rel = relate — a relation: products, powers, sums   relate NAME: left = right [+/- sigma]
[when ...]`). Under it, a menu: the words of the machine from the first letter typed (with their short forms), then
the names of nodes and relations from the second letter, when there are no more than twelve of them. Up and Down
choose, Tab or Enter takes, Esc closes. The menu can be turned off (the box under it, or `help off`); the line stays.

**Two languages.** The interface speaks English or French: `lang fr`, `lang en`. The first time, it follows the
language of the system. The words of GRML (`node`, `relate`, `observe`...) stay English in both, so a program written
in one runs in the other. The choice, and that of the menu, are kept in `vm/settings.json`, next to the memory.

## Pitfalls

- **Saying the same thing twice.** A relation that follows from others (S · E_quant = E_stock written next to the
  seven relations it comes from) brings nothing new, and around the loop it closes, the machine's messages swing.
  The relations that see it calm themselves down; the network settles, more slowly. Write what is new.
- **A percent on a sum**: `± 1%` is for product relations and measurements; a sum takes its sigma in its own unit.
- **Spaces in conditions**: `x in 3-0.25 .. 8` and not `x in 3 - 0.25 .. 8`.
- **`e`, `pi`, `tau`, `inf` are constants in lower case only**: `E` is a name (an energy), `e` is Euler's number.
- **A typo is a new node**: `relate r: heigt = g * t` makes a node `heigt`. The machine says it (`'heigt' is a new
  node; did you mean 'height'?`). There is no statement yet to remove a node: `blank`, and say the program again.
- **After a tick, the machine is already at the next moment**: a variable written by `set` (a counter, the past of
  an oscillation) has its new value, and what depends on it follows. `ask` after a tick answers for the moment that
  begins.

## Limits

- On networks with loops the uncertainties given by the machine are not reliable; the values are.
- A fusion is not undone yet; data from a file is taken as exact.
- Learning is exact for weights that enter their relations straight; approached otherwise.
- Relations found by itself: among the forms above, between up to three inputs (a sum: up to three products). The
  search looks at every input; with many inputs it will have to look first near what moves together.
- A signed node is held by one value in the machine; the two opposed channels of the brain are in its body (what a
  human sees and hears), not in its processors.

## Examples

| file | what it shows |
|---|---|
| `vm/programs/hello.grm` | measurements, a relation, an unknown found |
| `vm/programs/fall.grm` | units: given and read in SI |
| `vm/programs/count.grm` | a loop that stops |
| `vm/programs/fibonacci.grm` | the writes of a tick, all at once |
| `vm/programs/thermostat.grm` | choices, a state, a loop with the outside |
| `vm/programs/circles.grm` | a network called twice |
| `vm/programs/universe.grm` | the constants of the universe and the seven relations of the chain: the master equation the machine brings up is S · Equant = Estock, over 175 decades, never written (pygrm ≥ 0.5.1; `vm/test_universe_unbiased.py` checks it seven ways) |
| `vm/programs/mean.grm` + `numbers.csv` | learning a mean |
| `vm/programs/fit.grm` + `measures.csv` | weights that learn together |
| `vm/programs/double.grm` | a Minsky machine |
| `vm/programs/falling.csv` | data only: the machine finds h = K t² by itself |
| `vm/programs/wave.csv` | data only: the machine finds an oscillation (period 25) and carries it on |
| `vm/base.grm` | the base the machine is born with |
| `talk/universe.grm` | the constants, the seven relations of the chain, `network` and `call` |
| `talk/examples/equation.grm` | S × E_quant = E_stock |
