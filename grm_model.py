# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
Global Relational Model, full network exported from the web model (https://grm.anthony-charretier.fr),
default preset: H x age = 1, local void, dark energy = space / time tension. 113 relations, 147 quantities, 55 measurements.

Units: SI for positive quantities (kg, m, s, K, J...), raw values for signed quantities ("scale": "lin").
Generated automatically from model.js (node and relation ids are those of the web model).
Relation kinds: identity (definition), standard (established physics), zero (symmetry), claim (relation under test).
"""
import math


def lg(x):
    return math.log10(x)


def cbrt(x):
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


def lcdm_age(H, OL, a):
    """Age at scale factor a of a flat matter + Lambda universe, in s."""
    Om = 1 - OL
    return 2 / (3 * H * math.sqrt(OL)) * math.asinh(math.sqrt(OL / Om) * a ** 1.5)


NODES = {
    "AU": {"guess": 149600000000.0},
    "DS": {"guess": 2.5549596e+20},
    "E0ratio": {"guess": 3.14},
    "EH": {"guess": 8e+69},
    "EP": {"guess": 1956000000.0},
    "Edark": {"guess": 0.0022},
    "Egam": {"guess": 511000.0},
    "Emid": {"guess": 0.0038},
    "Emin": {"guess": 6e-52},
    "Emq": {"guess": 1e-12},
    "Equant": {"guess": 3e-53},
    "Estock": {"guess": 1e+70},
    "Fratio": {"guess": 4.17e+42},
    "G": {"guess": 6.6743e-11, "fixed": True},
    "H0": {"guess": 2.26852902096769e-18},
    "H0loc": {"guess": 2.36575169329487e-18},
    "Hend": {"guess": 1.87963833165894e-18},
    "Ldark": {"guess": 0.000088},
    "Lmid": {"guess": 0.000047},
    "M": {"guess": 1.2e+15},
    "MS": {"guess": 8.550421e+36},
    "N": {"guess": 1.3e+19},
    "Nlam": {"guess": 1.6e+29},
    "Nops": {"guess": 2e+121},
    "Nph": {"guess": 22.6},
    "OB": {"guess": 0.047},
    "ODM": {"guess": 0.25},
    "OK": {"guess": 0.0, "scale": "lin"},
    "OL": {"guess": 0.7},
    "Odark": {"guess": 0.95},
    "Om": {"guess": 0.3},
    "Qatom": {"guess": 0.0, "scale": "lin"},
    "Qd": {"guess": -0.333333333333333, "scale": "lin"},
    "Qe": {"guess": -1.0, "scale": "lin"},
    "Qn": {"guess": 0.0, "scale": "lin"},
    "Qnu": {"guess": 0.0, "scale": "lin"},
    "Qp": {"guess": 1.0, "scale": "lin"},
    "Qu": {"guess": 0.666666666666667, "scale": "lin"},
    "Rh": {"guess": 1.3e+26},
    "Rs": {"guess": 1.3e+26},
    "Rsun": {"guess": 695700000.0},
    "Ry": {"guess": 13.6057},
    "RyH": {"guess": 13.598},
    "S": {"guess": 3e+122},
    "S0": {"guess": 2e+122},
    "Sigma": {"guess": 4.84884042682787e-28},
    "Snow": {"guess": 3e+104},
    "Snu": {"guess": 0.0607},
    "TD": {"guess": 0.1},
    "THS": {"guess": 1.4e-14},
    "TP": {"guess": 1.417e+32},
    "Tcmb": {"guess": 2.7255},
    "Tearth": {"guess": 255.0},
    "Tfloor": {"guess": 2.2e-30},
    "Tfr": {"guess": 1.0},
    "Trec": {"guess": 2973.0},
    "Tsun": {"guess": 5772.0},
    "YL": {"guess": -0.5, "scale": "lin"},
    "YQ": {"guess": 0.166666666666667, "scale": "lin", "fixed": True},
    "Yd": {"guess": -0.333333333333333, "scale": "lin"},
    "Ye": {"guess": -1.0, "scale": "lin"},
    "Yu": {"guess": 0.666666666666667, "scale": "lin"},
    "Z2A": {"guess": 51.0},
    "a0": {"guess": 1.1e-10},
    "aC": {"guess": 0.714},
    "aS": {"guess": 18.3},
    "ageP2": {"guess": 6e+121},
    "albedo": {"guess": 0.29, "scale": "lin"},
    "allRatio": {"guess": 1.0},
    "alpha": {"guess": 0.007297},
    "c": {"guess": 299792458.0, "fixed": True},
    "cosW": {"guess": 0.8813},
    "d21": {"guess": 0.0000749},
    "d31": {"guess": 0.002534},
    "dQCD": {"guess": 2.52, "scale": "lin"},
    "dQED": {"guess": -1.0, "scale": "lin"},
    "darkRatio": {"guess": 3.0},
    "delta": {"guess": 0.46, "scale": "lin"},
    "dmnp": {"guess": 1.293, "scale": "lin"},
    "e": {"guess": 1.602176634e-19, "fixed": True},
    "eps0": {"guess": 8.854e-12},
    "eta": {"guess": 6.1e-10},
    "etaEP": {"guess": 0.0, "scale": "lin"},
    "fH": {"guess": 2.9e-19},
    "fe": {"guess": 1.2e+20},
    "fmid": {"guess": 255.0},
    "fp": {"guess": 2.3e+23},
    "fpi": {"guess": 1.6412968312428e-28},
    "fq": {"guess": 0.00961},
    "hbar": {"guess": 1.054571817e-34, "fixed": True},
    "kB": {"guess": 1.380649e-23, "fixed": True},
    "lA": {"guess": 301.8},
    "lP": {"guess": 1.616e-35},
    "lamH": {"guess": 0.129},
    "ly": {"guess": 9.461e+15},
    "lyA": {"guess": 1.21567e-7},
    "m1": {"guess": 0.0015},
    "m2": {"guess": 0.0088},
    "m3": {"guess": 0.0504},
    "mH": {"guess": 125.2},
    "mHub": {"guess": 1.2e-33},
    "mP": {"guess": 2.176e-8},
    "mS": {"guess": 1.86e-9},
    "mW": {"guess": 80.36},
    "mZ": {"guess": 91.19},
    "md_q": {"guess": 8.3785110316511e-30},
    "me": {"guess": 9.10940241951853e-31},
    "mmu": {"guess": 1.8835249331536e-28},
    "mp": {"guess": 1.6726182012058e-27},
    "mpi": {"guess": 2.48806124401605e-28},
    "mtau": {"guess": 3.1676119685406e-27},
    "mu0": {"guess": 0.0000012566},
    "muH": {"guess": 88.5},
    "mu_q": {"guess": 3.85054975071625e-30},
    "oct": {"guess": 70.0, "scale": "lin"},
    "p1": {"guess": -0.333333333333333, "scale": "lin"},
    "p2": {"guess": 0.666666666666667, "scale": "lin"},
    "p3": {"guess": 0.666666666666667, "scale": "lin"},
    "pixRatio": {"guess": 1.5},
    "rF": {"guess": 1.062},
    "re": {"guess": 2.818e-15},
    "rhoL": {"guess": 5.5e-10},
    "rhoS": {"guess": 1000000.0},
    "rnuc": {"guess": 1.41e-15},
    "rsS": {"guess": 12700000000.0},
    "s2W": {"guess": 0.2233, "scale": "lin"},
    "shS": {"guess": 2.56951251295871e-10},
    "stockEP": {"guess": 5e+60},
    "t0": {"guess": 4.29183359999998e+17},
    "tD": {"guess": 130.0},
    "tP": {"guess": 5.39e-44},
    "tPresent": {"guess": 3.0},
    "tauS": {"guess": 66.0},
    "teq": {"guess": 1.104516e+17},
    "tfr": {"guess": 0.74},
    "theta": {"guess": 0.010411},
    "thetaW": {"guess": 28.2, "scale": "lin"},
    "tlife": {"guess": 3.78691199999999e+19},
    "tturn": {"guess": 1.92501359999999e+17},
    "used": {"guess": 1e-18},
    "v": {"guess": 246.22},
    "vacRatio": {"guess": 8.8e+122},
    "w0": {"guess": -0.9, "scale": "lin"},
    "wb": {"guess": 0.02237},
    "wc": {"guess": 0.12},
    "zp1": {"guess": 1090.9},
    "zturn": {"guess": 0.63, "scale": "lin"},
}

RELATIONS = [
    {"name": "i_lP", "kind": "identity", "terms": {"lP": 1.0, "hbar": -0.5, "G": -0.5, "c": 1.5}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_tP", "kind": "identity", "terms": {"tP": 1.0, "lP": -1.0, "c": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_mP", "kind": "identity", "terms": {"mP": 1.0, "hbar": -0.5, "c": -0.5, "G": 0.5}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_EP", "kind": "identity", "terms": {"EP": 1.0, "mP": -1.0, "c": -2.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_TP", "kind": "identity", "terms": {"TP": 1.0, "EP": -1.0, "kB": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_c", "kind": "identity", "terms": {"c": 1.0, "eps0": 0.5, "mu0": 0.5}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_alpha", "kind": "identity", "terms": {"alpha": 1.0, "e": -2.0, "eps0": 1.0, "hbar": 1.0, "c": 1.0}, "rhs": -1.0992098640221, "sigma": 1e-7},
    {"name": "i_stoney", "kind": "identity", "terms": {"mS": 1.0, "alpha": -0.5, "mP": -1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_N", "kind": "identity", "terms": {"N": 1.0, "mP": -1.0, "mp": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_re", "kind": "identity", "terms": {"re": 1.0, "alpha": -1.0, "hbar": -1.0, "me": 1.0, "c": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Ry", "kind": "identity", "terms": {"Ry": 1.0, "alpha": -2.0, "me": -1.0, "c": -2.0, "e": 1.0}, "rhs": -0.301029995663981, "sigma": 1e-7},
    {"name": "i_RyH", "kind": "identity", "type": "fn", "nodes": ["RyH", "Ry", "me", "mp"], "f": lambda v: lg(v["RyH"]) - lg(v["Ry"] / (1 + v["me"] / v["mp"])), "sigma": 1e-7},
    {"name": "i_lyA", "kind": "identity", "type": "fn", "nodes": ["lyA", "RyH", "hbar", "c", "e"], "f": lambda v: lg(v["lyA"]) - lg(4 * 2 * math.pi * v["hbar"] * v["c"] / (3 * v["RyH"] * v["e"])), "sigma": 0.00003},
    {"name": "i_Egam", "kind": "identity", "terms": {"Egam": 1.0, "me": -1.0, "c": -2.0, "e": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_ly", "kind": "identity", "terms": {"ly": 1.0, "c": -1.0}, "rhs": 7.49910396708523, "sigma": 1e-7},
    {"name": "i_Fratio", "kind": "identity", "terms": {"Fratio": 1.0, "alpha": -1.0, "hbar": -1.0, "c": -1.0, "G": 1.0, "me": 2.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "z_grav", "kind": "zero", "type": "sum", "terms": {"YQ": 6.0, "YL": 2.0, "Yu": -3.0, "Yd": -3.0, "Ye": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "z_cube", "kind": "zero", "type": "sum", "terms": {"YQ": 6.0, "YL": 2.0, "Yu": -3.0, "Yd": -3.0, "Ye": -1.0}, "pow": {"YQ": 3.0, "YL": 3.0, "Yu": 3.0, "Yd": 3.0, "Ye": 3.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "z_su2", "kind": "zero", "type": "sum", "terms": {"YQ": 3.0, "YL": 1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "z_su3", "kind": "zero", "type": "sum", "terms": {"YQ": 2.0, "Yu": -1.0, "Yd": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "i_Qu", "kind": "identity", "type": "sum", "terms": {"Qu": 1.0, "YQ": -1.0}, "K": 0.5, "sigma": 1e-7},
    {"name": "i_Qd", "kind": "identity", "type": "sum", "terms": {"Qd": 1.0, "YQ": -1.0}, "K": -0.5, "sigma": 1e-7},
    {"name": "i_Qe", "kind": "identity", "type": "sum", "terms": {"Qe": 1.0, "YL": -1.0}, "K": -0.5, "sigma": 1e-7},
    {"name": "i_Qnu", "kind": "identity", "type": "sum", "terms": {"Qnu": 1.0, "YL": -1.0}, "K": 0.5, "sigma": 1e-7},
    {"name": "i_Qp", "kind": "identity", "type": "sum", "terms": {"Qp": 1.0, "Qu": -2.0, "Qd": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "i_Qn", "kind": "identity", "type": "sum", "terms": {"Qn": 1.0, "Qu": -1.0, "Qd": -2.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "z_atom", "kind": "zero", "type": "sum", "terms": {"Qatom": 1.0, "Qp": -1.0, "Qe": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "z_EP", "kind": "zero", "type": "sum", "terms": {"etaEP": 1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "i_lamH", "kind": "identity", "terms": {"lamH": 1.0, "mH": -2.0, "v": 2.0}, "rhs": -0.301029995663981, "sigma": 1e-7},
    {"name": "i_muH", "kind": "identity", "terms": {"v": 1.0, "muH": -1.0, "lamH": 0.5}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_cosW", "kind": "identity", "terms": {"cosW": 1.0, "mW": -1.0, "mZ": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_s2W", "kind": "identity", "type": "sum", "terms": {"s2W": 1.0, "cosW": 1.0}, "pow": {"cosW": 2.0}, "K": 1.0, "sigma": 1e-7},
    {"name": "i_thetaW", "kind": "identity", "type": "fn", "nodes": ["thetaW", "cosW"], "f": lambda v: v["thetaW"] - math.acos(v["cosW"]) * 180 / math.pi, "sigma": 1e-7},
    {"name": "c_koide", "kind": "claim", "type": "fn", "nodes": ["me", "mmu", "mtau"], "f": lambda v: (v["me"] + v["mmu"] + v["mtau"]) / math.pow(math.sqrt(v["me"]) + math.sqrt(v["mmu"]) + math.sqrt(v["mtau"]), 2) - 2 / 3, "sigma": 1e-7},
    {"name": "i_fq", "kind": "identity", "type": "fn", "nodes": ["fq", "mu_q", "md_q", "mp"], "f": lambda v: lg(v["fq"]) - lg((2 * v["mu_q"] + v["md_q"]) / v["mp"]), "sigma": 1e-7},
    {"name": "s_np", "kind": "standard", "type": "sum", "terms": {"dmnp": 1.0, "dQCD": -1.0, "dQED": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "i_m2", "kind": "identity", "type": "fn", "nodes": ["m2", "m1", "d21"], "f": lambda v: lg(v["m2"]) - 0.5 * lg(v["m1"] * v["m1"] + v["d21"]), "sigma": 1e-7},
    {"name": "i_m3", "kind": "identity", "type": "fn", "nodes": ["m3", "m1", "d31"], "f": lambda v: lg(v["m3"]) - 0.5 * lg(v["m1"] * v["m1"] + v["d31"]), "sigma": 1e-7},
    {"name": "i_Snu", "kind": "identity", "type": "sum", "terms": {"Snu": 1.0, "m1": -1.0, "m2": -1.0, "m3": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "c_seesaw", "kind": "claim", "terms": {"m3": 1.0, "M": 1.0, "v": -2.0}, "rhs": 9.0, "sigma": 1e-7},
    {"name": "c_ruleA", "kind": "claim", "terms": {"m1": 2.0, "EP": -1.0, "kB": -1.0, "Tfloor": -1.0, "e": 2.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_yukawa", "kind": "identity", "terms": {"rnuc": 1.0, "hbar": -1.0, "mpi": 1.0, "c": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "s_gmor", "kind": "standard", "type": "fn", "nodes": ["mpi", "fpi", "rF", "mu_q", "md_q", "Sigma"], "f": lambda v: lg(v["mpi"] * v["mpi"] * math.pow(v["fpi"] / v["rF"], 2)) - lg((v["mu_q"] + v["md_q"]) * math.pow(v["Sigma"], 3)), "sigma": 0.02},
    {"name": "i_Z2A", "kind": "identity", "terms": {"Z2A": 1.0, "aS": -1.0, "aC": 1.0}, "rhs": 0.301029995663981, "sigma": 1e-7},
    {"name": "i_OB", "kind": "identity", "terms": {"OB": 1.0, "wb": -1.0, "H0": 2.0}, "rhs": -34.9787074010188, "sigma": 1e-7},
    {"name": "i_ODM", "kind": "identity", "terms": {"ODM": 1.0, "wc": -1.0, "H0": 2.0}, "rhs": -34.9787074010188, "sigma": 1e-7},
    {"name": "i_Om", "kind": "identity", "type": "sum", "terms": {"Om": 1.0, "OB": -1.0, "ODM": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "z_flat", "kind": "zero", "type": "sum", "terms": {"OK": 1.0, "OL": 1.0, "Om": 1.0}, "K": 1.0, "sigma": 1e-7},
    {"name": "i_Hend", "kind": "identity", "terms": {"Hend": 1.0, "H0": -1.0, "OL": -0.5}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Rh", "kind": "identity", "terms": {"Rh": 1.0, "c": -1.0, "H0": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_EH", "kind": "identity", "terms": {"EH": 1.0, "c": -5.0, "G": 1.0, "H0": 1.0}, "rhs": -0.301029995663981, "sigma": 1e-7},
    {"name": "i_Rs", "kind": "identity", "terms": {"Rs": 1.0, "G": -1.0, "EH": -1.0, "c": 4.0}, "rhs": 0.301029995663981, "sigma": 1e-7},
    {"name": "i_rsS", "kind": "identity", "terms": {"rsS": 1.0, "G": -1.0, "MS": -1.0, "c": 2.0}, "rhs": 0.301029995663981, "sigma": 1e-7},
    {"name": "i_rhoS", "kind": "identity", "terms": {"rhoS": 1.0, "MS": -1.0, "rsS": 3.0}, "rhs": -0.622088609302434, "sigma": 1e-7},
    {"name": "i_THS", "kind": "identity", "terms": {"THS": 1.0, "hbar": -1.0, "c": -3.0, "G": 1.0, "MS": 1.0, "kB": 1.0}, "rhs": -1.40023985968608, "sigma": 1e-7},
    {"name": "i_tauS", "kind": "identity", "terms": {"tauS": 1.0, "G": -1.0, "MS": -1.0, "c": 3.0}, "rhs": 0.497149872694134, "sigma": 1e-7},
    {"name": "i_dens_heat", "kind": "identity", "terms": {"rhoS": 1.0, "kB": -2.0, "THS": -2.0, "G": 1.0, "hbar": 2.0}, "rhs": 1.27530112307778, "sigma": 1e-7},
    {"name": "i_heat_time", "kind": "identity", "terms": {"THS": 1.0, "tauS": 1.0, "kB": 1.0, "hbar": -1.0}, "rhs": -0.903089986991944, "sigma": 1e-7},
    {"name": "i_heat_space", "kind": "identity", "terms": {"THS": 1.0, "rsS": 1.0, "kB": 1.0, "hbar": -1.0, "c": -1.0}, "rhs": -1.0992098640221, "sigma": 1e-7},
    {"name": "i_dens_space", "kind": "identity", "terms": {"rsS": 1.0, "c": -1.0, "G": 0.5, "rhoS": 0.5}, "rhs": -0.461559302483207, "sigma": 1e-7},
    {"name": "s_shadow", "kind": "standard", "terms": {"shS": 1.0, "G": -1.0, "MS": -1.0, "c": 2.0, "DS": 1.0}, "rhs": 1.01671187774347, "sigma": 0.02},
    {"name": "z_kasner1", "kind": "zero", "type": "sum", "terms": {"p1": 1.0, "p2": 1.0, "p3": 1.0}, "K": 1.0, "sigma": 1e-7},
    {"name": "z_kasner2", "kind": "zero", "type": "sum", "terms": {"p1": 1.0, "p2": 1.0, "p3": 1.0}, "pow": {"p1": 2.0, "p2": 2.0, "p3": 2.0}, "K": 1.0, "sigma": 1e-7},
    {"name": "z_kasner_inv", "kind": "zero", "type": "sum", "terms": {"p1": 1.0, "p2": 1.0, "p3": 1.0}, "pow": {"p1": -1.0, "p2": -1.0, "p3": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "s_bh", "kind": "standard", "type": "sum", "terms": {"p1": 1.0}, "K": -0.333333333333333, "sigma": 1e-7},
    {"name": "i_sph", "kind": "identity", "type": "sum", "terms": {"p2": 1.0, "p3": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "c_ht1", "kind": "claim", "type": "fn", "nodes": ["H0", "t0"], "f": lambda v: lg(v["H0"] * v["t0"]), "sigma": 1e-7},
    {"name": "c_kbc", "kind": "claim", "type": "fn", "nodes": ["H0loc", "H0", "Om", "delta"], "f": lambda v: lg(v["H0loc"]) - lg(v["H0"] * (1 + math.pow(v["Om"], 0.55) * v["delta"] / 3)), "sigma": 1e-7},
    {"name": "i_dark", "kind": "identity", "type": "sum", "terms": {"Odark": 1.0, "OL": -1.0, "ODM": -1.0}, "K": 0.0, "sigma": 1e-7},
    {"name": "i_darkRatio", "kind": "identity", "terms": {"darkRatio": 1.0, "OL": -1.0, "ODM": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "c_hde", "kind": "claim", "type": "fn", "nodes": ["w0", "OL"], "f": lambda v: v["w0"] - (-1 / 3 - (2 / 3) * math.sqrt(v["OL"])), "sigma": 1e-7},
    {"name": "c_a0", "kind": "claim", "terms": {"a0": 1.0, "c": -1.0, "H0": -1.0}, "rhs": -0.798179868358115, "sigma": 1e-7},
    {"name": "c_verlinde", "kind": "claim", "terms": {"ODM": 2.0, "OB": -1.0}, "rhs": 0.1249387366083, "sigma": 1e-7},
    {"name": "s_eta", "kind": "standard", "terms": {"eta": 1.0, "wb": -1.0}, "rhs": -7.56224943717961, "sigma": 1e-7},
    {"name": "i_Trec", "kind": "identity", "terms": {"Trec": 1.0, "Tcmb": -1.0, "zp1": -1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_lA", "kind": "identity", "terms": {"lA": 1.0, "theta": 1.0}, "rhs": 0.497149872694134, "sigma": 1e-7},
    {"name": "i_tfr", "kind": "identity", "terms": {"tfr": 1.0, "Tfr": 2.0}, "rhs": -0.131888866145381, "sigma": 1e-7},
    {"name": "i_tD", "kind": "identity", "terms": {"tD": 1.0, "TD": 2.0}, "rhs": 0.120645727285509, "sigma": 1e-7},
    {"name": "s_zturn", "kind": "standard", "type": "fn", "nodes": ["zturn", "Om", "OL"], "f": lambda v: v["zturn"] - (cbrt(2 * v["OL"] / v["Om"]) - 1), "sigma": 1e-7},
    {"name": "s_tturn", "kind": "standard", "type": "fn", "nodes": ["tturn", "H0", "OL", "zturn"], "f": lambda v: lg(v["tturn"]) - lg(lcdm_age(v["H0"], v["OL"], 1) - lcdm_age(v["H0"], v["OL"], 1 / (1 + v["zturn"]))), "sigma": 1e-7},
    {"name": "s_teq", "kind": "standard", "type": "fn", "nodes": ["teq", "H0", "OL", "Om"], "f": lambda v: lg(v["teq"]) - lg(lcdm_age(v["H0"], v["OL"], 1) - lcdm_age(v["H0"], v["OL"], cbrt(v["Om"] / v["OL"]))), "sigma": 1e-7},
    {"name": "i_Tfloor", "kind": "identity", "terms": {"Tfloor": 1.0, "hbar": -1.0, "Hend": -1.0, "kB": 1.0}, "rhs": -0.798179868358115, "sigma": 1e-7},
    {"name": "i_S", "kind": "identity", "terms": {"S": 1.0, "c": -2.0, "Hend": 2.0, "lP": 2.0}, "rhs": 0.497149872694134, "sigma": 1e-7},
    {"name": "i_rhoL", "kind": "identity", "terms": {"rhoL": 1.0, "c": -2.0, "H0": -2.0, "OL": -1.0, "G": 1.0}, "rhs": -0.923118604966415, "sigma": 1e-7},
    {"name": "i_Edark", "kind": "identity", "terms": {"Edark": 1.0, "rhoL": -0.25, "hbar": -0.75, "c": -0.75, "e": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Emid", "kind": "identity", "terms": {"Emid": 1.0, "EP": -0.5, "hbar": -0.5, "Hend": -0.5, "e": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Estock", "kind": "identity", "terms": {"Estock": 1.0, "rhoL": -1.0, "c": -3.0, "Hend": 3.0}, "rhs": 0.622088609302434, "sigma": 1e-7},
    {"name": "i_stockEP", "kind": "identity", "terms": {"stockEP": 1.0, "Estock": -1.0, "EP": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_pix", "kind": "identity", "terms": {"pixRatio": 1.0, "rhoL": -1.0, "lP": -3.0, "S": -1.0, "EP": 1.0}, "rhs": 0.602059991327962, "sigma": 1e-7},
    {"name": "i_vac", "kind": "identity", "terms": {"vacRatio": 1.0, "EP": -1.0, "lP": 3.0, "rhoL": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Nops", "kind": "identity", "terms": {"Nops": 1.0, "EH": -1.0, "t0": -1.0, "hbar": 1.0}, "rhs": -0.196119877030153, "sigma": 1e-7},
    {"name": "i_S0", "kind": "identity", "terms": {"S0": 1.0, "c": -2.0, "H0": 2.0, "lP": 2.0}, "rhs": 0.497149872694134, "sigma": 1e-7},
    {"name": "i_allRatio", "kind": "identity", "terms": {"allRatio": 1.0, "Nops": -1.0, "S0": 1.0}, "rhs": 0.994299745388268, "sigma": 1e-7},
    {"name": "i_ageP2", "kind": "identity", "terms": {"ageP2": 1.0, "t0": -2.0, "tP": 2.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Lmid", "kind": "identity", "terms": {"Lmid": 1.0, "lP": -0.5, "Rh": -0.5}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Ldark", "kind": "identity", "terms": {"Ldark": 1.0, "hbar": -1.0, "c": -1.0, "Edark": 1.0, "e": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Equant", "kind": "identity", "terms": {"Equant": 1.0, "kB": -1.0, "Tfloor": -1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_E0", "kind": "identity", "terms": {"E0ratio": 1.0, "hbar": -1.0, "Hend": -1.0, "Equant": 1.0}, "rhs": -0.301029995663981, "sigma": 1e-7},
    {"name": "i_mHub", "kind": "identity", "terms": {"mHub": 1.0, "hbar": -1.0, "Hend": -1.0, "e": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Emin", "kind": "identity", "terms": {"Emin": 1.0, "hbar": -1.0, "t0": 1.0}, "rhs": 0.196119877030153, "sigma": 1e-7},
    {"name": "c_dirac", "kind": "claim", "terms": {"Rh": 3.0, "re": -3.0, "S": -1.0}, "rhs": 0.0, "sigma": 0.5},
    {"name": "i_fH", "kind": "identity", "terms": {"fH": 1.0, "Hend": -1.0}, "rhs": -0.798179868358115, "sigma": 1e-7},
    {"name": "i_oct", "kind": "identity", "type": "fn", "nodes": ["oct", "fH"], "f": lambda v: v["oct"] - math.log2(440 / v["fH"]), "sigma": 1e-7},
    {"name": "i_fe", "kind": "identity", "terms": {"fe": 1.0, "me": -1.0, "c": -2.0, "hbar": 1.0}, "rhs": -0.798179868358115, "sigma": 1e-7},
    {"name": "i_fp", "kind": "identity", "terms": {"fp": 1.0, "mp": -1.0, "c": -2.0, "hbar": 1.0}, "rhs": -0.798179868358115, "sigma": 1e-7},
    {"name": "i_fmid", "kind": "identity", "terms": {"fmid": 1.0, "fp": -0.5, "fH": -0.5}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_Emq", "kind": "identity", "terms": {"Emq": 1.0, "hbar": -1.0, "fmid": -1.0, "e": 1.0}, "rhs": 0.798179868358115, "sigma": 1e-7},
    {"name": "i_Nlam", "kind": "identity", "terms": {"Nlam": 1.0, "c": -1.0, "Hend": 1.0, "Tcmb": -1.0}, "rhs": 2.53793579504912, "sigma": 1e-7},
    {"name": "i_tlife", "kind": "identity", "type": "fn", "nodes": ["tlife", "Nlam", "Hend"], "f": lambda v: lg(v["tlife"]) - lg(math.log(v["Nlam"]) / v["Hend"]), "sigma": 1e-7},
    {"name": "s_Tearth", "kind": "standard", "type": "fn", "nodes": ["Tearth", "Tsun", "Rsun", "AU", "albedo"], "f": lambda v: lg(v["Tearth"]) - lg(v["Tsun"] * math.sqrt(v["Rsun"] / (2 * v["AU"])) * math.pow(1 - v["albedo"], 0.25)), "sigma": 1e-7},
    {"name": "i_Nph", "kind": "identity", "terms": {"Nph": 1.0, "Tsun": -1.0, "Tearth": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "i_used", "kind": "identity", "terms": {"used": 1.0, "Snow": -1.0, "S": 1.0}, "rhs": 0.0, "sigma": 1e-7},
    {"name": "c_present", "kind": "claim", "terms": {"tPresent": 1.0, "t0": -1.0, "Snow": -1.0, "S": 1.0}, "rhs": 0.0, "sigma": 0.5},
]

MEASURED = {  # node: (value, sigma) - sigma in dex for positive quantities, in value units for signed ones
    "eps0": (8.8541878188e-12, 1e-7),  # CODATA 2022
    "mu0": (0.00000125663706127, 1e-7),  # CODATA 2022
    "me": (9.10938370156836e-31, 1e-7),  # CODATA 2022
    "mp": (1.6726219259531e-27, 1e-7),  # CODATA 2022
    "Ry": (13.60569312299, 1e-7),  # CODATA 2022
    "lyA": (1.21567e-7, 0.00000357247017614362),  # hydrogen line (NIST)
    "Yu": (0.666666666666667, 1e-7),  # Standard Model, from the measured charges
    "Yd": (-0.333333333333333, 1e-7),  # Standard Model, from the measured charges
    "YL": (-0.5, 1e-7),  # Standard Model, from the measured charges
    "Ye": (-1.0, 1e-7),  # Standard Model, from the measured charges
    "Qatom": (-1e-22, 1e-7),  # neutrality of matter (Bressi et al. 2011)
    "etaEP": (-1.5, 2.7),  # MICROSCOPE satellite (2022)
    "v": (246.22, 0.0000176384729877042),  # Fermi constant
    "mH": (125.2, 0.000381568634260045),  # PDG 2024
    "mW": (80.3625, 0.0000702545125492894),  # world average
    "mZ": (91.1876, 0.0000100015617473958),  # LEP
    "mmu": (1.88353162704912e-28, 1e-7),  # CODATA / PDG
    "mtau": (3.16766544839825e-27, 0.0000219966477977707),  # PDG 2024
    "mpi": (2.48806819639754e-28, 5.60097358347894e-7),  # PDG
    "fpi": (1.6412968312428e-28, 0.00268869180715601),  # PDG 2024 (f_pi = 130.2 +- 0.8 MeV, divided by sqrt 2)
    "rF": (1.062, 0.00286258133081239),  # FLAG 2021, lattice QCD (N_f = 2+1)
    "Sigma": (4.84884042682787e-28, 0.00798335444675095),  # FLAG 2021, lattice QCD (N_f = 2+1, MS-bar at 2 GeV)
    "mu_q": (3.85054975071625e-30, 0.0140743582098276),  # PDG 2024
    "md_q": (8.3785110316511e-30, 0.00646821568792077),  # PDG 2024
    "dQCD": (2.52, 0.29),  # Borsanyi et al. 2015 (lattice QCD)
    "dQED": (-1.0, 0.16),  # Borsanyi et al. 2015 (lattice QCD)
    "dmnp": (1.29333236, 5e-7),  # CODATA 2022
    "d21": (0.0000749, 0.0110168159628328),  # NuFIT 6.0
    "d31": (0.002534, 0.00428467326266034),  # NuFIT 6.0
    "aS": (18.3, 0.00949277556072682),  # nuclear mass formula
    "aC": (0.714, 0.00912383365342966),  # nuclear mass formula
    "H0loc": (2.36704799559257e-18, 0.00618382066236832),  # SH0ES (Riess et al. 2022)
    "t0": (4.26027599999998e+17, 0.0167283800436808),  # oldest stars (Valcin et al. 2020), stat. +-0.15, syst. +-0.5
    "wb": (0.02237, 0.00291212214061188),  # Planck 2018, CMB
    "wc": (0.12, 0.00434294481903252),  # Planck 2018, CMB
    "OK": (0.001, 0.002),  # Planck 2018 + BAO
    "a0": (1.2e-10, 0.0868588963806504),  # McGaugh, Lelli & Schombert 2016
    "delta": (0.46, 0.06),  # KBC void (Keenan, Barger & Cowie 2013)
    "eta": (6.04e-10, 0.00848456107029532),  # first nuclei, deuterium (PDG 2025)
    "MS": (8.54445559e+36, 0.0042449076657986),  # GRAVITY 2022 (stellar orbits)
    "DS": (2.55403389e+20, 0.00162657109327061),  # GRAVITY 2022
    "shS": (2.51133487115587e-10, 0.019283345721573),  # ring, Event Horizon Telescope 2022
    "w0": (-0.841, 0.053),  # DESI DR2 + CMB + Pantheon+ supernovae (arXiv 2512.07281)
    "Tcmb": (2.72548, 0.0000908272504971064),  # Fixsen 2009
    "zp1": (1090.92, 0.00009952482352126),  # Planck 2018
    "theta": (0.010411, 0.000129316385928353),  # Planck 2018
    "Tfr": (1.0, 0.0434294481903252),  # marker: freeze-out near 1 MeV (PDG)
    "TD": (0.1, 0.0434294481903252),  # marker: nuclei near 0.1 MeV (PDG)
    "Tsun": (5772.0, 0.0000601932753850661),  # IAU 2015, nominal value
    "Rsun": (695700000.0, 0.0000624255400177162),  # IAU 2015, nominal value
    "AU": (149597870700.0, 1e-7),  # IAU 2012, exact value
    "albedo": (0.29, 0.01),  # energy budget (CERES)
    "Tearth": (255.0, 0.00170311561530687),  # about 240 W/m2 emitted to space (CERES)
    "Snow": (3.1e+104, 0.3),  # Egan & Lineweaver 2010
    "tPresent": (3.0, 0.2),  # psychological present (Poppel), debated value
}
