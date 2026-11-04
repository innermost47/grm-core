# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Scales - from the forces to the classical world, and back.

Every scale of the classical world is written as a pair in tension that gives a third thing: the size of an atom
is the electric pull of the nucleus against the quantum agitation of the electron, a planet stops growing where
gravity meets the electrons' refusal to be squeezed, a star is gravity against the pressure of hot matter, an
asteroid becomes round where gravity overcomes the strength of rock, a mountain stops where gravity crushes its
base. These are established relations of physics (Carr & Rees 1979, Weisskopf 1975, Press & Lightman 1983,
Lineweaver & Norman 2010); the GRM puts them in one network and runs it both ways:

    up      only the constants of the small (hbar, c, G, electron and proton masses, alpha) are measured:
            the network predicts the large (atoms, rocks, Jupiter, the Sun, asteroids, mountains)
    down    only the large is measured: the network infers the constants of the small
    cycle   does the large predicted by the small give back the small it came from?
    protocol each large-scale measurement is hidden in turn and predicted by all the rest; then every
            measurement is scrambled (up to a factor of 10) to see whether the successes could be chance

Scaling laws are written with their prefactor 1 and a tolerance of SCALING_SIGMA (they hold to a factor of a few,
not exactly); exact relations (definitions, Bohr's atom) are tight. All of it is printed with the pair behind it.

Usage:
    python grm_scales.py            # up, down, cycle and protocol
"""
import math
import random

from grm import GlobalRelationalNetwork

LG = math.log10
SCALING_SIGMA = 0.15        # dex: a law of physics written without its exact prefactor (hypothesis)
EXACT = 1e-9
EV = 1.602176634e-19
M_SUN = 1.98847e30

# ------------------------------------------------------------------ the network
# node: (guess, unit, scale) ; the constants of the small first, then the scales they make
NODES = {
    "hbar": (1.054571817e-34, "J s"), "c": (299792458.0, "m/s"), "G": (6.6743e-11, "m3/(kg s2)"),
    "me": (9.1093837e-31, "kg"), "mp": (1.67262192e-27, "kg"), "alpha": (7.2973525693e-3, ""),
    "alphaG": (5.9e-39, ""), "a0": (5.29e-11, "m"), "ER": (2.18e-18, "J"),
    "A_rock": (20.0, ""), "eta": (4.0, "Bohr radii"), "rho_rock": (2700.0, "kg/m3"),
    "R_jup": (7e7, "m"), "M_jup": (1.9e27, "kg"), "M_star": (2e30, "kg"), "M_ch": (2.9e30, "kg"),
    "sigma_y": (1e7, "Pa"), "R_potato": (2.5e5, "m"), "S_crust": (2.7e8, "Pa"),
    "M_earth": (5.97e24, "kg"), "R_earth": (6.37e6, "m"), "g_earth": (9.8, "m/s2"), "h_earth": (1e4, "m"),
    "M_mars": (6.42e23, "kg"), "R_mars": (3.39e6, "m"), "g_mars": (3.7, "m/s2"), "h_mars": (2.4e4, "m"),
    "M_venus": (4.87e24, "kg"), "R_venus": (6.05e6, "m"), "g_venus": (8.9, "m/s2"), "h_venus": (6.4e3, "m"),
}

# (name, pair in tension -> what is born, terms {node: exponent}, rhs (log10), sigma)
RELATIONS = [
    ("gravity's own coupling", "definition", {"alphaG": 1, "G": -1, "mp": -2, "hbar": 1, "c": 1}, 0.0, EXACT),
    ("atom: size", "electric pull  x  quantum agitation -> the atom",
     {"a0": 1, "hbar": -1, "me": 1, "c": 1, "alpha": 1}, 0.0, EXACT),
    ("atom: binding", "electric pull  x  quantum agitation -> its binding energy",
     {"ER": 1, "alpha": -2, "me": -1, "c": -2}, LG(0.5), EXACT),
    ("solid: density", "size of atoms  x  mass of nuclei -> the density of rock",
     {"rho_rock": 1, "A_rock": -1, "mp": -1, "eta": 3, "a0": 3}, 0.0, EXACT),
    ("cold body: largest radius", "gravity  x  electrons that refuse to be squeezed -> the largest planet (Jupiter)",
     {"R_jup": 1, "a0": -1, "alpha": -0.5, "alphaG": 0.5}, 0.0, SCALING_SIGMA),
    ("cold body: largest mass", "gravity  x  atomic matter -> the mass of the largest planet",
     {"M_jup": 1, "mp": -1, "alpha": -1.5, "alphaG": 1.5}, 0.0, SCALING_SIGMA),
    ("star: mass", "gravity  x  pressure of hot matter -> the mass of a star",
     {"M_star": 1, "mp": -1, "alphaG": 1.5}, 0.0, SCALING_SIGMA),
    ("star: Chandrasekhar limit", "gravity  x  relativistic electrons -> the heaviest white dwarf",
     # M_Ch = 0.77 alphaG^-3/2 mp / mu_e^2 ... written exactly: 3.098 (hbar c / G)^3/2 / (mu_e m_p)^2, mu_e = 2
     {"M_ch": 1, "hbar": -1.5, "c": -1.5, "G": 1.5, "mp": 2}, LG(3.098 / 4.0), 0.01),
    ("asteroid: round", "gravity  x  strength of rock -> the size from which a body is round (Lineweaver & Norman)",
     {"R_potato": 1, "sigma_y": -0.5, "G": 0.5, "rho_rock": 1}, LG(math.sqrt(1 / 0.44)), 0.1),
    ("Earth: surface gravity", "mass  x  size -> the pull at the surface", {"g_earth": 1, "G": -1, "M_earth": -1, "R_earth": 2}, 0.0, EXACT),
    ("Mars: surface gravity", "mass  x  size -> the pull at the surface", {"g_mars": 1, "G": -1, "M_mars": -1, "R_mars": 2}, 0.0, EXACT),
    ("Venus: surface gravity", "mass  x  size -> the pull at the surface", {"g_venus": 1, "G": -1, "M_venus": -1, "R_venus": 2}, 0.0, EXACT),
    ("Earth: highest mountain", "gravity  x  strength of the crust -> the tallest mountain",
     {"h_earth": 1, "S_crust": -1, "rho_rock": 1, "g_earth": 1}, 0.0, SCALING_SIGMA),
    ("Mars: highest mountain", "gravity  x  strength of the crust -> the tallest mountain",
     {"h_mars": 1, "S_crust": -1, "rho_rock": 1, "g_mars": 1}, 0.0, SCALING_SIGMA),
    ("Venus: highest mountain", "gravity  x  strength of the crust -> the tallest mountain",
     {"h_venus": 1, "S_crust": -1, "rho_rock": 1, "g_venus": 1}, 0.0, SCALING_SIGMA),
]

# measurements: (value, sigma in dex)
SMALL = {   # the constants of the small (CODATA 2018)
    "hbar": (1.054571817e-34, 1e-9), "c": (299792458.0, 1e-9), "G": (6.6743e-11, 1e-5),
    "me": (9.1093837015e-31, 1e-9), "mp": (1.67262192369e-27, 1e-9), "alpha": (7.2973525693e-3, 1e-9),
}
UNIVERSAL = ["hbar", "c", "G"]          # the constants that do not belong to matter: kept in both directions
MATERIAL = {   # what rock is made of: hypotheses, loose
    "A_rock": (20.0, 0.1),               # mean mass number of silicate rock (SiO2: 20)
    "eta": (4.0, 0.2),                   # spacing of atoms in rock, in Bohr radii (a few)
    "sigma_y": (1e7, 0.3),               # yield strength of rock under self-gravity (Lineweaver & Norman use 10 MPa)
}
PLANETS = {    # masses and radii of the planets (NASA fact sheets): the context of the mountains
    "M_earth": (5.9722e24, 1e-4), "R_earth": (6.371e6, 1e-4), "M_mars": (6.4171e23, 1e-4), "R_mars": (3.3895e6, 1e-4),
    "M_venus": (4.8675e24, 1e-4), "R_venus": (6.0518e6, 1e-4),
}
LARGE = {      # what the large world shows
    "a0": (5.29177210903e-11, 1e-6),                 # the size of hydrogen
    "ER": (13.598434 * EV, 3e-4),                     # ionisation energy of hydrogen (reduced mass: 0.05 %)
    "rho_rock": (2700.0, 0.05),                       # continental crust
    "R_jup": (6.9911e7, 1e-3), "M_jup": (1.89813e27, 1e-3),
    "M_star": (M_SUN, 0.3),                           # "a star": the Sun, one star among others (factor 2)
    "R_potato": (2.5e5, 0.1),                         # 200 to 300 km (Lineweaver & Norman 2010)
    "h_earth": (1.02e4, 0.05),                        # Mauna Kea, base to peak
    "h_mars": (2.4e4, 0.05),                          # Olympus Mons, 21.9 to 26 km base to peak
    "h_venus": (6.4e3, 0.05),                         # Maxwell Montes, base to peak
}


def network():
    nodes = {k: {"guess": g} for k, (g, _) in NODES.items()}
    rels = [{"name": n, "terms": t, "rhs": r, "sigma": s} for n, _, t, r, s in RELATIONS]
    return GlobalRelationalNetwork(nodes, rels, undetermined_sigma=1.0)


def solve(measured):
    return network().solve(measured, compute_uncertainty=True)


def pull(value, sigma_pred, truth, sigma_meas):
    """Distance between a prediction and a measurement, in dex and in combined sigmas."""
    d = LG(value) - LG(truth)
    return d, d / math.hypot(max(sigma_pred, 1e-12), sigma_meas)


def report(title, out, targets):
    print(f"\n{title}")
    print(f"  {'quantity':<12}{'predicted':>12}{'measured':>12}{'factor':>9}{'sigma':>8}   status")
    for k, (truth, s_m) in targets.items():
        v, s = out["values"][k], out["sigma_dex"][k]
        if k in out["undetermined"]:
            print(f"  {k:<12}{'—':>12}{truth:>12.3g}{'':>9}{'':>8}   not determined by this side")
            continue
        d, z = pull(v, s, truth, s_m)
        print(f"  {k:<12}{v:>12.3g}{truth:>12.3g}{10 ** abs(d):>9.2f}{z:>+8.1f}   {'ok' if abs(z) < 2 else 'off'}")


def run_up():
    measured = {**SMALL, **MATERIAL, **PLANETS}
    measured["S_crust"] = (2.7e8, 1.0)            # strength of a planet's crust: unknown, a very weak prior
    return solve(measured)


ATOMIC = ("a0", "ER")     # measured on the atom itself: too close to the small to count as "the large"


def run_down(with_atom=True):
    """From the large: every constant of matter (me, mp, alpha) is hidden; hbar, c, G stay.
    with_atom=False: the hydrogen atom is hidden too, only planets, stars, rocks and mountains remain."""
    measured = {k: SMALL[k] for k in UNIVERSAL}
    measured.update(MATERIAL)
    measured.update(PLANETS)
    measured.update({k: v for k, v in LARGE.items() if with_atom or k not in ATOMIC})
    return solve(measured)


def leave_one_out():
    base = {**SMALL, **MATERIAL, **PLANETS, **LARGE}
    rows = []
    for k, (truth, s_m) in LARGE.items():
        rest = {q: v for q, v in base.items() if q != k}
        out = solve(rest)
        if k in out["undetermined"]:
            rows.append((k, None, None))
            continue
        d, z = pull(out["values"][k], out["sigma_dex"][k], truth, s_m)
        rows.append((k, d, z))
    return rows


def chance_test(trials=20, seed=0):
    """Scramble every large-scale measurement by up to a factor of 10 and count how many are still recovered."""
    rng = random.Random(seed)
    real = sum(1 for _, d, z in leave_one_out() if z is not None and abs(z) < 2)
    counts = []
    for _ in range(trials):
        fake = {k: (v * 10 ** rng.uniform(-1, 1), s) for k, (v, s) in LARGE.items()}
        base = {**SMALL, **MATERIAL, **PLANETS, **fake}
        n = 0
        for k, (truth, s_m) in fake.items():
            out = solve({q: v for q, v in base.items() if q != k})
            if k not in out["undetermined"]:
                n += abs(pull(out["values"][k], out["sigma_dex"][k], truth, s_m)[1]) < 2
        counts.append(n)
    return real, sum(counts) / trials, max(counts)


def main():
    print("The pairs in tension of this network:")
    for name, pair, *_ in RELATIONS:
        if pair != "definition" and "surface" not in name:
            print(f"  {name:<28} {pair}")
    up = run_up()
    report("UP: only the constants of the small are measured -> the large", up, LARGE)
    print(f"  (and a prediction no measurement enters: the heaviest white dwarf, "
          f"{up['values']['M_ch'] / M_SUN:.2f} solar masses; Chandrasekhar's limit is 1.4)")
    down = run_down()
    report("DOWN: only the large is measured (with hbar, c, G) -> the constants of matter", down,
           {k: SMALL[k] for k in ("me", "mp", "alpha")})
    print("  (here the hydrogen atom is among the data: it gives alpha and the electron mass by itself)")
    far = run_down(with_atom=False)
    report("DOWN, FROM THE SKY ONLY: Jupiter, the Sun, rocks, asteroids, mountains -> the constants of matter", far,
           {k: SMALL[k] for k in ("me", "mp", "alpha")} | {"a0": LARGE["a0"]})
    # cycle: the large predicted by the small, used as data, must give back the small
    cycle_meas = {k: SMALL[k] for k in UNIVERSAL}
    cycle_meas.update(MATERIAL)
    cycle_meas.update(PLANETS)
    for k in LARGE:
        if k not in up["undetermined"]:
            cycle_meas[k] = (up["values"][k], max(up["sigma_dex"][k], 1e-6))
    back = solve(cycle_meas)
    report("CYCLE: the large predicted from the small, used as data -> the small again", back,
           {k: SMALL[k] for k in ("me", "mp", "alpha")})
    print("\nPROTOCOL: each large-scale measurement hidden in turn, predicted by everything else")
    print("  (a0 and ER follow exactly from the constants: they are checks of the definitions, not tests)")
    rows = leave_one_out()
    for k, d, z in rows:
        print(f"  {k:<12}" + ("not determined" if z is None else f"factor {10 ** abs(d):5.2f}   {z:+5.1f} sigma   {'ok' if abs(z) < 2 else 'off'}"))
    real, mean_fake, max_fake = chance_test()
    print(f"\nCHANCE TEST: recovered with the real values {real}/{len(LARGE)}; "
          f"with scrambled values {mean_fake:.1f} on average (at most {max_fake})")


if __name__ == "__main__":
    main()
