# GRM Core

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23964101.svg)](https://doi.org/10.5281/zenodo.23964101)

> **Work in progress.** The engine, the tests and the guitar simulator work and are tested, but the project is young: APIs, values and hypotheses may still change.

**GRM Core** is the computing heart of the **Global Relational Model** (GRM), an attempt to describe physical systems through relations rather than objects. Each quantity is a node, each relation between quantities is an equation, and the whole network is solved at once, with the uncertainty of every input propagated to every result.

This repository contains:

| File | What it is |
|---|---|
| [`pygrm`](https://pypi.org/project/pygrm/) | The relational solver, now its own package: `pip install pygrm` ([repository](https://github.com/innermost47/pygrm)) |
| `equation/` | **The equation between the data**: one network of 199 quantities (cosmos, atoms, planets, a guitar, a voice) brings up S × Equant = Estock, the quantum and gravity in one loop, and shows how it found it |
| `web/` | **The Relational Universe** ([live](https://simulation.anthony-charretier.fr)): from the Big Bang to the end of time in the browser (3D, music), every number held by one GRM network (`grm.js`, the JavaScript port) |
| `grm_hidden_node.py` | **A node nobody mentioned**: the network sees that something is missing, makes the missing node emerge (where it acts, how large it is), and refuses to invent one when nothing is missing |
| `grm_tao.py` | **From the 0 the 1, from the 1 the 2...**: are the particle masses harmonics born in cascade from two seeds? Three readings of "relation" (spiral, intermodulation, trinity), each judged against random spectra |
| `grm_loop.py` | **A loop without a seed**: three waves, the full and the void in balance for ever. Predicts the tau from the electron and the muon, and makes a dated bet on the neutrino masses ([predictions/](predictions/)) |
| `grm_world.py` | **The world economy as a network of zeros**: the current accounts of all the countries should add up to zero and do not; where the missing node sits (trade, not income), what carries it, and a small dated bet against the IMF |
| `grm_carbon.py` | **The carbon of the Earth as a network of zeros**: where the global CO2 budget does not close, and which estimates are least consistent with the others (Global Carbon Budget 2025) |
| `grm_explorer.py` | The explorer: write a network with forms or JSON, solve it, see at once if it is valid; presets of known and open problems (`grm_presets.py`); missing nodes that emerge where the network is in tension, looked up in a bank of known numbers (`grm_bank.py`) |
| `test_grm.py` | A hardcore test battery: 113 tests, plus a validation protocol for full models |
| `grm_model.py` | The full GRM physics network (147 quantities, 113 relations, 55 measurements), exported from the web model |
| `grm_sat.py` | Random 3-SAT written as a GRM network (one relation per clause), with a WalkSAT baseline |
| `grm_tsp.py` | The travelling salesman as a GRM network: an elastic ring pulled between cities and its own length |
| `grm_text.py` | Sentence categories without any training: a table of example sentences and their categories, and one small GRM network per new sentence |
| `grm_matter.py` | **GRM Matter**: from the quantum constants and Z alone to ionization energies, then the density and stiffness of simple metals |
| `grm_rain.py` | **GRM Rain**: the sound of every drop falling on water (drag, impact, trapped bubble), used by GRM Water |
| `grm_water.py` | **GRM Water**: a basin of liquid to play with (drops, finger, rain, paddle); every wave swings and dies as a GRM network says |
| `grm_brain.py` | **GRM Brain**: a brain that learns while it discovers a maze, with a memory of tensions; watch its network form |
| `grm_scales.py` | **GRM Scales**: from the forces to the classical world and back: atoms, rock, Jupiter, the Sun, asteroids and mountains as pairs in tension |
| `grm_voice.py` | **GRM Voice**: a voice made of relations. Lungs, vocal folds, airflow, vocal tract, velum, nose and lips are GRM networks; it says "Bonjour Anthony. Je suis le réseau." |
| `grm_pong.py` | **GRM Pong**: two paddles that play by themselves, each one deciding with two small GRM networks |
| `talk/` | **grm talk**: talk to a network from a terminal (node, relate, observe, keep, network, call, use, ask, why, what-if), watch it work, put it to sleep and wake it; a relational machine where every node and relation is a processor; the constants of the universe and the seven relations as a base (`universe.grm`) |
| `vm/` | **The GRM machine**: a virtual machine that is one GRM network: a blank network that is the program, the memory and the calculator at once, a Turing-complete language, GRML ([docs/GRML.md](docs/GRML.md)), weights that learn from CSV or JSON files, a memory kept between sessions, and a body (keyboard and files in, outputs shown and heard by a human) |
| `grm_guitar.py` | **GRM Guitar**: a guitar simulated as one object: strings, bridge, top, air, palm, fingers and the player's arm are all GRM networks. VST3 plugin (work in progress): [grm-guitar-vst](https://github.com/innermost47/grm-guitar-vst) |

The cosmology and particle-physics model this engine was built for is presented at [grm.anthony-charretier.fr](https://grm.anthony-charretier.fr), with its own repository: [innermost47/GRM](https://github.com/innermost47/GRM).

![GRM Guitar](docs/grm_guitar.png)

### Listen to the guitar model
Every sound below was rendered by `grm_guitar.py`, from the GRM networks only (no samples):

| Sound | What you hear |
|---|---|
| [strum_pick.wav](docs/audio/strum_pick.wav) | a G chord strummed down with a 0.71 mm pick |
| [strum_fingers.wav](docs/audio/strum_fingers.wav) | the same chord strummed with the fingers: softer release, rounder sound |
| [folk_loop_pick.wav](docs/audio/folk_loop_pick.wav) | C – Am – Em – G, folk strumming pattern played three times by the player network (no two strokes alike), with the fingers lifting, landing and rubbing between chords |
| [folk_loop_no_finger_noise.wav](docs/audio/folk_loop_no_finger_noise.wav) | the same loop without finger noise, to compare |
| [travis_fingers.wav](docs/audio/travis_fingers.wav) | C – Am, Travis picking (alternating bass) with the fingers |
| [bach_prelude_two_grm_guitars.wav](docs/audio/bach_prelude_two_grm_guitars.wav) | Bach, Prelude of the Cello Suite No. 1 (BWV 1007), two GRM guitars in a church: Bach's line note for note on the left, the harmony of each bar on the right (bass and chord, strums, palm-muted eighths, wide strums). `python demos/bach_two_guitars.py` |
| [palm_muted_rock.wav](docs/audio/palm_muted_rock.wav) | a power-chord riff at 120 BPM, muted by the palm network (skin on the strings near the bridge) |

---

## The idea

The GRM starts from one principle: a quantity only has meaning through its relations with other quantities. Pairs of opposites (hot and cold, full and empty, beginning and end) become numerical relations, and the relations are wired together into a network.

The engine does not explain *why* things are the way they are. It connects known elements, then submits the network to one test: **when a measurement is hidden, can the rest of the network recover it?**

The guitar simulator applies the same method to a concrete object. Every place where two things meet (string and fret, pick and string, finger and winding, air and wood) is written as a small network of relations, and the sound comes out of what those networks compute.

---

## The engine (`pygrm`)

The engine is published on PyPI as [pygrm](https://pypi.org/project/pygrm/) (one file, NumPy optional):

```bash
pip install pygrm            # pure Python
pip install pygrm[fast]      # with NumPy
```

Every script of this repository imports it with `from pygrm import GlobalRelationalNetwork`.

### Nodes
- **positive quantities** (default), handled in log space: `x = log10(value)`. Values from 1e-44 to 1e122 coexist without loss.
- **signed quantities** (`"scale": "lin"`), handled as raw values: charges, curvature, equation of state.

```python
nodes = {
    "c": {"guess": 2.99792458e8, "fixed": True},   # a constant
    "m": {"guess": 1.0},                           # an unknown
    "w0": {"guess": -1.0, "scale": "lin"},         # a signed unknown
}
```

### Relations
| Type | Form | Example |
|---|---|---|
| log-linear (default) | `sum(coeff * log10(node)) = rhs` | `E = m c^2` -> `{"terms": {"E": 1, "m": -1, "c": -2}, "rhs": 0}` |
| `sum` | `sum(coeff * value^p) = K` | `Omega_b + Omega_c + Omega_L = 1` |
| `fn` | `f(values) = 0`, any equation | Koide, cosmological ages |

Each relation has a `sigma` (its tolerance, in dex for log-linear relations). A `rhs` may itself be a function of the current values.

### Measurements
Measurements are data with an uncertainty, not starting points:

```python
from pygrm import GlobalRelationalNetwork

net = GlobalRelationalNetwork(nodes, relations)
out = net.solve(measured_dict={"m": 2.0, "H0": (70.0, 0.01)})   # value, or (value, sigma in dex)
```

### Results
| Key | Meaning |
|---|---|
| `values` | best estimate of every node |
| `sigma_dex`, `uncertainty` | 1-sigma uncertainty (dex, and relative; absolute for signed nodes) |
| `undetermined` | nodes nothing determines: their value is only the starting point, not a prediction |
| `relation_pulls` | residual of every relation in sigma |
| `covariance`, `cost`, `reduced_chi2`, `converged`, `iterations` | the rest of the fit |

`leave_one_out(measured)` hides each measurement in turn and predicts it from the rest.

### Numerics
- weighted least squares solved by **QR factorisation**, not normal equations, so relations as tight as 1e-9 coexist with loose measurements;
- purely log-linear networks are solved exactly in a few steps;
- networks with sums or functions use **Levenberg-Marquardt**: Gauss-Newton with backtracking first, then adaptive damping; a warm start from the log-linear part of the network; a finite-difference Jacobian for functions;
- if a very tight `sum` or `fn` relation makes every step crawl and the solve does not converge, the core solves again by **continuation**: that relation loosened to sigma 1e-2, then tightened by a factor 100 per stage down to its own sigma, and keeps the better end point. It shares the iteration budget of the direct solve between its stages, can be turned off with `continuation=False`, and networks that converge directly are not touched;
- points outside the domain of a relation (the square root of a negative number, for example) are rejected cleanly;
- a very weak ridge keeps undetermined directions finite without biasing the determined ones;
- unknown node names, non-positive values in log space and invalid sigmas raise errors.

---

## The equation between the data (`equation/`)

```bash
cd equation
python trace_derivation.py           # the chain of relations the network took (1 second)
python test_equation.py              # the equation against data: four tests (a few seconds)
python equation_wave.py              # the wave of the equation over a cycle (picture)
```

Nothing new was measured. One GRM network holds 199 quantities already known (cosmology, the Planck units, atoms,
planets, rock, a guitar, a voice), 123 relations and 98 measurements (`data/grm_network_fully_enriched.json`). Solved
and asked for the invariant that ties the widest span of scales together (pygrm ≥ 0.5.1: the equations the network
implies between pairs and triples of its nodes, a node that is a pure number times another counted as one scale), it
brings up, over 175 decades:

```math
S \cdot E_{quant} = E_{stock}
\qquad
S = \frac{\pi}{(H\,t_P)^2} \approx 10^{122},\quad
E_{quant} = \frac{\hbar H}{2\pi} \approx 10^{-53}\ \text{J},\quad
E_{stock} = \frac{c^5}{2 G H} \approx 10^{70}\ \text{J}
```

S is the entropy of the horizon (its area in Planck cells), E_quant the energy of the horizon's temperature (the
quantum, ħ only), E_stock the energy that fills the horizon (gravity, G only). The equation holds for any H: it ties the
quantum and gravity through S, the only term that holds both.

`vm/test_universe_unbiased.py` checks it, with its criteria fixed before running: on this network (the invariant
comes from exactly the seven relations below), and on the seven relations alone (`vm/programs/universe.grm`), run
seven ways: as written, G measured, nothing fixed, among distractors, with neutral names, with another H, and with one
relation made wrong, which must not give it (it does not). With G measured, the GRM machine settles its values less
finely than its exact relations and brings up S · E_quant² · l_P² = ħ²c²/(4π) instead; the equation is still
implied, exactly.

### The chain the network took

`trace_derivation.py` asks the network for the smallest combination of its own relations that gives the equation.
Seven relations, all written separately; every constant cancels, and the right side comes out exactly 1:

```math
\begin{aligned}
(0)\quad & l_P = \sqrt{\hbar G / c^3} && \times(-2)\\
(0\to 1)\quad & H_{end} = H_0 \sqrt{\Omega_\Lambda} && \times 2\\
(1\to 2A)\quad & \rho_\Lambda = 3 c^2 H_0^2 \Omega_\Lambda / (8\pi G) && \times(-1)\\
(1\to 2A)\quad & E_{stock} = \tfrac{4\pi}{3}\,\rho_\Lambda\,(c/H_{end})^3 && \times(-1)\\
(1\to 2B)\quad & T_{floor} = \hbar H_{end} / (2\pi k_B) && \times 1\\
(1\to 2B)\quad & E_{quant} = k_B T_{floor} && \times 1\\
(2A \leftrightarrow 2B)\quad & S = \pi c^2 / (H_{end}^2\, l_P^2) && \times 1\\
\Longrightarrow\quad & S \cdot E_{quant} = E_{stock}
\end{aligned}
```

The Planck definition enters twice, the other way round: it is what cancels ħ and G and closes the loop
(left side minus right side on the solved values: 1e-14 decades). The network builds E_stock as the vacuum filling the
horizon; on paper it is a black hole of the horizon's size. Both give the same number: a sphere of radius c/H filled at
the critical density has exactly the size of its own black hole.

![The chain and its triangle](docs/equation/draw_chain.png)

**The structure.** Four nodes and four relations: 0 (the Planck tick, where ħ, G and c are fused) to 1 (the bubble and
its rate H), 1 to 2A (gravity: the content) and to 2B (the quantum: the grain), and the 3, which is not a node but the
relation between 2A and 2B: S. A network of N nodes and R relations holds R − N + 1 independent loops: here
4 − 4 + 1 = 1, one invariant, and it is this equation; the open tail 0 – 1 is its one degree of freedom, H. Placed by
their powers of ħ, G and H, the three terms close a triangle on the origin: in log, the equation is a zero.
`generations.py --with-equation` shows the same order inside the network: S and E_quant are born in the same
generation, E_stock one generation later, from the two of them.

**The wave.** In log, E_quant and E_stock are one wave and its mirror around E_P/√(4π) ≈ 10^8.74 J: their sum never
moves, S is the gap between them. From the point zero (S = 1, the grain equals the content) to the plateau and back,
each cycle closes on the point it started from (the return drawn as the expansion replayed backwards, a hypothesis).
Today sits almost exactly in the middle of the cycle counted in decades of Planck time (60.9 of 61.2).

![The wave of the equation](docs/equation/equation_wave.png)

### Against data (`test_equation.py`)

| test | what is compared | result |
|---|---|---|
| 1. a final plateau? | the future of H with each DESI DR2 fit of w(a) (CPL, or w frozen at today's value) | the plateau needs w = −1 in the end; DESI measures the past only, so this is an extrapolation |
| 2. **the container is the content** | the law Econtent = Econtainer added to the network (it is Friedmann's equation for a flat universe: Ω_K = 0, for ever), with DESI+CMB Ω_K = 0.0023 ± 0.0011 | 2.1 sigma: not rejected, the number to watch |
| 3. Padmanabhan's equipartition | N_bulk / N_sur, 1 at equilibrium | 0.56 today; reaches 1 (the equation) only with w = −1 |
| 4. the equation at every instant | holographic dark energy on the event horizon (Li 2004, C = 1, no free parameter) | w today −0.89 and w_a > 0, where the four DESI fits give w_a < 0 (3.7 to 5.6 sigma, w0–wa correlation left out) |

With the Cosmicflows-4 distances (`import_cf4.py`, one H0 node per distance method, a network per systematic floor;
`test_master_discovery.py` compares them), the network takes H0 = 75.2 km/s/Mpc and puts the Hubble tension on
Planck's ω_c (+7.1 sigma); it stops siding with CF4 only once each method is given a systematic floor between 3 and 5 %. The type II supernovae disagree with the other CF4 methods at every floor. The equation itself does not move:
only the scale of the cycle does (H_end from 58.4 to 64.3 km/s/Mpc).

**What is known, what is not.** The equation is not new physics: it is the equilibrium of Padmanabhan's holographic
equipartition for a vacuum ([arXiv:1206.4916](https://arxiv.org/abs/1206.4916)), the cosmic form of Smarr's relation
for black holes. What this folder shows is that a network of unrelated known relations brings it up by itself, and how:
the chain, the loop that closes through the Planck time, the wave. It is a demonstration of what the tool does, and a
point of view; the tests above are where it meets the data.

| script | what it does |
|---|---|
| `expand.py` | solves the store with its measurements, expands it where it is in tension, writes `data/grm_network_fully_enriched.json` |
| `trace_derivation.py` | the relations the network combines to give an equation, with their weights |
| `generations.py` | in which generation each node is born from the constants (`--with-equation`, `--data`) |
| `test_master_discovery.py` | solves every network of a store and compares them (the master invariant, H0, the tensions) |
| `test_equation.py` | the four tests above; `--save` writes a store with the container law in every network |
| `import_cf4.py` | adds the Cosmicflows-4 H0 per method, one network per systematic floor (`--sys 0,0.01,...`) |
| `equation_graph.py`, `equation_wave.py`, `draw_chain.py` | the figures |
| `grm_strings.py` (+ `grm_anatomy.py`) | every relation plucked like a string: families, timbres, the load and resistance of each node, the floors that never answer and why, where each string breaks (HTML report with the equations) |
| `seismograph.py` | shakes one node over a range of decades and records how every other node answers |
| `quantum_classical.py`, `bridge_explorer.py` | the laws that hold for any object between a quantum and a classical quantity |
| `harmonics.py` | are the network's dimensionless numbers rational powers of S? (judged against random fundamentals) |

The Cosmicflows-4 table is not shipped: download "All CF4 Individual Distances" from the
[Extragalactic Distance Database](https://edd.ifa.hawaii.edu) and cite its article (Tully et al. 2023), as the EDD asks.
DESI DR2 numbers: [arXiv:2503.14738](https://arxiv.org/abs/2503.14738).

---

## The Relational Universe (`web/`)

> **Live: [simulation.anthony-charretier.fr](https://simulation.anthony-charretier.fr)**, nothing to install, phones included.

```bash
cd web && python -m http.server 8000      # then open http://localhost:8000 (phones included)
```

From the Big Bang to the end of time, in 3D and with music, and every number held by one GRM network: the atom, the
expansion (Friedmann, Planck 2018 values), the first nuclei and the moment light is freed (Saha), the first acoustic
peak of the microwave sky, the stars and the Sun's life, the evaporation of black holes, the air of the Earth, and the
music itself (a flute in the Lydian mode cut in our air, a chord made of the sound of the young universe). Change a
constant of nature: everything answers, the pitch of the flute included. Push it too far (too much matter, a burning
sky) and the universe closes: the expansion stops, the light warms up again and everything falls into a Big Crunch.
Both endings are played to the end, every step a node of the network: black dwarfs, evaporating galaxies, decaying
protons and the last flashes of the black holes on one side; galaxies colliding, stars cooked by the sky, atoms then
nuclei broken and the final point on the other. `grm.js` is the JavaScript port of the engine (`pygrm`),
checked against it (`web/tests`). Details, sources and limits: [web/README.md](web/README.md).

---

## A node nobody mentioned (`grm_hidden_node.py`)

```bash
python grm_hidden_node.py            # one draw, with the hidden node and without (control)
python grm_hidden_node.py --sweep    # 30 draws of the noise each way (about 2 minutes)
```

The Neptune question on a kitchen scale. Five objects are weighed alone, then in ten groups (0.5 g each). Nobody told
the network that a coin (18 g) was stuck under the tray during four of the weighings.

1. **As told**, the network sees that something is missing: chi2 = 2574 for 10 degrees of freedom.
2. **One node more, H, that nobody measured**, and for each weighing a share in (0, 1): how much of H was there.
   Nothing says where H is or how heavy. A yes-or-no relation s (1 - s) = 0, loose then tightened, asks each weighing
   to choose. The start comes from the tensions of step 1: a weighing heavier than its objects probably held H.
3. **A judge**: H exists only if the tension it removes is worth the nodes it adds (Bayesian information criterion),
   its mass is determined, its shares are clear-cut, and nothing is left unexplained.

| 30 draws of the noise | result |
|---|---|
| with the coin | found 28 / 30, in the right four weighings, H = 18.11 g on average (spread 0.32 g) |
| without the coin (control) | a coin invented 0 / 30 times |

The two misses are "not found", never a wrong answer. Starting the shares at 0.5 instead of from the tensions left
the network stuck (3 weighings of 4, wrong mass) in 22 draws of 30: the tension says that a node is missing, and
where it hides. Limit: the kind of node was known here (a mass that adds); a node of unknown form (a force that
depends on distance, as Neptune for Uranus) is the next test.

---

## From the 0 the 1... (`grm_tao.py`)

```bash
python grm_tao.py                    # the three rules against chance (200 random spectra, a few minutes)
python grm_tao.py --draw tao.png     # also the cascade drawn as waves, and the result
```

An open question, asked honestly. "From the 0 the 1, from the 1 the 2, from the 2 the 3, from the 3 the ten thousand
beings": a fundamental wave (1), two waves born from it (2A, 2B, two seeds), their relation (3), and the cascade of
everything the relations make. Are the 12 measured masses of the particles (charged leptons, quarks, W, Z, H; PDG 2024)
such harmonics? Three readings of "relation", each fixed before looking at the masses:

- **spiral**: the relation multiplies (m0 a^i b^j, |i| + |j| <= 3). Best seeds a = 1.74, b = 22.8 fit every mass to 12 %
  on average, which sounds good, until chance: random spectra over the same span fit as well or better (p = 0.95).
  A cascade of 25 harmonics with 3 free numbers covers 5.5 decades whatever is put in it. Not better than chance.
- **intermodulation**: the relation is that of real waves (sum and difference tones). p = 0.92: not better than chance.
- **trinity**: the 3 is the relation itself, three waves on one circle 120 degrees apart (Koide's formula, in Brannen's
  form: sqrt m_n = mu (1 + sqrt 2 cos(delta + 2 pi n / 3))). For the charged leptons Q = 0.666664 +- 0.000005 against
  2/3, a chance of about 1 in 70 000 for three random masses over the same span, and delta = 0.2222 rad (2/9). For the
  quarks: no (p = 0.57 and 0.12; their masses depend on the scheme they are quoted in). One caveat that the p-value does
  not include: the formula was found by looking at these very masses.

So far: the cascade as a spiral or as sum tones is refused by chance; the three-on-a-circle holds for the leptons only,
strikingly, and nobody knows why. The GRM network refines the seeds of every rule (log-linear relations) and shows
which relation strains most. Next steps: other cascade rules (written before looking), a leave-one-out prediction,
and a dated bet on a mass not yet measured well (the neutrinos).

---

## A loop without a seed (`grm_loop.py`)

```bash
python grm_loop.py                   # what the loop fixes, what it leaves free, and the bet on the neutrinos
```

Nothing starts from a first seed: for an absolute to exist, it must be a loop. Three waves are born from the void in
opposition to the full, for ever. Their amplitudes r = √m split into the **full** (the part shared by all three) and the
**void** (deviations that sum to zero); the loop is that neither wins: |void| = |full|. No seed, no scale, no number.

- **What it fixes.** |void| = |full| is exactly Koide's Q = 2/3 (the amplitudes at 45° from (1, 1, 1), as Foot noticed in
  1994). For the charged leptons the ratio is 0.999997. The GRM network shows that the loop fixes one ratio only (given
  one mass, the others stay undetermined) and that, given two masses, it predicts the third: the tau at 1776.97 MeV from
  the electron and the muon (measured 1776.93 ± 0.09), and the same in every direction (0.4 sigma each).
- **What it leaves free.** The phase of the three waves on their circle: measured 0.2222248 ± 0.0000062 rad, where
  2/9 = 0.2222222 (0.4 sigma). A simple fraction that close would happen by chance about once in 900, but 2/9 was
  noticed after looking (Brannen, 2006). Unexplained.
- **A bet.** The neutrinos: only the differences of their squared masses are measured. The loop closes only with one wave
  in opposition, and only in the normal order (the inverted solution sums to 103 meV, refused by cosmology). It gives
  m = 0.365, 8.685, 50.30 meV, **sum 59.35 ± 0.30 meV**, the lightest almost massless. Written, dated, before the
  measurements that will decide it: [predictions/2026-11-04-loop-neutrinos.md](predictions/2026-11-04-loop-neutrinos.md).
- **A second bet, on the Cantor cascade** (1/3, 2/9, 4/27…: ratio 2/3, the loop itself; the leptons' phase is its second
  term): the neutrino phase 13/27 = 1/3 + 4/27 gives Δm²₂₁ = (7.667 ± 0.087) × 10⁻⁵ eV². On its own this is a 1-in-10
  hit, not significant. First check after writing it: JUNO's first measurement, (7.50 ± 0.12) × 10⁻⁵ eV², 1.1 sigma
  away; to be decided by JUNO's next data ([predictions/2026-11-04-cantor-phase.md](predictions/2026-11-04-cantor-phase.md)).
- **Four more bets that follow from the same masses**: the tau at 1776.969 MeV, the mass seen in beta decay
  m_β = 8.84 meV, neutrinoless double beta decay m_ββ between 1.1 and 4.1 meV, the cosmological sum 59.35 meV. Each can
  refute the loop on its own ([predictions/2026-11-04-loop-observables.md](predictions/2026-11-04-loop-observables.md)).

---

## The world economy as a network of zeros (`grm_world.py`)

```bash
python grm_world.py                  # the broken zero, its parts, its carriers, the hidden node (a few seconds)
python grm_world.py --draw world.png # and the picture
```

Everything a country sells, another buys: added up over all the countries, the current accounts must make zero. In
the IMF World Economic Outlook (October 2026, data in `data/`) they do not: the world "runs a deficit with itself" from
1981 to 2003, then a surplus from 2004 on (+490 billion dollars in 2024, 0.44 % of world GDP), and the IMF's own
projections do not close either.

- **Where it sits.** Split in two zeros, both broken in opposite directions: the world exports 1117 billion more than it
  imports (3.4 % of its exports), and pays 627 billion more income than it receives.
- **What carries it.** Three carriers written before looking (world GDP, world exports, oil price), judged on
  year-to-year changes against every country's own current account as a placebo, with a permutation test. The trade
  part follows world GDP (rank 1 of 170, p = 0.0002) and world exports (rank 5, p = 0.002). The income part follows
  nothing: the network refuses to invent a carrier for it.
- **The hidden node.** Written into a GRM network: trade gap = (2.27 % in 2010, +0.061 point a year) × world exports;
  the drift beats a constant share by 63 in BIC. The years that pull hardest are 2021 and 2024 (up) and 2000-2001 (down).
- **Inside each country.** The second zero, current account = saving - investment: 136 of 163 countries close it;
  the largest gaps (Mauritius, Albania, Bolivia, Cabo Verde, Benin, Taiwan...) are listed.
- **A small bet**: the world trade gap of 2025, +1107 billion by the GRM node against +1170 projected by the IMF
  ([predictions/2026-11-04-world-trade-gap.md](predictions/2026-11-04-world-trade-gap.md)).

---

## The carbon of the Earth as a network of zeros (`grm_carbon.py`)

```bash
python grm_carbon.py                 # the broken zero, every estimate against the rest, the two oceans, 2024 (1 second)
```

Carbon is neither created nor destroyed: what humanity emits must equal what the atmosphere, the ocean, the land and
cement take up. The Global Carbon Budget 2025 (data in `data/`) publishes each term, its uncertainty and the gap. No
causes are looked for: only where the gap sits and which estimates are blurred.

- **The zero that is not zero.** Year by year the gap stays within the stated uncertainties (Birge ratio 0.87; one year
  beyond 2 sigma, 1991), but its mean is not zero: +0.54 ± 0.09 GtC/yr over 1959-2024, positive in seven decades out of
  eight (about 2 Gt of CO2 a year the budget does not see). The Global Carbon Budget calls the overall imbalance
  "near-zero"; the network says small, persistent, and not zero.
- **Every estimate against all the others.** A GRM network per year, the conservation law exact, every independent
  estimate a measurement, each hidden in turn: the ocean models sit below what the rest implies (-0.81 sigma on average),
  the fCO2 data products above (+0.66). The budget closes better with the data products (mean gap +0.30, rms 0.85) than
  with the models (+0.65, rms 1.01).
- **Where the yearly swings sit.** The gap swings against the atmospheric growth (correlation -0.87 after removing slow
  trends): the year-to-year jumps measured in the air are not followed by the estimated sinks.
- **2024.** The record atmospheric growth (7.9 GtC, NOAA) and the largest negative gap (-1.7 GtC/yr). The two estimates
  of the atmospheric growth disagree with each other: the stations are 2.1 sigma above what the rest implies, the inverse
  models 1.8 sigma below. The Global Carbon Budget 2025 itself writes that "the total sink or G_ATM is strongly
  overestimated in 2024".

---

## The explorer (`grm_explorer.py`)

```bash
python grm_explorer.py
```

Write a network with the forms or as JSON: both stay in sync, edit either side. Solve with F5, or let it solve
live while typing.
- **Validity at a glance**: give any node an *expected* value (and, optionally, a relative tolerance). After the
  solve each check turns green or red, and the banner says VALID or NOT VALID. Without a tolerance, a check passes
  within 3 sigma of the solved uncertainty.
- **Consistency**: chi2 per degree of freedom (a TENSION banner when the data and the relations disagree beyond
  chance), the pull of every relation and measurement, the nodes the network does not determine, and *Leave one
  out* (each measurement predicted from all the others).
- **Relations**: `log` (products and powers), `sum` (with powers) and `fn`, an expression of the nodes that must be
  zero, e.g. `x - 5 * (1 - exp(-x))`. Expressions only allow numbers, node names, arithmetic and math functions.
- **Presets** (`grm_presets.py`):
  - *Known answers*: Rydberg constant, Bohr radius, mass of the Sun from the Earth's orbit, speed of sound, solar
    luminosity, g from a pendulum, Pythagoras (sum relation), Wien's constant (fn relation).
  - *Open problems*, labelled as such: the Hubble tension, the neutron lifetime puzzle, Koide's relation. Each comes
    as the data alone (the network measures the tension: about 5 sigma for H0, 4.5 sigma for the neutron), and some
    with the node of a hypothesis proposed in the literature (a smaller sound horizon, a neutron decay without a
    proton, Koide's Q = 2/3 predicting the tau mass). **These presets do not solve the problems**: they show how
    large a hypothesis would have to be for the data to agree, not whether it is true.

- **Missing nodes?** When a network is in tension, a node nobody measured is tried at every place it could act (a
  factor in a log relation, or a systematic factor in one measurement). The placement that removes the most tension is
  kept if it is worth one more node (BIC), then again while tension remains (at most 3 nodes). The other placements
  that explain the data as well are listed (the data cannot tell them apart), and the value is looked up in a bank of
  known numbers (`grm_bank.py`: CODATA 2018, IAU, Planck 2018, PDG, mathematical constants, and simple forms of them),
  with **how many candidates would match by chance** at that precision. On the neutron puzzle, the factor 0.98887 lies
  1.55 sigma from 1 - alpha, and about 0.6 candidates would fall that close by chance: suggestive at most. On the
  Hubble tension, almost four would: a match means nothing. Perspectives to consider, never proofs.

Files: Open / Save JSON. The logic (`normalize`, `build_network`, `solve_document`, `find_missing_nodes`) works without
a display.

---

## The tests (`test_grm.py`)

```bash
pip install -r requirements.txt      # pygrm included
python -m pytest -v test_grm.py
```

**1. Engine**: exact answers on small systems, the physical range from 1e-44 to 1e122, measurements as constraints, identifiability, state and inputs, robustness, the three relation types, and uncertainties checked against known propagation.

**2. Protocol**, run on Kepler's third law and on the Planck units, and on any full model:

```bash
GRM_SPEC=grm_model.py python -m pytest -v -s test_grm.py          # PowerShell: $env:GRM_SPEC = "grm_model.py"
```

- **leave-one-out**: each measurement is hidden, the starting points are drawn at random, and the network must recover it within 2 sigma. A value that changes with the starting point is reported as *not determined*, never as a success;
- **relation knock-out**: each relation is removed in turn. A relation matters if its removal moves a prediction by more than 0.1 sigma or widens its uncertainty by more than 5 %. Relations are sorted into definitions, untestable theory, redundant identities, and *idle claims*, which fail the test;
- **chance test**: every measurement is scrambled by up to a factor of 10. If the network recovers as many scrambled values as real ones, its successes prove nothing.

With part 3 below, the file holds 113 tests, all passing; 4 more run only on a full model.

**3. The water test.** A geometry test that looked like an emergent bond angle is kept as a lesson: the tests show that the angle is an input, not an emergence.

### Results on the full GRM model
- converges in 5 iterations, reduced chi2 = 0.35, no undetermined node;
- **42 of the 42 measurements** that another path can reach are recovered (13 have no other path);
- no claim and no established relation is idle (63 definitions, 9 untestable, 4 redundant identities in the black-hole chain);
- **42 recovered with the real values, 4.7 on average (at most 7) with scrambled values.**

The protocol checks the consistency of the network with today's measurements. It is not yet the proof by future measurements, which will come from the model's dated predictions.

---

## GRM Guitar (`grm_guitar.py`)

> **The VST3 / standalone plugin: [github.com/innermost47/grm-guitar-vst](https://github.com/innermost47/grm-guitar-vst)**
> The same networks ported to C++ (JUCE), with a guitar roll that writes notes string by string. Work in progress:
> it builds and plays (tested in Bitwig on Windows), and the palm mute still does not sound like a real one.

```bash
pip install numpy sounddevice        # sounddevice is optional: without it, WAV export still works
python grm_guitar.py
```

### The networks

**String** (one per string, solved for its fret)
```
wave speed    c^2 * mu / T = 1
fundamental   2 * L_eff * f1 / c = 1
fret          L_eff = L * 2^(-fret / 12)
steel core    d^2 = 4 * mu * k^2 / (pi * rho)          k: core share of a wound string
stiffness     B = pi^3 * E * d^4 / (64 * T * L_eff^2)   partials: f_n = n * f1 * sqrt(1 + B n^2)
```
- **Play**: length, mass and tension are the measurements; the network gives the note, its uncertainty in cents (about ±11 cents for L ±0.5 mm, mu ±1 %, T ±0.5 N) and the stiffness.
- **Tune**: the target pitch becomes the measurement, and the same network gives the tension.

**Attack**: the pick, or the finger, meets the string
```
string stiffness  k_s = T * L_eff / (x * (L_eff - x))    x: pluck point
release height    y0 = F / k_s                           loudness of each note
pick tip          k_c = E_p * b * t^3 / (4 * l^3)        a small bending beam (pick thickness t)
finger            k_c = flesh stiffness
release time      tau = pi * sqrt(m_c / k_c)             m_c: mass of string touched
brightness limit  f_c = 1 / (2 pi tau)                   the string slips off: highs softened
click energy      E_c = F^2 / (2 * k_c)                  snap of the pick (the pick's own vibration: not a force on the bridge)
```

**The player**: the arm meets the tempo (one network per sequence, nodes for every stroke)
```
intent            t_k = grid_k, A_k = A0 * accent_k, pluck point, pick depth   drawn with the player's imprecision
arm               t_k - t_(k-1) = grid_k - grid_(k-1)    the swing keeps its period; same continuity for A, p, d
hand speed        v_k = pi A_k / step                    half a pendulum swing per step -> time between strings
pluck force       F_k = F0 A_k / A0                      an upstroke is lighter
pick depth        o_j = d_k - (y_j - y_c)^2 / (2 R)      along the arc of the wrist: an upstroke misses the bass
```
The network finds what the arm actually does, a compromise between each intent and the continuity of the swing:
about 9 ms of timing spread (musicians: 10 to 20 ms), louder first beats, strums of 40 to 60 ms, a hand that
wanders along the strings. No two strokes are the same, and no two passes of a loop either.

**Palm**: the edge of the hand lies on a strip of the strings near the bridge
```
skin damping      r = R_skin * N                           pressure of the hand
contact width     w = w0 * (N / N0)^(1/3)                  Hertz contact: soft bodies pressed together
per metre         r' = r / w
inside the strip  kappa^2 = (mu w^2 - i w r') / T          complex wavenumber
mode n            y(fret) = 0 for a wave leaving the saddle (transfer matrices: free part, strip, free part)
                  -> one GRM network per mode: unknowns F_n and S_n (frequency, decay rate)
```
The palm is not a small perturbation: its resistance is larger than the string's own impedance `Z_s = sqrt(T mu)`
(0.7 kg/s for the low E, 0.17 for the high E). So each mode is solved exactly, followed from the free string while
the skin's resistance grows. What comes out, with no rule written for it: the long waves are partly reflected by the
strip (the string is cut a little shorter, the note goes a few cents sharp, and loses a share of its energy at each
round trip), the short waves enter the strip and die inside it, a light string is cut harder than a heavy one, and
moving the hand away from the bridge mutes more than pressing harder. That last point is what Ottaviani et al.
measured on players ("Towards a dynamic model of the palm mute guitar technique", ICMC-SMC 2014: "the distance of
the hand from the bridge is more important than the applied force"). The same paper found that the pressure drops
while the pick goes through the strings and comes back after: a struck note starts under half the palm's damping and
reaches it in 30 ms. Where the palm rests and how hard it presses change from stroke to stroke (player network).
While the palm rests, it mutes every string under it, including what the fingers do between chords and the strings
that answer in sympathy. Two sliders: "Palm pressure" and "Palm from bridge (mm)".

**Body and bridge**: the air in the box meets the wooden top, the top meets the strings
```
speed of sound    c_air^2 = gamma R T / M
Helmholtz         f_H = c_air / (2 pi) * sqrt(A / (V * l_neck)),  l_neck = t + 1.7 r
top plate         f_T = 10.21 / (2 pi a^2) * h * sqrt(E / (12 rho (1 - nu^2)))
coupling          the two oscillators push apart into the two lowest body resonances
radiation         f_rad = c_air / (2 pi a): the top radiates the bass poorly below it
plate rigidity    D = E h^3 / (12 (1 - nu^2))
plate impedance   Zp = 8 sqrt(D rho h)                   the top seen from the bridge, between its modes
bridge mass       m_b = share * rho_b V_b                Y_plate = 1 / (Zp + i w m_b): above Zp / (2 pi m_b)
                                                         the bridge lets less and less treble into the top
modal mass        M = beta * rho h pi a^2                the top seen from the bridge, at a mode
string impedance  Zs = sqrt(T mu)
bridge loss       sigma_n = (c / L) Zs Re Y(f_n)         each string gives its energy to the top
sound             p ~ i ka / (1 + i ka) * Y(f) F          the force moves the top, the moving top radiates
```

**The whole guitar.** A guitar is one object: every string pushes on the bridge, and the moving bridge moves every
string. The bridge velocity is `V = Y F` (all the strings together); mode n of a string answers with
`F_n = (2T/L)(-iw) Y F_others / (w_n^2 - w^2 + 2i (sigma_n + kappa_n) w)`, where `kappa_n = (c/L) Zs |Y|` is its
coupling to the bridge. So the open strings nobody plays, and a string the finger has just left, ring in sympathy;
a note sitting on a body resonance gives its energy away fast. A mode can share energy with the bridge but never
answer more than it receives (tested).

**Fingers on the frets** (chord changes)
```
finger position   x_f = L (1 - 2^(-fret / 12))
string height     h = h_nut + (h_12 - h_nut) x_f / (L / 2)
lift              the string jumps back from h: a soft, slow pluck of the open string (low, no click)
landing           the finger pushes the string onto its fret: a small knock on the stopped string
```
**Finger on the winding** (wound strings): measured on real strings by Pakarinen, Penttinen and Bank (JASA 2007), the
noise has moving harmonics at `k v / p` (one shock per turn of wire, level growing with v) and static harmonics: the
**longitudinal** modes of the string, while the fingertip damps the transverse ones.
```
winding wire      2 p = D - d_core,  D^2 = d_eq^2 / fill
slide             dx = |L_1 - L_2|,  v = dx / dt,  f = v / p
friction          P = mu_f * N * v
longitudinal      c_L^2 mu = E A_core,  f_L = c_L / (2 L)     only the steel core is stretched
```
The soft edge of the finger pad spreads each shock over `edge / v`, so most of the noise of a chord change is low.
When the finger slides from fret to fret it rides over the fret wires: each one is a knock of a share of the pressing
force lasting `crown / v`, a low woody thud. All of it reaches the ear only through the bridge and the body.
Check against the measurement: the paper reports the first longitudinal mode of an open 6th string near 1400 Hz;
the network gives 1400 Hz for a steel core of 36 % of the equivalent diameter (1750 Hz with the default 45 %).

**The room**: the sound meets the walls (optional, four sizes from a small room to a church, six wall materials)
```
volume, surface       V = L W H,  S = 2 (L W + L H + W H)
absorption            alpha_b by octave band (125 Hz to 4 kHz), walls and ceiling of one material, floor of wood
reverberation         RT_b = 0.161 V / (-S ln(1 - alpha_b))        Eyring
critical distance     r_c = 0.057 sqrt(V / RT)                     the room as loud as the guitar itself
mixing                reverberant energy = (r / r_c)^2 x direct    at the listener's distance r
Schroeder frequency   f_s = 2000 sqrt(RT / V)
```
The ear receives the direct sound, the first reflections (image sources, each wall a mirror, each bounce taking its
share), then a diffuse tail decaying band by band. How much room is heard is not a setting: it follows from the size,
the walls and the distance. Absorption coefficients: sengpielaudio's table.

### Synthesis
Modal synthesis of the force of each string on the bridge (in newtons), with the exact Fourier amplitudes of a
string plucked at a point. Each partial decays by its internal losses, the bridge loss and, under the palm, the skin.
The six strings and the finger noises are then coupled through the bridge, and the whole guitar radiates through its
body. The onset is the release itself, shaped only by the release time of the attack network.

### Playing
- play, strum down or up, arpeggio, palm mute, pick or fingers, steel stiffness, human feel, sympathetic strings;
- every setting, the room and the sequencer in one window, without tabs. **A setting moved while the guitar plays is
  heard at once**: the same playing (same player, same randomness) is rendered again in the background and takes
  the place of the sound at the same moment, with a 40 ms crossfade (a change of room or listener only recomputes
  the room). The notes are computed side by side on every core;
- a slow-motion view of the six strings (×100), with fingers on the frets and sliding between chords: **click a
  string to hear it alone**; a small oscilloscope below it;
- **sequencer**: 16 eighth-note steps, tempo, loop (two passes that differ). Each step holds a chord, notes written
  `string:fret` (e.g. `6:3 1:3`) or a rest, and a gesture: ↓ strum down, ↑ strum up, x palm-muted strum, · let ring.
  **Arpeggio mode** offers up and down, Travis (alternating bass), bass + chord, ballad and pinch patterns;
- WAV export.

### Hypotheses (all adjustable in the code)
Body dimensions and wood values are typical figures, not measurements of a given guitar. Other assumptions:
- share of the steel core in wound strings: 45 %, adjustable with a slider; metal fill of the winding: 80 %;
- skin-on-steel friction: 0.3; soft edge of the finger pad: 1 mm; share of the longitudinal force reaching the top: 0.3;
- pick plastic: 2.5 GPa, with a 5 mm wide, 4 mm free tip; fingertip pulp: about 2 N per mm;
- palm: 30 mm from the saddle (± 3 mm from stroke to stroke), 1 N per string (± 0.12 dex), 25 mm of skin on the
  strings, resistance 1 N s/m per newton (no measured value was found; a fingertip behaves as a damper above about
  150 Hz, Wiertlewski and Hayward 2012), half the damping released during the stroke, back in 30 ms;
- fret wire crown 2 mm, knock of 0.3 of the finger's pressing force;
- string height: 0.5 mm at the nut, 2.2 mm at the 12th fret; finger lift 3 ms, landing 1 ms;
- top: half of its mass moves in its first modes; its braces make it 4 times stiffer than bare spruce, seen from the bridge; rosewood bridge of 32 cm3, of which the saddle carries 20 % (set by ear);
- player: timing intent 15 ms (Repp and Su 2013: 10 to 20 ms for musicians), arm continuity 15 ms, swing 10 cm,
  pick 3 mm deep, wrist arc of 25 cm, accents on beats 1 and 3, upstroke 0.8 of the force.

---

## 3-SAT as a GRM network (`grm_sat.py`)

```bash
python grm_sat.py                                   # alpha = 3.11 (clauses per variable)
python grm_sat.py --alpha 4.2 --sizes 50 100 200 --trials 5 --restarts 3
python grm_sat.py --dimacs formula.cnf
```

Each variable is a positive node o_i whose truth value is v_i = o_i / (1 + o_i); each clause is a relation
(1 - l_1)(1 - l_2)(1 - l_3) = 0, zero as soon as one literal is true. The GRM engine solves the network, the result
is rounded, and every clause is checked. A classical WalkSAT runs on the same formulas as a baseline.

First results (random formulas, this machine):

| alpha | N | GRM: formulas fully satisfied | WalkSAT |
|---|---|---|---|
| 3.11 | 20 to 200 (3 each) | 12 / 12 | 12 / 12 |
| 3.11 | 500, 1000 (2 each) | 4 / 4 (6 s and 36 s per formula) | 4 / 4 (under 0.1 s) |
| 4.2 | 50 / 100 / 200 (5 each, 3 restarts) | 3 / 0 / 1 | 3 / 3 / 4 |

**GRM+** (`--compare`) adds two tensions between successive solves, using `set_sigma` from the core: a binarity
relation v (1 - v) = 0 per variable, loose at first then tightened round after round (continuous against discrete),
and a reweighting of every clause still false. On satisfiable formulas only (checked by MiniSat), alpha = 4.2,
WalkSAT limited to 20 000 flips:

| N | GRM | GRM+ | WalkSAT | GRM+ then WalkSAT |
|---|---|---|---|---|
| 50 (6 formulas) | 5 / 6 | 6 / 6 | 6 / 6 | 6 / 6 |
| 100 (8 formulas) | 4 / 8 | 7 / 8 | 8 / 8 | 8 / 8 |
| 200 (8 formulas) | 1 / 8 | 1 / 8 | 2 / 8 | 1 / 8 |

GRM+ clearly improves on plain GRM up to N = 100, but does not beat WalkSAT, and both struggle at N = 200 with this
flip budget. Work in progress.

At alpha = 3.11 random 3-SAT is in its easy region: below a density of 3.52, formulas are satisfiable with high
probability and a polynomial algorithm finds the solutions ([arXiv math/0310193](https://arxiv.org/abs/math/0310193)).
The hard region is near the conjectured threshold, about 4.2, where some formulas have no solution at all.

## Travelling salesman with the GRM only (`grm_tsp.py`)

```bash
python grm_tsp.py lin318.tsp --optimum 42029 --plot     # TSPLIB instance (EUC_2D), not included: download it
                                                        # from http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/
```

Two GRM methods, no algorithm borrowed from elsewhere:

- **Method 1, the circle by levels (pure GRM, no move).** Relations between groups first, then between cities.
  Cities linked by a chain of short gaps form a group. Each group centre gets a point on the unit circle, its place
  in the tour: attraction relations pull centres that are close on the map to close places, dispersion relations
  (sum of cos k theta and sin k theta = 0) make them fill the circle, and the core solves the network while the
  attraction is narrowed round after round. Inside a group, cities follow their angle around the group centre,
  starting from the city facing the previous group.
- **Method 2, tension refinement.** Every edge of the tour is a relation with residual sqrt(d), so the cost of the
  network is exactly the tour length. The most tense edges (length beyond the nearest-neighbour distance) are
  treated first: reversing a piece of tour, or moving one, two or three cities, is kept only if the total tension
  goes down. Then, round after round, a region around a tense edge (drawn in proportion to its tension) is released
  and rebuilt where the tension rises least. The network may *breathe*: a rebuild that ends a little higher can be
  kept, within an allowance that shrinks to zero over the rounds.

![GRM tours of lin318](docs/grm_tsp_lin318.png)

Results on lin318 (318 cities, optimum 42 029), same machine:

| Version | Method 1 | Method 2 | Time |
|---|---|---|---|
| first try: plain circle, strict refinement | 85 326 (+103 %) | 44 730 (+6.43 %) | 66 s + 23 s |
| **current: circle by levels, refinement with pieces and breathing** | **74 500 (+77 %)** | **43 136 (+2.63 %)** | **5 s + 46 s** |

For reference, a simulated annealing run with 2-opt moves (3 million moves, not part of this repository) reached
42 471 (+1.05 %) in 7 s on the same machine. Method 1 still gives a rough tour on a clustered map; method 2 does
most of the work. Work in progress.

## Sentence categories without training (`grm_text.py`)

```bash
python grm_text.py "le gardien a arrêté le penalty"
python grm_text.py --eval
```

A table, nothing more: on the left example sentences, on the right their category (5 categories, 25 French
sentences each, written for the demo). Nothing is fitted. For a new sentence, the GRM core solves a small network:

```
shares      one positive node s_c per category
balance     sum of s_c = 1                       what one category gains, the others lose
evidence    log s_c = log p(c | w)               for every known word w, read from the table,
                                                 sigma = 0.5 dex / sqrt(times w was seen)
```

The answer is the leading category when it leads the runner-up by more than 1 sigma (with their covariance),
otherwise `unsure: A or B`. A sentence with no word in the table gets `unknown`, not a guess. `explain` lists the
words that pulled the decision. The tight balance is handled by the core's continuation (see *Numerics*).

Results on 40 held-out sentences, written separately and never used to build the relations:

| Answer | Count |
|---|---|
| right | 32 |
| unsure, right one among the two | 5 |
| unsure, right one missing | 3 |
| confidently wrong | 0 |

Off-topic sentences: 4 of 6 give `unknown`. The two others share a word with the table by chance (`acte`, then `plante` and `besoin`)
and get an answer: the table is small, and a single shared word is enough. A larger table, or a minimum amount of
evidence, would be the next step.

## GRM Matter (`grm_matter.py`)
```bash
python grm_matter.py              # atoms, then metals at first and second order (about 1 minute)
```
Optional: `pip install numba` compiles the step-by-step integration of the atom (about 50 times faster; without
it the same code runs in plain Python, slowly).
Can the density and the stiffness of a material be predicted from the quantum world alone? What goes in: the
fundamental constants (CODATA 2018) and, for each element, its number of protons Z and its atomic mass. No
material data. The measured values are only read afterwards, to compare.

1. **Constants network**: Bohr radius and Hartree energy from m_e, e, hbar, eps0 (CODATA values recovered).
2. **The atom**: orbitals filled by the Madelung rule, Schrodinger's equation solved self-consistently in the field
   of the nucleus and of all the electrons (local density approximation, Perdew-Zunger). Neon: -128.217 Ha, the
   NIST LDA reference is -128.233 (0.013 %). Ionization energies of 24 elements, H to Ba: median error 4 %
   (Na 0.0 %, K +0.4 %, Rb -0.3 %, Cs -2.4 %).
3. **The metal**: valence electrons as a uniform gas among ions with an empty core (Ashcroft). The core radius
   comes from the atom: an inverse GRM network finds the radius for which the valence electron of the ion is bound
   as the atom calculation says, and carries the uncertainty of that calculation (about 4 %) through to the
   density and the bulk modulus. Equilibrium where dE/dr_s = 0, bulk modulus from the curvature there.

| | first order (gas + ions) | second order (+ band-structure energy, bcc or fcc) |
|---|---|---|
| median error, density (11 metals) | 23 % | 14 % |
| median error, bulk modulus (10 metals) | 20 % | 50 % |
| K, Rb, Cs | density within 1-8 %, stiffness within 1-8 % | density 14-26 % too high |
| Mg, Ca, Ba, Al | density 21-43 % too low | density within 0-12 % |
| Li, Be | 50-55 % too light | 42-49 % too light |

Reading: the simplest picture already gets the heavy alkali metals right from Z alone. The lattice term fixes the
density of the divalent metals and aluminium, but overshoots the alkali metals and spoils the stiffness. Li and Be
fail in both (their cores are a single 1s shell: the empty-core picture is known to be poor for them). The
lattice chosen by the lower energy is bcc for all except Be and Al (fcc); in reality Mg and Be are hcp (not tried),
Ca and Sr fcc. The error bars come only from the atom's uncertainty: where the measurement falls outside them,
the missing piece is in the physics, not in the numbers.

## GRM Water (`grm_water.py`)
```bash
python grm_water.py              # the window
python grm_water.py --headless   # a drop in a bathtub, without a window
```
![GRM Water](docs/grm_water.png)

A basin of liquid seen from above. Click: a drop falls. Drag: a finger goes through the water and leaves a wake.
Rain, a paddle on the left wall, four basins (puddle, bathtub, pool, harbour), four liquids (water, sea water,
olive oil, mercury), three gravities (Earth, Mars, Moon) and the depth.

The surface is the sum of the standing waves of the basin (cosine modes, walls that reflect). How fast each one
swings and how fast it dies is the answer of one GRM network, solved for 32 wavenumbers covering the basin (the modes
in between read it by interpolation):
```
gravity          G = g k                     capillarity   C = (sigma / rho) k^3
restoring        S = G + C                   depth         th = tanh(k h)
dispersion       w^2 = S th
bulk viscosity   g_bulk = 2 nu k^2           walls, bottom g_edge = sqrt(nu w / 2) (k / sinh(2 k h) + 1/Lx + 1/Ly)
decay            gamma = g_bulk + g_edge
also             c0 = sqrt(g h), capillary length sqrt(sigma / (rho g)), slowest ripple (4 g sigma / rho)^(1/4)
```
The liquid's handbook values come with their uncertainties, so every frequency has one too (about 0.4 %).
A second network runs backwards: given the paddle's frequency, which wavelength must it make? (unknown: k).
What the network finds, without being told: water ripples never run slower than 23.1 cm/s, and do so near
1.7 cm; the capillary length of water is 2.73 mm; long waves in a 30 cm deep bathtub run at 1.72 m/s; a 2 Hz
paddle makes 39 cm waves. The tests check these numbers against the textbook values.

The picture: a fixed camera; each pixel sees the sky (with clouds, a texture to read the slopes) reflected by the
tilted surface (Fresnel, Schlick), and the bottom through the water, which absorbs red more than blue (Pope and
Fry 1997).

**The sound of the rain** (`grm_rain.py`). A slider in millimetres per hour: the drops come in the sizes of real
rain (Marshall and Palmer 1948), each at the terminal speed a drag network gives it (weight = drag; 0.8 to 1.2 mm
drops within 6 % of the measured speeds). What makes the sound of rain on water is mostly not the impact but a tiny
air bubble trapped under the surface, ringing for a millisecond (Prosperetti and Oguz 1993). The impact network
gives the Froude and Weber numbers of each drop and decides: drops of 0.82 to 1.1 mm always trap one (the 13-25 kHz
hiss of drizzle), 1.1 to 2 mm trap none and are quiet, larger ones trap one about half of the time, lower and
louder (Nystuen, NASA Earth Observatory). The bubble network gives its pitch (Minnaert) and its damping (radiation,
viscosity, heat exchange, Devin 1959). A click is heard too. The place: outdoors (the air takes the highs with
distance), or one of the rooms of GRM Guitar, with its walls and the listener's distance. Light rain comes out high,
heavy rain spreads down to 1 kHz; both are checked by the tests.
Hypotheses: the size of the regular bubble follows the drop; the bubble wall starts with 3 % of its radius (0.6 %
for the irregular bubbles of big drops, set so that drizzle peaks high, as measured); the loudness scale of the
impact (its law, E ~ M^3 T, is the review's). A real bathtub receives thousands of drops a second: a sample of up to
120 per frame is synthesized and made louder in proportion (incoherent sum); the ripples drawn are only those of
drops above 1.6 mm, and exaggerated (a real drop's crater is smaller than the finest wave the basin's modes show).
Examples: [drizzle outdoors](docs/audio/grm_rain_outdoors.wav), [heavy rain outdoors](docs/audio/grm_rain_heavy_outdoors.wav),
[drizzle heard in a living room](docs/audio/grm_rain_living_room.wav).

Limits: linear waves (small amplitude: no breaking, no splash, no drops thrown up), a flat bottom, perfectly
reflecting walls, a clean surface. The damping by the walls of a closed box (1/Lx + 1/Ly) extends the channel formula
of Robertson and Rousseaux (arXiv:1706.05255), a hypothesis; real water, with dust on its surface, calms down faster.

## GRM Brain (`grm_brain.py`)

```bash
python grm_brain.py                                   # the window: the world on the left, the brain on the right
python grm_brain.py --headless 10 --change-after 5    # without a window: steps per trip, the maze changed after trip 5
```

![GRM Brain](docs/grm_brain.png)

The brain and the maze are two separate things. The brain is never shown the maze: not its size, its walls, or
where the exit is. It only knows its own moves (from which it builds its own idea of where it is, as animals do),
feels a wall by bumping into it, feels the exit when it is there, and can smell it faintly (optional). Nothing is
learned before: everything is learned while it lives.

**Memory: a matrix of triplets (A, tension, B).** From place A, this move led to B, or into a wall, with the tension
it left, the sensation of the memory:
- a prediction that comes true lowers the tension (the relation becomes sure);
- a surprise (a wall where it went before) raises it; a wall has two sides, so the way back is shut too;
- a bump leaves a painful tension, remembered longer than a calm one;
- time brings every tension back towards neutral: a forgotten wall is tried again, a changed maze is learned again.

**Desire: a GRM network.** One node per known place, tied to its neighbours like springs: a sure relation is a stiff
spring, a doubtful one a soft spring. The exit, once found, is pinned at 0; every untried move leads to the unknown,
pinned at a height set by curiosity; every place leans weakly towards "far". The core finds the equilibrium after
every step: a landscape that only goes down towards what attracts, with no hollow to get stuck in. The brain follows
the slope, and avoids what hurt.

The window shows the world (with the brain's trail) and the brain itself: its places where it believes they are,
coloured by desire (blue: where it wants to go), its relations coloured by tension (green sure, red painful), its
doubt as a halo, and the steps of each trip against the shortest possible. "Change the maze" closes a passage on the
way it uses and opens another one elsewhere.

In tests on several mazes: the first trips explore (70 to 440 steps), then it takes the shortest way or close to it.
When the maze changes, one long trip follows (the surprise, the bumps, the exploring), then it settles again on a way
close to the new shortest one, sometimes the shortest itself.

Hypotheses: the learning, surprise, pain and forgetting rates, the stiffness of a sure relation, curiosity. The
brain knows its own moves exactly (no slipping), which makes "where am I" easy; noisy moves would be the next test.

## GRM Scales (`grm_scales.py`)

```bash
python grm_scales.py
```

Every scale of the classical world written as a pair in tension that gives a third thing, with established physics
(Carr & Rees 1979, Weisskopf 1975, Press & Lightman 1983, Lineweaver & Norman 2010):

| relation | pair in tension | what is born |
|---|---|---|
| a0 = hbar / (m_e c alpha) | electric pull x quantum agitation | the atom |
| rho = A m_p / (eta a0)^3 | size of atoms x mass of nuclei | the density of rock |
| R = a0 (alpha / alpha_G)^1/2 | gravity x electrons that refuse to be squeezed | the largest planet |
| M = m_p (alpha / alpha_G)^3/2 | gravity x atomic matter | its mass |
| M = m_p alpha_G^-3/2 | gravity x pressure of hot matter | a star |
| M_Ch = 3.1 (hbar c / G)^3/2 / (2 m_p)^2 | gravity x relativistic electrons | the heaviest white dwarf |
| R = 1.5 (sigma_y / G rho^2)^1/2 | gravity x strength of rock | the size from which a body is round |
| h = S / (rho g) | gravity x strength of the crust | the tallest mountain, on each planet |

Scaling laws carry a tolerance of 0.15 dex (they hold to a factor of a few). The same network is run both ways:

- **up**, from the constants of the small only: rock density within a factor 1.3, Jupiter's radius 1.2 and mass 1.2,
  a star within 1.9, the size from which asteroids are round 1.5, the heaviest white dwarf 1.44 solar masses. The
  mountains stay *not determined*: the strength of a planet's crust is not given by the small;
- **down, from the sky only** (Jupiter, the Sun, rock, asteroids, mountains; no atom): the fine-structure constant
  comes back within a factor 1.34, the proton mass 1.36, the electron mass 1.8;
- **cycle**: the large predicted by the small, used as data, gives back the small exactly (the network inverts
  without loss);
- **protocol**: each large-scale measurement hidden in turn is recovered within 2 sigma (10 of 10; the two atomic ones
  follow from the definitions and prove nothing), against 3.4 on average (at most 6) with scrambled values. The
  tallest mountains of Earth, Mars and Venus follow the 1/g law of one another.

Hypotheses: the mean mass number of rock (20), the spacing of its atoms (4 Bohr radii, loose), the yield strength of
rock under self-gravity (10 MPa, loose), prefactors of 1 in the scaling laws.

## GRM Voice (`grm_voice.py`)

```bash
python grm_voice.py                              # "Bonjour Anthony. Je suis le réseau." -> grm_voice.wav
python grm_voice.py "m e R s i ||" -o merci.wav  # any French phonemes (SAMPA), "|" pause, "||" end of sentence
python grm_voice.py --vowels                     # the eleven vowels, one after the other
```

Listen: [grm_voice_bonjour.wav](docs/audio/grm_voice_bonjour.wav), [grm_voice_vowels.wav](docs/audio/grm_voice_vowels.wav).

No recording, no learning, no speech library: every part of the voice is a network solved by the GRM core.

**Lungs, glottis and airflow** (one network per 5 ms)
```
pressure      dPg + dPc = Ps                         the lungs' pressure is shared by two orifices in series
glottis       U = (Ag + OQ/2 Avib) sqrt(2 dPg / rho)  Bernoulli
downstream    U = A_out sqrt(2 dPc / rho)            tongue or lip constriction, velum port, yielding walls
vibration     Avib = Amax k sqrt((dPg - P_th) / (P_ref - P_th))   no voicing below the threshold pressure
folds         f0 = 1 / (2 L_f) sqrt(stress / rho)    a string under tension
pressure      f0 += KP dPg                           pitch rises with the pressure across the folds
```
When the lips close for p or b, the pressure moves from the glottis to the lips and the voicing dies by itself;
when they open, the fast flow through the small opening is the burst.

**The vocal tract** is a tube of 0.5 cm sections whose areas come from the articulators (tongue place and
narrowing, tongue length, jaw, pharynx, lips, lip protrusion, velum). Each section is a lossless tube with the
viscous drag of its walls and the flow its yielding walls take; the lips and nostrils radiate. Its resonances are
the complex frequencies at which a closed glottis lets no flow through:
```
resonance     U_glottis(F + iB/2) = 0                two nodes (F, B), two relations (real and imaginary parts)
glottal loss  U_g + P_g / R_g,  R_g = 2 dPg / U      an open glottis widens the formants (from the airflow network)
nose          a side branch at the velum: poles of the whole, zeros where the closed mouth shorts it ([m], [n], nasal vowels)
hiss          p = K 1/2 rho v^2 (1 - (Re_c / Re)^2)  turbulence of the jet (Stevens), strongest at f = 0.2 v / d,
              through the resonances of the cavity in front of the constriction (s, ch, f, bursts)
```

**The vowels are found, not written.** For each vowel an inverse network has the articulators as unknowns and
measured formants as measurements (male averages, Wikipedia "Formant"); its relations are the tract's own
resonance relations. The network finds the mouth shape whose resonances match, within the limits of a human mouth:

| vowel | i | e | ɛ | a | ɑ | ɔ | o | u | y | ø | œ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 found / measured | 271 / 240 | 390 / 390 | 589 / 610 | 729 / 850 | 729 / 750 | 488 / 500 | 357 / 360 | 251 / 250 | 250 / 235 | 370 / 370 | 578 / 585 |
| F2 found / measured | 2221 / 2400 | 2174 / 2300 | 1798 / 1900 | 1493 / 1610 | 970 / 940 | 755 / 700 | 656 / 640 | 602 / 595 | 1964 / 2100 | 1895 / 1900 | 1690 / 1710 |

Where the match is not exact ([i], [a]), the measured formants ask for a mouth the bounds do not allow.

**Articulation in time.** Each articulator is a network over all the frames: the targets of the sounds are
measurements, the continuity of its motion (second difference ~ 0) is a relation. A sound that does not use an
articulator gives it no target, and the network moves it from its neighbours: coarticulation is what it finds.
The prosody is planned the same way (lung pressure, fold stress): a slow fall through each group, a rise at the end
of a group that goes on, a fall at the end of the sentence, and the French lengthening of the last syllable.

**Sound.** The glottal pulses (with the folds' small irregularities), the aspiration and the hiss are filtered,
frame by frame, by the transfer of the tract built from its GRM poles and zeros, then radiated from the lips.

**Hypotheses**: male tract of 17 cm and its typical areas; wall mass and resistance (Fant); folds 16 mm; phonation
threshold 300 Pa; turbulence constant K = 0.02 and the voice bar radiated by the walls (set without a measurement);
the bounds of a human mouth used by the inverse networks; the inertia of each articulator; the durations of the
sounds. Work in progress: how intelligible and how natural it is remains to be judged by ear.

## GRM Pong (`grm_pong.py`)

```bash
python grm_pong.py                 # tkinter window
python grm_pong.py --headless 3    # 3 matches without a window
```

The ball is the relation, the paddles are its two ends. No paddle has a rule of play: each one solves two small
networks with what it perceives, every reaction time.

```
intercept   x + vx * t = x_paddle            the ball comes to my line
            y_hit = fold(y + vy * t)         the walls fold its path
            x, y, vx, vy measured, with a noise that grows with the distance -> y_hit and its sigma
aim         y_land = fold(y_hit + vy_out(o) * T)     the hit offset o sets the return angle
            escape      high tension when y_land is within the other paddle's reach
            self reach  I must be able to get to y_hit - o in time
            edge        the ball may arrive 3 sigma away from y_hit: it must still meet the paddle
            safety      o measured at 0, sigma 0.4 paddle height
```

The ball speeds up at each hit, so sooner or later a paddle cannot reach it: a point. Matches are played to 11, then
a new one starts. The window shows what each paddle thinks: the predicted hit with its uncertainty, the dotted
relation between the ball and that point, and where it intends to send the ball. Noise, speed, reaction time and
aiming can be changed for each paddle.

![GRM Pong](docs/grm_pong.png)

With equal settings, a paddle that aims wins 57 % of the points against one that only intercepts (175 to 133 over
three runs of 1500 s). Aiming only paid off once the edge relation was added: without it, the aiming paddle hit too
close to the edge for its own uncertainty and lost more points than it won.

## grm talk (`talk/`)

```bash
python talk/grm_talk.py -c "load equation; graph on; relax; why S; bench"
```

A small language to talk to a GRM network (`node`, `relate`, `observe`, `forget`), questions (`ask`, `why`,
`what-if`) and two ways of working: `solve` (pygrm, the whole network at once) and `relax`, a **relational machine**
where every node and every relation is its own small processor that only talks to its neighbours (Gaussian belief
propagation). The graph shows the nodes moving and the relations coming to hold. `bench` prices both on a cost model
(cycles for operations, cache and RAM accesses, messages between neighbours): on the store network of `equation/`,
the relational machine needs 515 processors and 134 rounds, 8 300 x fewer modelled cycles than a dense solve and
400 x fewer than the same messages run by one core; the number of rounds stays about 80 from 100 to 10 000 random
nodes. A model, not a chip, and in Python the simulation is slower than pygrm: the details and the limits are in
[talk/README.md](talk/README.md).

![grm talk](docs/grm_talk.png)

**Programs in the network.** The same language writes programs: signed quantities and sums (a sum is a product of
exponentials, e^x1 = e^x0 · (e^v)^dt, and a converter ties a positive quantity to its signed twin), contacts that
decide by themselves when they push, networks that can be called (`network`, `call`, `use`). They run on the GRM
machine below.

## The GRM machine (`vm/`)

```bash
python vm/grm_vm.py               # in the terminal
python vm/grm_vm.py --window      # in a window: the network drawn, the outputs shown and heard
```

A virtual machine that is one GRM network, and nothing else: the network is the program, the memory and the
calculator at once. It starts blank (or from its memory, `vm/memory.json`) and puts itself to sleep there when it
stops. Its language, GRML (the Global Relational Model Language: [docs/GRML.md](docs/GRML.md), a reference, a tutorial and
examples run by the tests), is Turing complete: variables that the network holds until they are written again (`var`,
`set x = x + 1` at each tick: loops), relations that hold only while conditions hold (`when`: choices); any Minsky
machine is written in it (the tests run addition and multiplication). Weights (`learn k`) learn from files
(`load data.csv`, row by row), together with the weights they share relations with (the least squares, exactly, for
a line), and stay learned at the next session. Inspired by the brain: weights that know how sure they are, a surprise
(prediction errors) shown and heard with the outputs, a night of sleep that loosens what was learned a little. It is
born with a small base (30 points of the world, from the Planck scales to the Sun) that new data can find, and it
never writes a node twice: a routine of its own fuses what is one thing under two names (two inputs that agree row
by row; an input that holds still at the value of a node known precisely). It also writes, by itself, the relations
it finds among what it has seen (power laws, lines, exponentials and logarithms, sums built on products, growths,
decays and oscillations from one moment to the next: a blank machine given heights and times of a fall writes
h = 4.90 t²; given a damped wave, it finds its period and carries it on) and makes a node appear where a relation
keeps missing something, a constant or a hidden variable with its own law (pygrm 0.3.0, `pygrm.discover`); the user
is told, not asked. Its nodes are held as the brain seems to hold quantities: magnitudes in log with relative
uncertainties, the inverse as the same node, and, for the human, every output as two opposed channels. Inside, it counts in its own units, where c, ħ, G and k_B are 1 (pygrm.units "ticks"): the constants are in
how it counts, not in nodes. It feels and forgets as a brain does, as closely as is known: pleasure and displeasure (a
dopamine-like prediction error on its surprise; finding something is a burst of pleasure, an error one of
displeasure) tag what has just worked, which is kept longer and keeps more of its precision through the night; every
node and relation carries a trace of its use that fades when nothing uses it, and pays a rent in bits against the
information it brings (a price that rises as room runs out); its room is an energy budget given by the host (the time
a tick may take, the memory available), and what pays the least is forgotten first (never its base); it tends to flourish (learning progress, and accuracy times room left) and,
surprised and no longer learning, goes looking for what it misses by itself. Its master equation (pygrm's master
invariant) can be read now or n ticks ago. Nothing goes wrong in silence: errors are said with their line, typos
(`heigt` next to `height`), contradictions and networks that do not settle, errors of the machine itself. Python is
only its body: the inputs measured, the clock's ticks, the outputs turned into what a human sees and hears: a window
with the words (coloured, Tab completes), the network itself drawn (the mouse over a node or a relation shows what it
holds; a relation far from holding turns red), the master equation, a panel of values, bars and curves, and a voice
per output (its pitch where its value stands, its loudness how much it has just moved). Help is where the typing is:
`help WORD`, a guided `tour`, a line of help under the prompt and a menu of words floating above it, a short form for every word (`rel`,
`obs`, `t`...) and `+/-` for `±`; programs carry a header that says what they do (`programs` lists them) and open in
a window of their own, a tab each, edited, run and searched from the keyboard. The interface speaks English or French
(`lang fr`; the words of GRML stay English, so a program runs anywhere: [docs/GRML.fr.md](docs/GRML.fr.md)). It can be
watched at work: played and paused, a tick or a round at a time (who worked, who moved), stopped at breakpoints
(`watch`), and asked `why` a node has its value (the messages it hears, and their share). Details
and limits: [vm/README.md](vm/README.md).

![The GRM machine's window: the words, the network itself (the mouse over a relation it found), the master equation, the outputs and what it feels](docs/grm_vm_window.png)

## Status and limits
- **Work in progress**: names, defaults and interfaces may change.
- Pure Python with NumPy: comfortable up to a few hundred nodes. The full knock-out protocol on the GRM model takes several minutes.
- The guitar is a physical model built from relations, not a sampled instrument. Several of its values are hypotheses, listed above.
- The GRM physics model is an attempt under test, presented with its successes, failures and limits on its own site.

## Credits
Concept, method and direction: **Anthony Charretier**. Code written in collaboration with Claude (Anthropic).

## License
[GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later).

---

## Cite

Each GitHub release of this repository is archived on [Zenodo](https://zenodo.org), with a permanent DOI and its date
(metadata in `.zenodo.json` and `CITATION.cff`). The dated prediction on the neutrino masses is in
[predictions/](predictions/): it was written before the measurements that will decide it.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23964101.svg)](https://doi.org/10.5281/zenodo.23964101)

Concept DOI (always the latest version): [10.5281/zenodo.23964101](https://doi.org/10.5281/zenodo.23964101) · v0.1.0, with the dated neutrino prediction: [10.5281/zenodo.23964102](https://doi.org/10.5281/zenodo.23964102)
