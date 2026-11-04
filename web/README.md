# The Relational Universe (web)

**Live: [simulation.anthony-charretier.fr](https://simulation.anthony-charretier.fr)**

From the Big Bang to the end of time, in a browser (phones included). Every number the page shows or plays is a node
of one GRM network (`universe.js`), solved by `grm.js`, the JavaScript port of `grm.py`:

- **the atom**: Bohr radius, Rydberg energy, the weakness of gravity (α_G);
- **the cosmos**: Friedmann (H0, Ω_b, Ω_c, radiation from T0 and neutrinos, flat: Ω_Λ = 1 - Ω_m - Ω_r), baryons per photon,
  the first nuclei (deuterium Saha), recombination (hydrogen Saha), the age of the universe and the time of every event
  (the Friedmann integral), the sound horizon and the first acoustic peak of the microwave sky, the radius of the observable universe (46.2
  billion light-years today; shown at every moment as a(t) times how far light has gone, ∫ c dt / a);
- **the stars**: mass, life and surface temperature (Carr & Rees scaling laws, prefactors set on the Sun), the Sun's
  birth and red giant, the end of the stars, the evaporation of black holes (Hawking);
- **the Earth and the music**: the Earth warmed by the Sun, the speed of sound in its air, a flute cut for the Lydian mode
  on F in our air (when the air changes, it plays higher or lower, still in tune), the cosmic chord (the acoustic peaks,
  heard 50 octaves higher), the air between the flute and the listener (ISO 9613-1 absorption at the Earth's temperature).

Each relation says what kind of elastic it is: a **law** of physics (with its source), a **hypothesis** (a scaling law,
its prefactor set on our universe: said where), or a **musical** choice. The "Elastics" panel lists them all.

The constants go far from ours (G from ÷1000 to ×1000, dark matter up to ×40, the light up to 300 K). With too much matter
the universe is **closed** (Ω_k < 0): it reaches a largest size a_max, stops (t_max), falls back as it grew and ends in a
**Big Crunch** at 2 t_max; the light heats up again, the sky turns back into plasma, the galaxies fall into one point.
Far universes are reached by continuation (solved step by step from ours). A universe the network cannot hold together
says so, and names its most strained relation. Double-click (or double-tap) a slider: that constant goes back to ours. "New Big Bang" opens the constants first; the
panel's button launches it. The buttons carry Font Awesome 6.5.1 icons (cdnjs); on a phone the HUD shows the icons only.

### Both endings, to the end

The film runs on one coordinate: log10 t, every decade of time given its share (slower where things happen). The film
pauses at the start of each epoch, with a card in the middle of the screen (its text and its numbers; "Resume" goes on; the bookmark button turns the pauses off, "To the end" plays
through), and each start is a mark on the timeline that can be clicked. Every
moment of both endings is a node of the network.

- **The cold end** (open universe, Adams & Laughlin 1997): the last stars go out (10¹⁴ years for us), the dead stars cool
  into black dwarfs (10¹⁵), the galaxies evaporate (stars share out their energy in close passages, t_relax =
  N / (8 ln N) t_cross, t_evap ≈ 136 t_relax, Binney & Tremaine: 3.9 × 10¹⁸ years for us, where Adams & Laughlin
  estimate ~10¹⁹; nine stars in ten are flung away, the rest sink into the central black hole), protons decay if they do
  (10³⁷ years, a hypothesis: never observed, > 2.4 × 10³⁴ years), then the black holes evaporate one by one in a last flash
  (Hawking: stellar ones from 10⁶⁸ to 10⁷² years, the largest at 10⁹⁷), and the dark.
- **The Big Crunch** (closed universe, Rees 1969): after the turnaround the film mirrors itself, lt = 2 log10 t_max -
  log10 (time left), so the fall lasts on screen as long as the rise, down to the last hundredth of a second. Each
  threshold is a temperature of the light, held by the network, and the time left when it is crossed is the Friedmann
  integral run backwards: the galaxies merge when the universe is as dense as they are (18π² times the density at their
  collapse), the atoms are broken (plasma again, at the recombination temperature), the sky outshines the stars (they
  are cooked from outside, at the Sun's surface temperature), the nuclei are broken (at the temperature where they
  formed), and everything falls into one point: a last flash, then the dark. The cosmic chord climbs with the light
  (blueshift) while the universe falls.

## Online

The folder is the site: upload it as it is (`tests/` and the `.md` files are hidden by `.htaccess`). `.htaccess` (Apache)
forces HTTPS (301, also behind a proxy), drops `www`, sends HSTS and the usual security headers, the right MIME types,
compression, and caching (the page and scripts revalidated, images a month). SEO: title, description, canonical, Open
Graph and Twitter cards with `og-image.png` (1200×630, a capture of the page), JSON-LD (`WebApplication`), `robots.txt`,
`sitemap.xml`, favicons (`favicon.svg`, `favicon.ico`, `icons/`) and `site.webmanifest`.

## Run

Any static server, from this folder:

```bash
python -m http.server 8000        # then open http://localhost:8000
```

Three.js 0.160.0 comes from jsDelivr (import map in `index.html`). No build step, no server code.

## Tests

```bash
python web/tests/make_golden.py   # the Python GRM solves the reference networks -> golden.json
node web/tests/test_grm_js.mjs    # grm.js gives the same numbers (values to 1e-9, uncertainties to 1e-5)
node web/tests/test_universe.mjs  # the universe network against what is measured in ours
```

`test_universe.mjs` checks, among others: the age of the universe (13.81 Gyr, Planck: 13.80), baryons per photon
(6.1e-10), recombination at z = 1090 and 372 000 years, the first acoustic peak at ℓ = 221.5 (Planck: 220), the sound
horizon 144 Mpc, the first nuclei at kT = 0.066 MeV after 5 minutes, the speed of sound in air (340 m/s).

## Honest limits

- Recombination: Saha's equilibrium is corrected by one factor (0.79) so that our universe gives Planck's z* = 1089.9;
  the real delay (Peebles 1968) is not modelled.
- The first stars are set at z = 20 (structure formation is not computed); the stars follow scaling laws calibrated on
  the Sun; the end of the stars (10¹⁴ years for us) is scaled with the life of stars.
- The pictures between those moments (the gas gathering into galaxies, the camera, the colours from a black-body fit)
  are drawing, not physics.
- A closed universe falls back symmetrically (a(t) mirrored about t_max), as a universe of matter and curvature does; with
  radiation and dark energy this is an approximation. The Sun's birth keeps our share of the age (4.567 of 13.8 Gyr).
- Some universes do not settle (for example everything at its limit at once): the page says so, the network refuses.
- The far future: a galaxy is given 10¹¹ suns of matter; the stellar black holes' masses are spread over 4 decades and the
  central ones over 10 for the picture (only the network's two values, 10 and 10¹⁰ stars, are computed); the black dwarfs
  are drawn as faint ghosts so that their motion stays visible (they no longer shine). Proton decay is a hypothesis.
- The Big Crunch stops at the last hundredth of a second: what happens at the point itself needs a quantum gravity
  that no one has.
