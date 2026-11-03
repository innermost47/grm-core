# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
Global Relational Model engine - log-space relational solver.

Nodes
    positive quantities (default) are handled as x = log10(value);
    signed quantities ({"scale": "lin"}) are handled as x = value (charges, curvature, w0...).

Relations (sigma in the relation's own residual unit; dex for log-space relations)
    log-linear (default)  sum(coeff * log10(node)) = rhs        products, ratios, powers
                          E = m c^2  ->  {"terms": {"E": 1, "m": -1, "c": -2}, "rhs": 0}
                          rhs may be a callable of the current values
    sum                   {"type": "sum", "terms": {node: coeff}, "pow": {node: p}, "K": k}
                          sum(coeff * value^p) = K                charges, fractions of the universe
    fn                    {"type": "fn", "nodes": [...], "f": callable(values) -> residual}
                          any equation, written as f(values) = 0  (Koide, cosmological ages...)

What the solver returns for each node:
    values        best estimate
    sigma_dex     1-sigma uncertainty in log10 units (relative uncertainty ~ 2.303 * sigma_dex)
    undetermined  nodes that the relations and measurements do not fix (their value is only the guess)

Measurements are data with an uncertainty, not starting points:
    solve(measured_dict={"G": 6.674e-11, "H0": (70.0, 0.01)})   # value, or (value, sigma in dex)

Numerics: weighted least squares solved by QR factorisation (no normal equations), so relations
as tight as 1e-9 dex and values from 1e-44 to 1e122 coexist. Uses NumPy when it is installed,
pure Python otherwise. Purely log-linear problems are solved in a few exact steps; sums, functions
and callable rhs switch to Levenberg-Marquardt (analytic Jacobian for sums, finite differences
for functions).
"""
import math

try:
    import numpy as _np
except ImportError:  # pragma: no cover - pure Python fallback
    _np = None

LN10 = math.log(10.0)


# ---------------------------------------------------------------------- dense linear algebra
def _qr_solve(A, b):
    """Least squares min |A d - b| for a full-column-rank A (m x n, m >= n).
    Returns (d, R) where R is the n x n upper triangular factor."""
    if _np is not None:
        A = _np.asarray(A, dtype=float)
        Q, R = _np.linalg.qr(A, mode="reduced")
        if _np.any(_np.diag(R) == 0.0):
            raise ArithmeticError("rank-deficient system")
        d = _np.linalg.solve(R, Q.T @ _np.asarray(b, dtype=float))
        return [float(v) for v in d], R
    m, n = len(A), len(A[0]) if A else 0
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for k in range(n):
        norm = math.sqrt(sum(M[i][k] ** 2 for i in range(k, m)))
        if norm == 0.0:
            raise ArithmeticError("rank-deficient system")
        alpha = -norm if M[k][k] >= 0 else norm
        v = [0.0] * m
        v[k] = M[k][k] - alpha
        for i in range(k + 1, m):
            v[i] = M[i][k]
        vv = sum(v[i] ** 2 for i in range(k, m))
        if vv == 0.0:
            continue
        for j in range(k, n + 1):
            s = sum(v[i] * M[i][j] for i in range(k, m)) * 2.0 / vv
            if s:
                for i in range(k, m):
                    M[i][j] -= s * v[i]
    R = [[M[i][j] if j >= i else 0.0 for j in range(n)] for i in range(n)]
    return _back_substitution(R, [M[i][n] for i in range(n)]), R


def _back_substitution(R, y):
    n = len(y)
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = float(y[i])
        Ri = R[i]
        for j in range(i + 1, n):
            s -= float(Ri[j]) * x[j]
        if Ri[i] == 0.0:
            raise ArithmeticError("rank-deficient system")
        x[i] = s / float(Ri[i])
    return x


def _covariance_from_R(R):
    """(R^T R)^-1 = R^-1 R^-T."""
    if _np is not None:
        Rinv = _np.linalg.inv(_np.asarray(R, dtype=float))
        return (Rinv @ Rinv.T).tolist()
    n = len(R)
    Rinv = [[0.0] * n for _ in range(n)]
    for j in range(n):
        e = [1.0 if i == j else 0.0 for i in range(n)]
        col = _back_substitution(R, e)
        for i in range(n):
            Rinv[i][j] = col[i]
    return [[sum(Rinv[i][k] * Rinv[j][k] for k in range(n)) for j in range(n)] for i in range(n)]


# ---------------------------------------------------------------------- network
class GlobalRelationalNetwork:
    def __init__(self, nodes_spec, relations_spec, prior_sigma=1e3, undetermined_sigma=1.0):
        """
        nodes_spec      {name: {"guess": value, "fixed": bool, "scale": "log" | "lin"}}
        relations_spec  list of relations (see module docstring); each may have "name" and "sigma"
                        (default 1e-3), log-linear ones may have "depends" (nodes a callable rhs reads)
        prior_sigma     width of a very weak ridge that keeps the problem solvable when some direction
                        is not determined by anything (it does not bias determined nodes)
        undetermined_sigma  a free node whose uncertainty exceeds this (dex, or value units for a
                        signed node, relative to max(1, |value|)) is reported as undetermined
        """
        if not nodes_spec:
            raise ValueError("the network has no nodes")
        self.nodes_names = list(nodes_spec)
        self.node_to_idx = {name: i for i, name in enumerate(self.nodes_names)}
        self.prior_sigma = float(prior_sigma)
        self.undetermined_sigma = float(undetermined_sigma)

        self.x0, self.lin, self.fixed_nodes = [], [], set()
        for name, spec in nodes_spec.items():
            scale = spec.get("scale", "log")
            if scale not in ("log", "lin"):
                raise ValueError(f"node '{name}': scale must be 'log' or 'lin'")
            self.lin.append(scale == "lin")
            guess = spec.get("guess", 0.0 if scale == "lin" else 1.0)
            self.x0.append(float(guess) if scale == "lin" else self._log10_checked(guess, f"guess of node '{name}'"))
            if spec.get("fixed", False):
                self.fixed_nodes.add(name)

        self.relations = []
        for k, rel in enumerate(relations_spec):
            name = rel.get("name", f"relation_{k}")
            kind = rel.get("type", "log")
            sigma = rel.get("sigma", 1e-3)
            if not callable(sigma) and not float(sigma) > 0:
                raise ValueError(f"relation '{name}' needs a positive sigma")
            if kind == "fn":
                nodes = rel.get("nodes")
                if not nodes or not callable(rel.get("f")):
                    raise ValueError(f"relation '{name}' (fn) needs 'nodes' and a callable 'f'")
                self._check_names(name, nodes)
                self.relations.append({"name": name, "type": "fn", "f": rel["f"], "sigma": sigma,
                                       "nodes": [self.node_to_idx[n] for n in nodes]})
                continue
            terms = rel.get("terms")
            if not terms:
                raise ValueError(f"relation '{name}' has no terms")
            self._check_names(name, terms)
            if kind == "sum":
                pw = rel.get("pow", {})
                self._check_names(name, pw)
                self.relations.append({"name": name, "type": "sum", "sigma": sigma, "K": float(rel.get("K", 0.0)),
                                       "terms": [(self.node_to_idx[n], float(c), float(pw.get(n, 1.0))) for n, c in terms.items()]})
                continue
            if kind != "log":
                raise ValueError(f"relation '{name}': unknown type '{kind}'")
            signed = [n for n in terms if self.lin[self.node_to_idx[n]]]
            if signed:
                raise ValueError(f"relation '{name}' is log-linear but uses signed nodes {signed}: use type 'sum' or 'fn'")
            depends = rel.get("depends")
            if depends is not None:
                self._check_names(name, depends)
            self.relations.append({
                "name": name, "type": "log", "sigma": sigma, "rhs": rel.get("rhs", 0.0),
                "terms": [(self.node_to_idx[n], float(c)) for n, c in terms.items()],
                "depends": None if depends is None else [self.node_to_idx[n] for n in depends],
            })
        self._nonlinear = any(r["type"] != "log" or callable(r["rhs"]) for r in self.relations)
        self._has_callables = self._nonlinear or any(callable(r["sigma"]) for r in self.relations)
        self.x = list(self.x0)  # last solution (solver space), kept for inspection

    # ------------------------------------------------------------------ helpers
    def _check_names(self, rel_name, names):
        unknown = [n for n in names if n not in self.node_to_idx]
        if unknown:
            raise KeyError(f"relation '{rel_name}' uses unknown nodes: {unknown}")

    @staticmethod
    def _log10_checked(value, what):
        value = float(value)
        if not value > 0 or math.isinf(value):
            raise ValueError(f"{what} must be a finite positive number (log-space), got {value}")
        return math.log10(value)

    def _to_value(self, i, xi):
        return xi if self.lin[i] else 10.0 ** xi

    def _values(self, x):
        return {name: self._to_value(i, x[i]) for i, name in enumerate(self.nodes_names)}

    @staticmethod
    def _eval(param, values):
        return float(param(values)) if callable(param) else float(param)

    def _residual(self, rel, x, values):
        if rel["type"] == "log":
            r = -self._eval(rel["rhs"], values)
            for i, c in rel["terms"]:
                r += c * x[i]
            return r
        if rel["type"] == "sum":
            r = -rel["K"]
            for i, c, p in rel["terms"]:
                r += c * self._to_value(i, x[i]) ** p
            return r
        return float(rel["f"](values))

    def _fd_step(self, i, xi):
        return 1e-6 * max(1.0, abs(xi)) if self.lin[i] else 1e-6

    def _derivative(self, rel, x, xp, xm, h, rhs_only, values, i):
        """Central difference, falling back to a one-sided one at the edge of a domain."""
        name = self.nodes_names[i]

        def g(z):
            try:
                vz = dict(values) if values is not None else self._values(z)
                vz[name] = self._to_value(i, z[i])
                if rhs_only:
                    return -self._eval(rel["rhs"], vz)
                return self._residual(rel, z, vz)
            except (ValueError, ZeroDivisionError, OverflowError, TypeError):
                return None
        fp, fm = g(xp), g(xm)
        if fp is not None and fm is not None:
            return (fp - fm) / (2 * h)
        f0 = g(x)
        if fp is not None and f0 is not None:
            return (fp - f0) / h
        if fm is not None and f0 is not None:
            return (f0 - fm) / h
        return 0.0

    def _rows(self, x, measurements, col, jacobian=True):
        """Residual rows: list of (entries [(column, derivative)], residual, weight), and the cost."""
        values = self._values(x) if self._has_callables else None
        rows, cost = [], 0.0
        for rel in self.relations:
            r = self._residual(rel, x, values)
            w = 1.0 / max(self._eval(rel["sigma"], values), 1e-300)
            cost += (w * r) ** 2
            entries = {}
            if jacobian:
                if rel["type"] == "log":
                    for i, c in rel["terms"]:
                        if i in col:
                            entries[col[i]] = entries.get(col[i], 0.0) + c
                    probe = (rel["depends"] if rel["depends"] is not None else list(col)) if callable(rel["rhs"]) else []
                    rhs_only = True
                elif rel["type"] == "sum":
                    for i, c, p in rel["terms"]:
                        if i in col:
                            v = self._to_value(i, x[i])
                            dv = 1.0 if self.lin[i] else v * LN10
                            entries[col[i]] = entries.get(col[i], 0.0) + c * p * v ** (p - 1) * dv
                    probe, rhs_only = [], False
                else:
                    probe, rhs_only = rel["nodes"], False
                for i in probe:
                    if i not in col:
                        continue
                    h = self._fd_step(i, x[i])
                    xp, xm = list(x), list(x)
                    xp[i] += h
                    xm[i] -= h
                    d = self._derivative(rel, x, xp, xm, h, rhs_only, values, i)
                    if d:
                        entries[col[i]] = entries.get(col[i], 0.0) + d
            rows.append((list(entries.items()), r, w))
        for i, (target, sigma) in measurements:
            r = x[i] - target
            w = 1.0 / sigma
            cost += (w * r) ** 2
            rows.append(([(col[i], 1.0)] if (jacobian and i in col) else [], r, w))
        return rows, cost

    def _cost(self, x, measurements):
        """Cost at x, or infinity when x is outside the domain of some relation (sqrt of a negative...)."""
        try:
            c = self._rows(x, measurements, {}, jacobian=False)[1]
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            return math.inf
        return c if math.isfinite(c) else math.inf

    def _step(self, rows, n, lam):
        """Solve the damped, ridge-regularised least-squares step. Returns (delta, R)."""
        A, b = [], []
        colnorm = [0.0] * n
        for entries, r, w in rows:
            if not entries:
                continue
            row = [0.0] * n
            for a, d in entries:
                row[a] = w * d
                colnorm[a] += (w * d) ** 2
            A.append(row)
            b.append(-w * r)
        ridge = 1.0 / self.prior_sigma
        for a in range(n):
            row = [0.0] * n
            row[a] = ridge
            A.append(row)
            b.append(0.0)
        if lam > 0:
            for a in range(n):
                row = [0.0] * n
                row[a] = math.sqrt(lam) * (math.sqrt(colnorm[a]) if colnorm[a] > 0 else 1.0)
                A.append(row)
                b.append(0.0)
        return _qr_solve(A, b)

    # ------------------------------------------------------------------ solve
    def solve(self, measured_dict=None, max_iterations=50, damping_lambda=1e-3,
              tolerance=1e-12, measurement_sigma=1e-4, compute_uncertainty=True, start=None):
        """
        measured_dict      {node: value} or {node: (value, sigma_dex)}
        max_iterations     upper bound for the nonlinear case (a linear problem needs 1 to 4 steps)
        damping_lambda     initial Levenberg-Marquardt damping (adapted during the solve)
        measurement_sigma  default sigma (dex) of a measurement given without its own
        start              optional {node: value} starting point (defaults to the guesses)
        """
        measured_dict = measured_dict or {}
        measurements = []
        for name, m in measured_dict.items():
            if name not in self.node_to_idx:
                raise KeyError(f"unknown measured node '{name}'")
            value, sigma = (m if isinstance(m, (tuple, list)) else (m, measurement_sigma))
            if not float(sigma) > 0:
                raise ValueError(f"measurement of '{name}' needs a positive sigma")
            i = self.node_to_idx[name]
            target = float(value) if self.lin[i] else self._log10_checked(value, f"measurement of '{name}'")
            measurements.append((i, (target, float(sigma))))

        x = list(self.x0)
        if start:
            for name, v in start.items():
                i = self.node_to_idx[name]
                x[i] = float(v) if self.lin[i] else self._log10_checked(v, f"start value of '{name}'")
        for i, (target, _) in measurements:  # a fixed node that is also measured takes the measured value
            if self.nodes_names[i] in self.fixed_nodes:
                x[i] = target

        free = [i for i, name in enumerate(self.nodes_names) if name not in self.fixed_nodes]
        col = {i: a for a, i in enumerate(free)}
        n = len(free)
        iterations, converged = 0, True
        R = None

        if n and not self._nonlinear:
            # linear in log-space: one least-squares step, then refinement steps that remove the
            # tiny bias of the ridge (each step shrinks it by a factor ~ (ridge / weight)^2)
            for iterations in range(1, 5):
                rows, _ = self._rows(x, measurements, col)
                delta, R = self._step(rows, n, 0.0)
                for a, i in enumerate(free):
                    x[i] += delta[a]
                if max(abs(d) for d in delta) < 1e-13:
                    break
        elif n:
            # warm start: solve the log-linear part of the network exactly (it is usually most of it),
            # then refine everything together; keep the original start if the warm one is invalid
            x = self._warm_start(x, measurements, free, col)
            lam = damping_lambda
            converged = False
            cost = self._cost(x, measurements)
            if not math.isfinite(cost):
                raise ValueError("the starting point is outside the domain of a relation "
                                 "(e.g. the square root or arccos of an invalid value): change the guesses")
            for iterations in range(1, max_iterations + 1):
                rows, cost = self._rows(x, measurements, col)
                accepted = False
                # 1) Gauss-Newton direction with backtracking; 2) if that fails, damped steps
                try:
                    gn, _R = self._step(rows, n, 0.0)
                except ArithmeticError:
                    gn = None
                if gn is not None:
                    alpha = 1.0
                    for _ in range(25):
                        delta = [alpha * d for d in gn]
                        x_new = list(x)
                        for a, i in enumerate(free):
                            x_new[i] += delta[a]
                        new_cost = self._cost(x_new, measurements)
                        if new_cost <= cost:
                            accepted = True
                            break
                        alpha *= 0.5
                if not accepted:
                    for _ in range(30):
                        try:
                            delta, _R = self._step(rows, n, lam)
                        except ArithmeticError:
                            lam *= 10.0
                            continue
                        x_new = list(x)
                        for a, i in enumerate(free):
                            x_new[i] += delta[a]
                        new_cost = self._cost(x_new, measurements)
                        if new_cost <= cost:
                            accepted = True
                            break
                        lam *= 10.0
                if not accepted:
                    converged = True  # no descent direction left: at the minimum
                    break
                step = max(abs(d) for d in delta)
                drop = cost - new_cost
                x, cost = x_new, new_cost
                lam = max(lam / 10.0, 1e-15)
                if step < 1e-12 or drop <= tolerance * max(1.0, cost):
                    converged = True
                    break

        self.x = x
        _, cost = self._rows(x, measurements, {}, jacobian=False)
        dof = len(self.relations) + len(measurements) - n
        result = {
            "values": self._values(x),
            "cost": cost,
            "iterations": iterations,
            "converged": converged,
            "dof": dof,
            "reduced_chi2": cost / dof if dof > 0 else None,
        }
        pulls = self._rows(x, [], {}, jacobian=False)[0]
        result["relation_pulls"] = {rel["name"]: r * w for rel, (_, r, w) in zip(self.relations, pulls)}

        if compute_uncertainty:
            sigma_dex = {name: 0.0 for name in self.nodes_names}
            covariance = {}
            if n:
                if R is None or self._nonlinear:
                    rows, _ = self._rows(x, measurements, col)
                    _, R = self._step(rows, n, 0.0)
                cov = _covariance_from_R(R)
                for a, i in enumerate(free):
                    sigma_dex[self.nodes_names[i]] = math.sqrt(max(cov[a][a], 0.0))
                    for b, j in enumerate(free):
                        covariance[(self.nodes_names[i], self.nodes_names[j])] = cov[a][b]
            result["sigma_dex"] = sigma_dex
            # relative 1-sigma uncertainty for positive nodes, absolute for signed nodes
            result["uncertainty"] = {k: (s if self.lin[self.node_to_idx[k]] else LN10 * s) for k, s in sigma_dex.items()}
            result["covariance"] = covariance
            result["undetermined"] = sorted(
                k for k, s in sigma_dex.items()
                if s > self.undetermined_sigma * (max(1.0, abs(x[self.node_to_idx[k]])) if self.lin[self.node_to_idx[k]] else 1.0))
        return result

    def _warm_start(self, x, measurements, free, col):
        linear = [r for r in self.relations if r["type"] == "log" and not callable(r["rhs"])]
        if not linear:
            return x
        saved = self.relations, self._has_callables
        self.relations = linear
        self._has_callables = any(callable(r["sigma"]) for r in linear)
        try:
            xw = list(x)
            for _ in range(3):
                rows, _ = self._rows(xw, measurements, col)
                delta, _R = self._step(rows, len(free), 0.0)
                for a, i in enumerate(free):
                    xw[i] += delta[a]
        except ArithmeticError:
            xw = None
        finally:
            self.relations, self._has_callables = saved
        if xw is None:
            return x
        cw, c0 = self._cost(xw, measurements), self._cost(x, measurements)
        return xw if (math.isfinite(cw) and (cw <= c0 or not math.isfinite(c0))) else x

    # ------------------------------------------------------------------ validation helper
    def leave_one_out(self, measured_dict, **solve_kwargs):
        """Hide each measurement in turn and predict it from the rest.
        Returns {node: {"measured", "predicted", "sigma_dex", "pull", "determined"}}.
        pull = (log predicted - log measured) / sqrt(sigma_pred^2 + sigma_meas^2), in value units
        for signed nodes."""
        default_sigma = solve_kwargs.get("measurement_sigma", 1e-4)
        report = {}
        for hidden, m in measured_dict.items():
            value, sigma_m = (m if isinstance(m, (tuple, list)) else (m, default_sigma))
            rest = {k: v for k, v in measured_dict.items() if k != hidden}
            out = self.solve(measured_dict=rest, **solve_kwargs)
            pred, s = out["values"][hidden], out["sigma_dex"][hidden]
            d = (pred - value) if self.lin[self.node_to_idx[hidden]] else math.log10(pred) - math.log10(value)
            report[hidden] = {
                "measured": value, "predicted": pred, "sigma_dex": s,
                "pull": d / math.sqrt(s * s + sigma_m * sigma_m),
                "determined": hidden not in out["undetermined"],
            }
        return report
