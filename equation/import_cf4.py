# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Add the Cosmicflows-4 individual distances (EDD table "All CF4 Individual Distances") to a GRM store.

The input store is never modified: the result is written to a new file (default data/grm_network_cf4.json).
That file holds the input's networks unchanged plus one CF4 network per systematic level (see --sys);
test_master_discovery.py runs them all and compares them.

What is added (to a copy of the input's active network, one copy per systematic level)
    One Hubble-constant node per distance method, measured from the galaxies of that method:
        H0_cf4_snIa, H0_cf4_tf, H0_cf4_fp, H0_cf4_sbf, H0_cf4_snII, H0_cf4_trgb, H0_cf4_cep, H0_cf4_mas
    (in s^-1, like H0), each one tied to the network's H0 by a log relation  H0_cf4_x / H0 = 1.
    The value from the averaged modulus DM (all methods together) is reported in cf4_summary.json but not added:
    it is made of the same measurements as the method nodes, and adding both would count them twice.
    A method with too few galaxies in the velocity window is left out (and listed).
    The 56,000 galaxies are not added one by one: each would be a node tied to nothing else (a silent floor).

How each galaxy gives a Hubble constant
    luminosity distance   d_L = 10^((DM - 25) / 5) Mpc
    low-z expansion       H0 = c z [1 + (1 - q0) z / 2 - (1 - q0 - 3 q0^2 + j0) z^2 / 6] / d_L,  z = Vcmb / c
    q0 = Om/2 - OL is read from the network's own Om and OL (flat universe); j0 = 1 (exact for flat LCDM).
    uncertainty (dex)     sigma_i^2 = (eDM / 5)^2 + (sigma_v / (Vcmb ln 10))^2,  sigma_v = peculiar velocity noise
    each method           inverse-variance weighted mean of log10 H0_i, after iterative clipping of outliers;
                          its error is inflated by sqrt(chi2/dof) when the galaxies scatter more than their errors say.

Choices made by this script (all can be changed on the command line)
    --vmin 3000 km/s   below this, peculiar velocities (a few hundred km/s) dominate the Hubble flow
    --sigma-v 250 km/s peculiar velocity noise per galaxy
    --clip 4           outlier clipping (sigmas)
    --min-galaxies 5   fewer than this: no node for the method
    --link-sigma 1e-7  tolerance (dex) of H0_cf4_x / H0 = 1; 1e-7 makes it an identity like the network's other
                       relations, so any disagreement shows up as tension on the measurements
    --sys 0,0.005,...  systematic floors, as fractions of H0 (0.01 = 1 %), added in quadrature to each method's
                       statistical error (the zero point of the distance ladder and the correlated motions of galaxies
                       in groups are not in the statistical error). One network per level is written in the same file
                       (ids cf4_sys_0pct, cf4_sys_0.5pct, cf4_sys_1pct...), next to the networks of the input store,
                       which are kept as they are. --active chooses which one the loader opens by default.

Things to keep in mind when reading the result
    - CF4 put its methods on a common zero point, so the methods are not fully independent of one another.
    - Distance-based averages at large distances suffer from Malmquist bias; --vmax can restrict the sample.
    - Galaxies in the same group share a peculiar velocity, so the statistical errors are optimistic.

Also writes cf4_summary.json: per-method numbers and the bulk flow (dipole of the peculiar velocities), which is
reported only, not tied to the network.

    python import_cf4.py CF4_individual.csv
    python import_cf4.py CF4_individual.csv --sys 0,0.01,0.02 --active 0.01
    python import_cf4.py CF4_individual.csv --store data/grm_network_fully_enriched.json --out data/grm_network_cf4.json
"""
import argparse
import copy
import csv
import json
import math
import os

import numpy as np

import settings
DEFAULT_STORE = getattr(settings, "GRM_NETWORK_STORE_JSON_ENRICHED", None) or settings.GRM_NETWORK_STORE_JSON

C_KMS = 299792.458
MPC_M = 3.0856775814913673e22          # metres in one megaparsec (IAU)
KMS_MPC_TO_SI = 1e3 / MPC_M            # km/s/Mpc -> s^-1
LN10 = math.log(10.0)

# node suffix -> (distance modulus column, its error column)
METHODS = {
    "": ("DM", "eDM"),
    "_snIa": ("DMsnIa", "eDMsn1"),
    "_tf": ("DMtf", "eDMtf"),
    "_fp": ("DMfp", "eDMfp"),
    "_sbf": ("DMsbf", "eDMsbf"),
    "_snII": ("DMsnII", "eDMsn2"),
    "_trgb": ("DMtrgb", "eDMt"),
    "_cep": ("DMcep", "eDMcep"),
    "_mas": ("DMmas", "eDMmas"),
}
METHOD_LABEL = {"": "all methods (DM)", "_snIa": "type Ia supernovae", "_tf": "Tully-Fisher",
                "_fp": "fundamental plane", "_sbf": "surface brightness fluctuations", "_snII": "type II supernovae",
                "_trgb": "tip of the red giant branch", "_cep": "Cepheids", "_mas": "water masers"}


def number(text):
    try:
        x = float(text)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def read_cf4(path):
    """Rows of the CF4 file as dicts; accepts the EDD export with its extra first header line (table names)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    start = 0
    while start < len(rows) and "pgc" not in [c.strip() for c in rows[start]]:
        start += 1
    if start == len(rows):
        raise SystemExit("no header line with a 'pgc' column found")
    header = [c.strip() for c in rows[start]]
    missing = {"Vcmb", "DM", "eDM"} - set(header)
    if missing:
        raise SystemExit(f"columns missing from the file: {', '.join(sorted(missing))}")
    return [dict(zip(header, r)) for r in rows[start + 1:] if any(c.strip() for c in r)]


def cosmography(z, q0, j0):
    return 1 + 0.5 * (1 - q0) * z - (1 - q0 - 3 * q0 ** 2 + j0) * z ** 2 / 6


def galaxy_log_h(rows, dm_col, edm_col, q0, j0, vmin, vmax, sigma_v):
    """log10 H0 (km/s/Mpc) and its sigma (dex) for every galaxy that has this distance; plus the rows used."""
    logh, sig, used = [], [], []
    for r in rows:
        v, dm, edm = number(r.get("Vcmb")), number(r.get(dm_col)), number(r.get(edm_col))
        if v is None or dm is None or edm is None or edm <= 0 or dm <= 0:
            continue
        if v < vmin or (vmax and v > vmax):
            continue
        z = v / C_KMS
        logh.append(math.log10(v * cosmography(z, q0, j0)) - (dm - 25) / 5)
        sig.append(math.hypot(edm / 5, sigma_v / (v * LN10)))
        used.append(r)
    return np.array(logh), np.array(sig), used


def weighted_mean(logh, sig, clip):
    """Inverse-variance mean with iterative clipping; returns mean, error (inflated by the excess scatter), kept mask."""
    keep = np.ones(len(logh), bool)
    for _ in range(20):
        w = 1 / sig[keep] ** 2
        mean = np.sum(w * logh[keep]) / np.sum(w)
        new = np.abs(logh - mean) <= clip * sig
        if np.array_equal(new, keep) or new.sum() < 2:
            break
        keep = new
    w = 1 / sig[keep] ** 2
    mean = np.sum(w * logh[keep]) / np.sum(w)
    err = 1 / math.sqrt(np.sum(w))
    dof = keep.sum() - 1
    chi2 = float(np.sum(w * (logh[keep] - mean) ** 2))
    inflate = math.sqrt(chi2 / dof) if dof > 0 and chi2 > dof else 1.0
    return mean, err * inflate, keep, chi2 / max(dof, 1)


def unit_vector(r):
    """Direction on the sky in supergalactic coordinates (falls back to galactic)."""
    for lon, lat, frame in (("sgl", "sgb", "supergalactic"), ("glon", "glat", "galactic")):
        a, b = number(r.get(lon)), number(r.get(lat))
        if a is not None and b is not None:
            a, b = math.radians(a), math.radians(b)
            return np.array([math.cos(b) * math.cos(a), math.cos(b) * math.sin(a), math.sin(b)]), frame
    return None, None


def bulk_flow(rows, h0, q0, j0, sigma_v):
    """Dipole of the peculiar velocities (Watkins-Feldman estimator), weighted least squares."""
    A, y, w, frame = [], [], [], None
    for r in rows:
        v, dm, edm = number(r.get("Vcmb")), number(r.get("DM")), number(r.get("eDM"))
        n, fr = unit_vector(r)
        if n is None or v is None or dm is None or edm is None or edm <= 0:
            continue
        z = v / C_KMS
        d = 10 ** ((dm - 25) / 5)
        vpec = v * math.log(v * cosmography(z, q0, j0) / (h0 * d)) / (1 + z)
        err = math.hypot(v * LN10 * edm / 5 / (1 + z), sigma_v)
        A.append(n), y.append(vpec), w.append(1 / err ** 2)
        frame = fr
    if len(A) < 10:
        return None
    A, y, w = np.array(A), np.array(y), np.array(w)
    cov = np.linalg.inv(A.T @ (A * w[:, None]))
    b = cov @ (A.T @ (w * y))
    amp = float(np.linalg.norm(b))
    amp_err = float(math.sqrt(b @ cov @ b) / amp) if amp > 0 else float("nan")
    lon = math.degrees(math.atan2(b[1], b[0])) % 360
    lat = math.degrees(math.asin(b[2] / amp)) if amp > 0 else float("nan")
    return {"frame": frame, "galaxies": int(len(y)), "vector_kms": [float(x) for x in b],
            "vector_err_kms": [float(math.sqrt(cov[i, i])) for i in range(3)],
            "amplitude_kms": amp, "amplitude_err_kms": amp_err, "lon_deg": lon, "lat_deg": lat}


def sys_label(level):
    """Network id of one systematic level: 0.01 -> cf4_sys_1pct, 0.005 -> cf4_sys_0.5pct."""
    return f"cf4_sys_{level * 100:g}pct"


def strip_cf4(net):
    """A network with any CF4 node, measurement and relation from an earlier import removed (in place)."""
    names = {n for n in net.get("nodes", {}) if n.startswith("H0_cf4")}
    if not names:
        return 0
    for n in names:
        net["nodes"].pop(n, None)
        net.get("measured", {}).pop(n, None)
    net["customRelations"] = [r for r in net.get("customRelations", [])
                              if not set(r.get("terms", {})) & names]
    return len(names)


def main():
    ap = argparse.ArgumentParser(description="Add Cosmicflows-4 Hubble constants to a GRM store (new file).")
    ap.add_argument("csv", help="EDD export of 'All CF4 Individual Distances'")
    ap.add_argument("--store", default=DEFAULT_STORE)
    ap.add_argument("--out", default=settings.GRM_NETWORK_STORE_CF4)
    ap.add_argument("--force", action="store_true", help="overwrite --out if it exists (never the input store)")
    ap.add_argument("--vmin", type=float, default=3000.0)
    ap.add_argument("--vmax", type=float, default=0.0, help="0 = no upper limit")
    ap.add_argument("--sigma-v", type=float, default=250.0)
    ap.add_argument("--clip", type=float, default=4.0)
    ap.add_argument("--min-galaxies", type=int, default=5)
    ap.add_argument("--link", default="H0", help="node the CF4 constants are tied to (default H0)")
    ap.add_argument("--link-sigma", type=float, default=1e-7)
    ap.add_argument("--sys", default="0,0.005,0.01,0.015,0.02,0.03,0.05",
                    help="systematic floors, fractions of H0 (0.01 = 1%%), comma separated: one network per level")
    ap.add_argument("--active", type=float, default=None,
                    help="level made the active network of the file (default: the first of --sys)")
    args = ap.parse_args()
    levels = [float(x) for x in str(args.sys).split(",") if x.strip()]
    active = levels[0] if args.active is None else args.active
    if active not in levels:
        raise SystemExit("--active must be one of the --sys levels")

    if os.path.abspath(args.out) == os.path.abspath(args.store):
        raise SystemExit("--out is the input store: choose another file, the input is never overwritten")
    if os.path.exists(args.out) and not args.force:
        raise SystemExit(f"{args.out} already exists (use --force to replace it)")

    with open(args.store, encoding="utf-8") as f:
        store = json.load(f)
    out = copy.deepcopy(store)
    base = copy.deepcopy(next((n for n in out["networks"] if n.get("id") == out.get("activeId")), out["networks"][0]))
    if isinstance(base.get("customRelations"), dict):
        base["customRelations"] = [dict(v, name=k) for k, v in base["customRelations"].items()]
    base.setdefault("customRelations", []), base.setdefault("measured", {})
    removed = strip_cf4(base)
    if removed:
        print(f"[WARN] the input network already had {removed} CF4 nodes: they are replaced")
    nodes = base.setdefault("nodes", {})
    if args.link not in nodes:
        raise SystemExit(f"node '{args.link}' is not in the active network")
    # earlier CF4 variants in the input store are dropped (they are rebuilt here)
    out["networks"] = [n for n in out["networks"] if not str(n.get("id", "")).startswith("cf4_sys_")]

    def node_value(name):
        spec = nodes[name]
        return spec.get("solved", spec.get("value", spec.get("guess")))

    om, ol = node_value("Om"), node_value("OL")
    q0, j0 = om / 2 - ol, 1.0
    rows = read_cf4(args.csv)
    print(f"{len(rows)} galaxies read from {args.csv}")
    print(f"q0 = Om/2 - OL = {q0:.4f} (network Om {om:.4f}, OL {ol:.4f}), j0 = 1")
    print(f"velocity window {args.vmin:g} - {args.vmax or 'no limit'} km/s, peculiar velocity noise {args.sigma_v:g} km/s\n")

    summary = {"source": os.path.basename(args.csv), "q0": q0, "j0": j0, "vmin": args.vmin, "vmax": args.vmax,
               "sigma_v": args.sigma_v, "sys_levels": levels, "methods": {}, "left_out": {}}
    print(f"{'node':16s} {'method':32s} {'galaxies':>8s} {'clipped':>7s} {'H0 km/s/Mpc':>18s} {'chi2/dof':>8s}")
    h0_all, found = None, []
    for suffix, (dm_col, edm_col) in METHODS.items():
        name = "H0_cf4" + suffix
        logh, sig, used = galaxy_log_h(rows, dm_col, edm_col, q0, j0, args.vmin, args.vmax, args.sigma_v)
        if len(logh) < args.min_galaxies:
            summary["left_out"][name] = int(len(logh))
            continue
        mean, err, keep, red = weighted_mean(logh, sig, args.clip)
        h_kms = 10 ** mean
        print(f"{name:16s} {METHOD_LABEL[suffix]:32s} {len(logh):8d} {int((~keep).sum()):7d} "
              f"{h_kms:9.2f} +- {h_kms * LN10 * err:5.2f} {red:8.2f}" + ("   (reported only)" if not suffix else ""))
        if suffix == "":
            h0_all = h_kms
            summary["all_methods_reported_only"] = {"galaxies": int(len(logh)), "H0_kms_Mpc": h_kms,
                                                    "H0_err_kms_Mpc": h_kms * LN10 * err, "chi2_per_dof": red}
            continue
        value = h_kms * KMS_MPC_TO_SI
        found.append((suffix, name, value, err))
        summary["methods"][name] = {"method": METHOD_LABEL[suffix], "galaxies": int(len(logh)),
                                    "clipped": int((~keep).sum()), "H0_kms_Mpc": h_kms,
                                    "H0_err_kms_Mpc": h_kms * LN10 * err, "sigma_dex": err,
                                    "chi2_per_dof": red, "H0_si": value}

    for name, n in summary["left_out"].items():
        print(f"{name:16s} left out: {n} galaxies in the window (fewer than {args.min_galaxies})")
    if not found:
        raise SystemExit("no method had enough galaxies: nothing added, no file written")

    # one network per systematic level, each a copy of the input's active network plus the CF4 constants
    for level in levels:
        net = copy.deepcopy(base)
        net["id"] = sys_label(level)
        net["cf4_base"] = base.get("id")      # the network without CF4, for comparisons
        net["cf4_sys"] = level
        net["name"] = f"{base.get('name', 'network')} + CF4 (systematic floor {level * 100:g} %)"
        for suffix, name, value, err in found:
            net["nodes"][name] = {"guess": value, "solved": value, "scale": "log", "fixed": False,
                                  "dim": [0, 0, -1, 0, 0]}
            net["measured"][name] = [value, math.hypot(err, level / LN10)]
            net["customRelations"].append({"name": "z_cf4" + suffix, "terms": {name: 1, args.link: -1}, "rhs": 0.0,
                                           "sigma": args.link_sigma})
        out["networks"].append(net)
    out["activeId"] = sys_label(active)

    link_value = node_value(args.link) / KMS_MPC_TO_SI
    print(f"\nnetwork {args.link} before the CF4 data: {link_value:.2f} km/s/Mpc")

    if h0_all:
        bf = bulk_flow([r for r in rows if (number(r.get("Vcmb")) or 0) >= args.vmin
                        and (not args.vmax or number(r.get("Vcmb")) <= args.vmax)], h0_all, q0, j0, args.sigma_v)
        if bf:
            summary["bulk_flow"] = bf
            print(f"\nbulk flow (reported only, not tied to the network): {bf['amplitude_kms']:.0f} +- "
                  f"{bf['amplitude_err_kms']:.0f} km/s towards ({bf['frame']}) lon {bf['lon_deg']:.0f}, "
                  f"lat {bf['lat_deg']:.0f}, from {bf['galaxies']} galaxies")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    # same layout as the input store (4-space indent)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=4)

    def counts(n):
        return (len(n.get("nodes", {})), len(n.get("relations", [])) + len(n.get("customRelations", [])),
                len(n.get("measured", {})))

    print("\nnetworks in the output (nodes / relations / measured):")
    for n in out["networks"]:
        print(f"  {n.get('id', '?'):24s} {counts(n)}" + ("   <- active" if n.get("id") == out["activeId"] else ""))
    with open("cf4_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {args.out} ({len(levels)} CF4 networks; {args.store} untouched) and cf4_summary.json")


if __name__ == "__main__":
    main()
