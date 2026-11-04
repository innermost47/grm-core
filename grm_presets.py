# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
Presets of the GRM explorer (grm_explorer.py): networks in the explorer's JSON form.

Two kinds:
    "known"  textbook problems with a known answer: each has an "expected" value, so the explorer can show at
             once whether the network reproduces it (a check of the solver and of the way the problem is written).
    "open"   problems that physics has not solved today. These presets do NOT solve them. They write the data
             as a network so that the tension can be seen and measured (pulls, chi2), and some add the node of a
             hypothesis that has been proposed in the literature, to show how large it would have to be.
             The network says what the data ask for; it does not test the physics of the hypothesis.

JSON form of a network:
    nodes:     {name: {"guess", "scale": "log"|"lin", "measured": [value, sigma_dex], "expected": value,
                       "tolerance": relative, "fixed": bool, "unit": str}}
    relations: [{"name", "type": "log", "terms": {node: power}, "rhs", "sigma"},
                {"name", "type": "sum", "terms": {node: coeff}, "pow": {node: p}, "K", "sigma"},
                {"name", "type": "fn", "expr": "expression of the nodes that must be 0", "sigma"}]
    sigma_dex: relative uncertainty / ln(10)  (1 % ~ 0.00434 dex)
"""
import math

LG = math.log10


def dex(relative):
    """relative 1-sigma uncertainty -> sigma in dex (3 significant figures)"""
    return float(f"{relative / math.log(10.0):.3g}")


PRESETS = [
    # ================================================================== known problems
    {
        "id": "rydberg",
        "category": "known",
        "title": "Rydberg constant from alpha, m_e, c, h",
        "description": "R_inf = alpha^2 m_e c / (2 h). From the fine-structure constant and the electron mass "
                       "(CODATA 2018), with c and h exact, the network must give the measured Rydberg constant.",
        "sources": ["CODATA 2018 recommended values, NIST: https://physics.nist.gov/cuu/Constants/"],
        "nodes": {
            "Rinf": {"guess": 1.0e7, "expected": 10973731.568160, "tolerance": 1e-9, "unit": "1/m"},
            "alpha": {"guess": 7.3e-3, "measured": [7.2973525693e-3, dex(1.5e-10)]},
            "me": {"guess": 9.1e-31, "measured": [9.1093837015e-31, dex(3.0e-10)], "unit": "kg"},
            "c": {"guess": 3.0e8, "measured": [299792458.0, 1e-12], "unit": "m/s"},
            "h": {"guess": 6.6e-34, "measured": [6.62607015e-34, 1e-12], "unit": "J s"},
        },
        "relations": [
            {"name": "Rydberg", "type": "log", "terms": {"Rinf": 1, "alpha": -2, "me": -1, "c": -1, "h": 1},
             "rhs": -LG(2.0), "sigma": 1e-12},
        ],
    },
    {
        "id": "bohr",
        "category": "known",
        "title": "Bohr radius",
        "description": "a0 = hbar / (m_e c alpha) = h / (2 pi m_e c alpha). Expected: CODATA 2018 a0.",
        "sources": ["CODATA 2018 recommended values, NIST: https://physics.nist.gov/cuu/Constants/"],
        "nodes": {
            "a0": {"guess": 5e-11, "expected": 5.29177210903e-11, "tolerance": 1e-9, "unit": "m"},
            "alpha": {"guess": 7.3e-3, "measured": [7.2973525693e-3, dex(1.5e-10)]},
            "me": {"guess": 9.1e-31, "measured": [9.1093837015e-31, dex(3.0e-10)], "unit": "kg"},
            "c": {"guess": 3.0e8, "measured": [299792458.0, 1e-12], "unit": "m/s"},
            "h": {"guess": 6.6e-34, "measured": [6.62607015e-34, 1e-12], "unit": "J s"},
        },
        "relations": [
            {"name": "Bohr radius", "type": "log", "terms": {"a0": 1, "me": 1, "c": 1, "alpha": 1, "h": -1},
             "rhs": -LG(2 * math.pi), "sigma": 1e-12},
        ],
    },
    {
        "id": "kepler",
        "category": "known",
        "title": "Mass of the Sun from the Earth's orbit (Kepler III)",
        "description": "G (M_sun + M_earth) = 4 pi^2 a^3 / T^2, with a = 1 au and T = one sidereal year. "
                       "Expected: the heliocentric gravitational constant GM_sun. The network finds a value "
                       "about 3e-6 higher: that is the Earth's own mass (and the Moon), which Kepler's law "
                       "includes; hence the tolerance of 1e-5.",
        "sources": ["IAU 2012 Resolution B2 (astronomical unit) and IAU 2015 Resolution B3 (nominal GM_sun)"],
        "nodes": {
            "GM": {"guess": 1e20, "expected": 1.3271244e20, "tolerance": 1e-5, "unit": "m^3/s^2"},
            "a": {"guess": 1.5e11, "measured": [1.495978707e11, 1e-10], "unit": "m"},
            "T": {"guess": 3.0e7, "measured": [365.256363004 * 86400, 1e-10], "unit": "s"},
        },
        "relations": [
            {"name": "Kepler III", "type": "log", "terms": {"GM": 1, "a": -3, "T": 2},
             "rhs": LG(4 * math.pi ** 2), "sigma": 1e-12},
        ],
    },
    {
        "id": "sound",
        "category": "known",
        "title": "Speed of sound in air at 20 degrees C",
        "description": "c^2 = gamma R T / M for an ideal gas. Expected about 343.2 m/s.",
        "sources": ["R from CODATA 2018 (exact since 2019); molar mass of dry air 28.9647 g/mol"],
        "nodes": {
            "c": {"guess": 300.0, "expected": 343.2, "tolerance": 1e-3, "unit": "m/s"},
            "gamma": {"guess": 1.4, "measured": [1.4, dex(1e-4)]},
            "R": {"guess": 8.3, "measured": [8.314462618, 1e-12], "unit": "J/(mol K)"},
            "T": {"guess": 300.0, "measured": [293.15, dex(1e-4)], "unit": "K"},
            "M": {"guess": 0.03, "measured": [0.0289647, dex(1e-5)], "unit": "kg/mol"},
        },
        "relations": [
            {"name": "ideal gas sound speed", "type": "log", "terms": {"c": 2, "gamma": -1, "R": -1, "T": -1, "M": 1},
             "rhs": 0.0, "sigma": 1e-12},
        ],
    },
    {
        "id": "sun_luminosity",
        "category": "known",
        "title": "Luminosity of the Sun (Stefan-Boltzmann)",
        "description": "L = 4 pi R^2 sigma_SB T_eff^4 with the IAU nominal radius and effective temperature. "
                       "Expected: the IAU nominal luminosity 3.828e26 W.",
        "sources": ["IAU 2015 Resolution B3 (nominal solar values); CODATA 2018 sigma_SB"],
        "nodes": {
            "L": {"guess": 1e26, "expected": 3.828e26, "tolerance": 1e-3, "unit": "W"},
            "sigmaSB": {"guess": 5.7e-8, "measured": [5.670374419e-8, 1e-12], "unit": "W/(m^2 K^4)"},
            "R": {"guess": 7e8, "measured": [6.957e8, dex(1e-4)], "unit": "m"},
            "T": {"guess": 6000.0, "measured": [5772.0, dex(1e-4)], "unit": "K"},
        },
        "relations": [
            {"name": "Stefan-Boltzmann", "type": "log", "terms": {"L": 1, "sigmaSB": -1, "R": -2, "T": -4},
             "rhs": LG(4 * math.pi), "sigma": 1e-12},
        ],
    },
    {
        "id": "pendulum",
        "category": "known",
        "title": "g from a pendulum",
        "description": "T = 2 pi sqrt(L / g): a 1 m pendulum that swings in 2.006 s. Expected g about 9.81 m/s^2. "
                       "Change the measured period to see g move, and its uncertainty follow the measurement's.",
        "sources": ["small-angle pendulum, any mechanics textbook"],
        "nodes": {
            "g": {"guess": 10.0, "expected": 9.81, "tolerance": 2e-3, "unit": "m/s^2"},
            "L": {"guess": 1.0, "measured": [1.0, dex(1e-3)], "unit": "m"},
            "T": {"guess": 2.0, "measured": [2.006, dex(5e-4)], "unit": "s"},
        },
        "relations": [
            {"name": "pendulum", "type": "log", "terms": {"T": 1, "L": -0.5, "g": 0.5}, "rhs": LG(2 * math.pi),
             "sigma": 1e-12},
        ],
    },
    {
        "id": "pythagoras",
        "category": "known",
        "title": "Pythagoras (a sum relation)",
        "description": "a^2 + b^2 = c^2, written as a sum relation with powers. a = 3 and b = 4 measured: "
                       "expected c = 5.",
        "sources": ["Euclid, Elements I.47"],
        "nodes": {
            "a": {"guess": 1.0, "measured": [3.0, 1e-6]},
            "b": {"guess": 1.0, "measured": [4.0, 1e-6]},
            "c": {"guess": 1.0, "expected": 5.0, "tolerance": 1e-6},
        },
        "relations": [
            {"name": "right triangle", "type": "sum", "terms": {"a": 1, "b": 1, "c": -1}, "pow": {"a": 2, "b": 2, "c": 2},
             "K": 0.0, "sigma": 1e-9},
        ],
    },
    {
        "id": "wien",
        "category": "known",
        "title": "Wien's displacement constant (an fn relation)",
        "description": "The peak of Planck's law: x = 5 (1 - exp(-x)), with x = h c / (lambda_max k T), "
                       "a transcendental equation written as an fn relation. Then b = lambda_max T = h c / (k x). "
                       "Expected: x = 4.965114231744276 and the CODATA 2018 value of b.",
        "sources": ["CODATA 2018 recommended values (Wien wavelength displacement law constant), NIST"],
        "nodes": {
            "x": {"guess": 3.0, "expected": 4.965114231744276, "tolerance": 1e-9},
            "b": {"guess": 3e-3, "expected": 2.897771955e-3, "tolerance": 1e-8, "unit": "m K"},
            "h": {"guess": 6.6e-34, "measured": [6.62607015e-34, 1e-12], "unit": "J s"},
            "c": {"guess": 3.0e8, "measured": [299792458.0, 1e-12], "unit": "m/s"},
            "k": {"guess": 1.4e-23, "measured": [1.380649e-23, 1e-12], "unit": "J/K"},
        },
        "relations": [
            {"name": "peak of Planck's law", "type": "fn", "expr": "x - 5 * (1 - exp(-x))", "sigma": 1e-12},
            {"name": "Wien constant", "type": "log", "terms": {"b": 1, "x": 1, "h": -1, "c": -1, "k": 1}, "rhs": 0.0,
             "sigma": 1e-12},
        ],
    },
    # ================================================================== open problems
    {
        "id": "hubble_tension",
        "category": "open",
        "title": "Hubble tension (data only)",
        "description": "OPEN PROBLEM. One universe, one expansion rate H0, measured two ways: from the cosmic "
                       "microwave background with the LambdaCDM model (Planck 2018: 67.4 +- 0.5 km/s/Mpc) and "
                       "from the local distance ladder (SH0ES 2022: 73.04 +- 1.04). The network asks both to be "
                       "the same H0: look at the chi2 and at the pulls of the two measurements. Leave-one-out "
                       "predicts each one from the other.",
        "sources": ["CERN Courier, 'The Hubble tension', March 2025: https://cern-courier.web.cern.ch/a/the-hubble-tension/",
                    "Planck 2018 results VI; Riess et al. 2022 (SH0ES)"],
        "nodes": {
            "H0": {"guess": 70.0, "unit": "km/s/Mpc"},
            "H0_cmb": {"guess": 70.0, "measured": [67.4, dex(0.5 / 67.4)], "unit": "km/s/Mpc"},
            "H0_ladder": {"guess": 70.0, "measured": [73.04, dex(1.04 / 73.04)], "unit": "km/s/Mpc"},
        },
        "relations": [
            {"name": "CMB measures H0", "type": "log", "terms": {"H0_cmb": 1, "H0": -1}, "rhs": 0.0, "sigma": 1e-9},
            {"name": "ladder measures H0", "type": "log", "terms": {"H0_ladder": 1, "H0": -1}, "rhs": 0.0, "sigma": 1e-9},
        ],
    },
    {
        "id": "hubble_sound_horizon",
        "category": "open",
        "title": "Hubble tension: a smaller sound horizon? (hypothesis)",
        "description": "OPEN PROBLEM, PROPOSAL. The CMB fixes the angle of the sound horizon, so it measures the "
                       "product H0 * r_s: if new physics before recombination (for instance early dark energy) "
                       "made r_s smaller than LambdaCDM's, the CMB value of H0 would rise. The node r_ratio = "
                       "r_s / r_s(LambdaCDM) starts at 1 with a loose prior of about 10 %: the network finds how "
                       "much smaller r_s would have to be for both measurements to agree. This is a size, not "
                       "evidence: whether such physics exists, and what it does to other data, is not in this "
                       "network.",
        "sources": ["CERN Courier, 'The Hubble tension', March 2025: https://cern-courier.web.cern.ch/a/the-hubble-tension/",
                    "Poulin, Smith, Karwal, Kamionkowski, Phys. Rev. Lett. 122, 221301 (2019), early dark energy"],
        "nodes": {
            "H0": {"guess": 70.0, "unit": "km/s/Mpc"},
            "H0_cmb": {"guess": 70.0, "measured": [67.4, dex(0.5 / 67.4)], "unit": "km/s/Mpc"},
            "H0_ladder": {"guess": 70.0, "measured": [73.04, dex(1.04 / 73.04)], "unit": "km/s/Mpc"},
            "r_ratio": {"guess": 1.0, "measured": [1.0, dex(0.10)]},
        },
        "relations": [
            {"name": "CMB measures H0 r_s", "type": "log", "terms": {"H0_cmb": 1, "H0": -1, "r_ratio": -1}, "rhs": 0.0,
             "sigma": 1e-9},
            {"name": "ladder measures H0", "type": "log", "terms": {"H0_ladder": 1, "H0": -1}, "rhs": 0.0, "sigma": 1e-9},
        ],
    },
    {
        "id": "neutron_lifetime",
        "category": "open",
        "title": "Neutron lifetime puzzle (data only)",
        "description": "OPEN PROBLEM. The free neutron's lifetime measured by counting the protons it makes "
                       "(beam: 887.7 +- 2.2 s) and by counting the neutrons that survive in a trap (bottle, "
                       "UCNtau: 877.82 +- 0.22 s). One neutron, one lifetime: the network shows how far apart "
                       "they are.",
        "sources": ["Particle Data Group, neutron mean life: https://pdglive.lbl.gov/view/S017T",
                    "Yue et al., Phys. Rev. Lett. 111, 222501 (2013); Musedinovic et al. 2025 (UCNtau)"],
        "nodes": {
            "tau": {"guess": 880.0, "unit": "s"},
            "tau_beam": {"guess": 880.0, "measured": [887.7, dex(2.2 / 887.7)], "unit": "s"},
            "tau_bottle": {"guess": 880.0, "measured": [877.82, dex(0.22 / 877.82)], "unit": "s"},
        },
        "relations": [
            {"name": "beam measures tau", "type": "log", "terms": {"tau_beam": 1, "tau": -1}, "rhs": 0.0, "sigma": 1e-9},
            {"name": "bottle measures tau", "type": "log", "terms": {"tau_bottle": 1, "tau": -1}, "rhs": 0.0, "sigma": 1e-9},
        ],
    },
    {
        "id": "neutron_dark_decay",
        "category": "open",
        "title": "Neutron lifetime: a decay without a proton? (hypothesis)",
        "description": "OPEN PROBLEM, PROPOSAL. A bottle counts every neutron that disappears; a beam counts only "
                       "the decays that make a proton. If a share of neutrons decayed into something else (a dark "
                       "particle), the beam would see tau_beam = tau / Br_p. The node Br_p (share of decays with a "
                       "proton) has a loose prior around 1: the network finds the branch the two experiments ask "
                       "for (about 1 %). Searches for such a decay have so far not found it; this network only "
                       "gives the size that would be needed.",
        "sources": ["Fornal & Grinstein, Phys. Rev. Lett. 120, 191801 (2018)",
                    "Particle Data Group, neutron mean life: https://pdglive.lbl.gov/view/S017T"],
        "nodes": {
            "tau": {"guess": 880.0, "unit": "s"},
            "Br_p": {"guess": 1.0, "measured": [1.0, dex(0.05)]},
            "tau_beam": {"guess": 880.0, "measured": [887.7, dex(2.2 / 887.7)], "unit": "s"},
            "tau_bottle": {"guess": 880.0, "measured": [877.82, dex(0.22 / 877.82)], "unit": "s"},
        },
        "relations": [
            {"name": "beam sees decays with a proton", "type": "log", "terms": {"tau_beam": 1, "tau": -1, "Br_p": 1},
             "rhs": 0.0, "sigma": 1e-9},
            {"name": "bottle sees every decay", "type": "log", "terms": {"tau_bottle": 1, "tau": -1}, "rhs": 0.0,
             "sigma": 1e-9},
        ],
    },
    {
        "id": "koide",
        "category": "open",
        "title": "Koide's relation for the charged leptons",
        "description": "OPEN PROBLEM. Q = (m_e + m_mu + m_tau) / (sqrt(m_e) + sqrt(m_mu) + sqrt(m_tau))^2 is "
                       "found equal to 2/3 within the precision of the tau mass. Nobody knows why (or whether it "
                       "is a coincidence). The network computes Q from the measured masses (in MeV) and checks it "
                       "against 2/3 within 3 sigma.",
        "sources": ["Koide, Lett. Nuovo Cimento 34, 201 (1982)",
                    "Particle Data Group: m_tau = 1776.93 +- 0.09 MeV; CODATA 2018 m_e; m_mu"],
        "nodes": {
            "Q": {"guess": 0.5, "expected": 2.0 / 3.0},
            "me": {"guess": 0.5, "measured": [0.51099895, dex(3e-10)], "unit": "MeV"},
            "mmu": {"guess": 100.0, "measured": [105.6583755, dex(2.2e-8)], "unit": "MeV"},
            "mtau": {"guess": 1800.0, "measured": [1776.93, dex(0.09 / 1776.93)], "unit": "MeV"},
        },
        "relations": [
            {"name": "Koide", "type": "fn",
             "expr": "Q * (sqrt(me) + sqrt(mmu) + sqrt(mtau))**2 - (me + mmu + mtau)", "sigma": 1e-9},
        ],
    },
    {
        "id": "koide_tau",
        "category": "open",
        "title": "Koide's relation predicts the tau mass (hypothesis)",
        "description": "OPEN PROBLEM, PROPOSAL. Take Q = 2/3 as exact and the electron and muon masses: the "
                       "network predicts the tau mass (about 1776.97 MeV) and compares it with the measured "
                       "1776.93 +- 0.09 MeV (tolerance 3 sigma of the measurement). A prediction that holds is "
                       "still not an explanation.",
        "sources": ["Koide, Lett. Nuovo Cimento 34, 201 (1982)", "Particle Data Group, tau mass"],
        "nodes": {
            "Q": {"guess": 0.6, "measured": [2.0 / 3.0, 1e-12]},
            "me": {"guess": 0.5, "measured": [0.51099895, dex(3e-10)], "unit": "MeV"},
            "mmu": {"guess": 100.0, "measured": [105.6583755, dex(2.2e-8)], "unit": "MeV"},
            "mtau": {"guess": 1800.0, "expected": 1776.93, "tolerance": 1.52e-4, "unit": "MeV"},
        },
        "relations": [
            {"name": "Koide", "type": "fn",
             "expr": "Q * (sqrt(me) + sqrt(mmu) + sqrt(mtau))**2 - (me + mmu + mtau)", "sigma": 1e-9},
        ],
    },
]


def by_id(preset_id):
    for p in PRESETS:
        if p["id"] == preset_id:
            return p
    raise KeyError(preset_id)
