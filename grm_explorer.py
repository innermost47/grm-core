# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Explorer: write a network with forms or as JSON (both stay in sync), solve it, and see at once whether
the result is valid.

    python grm_explorer.py

- Presets: textbook problems with a known answer, and open problems of physics written as networks
  (see grm_presets.py: those do not solve the problems, they show and measure the tensions).
- Validity: give a node an "expected" value (and optionally a relative tolerance): after the solve, each check
  is green or red, and a banner says whether the whole network reproduces what was expected. Without a
  tolerance, a check passes within 3 sigma of the solved uncertainty.
- Consistency: chi2 per degree of freedom, the pull of every relation and measurement, the nodes that the
  network does not determine, and leave-one-out (each measurement predicted from all the others).
- Relations: log (products and powers), sum (with powers) and fn, an expression of the nodes that must be
  zero, e.g. "x - 5 * (1 - exp(-x))" (only arithmetic and math functions are allowed in it).

The logic (JSON -> network -> report) is in plain functions above the interface, so it can be used and
tested without a display.
"""
import ast
import copy
import json
import math

from grm import GlobalRelationalNetwork
from grm_presets import PRESETS

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # the logic stays usable without a display
    tk = None

LN10 = math.log(10.0)

# ====================================================================== expressions of fn relations
_FUNCTIONS = {name: getattr(math, name) for name in (
    "sqrt", "exp", "log", "log10", "log2", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "sinh", "cosh", "tanh", "asinh", "acosh", "atanh", "erf", "erfc", "gamma", "lgamma", "hypot")}
_FUNCTIONS["abs"] = abs
_FUNCTIONS["pow"] = math.pow
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
_BINARY = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
           ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b}
_UNARY = {ast.USub: lambda a: -a, ast.UAdd: lambda a: a}


def compile_expression(expr, node_names):
    """A safe expression of the nodes -> (function of the values, nodes it uses).
    Only numbers, node names, + - * / ** %, and the math functions above: no attribute, no import, no call
    of anything else."""
    tree = ast.parse(expr, mode="eval")
    used = []

    def check(node):
        if isinstance(node, ast.Expression):
            check(node.body)
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                raise ValueError(f"only numbers are allowed as constants, not {node.value!r}")
        elif isinstance(node, ast.Name):
            if node.id in node_names:
                if node.id not in used:
                    used.append(node.id)
            elif node.id not in _CONSTANTS:
                raise ValueError(f"unknown name '{node.id}' (not a node, nor pi, e, tau)")
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in _BINARY:
                raise ValueError("operator not allowed")
            check(node.left)
            check(node.right)
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in _UNARY:
                raise ValueError("operator not allowed")
            check(node.operand)
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS or node.keywords:
                raise ValueError("only math functions can be called: " + ", ".join(sorted(_FUNCTIONS)))
            for a in node.args:
                check(a)
        else:
            raise ValueError(f"'{type(node).__name__}' is not allowed in an expression")

    check(tree)
    if not used:
        raise ValueError("the expression uses no node")

    def evaluate(node, values):
        if isinstance(node, ast.Expression):
            return evaluate(node.body, values)
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            return values[node.id] if node.id in node_names else _CONSTANTS[node.id]
        if isinstance(node, ast.BinOp):
            return _BINARY[type(node.op)](evaluate(node.left, values), evaluate(node.right, values))
        if isinstance(node, ast.UnaryOp):
            return _UNARY[type(node.op)](evaluate(node.operand, values))
        return _FUNCTIONS[node.func.id](*(evaluate(a, values) for a in node.args))

    def f(values):
        try:
            return float(evaluate(tree, values))
        except (ValueError, ZeroDivisionError, OverflowError):
            return math.nan               # outside the domain: the solver steps back
    return f, used


# ====================================================================== JSON document -> network -> report
def normalize(doc):
    """The explorer's JSON, cleaned (older files: scale "linear", relation type "linear")."""
    doc = copy.deepcopy(doc)
    out = {k: v for k, v in doc.items() if k not in ("nodes", "relations")}
    out["nodes"] = {}
    for name, spec in (doc.get("nodes") or {}).items():
        spec = dict(spec or {})
        scale = spec.get("scale", "log")
        spec["scale"] = "lin" if scale in ("lin", "linear") else "log"
        out["nodes"][str(name)] = spec
    out["relations"] = []
    for rel in doc.get("relations") or []:
        rel = dict(rel)
        kind = rel.get("type", "log")
        rel["type"] = {"linear": "sum"}.get(kind, kind)
        out["relations"].append(rel)
    return out


def _number(value, what):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what}: '{value}' is not a number") from None


def build_network(doc):
    """-> (GlobalRelationalNetwork, measured_dict). Raises ValueError with a readable message."""
    doc = normalize(doc)
    nodes, measured = {}, {}
    if not doc["nodes"]:
        raise ValueError("the network has no node")
    for name, spec in doc["nodes"].items():
        if not name:
            continue
        scale = spec["scale"]
        guess = spec.get("guess", "")
        guess = (0.0 if scale == "lin" else 1.0) if guess in ("", None) else _number(guess, f"guess of '{name}'")
        if scale == "log" and guess <= 0:
            raise ValueError(f"guess of '{name}' must be positive (or set the node's scale to lin)")
        nodes[name] = {"guess": guess, "scale": scale, "fixed": bool(spec.get("fixed", False))}
        m = spec.get("measured")
        if m not in (None, "", []) and not (isinstance(m, (list, tuple)) and (len(m) == 0 or m[0] in ("", None))):
            if not isinstance(m, (list, tuple)) or len(m) != 2:
                raise ValueError(f"measured of '{name}' must be [value, sigma_dex]")
            measured[name] = (_number(m[0], f"measured value of '{name}'"), _number(m[1], f"sigma of '{name}'"))
    relations = []
    names = set(nodes)
    for k, rel in enumerate(doc["relations"]):
        rname = rel.get("name") or f"relation {k + 1}"
        sigma = _number(rel.get("sigma", 1e-3), f"sigma of '{rname}'")
        kind = rel["type"]
        if kind == "fn":
            expr = (rel.get("expr") or "").strip()
            if not expr:
                raise ValueError(f"'{rname}': an fn relation needs an expression")
            try:
                f, used = compile_expression(expr, names)
            except SyntaxError as err:
                raise ValueError(f"'{rname}': {err.msg}") from None
            except ValueError as err:
                raise ValueError(f"'{rname}': {err}") from None
            relations.append({"name": rname, "type": "fn", "nodes": used, "f": f, "sigma": sigma})
            continue
        terms = {str(n): _number(c, f"coefficient of '{n}' in '{rname}'") for n, c in (rel.get("terms") or {}).items()}
        if not terms:
            raise ValueError(f"'{rname}' has no term")
        unknown = [n for n in terms if n not in names]
        if unknown:
            raise ValueError(f"'{rname}' uses unknown node(s): {', '.join(unknown)}")
        if kind == "sum":
            pw = {str(n): _number(p, f"power of '{n}' in '{rname}'") for n, p in (rel.get("pow") or {}).items()}
            relations.append({"name": rname, "type": "sum", "terms": terms, "pow": pw,
                              "K": _number(rel.get("K", rel.get("rhs", 0.0)), f"K of '{rname}'"), "sigma": sigma})
        elif kind == "log":
            relations.append({"name": rname, "type": "log", "terms": terms,
                              "rhs": _number(rel.get("rhs", 0.0), f"rhs of '{rname}'"), "sigma": sigma})
        else:
            raise ValueError(f"'{rname}': unknown relation type '{kind}' (log, sum or fn)")
    if not relations:
        raise ValueError("the network has no relation")
    return GlobalRelationalNetwork(nodes, relations), measured


def solve_document(doc, leave_one_out=False):
    """Solve and judge. Returns a report:
        result      the solver's output
        checks      [{node, value, expected, tolerance, deviation, ok}]   (nodes with an expected value)
        pulls       [(what, pull in sigma)] relations and measurements, largest first
        valid       True / False / None (no expected value)
        consistent  False when chi2/dof is too large for chance (p < 0.003)
        loo         leave-one-out report, if asked"""
    doc = normalize(doc)
    net, measured = build_network(doc)
    result = net.solve(measured_dict=measured)
    values, sigma = result["values"], result["sigma_dex"]
    checks = []
    for name, spec in doc["nodes"].items():
        exp = spec.get("expected")
        if exp in (None, "") or name not in values:
            continue
        exp = _number(exp, f"expected value of '{name}'")
        lin = spec["scale"] == "lin"
        v = values[name]
        tol = spec.get("tolerance")
        if tol in (None, ""):
            # 3 sigma of what the network found (relative for positive nodes), and never below 1e-9
            tol = 3 * (sigma[name] if lin else LN10 * sigma[name])
            tol_source = "3 sigma"
        else:
            tol = _number(tol, f"tolerance of '{name}'")
            tol_source = "set"
        if lin:
            deviation = abs(v - exp)
            ok = deviation <= max(tol * max(abs(exp), 1.0) if tol_source == "set" else tol, 1e-12)
            rel_dev = deviation / max(abs(exp), 1e-300)
        else:
            rel_dev = abs(v / exp - 1.0) if exp != 0 else math.inf
            ok = rel_dev <= max(tol, 1e-9)
        checks.append({"node": name, "value": v, "expected": exp, "tolerance": tol, "tolerance_source": tol_source,
                       "deviation": rel_dev, "ok": bool(ok) and result["converged"]})
    pulls = [(f"relation: {k}", p) for k, p in result["relation_pulls"].items()]
    for name, (m, s) in measured.items():
        i = net.node_to_idx[name]
        d = (values[name] - m) if net.lin[i] else math.log10(values[name]) - math.log10(m)
        pulls.append((f"measurement: {name}", d / s))
    pulls.sort(key=lambda t: -abs(t[1]))
    dof = result["dof"]
    chi2 = result["cost"]
    consistent = True
    if dof and dof > 0:
        # chi2 with dof degrees of freedom: 3-sigma threshold (Wilson-Hilferty approximation)
        z = ((chi2 / dof) ** (1 / 3) - (1 - 2 / (9 * dof))) / math.sqrt(2 / (9 * dof))
        consistent = z < 3.0
    report = {"result": result, "checks": checks, "pulls": pulls,
              "valid": (all(c["ok"] for c in checks) if checks else None),
              "consistent": consistent and result["converged"], "measured": measured}
    if leave_one_out and measured:
        report["loo"] = net.leave_one_out(measured)
    return report


def preset_document(preset):
    """A preset as an explorer document (its description and sources kept as metadata)."""
    doc = {k: copy.deepcopy(preset[k]) for k in ("title", "category", "description", "sources") if k in preset}
    doc["nodes"] = copy.deepcopy(preset["nodes"])
    doc["relations"] = copy.deepcopy(preset["relations"])
    return normalize(doc)


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return format(v, ".10g")
    return str(v)


# ====================================================================== the interface
COLORS = {"bg": "#f6f8fa", "panel": "#ffffff", "ink": "#1f2328", "muted": "#656d76", "ok": "#1a7f37",
          "bad": "#cf222e", "warn": "#9a6700", "accent": "#0969da", "open": "#8250df", "edge": "#8c959f"}

if tk is not None:
    class ScrollableFrame(ttk.Frame):
        """A frame that scrolls vertically (mouse wheel included)."""

        def __init__(self, container, **kwargs):
            super().__init__(container, **kwargs)
            self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, background=COLORS["panel"])
            bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.inner = ttk.Frame(self.canvas, style="Panel.TFrame")
            self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
            self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
            self.canvas.configure(yscrollcommand=bar.set)
            self.canvas.pack(side="left", fill="both", expand=True)
            bar.pack(side="right", fill="y")
            for w in (self.canvas, self.inner):
                w.bind("<Enter>", lambda e: self._wheel(True))
                w.bind("<Leave>", lambda e: self._wheel(False))

        def _wheel(self, on):
            if on:
                self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))
                self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
                self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
            else:
                for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                    self.canvas.unbind_all(seq)

    class Tooltip:
        def __init__(self, widget, text):
            self.widget, self.text, self.tip = widget, text, None
            widget.bind("<Enter>", self.show, add="+")
            widget.bind("<Leave>", self.hide, add="+")

        def show(self, _e=None):
            if self.tip:
                return
            x, y = self.widget.winfo_rootx() + 12, self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            self.tip = tk.Toplevel(self.widget)
            self.tip.wm_overrideredirect(True)
            self.tip.wm_geometry(f"+{x}+{y}")
            tk.Label(self.tip, text=self.text, background="#fff8c5", foreground=COLORS["ink"], relief="solid",
                     borderwidth=1, justify="left", wraplength=420, font=("Segoe UI", 9)).pack(ipadx=6, ipady=3)

        def hide(self, _e=None):
            if self.tip:
                self.tip.destroy()
                self.tip = None

    NODE_COLUMNS = [("name", "Name", 9), ("guess", "Guess", 8), ("scale", "Scale", 4), ("meas", "Measured", 11),
                    ("sigma", "σ (dex)", 8), ("expected", "Expected", 11), ("tol", "Tol. (rel)", 7),
                    ("fixed", "Fixed", 3)]
    REL_COLUMNS = [("name", "Name", 12), ("type", "Type", 4), ("terms", "Terms  or  fn expression", 24),
                   ("pow", "Powers (sum)", 8), ("rhs", "RHS / K", 8), ("sigma", "σ", 6)]

    HELP = {
        "Guess": "Starting value of the solver. Positive for log nodes.",
        "Scale": "log: a positive quantity (solved as log10). lin: a signed quantity.",
        "Measured": "Optional: a measured value. The node is then pulled towards it within σ.",
        "σ (dex)": "Uncertainty of the measurement in dex = relative uncertainty / 2.303  (1 % ≈ 0.00434). "
                   "Absolute for lin nodes.",
        "Expected": "Optional: the value the result should have. After the solve, the node turns green (valid) "
                    "or red (not valid).",
        "Tol. (rel)": "Relative tolerance of the check (e.g. 1e-6). Empty: 3 σ of the solved uncertainty.",
        "Fixed": "The node keeps its guess (not solved).",
        "Terms  or  fn expression": "log: node:power pairs, sum(power × log10 node) = RHS, e.g. 'E:1, m:-1, c:-2'.\n"
                                    "sum: node:coefficient pairs, sum(coeff × node^pow) = K.\n"
                                    "fn: an expression of the nodes that must be 0, e.g. 'x - 5*(1 - exp(-x))'.",
        "Powers (sum)": "sum relations only: node:power pairs, e.g. 'a:2, b:2, c:2'.",
        "RHS / K": "log: right-hand side in log10 units (e.g. -0.30103 for 1/2). sum: the constant K. fn: unused.",
        "σ": "How tightly the relation must hold, in its own residual unit (dex for log relations).",
    }

    class GRMExplorer:
        def __init__(self, root):
            self.root = root
            root.title("GRM Explorer")
            root.geometry("1500x900")
            root.minsize(1200, 700)
            self.node_rows, self.rel_rows = [], []
            self.meta = {}
            self._syncing = False
            self._json_job = self._solve_job = None
            self.live = tk.BooleanVar(value=True)
            self.last_report = None
            self._style()
            self._build()
            self.load_preset(PRESETS[0])
            root.bind("<F5>", lambda e: self.solve())
            root.bind("<Control-Return>", lambda e: self.solve())
            root.bind("<Control-s>", lambda e: self.export_json())
            root.bind("<Control-o>", lambda e: self.import_json())

        # ------------------------------------------------------------------ look
        def _style(self):
            s = ttk.Style(self.root)
            if "clam" in s.theme_names():
                s.theme_use("clam")
            self.root.configure(background=COLORS["bg"])
            base = ("Segoe UI", 10)
            s.configure(".", font=base, background=COLORS["bg"], foreground=COLORS["ink"])
            s.configure("Panel.TFrame", background=COLORS["panel"])
            s.configure("TLabelframe", background=COLORS["panel"], bordercolor="#d0d7de")
            s.configure("TLabelframe.Label", background=COLORS["panel"], foreground=COLORS["muted"],
                        font=("Segoe UI", 10, "bold"))
            s.configure("Head.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9, "bold"))
            s.configure("Panel.TLabel", background=COLORS["panel"])
            s.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 9))
            s.configure("Title.TLabel", background=COLORS["bg"], font=("Segoe UI", 15, "bold"))
            s.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), foreground="white", background=COLORS["accent"])
            s.map("Accent.TButton", background=[("active", "#0550ae")])
            s.configure("Small.TButton", padding=(2, 0))
            s.configure("Treeview", rowheight=22, font=("Consolas", 10))
            s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
            s.configure("Panel.TCheckbutton", background=COLORS["panel"])

        # ------------------------------------------------------------------ layout
        def _build(self):
            top = ttk.Frame(self.root, padding=(10, 8, 10, 2))
            top.pack(fill="x")
            ttk.Label(top, text="GRM Explorer", style="Title.TLabel").pack(side="left")
            ttk.Label(top, text="   Preset").pack(side="left")
            self.preset_var = tk.StringVar()
            labels = []
            for p in PRESETS:
                tag = "Known" if p["category"] == "known" else "OPEN PROBLEM"
                labels.append(f"{tag}  ·  {p['title']}")
            self.preset_box = ttk.Combobox(top, textvariable=self.preset_var, values=labels, state="readonly", width=58)
            self.preset_box.pack(side="left", padx=6)
            self.preset_box.bind("<<ComboboxSelected>>", lambda e: self.load_preset(PRESETS[self.preset_box.current()]))
            ttk.Button(top, text="New", command=self.new_network).pack(side="left", padx=2)
            ttk.Button(top, text="Open JSON…", command=self.import_json).pack(side="left", padx=2)
            ttk.Button(top, text="Save JSON…", command=self.export_json).pack(side="left", padx=2)
            ttk.Button(top, text="▶ Solve  (F5)", style="Accent.TButton", command=self.solve).pack(side="right", padx=2)
            ttk.Button(top, text="Leave one out", command=lambda: self.solve(leave_one_out=True)).pack(side="right", padx=2)
            ttk.Checkbutton(top, text="Solve live", variable=self.live).pack(side="right", padx=8)

            # the problem: title, category, description, sources
            info = ttk.Frame(self.root, padding=(10, 0, 10, 4))
            info.pack(fill="x")
            self.badge = tk.Label(info, text="", font=("Segoe UI", 9, "bold"), foreground="white", padx=8, pady=2)
            self.badge.pack(side="left", anchor="n", pady=2)
            self.description = tk.Label(info, text="", justify="left", anchor="w", wraplength=1380,
                                        background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 10))
            self.description.pack(side="left", fill="x", expand=True, padx=8)
            info.bind("<Configure>", lambda e: self.description.configure(wraplength=max(400, e.width - 160)))

            panes = ttk.PanedWindow(self.root, orient="horizontal")
            panes.pack(fill="both", expand=True, padx=10, pady=(0, 6))
            self.panes = panes
            # first widths: forms 44 %, JSON 24 %, results 32 % of the window
            self.root.after(50, lambda: self._place_sashes(0.44, 0.68))

            # ---- column 1: forms
            col1 = ttk.Frame(panes)
            panes.add(col1, weight=6)
            self.nodes_box = self._table(col1, " 1 · Nodes and measurements ", NODE_COLUMNS, "+ Node", self.add_node_row)
            self.rels_box = self._table(col1, " 2 · Relations ", REL_COLUMNS, "+ Relation", self.add_relation_row)

            # ---- column 2: JSON
            col2 = ttk.LabelFrame(panes, text=" Live JSON (edit either side) ", padding=4)
            panes.add(col2, weight=2)
            self.json_status = ttk.Label(col2, text="● In sync", foreground=COLORS["ok"], style="Panel.TLabel")
            self.json_status.pack(anchor="w")
            jf = ttk.Frame(col2)
            jf.pack(fill="both", expand=True)
            self.json_text = tk.Text(jf, wrap="none", font=("Consolas", 10), undo=True, background="#fbfcfd",
                                     relief="flat", borderwidth=1, highlightthickness=1, highlightcolor=COLORS["accent"],
                                     highlightbackground="#d0d7de")
            ys = ttk.Scrollbar(jf, orient="vertical", command=self.json_text.yview)
            xs = ttk.Scrollbar(jf, orient="horizontal", command=self.json_text.xview)
            self.json_text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
            self.json_text.grid(row=0, column=0, sticky="nsew")
            ys.grid(row=0, column=1, sticky="ns")
            xs.grid(row=1, column=0, sticky="ew")
            jf.rowconfigure(0, weight=1)
            jf.columnconfigure(0, weight=1)
            self.json_text.bind("<KeyRelease>", lambda e: self._schedule_json())

            # ---- column 3: verdict, topology, results
            col3 = ttk.Frame(panes)
            panes.add(col3, weight=4)
            self.verdict = tk.Label(col3, text="Not solved yet", font=("Segoe UI", 13, "bold"), anchor="w",
                                    padx=12, pady=6, background="#eaeef2", foreground=COLORS["muted"])
            self.verdict.pack(fill="x")
            self.verdict_detail = tk.Label(col3, text="", font=("Segoe UI", 9), anchor="w", justify="left",
                                           padx=12, pady=4, background="#eaeef2", foreground=COLORS["ink"],
                                           wraplength=480)
            self.verdict_detail.pack(fill="x")
            col3.bind("<Configure>", lambda e: (self.verdict_detail.configure(wraplength=max(300, e.width - 30)),
                                                self.verdict.configure(wraplength=max(300, e.width - 30))))
            right = ttk.PanedWindow(col3, orient="vertical")
            right.pack(fill="both", expand=True, pady=(6, 0))
            cf = ttk.LabelFrame(right, text=" Network ", padding=2)
            right.add(cf, weight=2)
            self.canvas = tk.Canvas(cf, background=COLORS["panel"], highlightthickness=0, height=240)
            self.canvas.pack(fill="both", expand=True)
            self.canvas.bind("<Configure>", lambda e: self._draw())
            rf = ttk.LabelFrame(right, text=" Solved values ", padding=2)
            right.add(rf, weight=3)
            cols = ("node", "value", "unit", "unc", "check", "expected")
            self.tree = ttk.Treeview(rf, columns=cols, show="headings", height=8)
            for c, title, w in (("node", "Node", 80), ("value", "Value", 130), ("unit", "Unit", 70), ("unc", "± 1σ", 70),
                                ("check", "Check", 95), ("expected", "Expected", 110)):
                self.tree.heading(c, text=title)
                self.tree.column(c, width=w, minwidth=50, stretch=True, anchor="w" if c == "node" else "e")
            self.tree.tag_configure("ok", foreground=COLORS["ok"])
            self.tree.tag_configure("bad", foreground=COLORS["bad"])
            self.tree.tag_configure("undetermined", foreground=COLORS["warn"])
            self.tree.pack(fill="both", expand=True)
            pf = ttk.LabelFrame(right, text=" Pulls (σ): what disagrees, and how much ", padding=2)
            right.add(pf, weight=2)
            self.pulls = ttk.Treeview(pf, columns=("what", "pull"), show="headings", height=5)
            self.pulls.heading("what", text="Relation / measurement")
            self.pulls.heading("pull", text="Pull")
            self.pulls.column("what", width=300, stretch=True)
            self.pulls.column("pull", width=70, minwidth=60, stretch=False, anchor="e")
            self.pulls.tag_configure("bad", foreground=COLORS["bad"])
            self.pulls.tag_configure("warn", foreground=COLORS["warn"])
            self.pulls.pack(fill="both", expand=True)

            self.status = ttk.Label(self.root, text="", style="Muted.TLabel", padding=(10, 0, 10, 6))
            self.status.pack(fill="x")

        def _place_sashes(self, a, b):
            w = self.panes.winfo_width()
            if w < 100:
                self.root.after(50, lambda: self._place_sashes(a, b))
                return
            self.panes.sashpos(0, int(w * a))
            self.panes.sashpos(1, int(w * b))

        def _table(self, parent, title, columns, add_text, add_command):
            box = ttk.LabelFrame(parent, text=title, padding=4)
            box.pack(fill="both", expand=True, pady=(0, 6))
            scroll = ScrollableFrame(box)
            scroll.pack(fill="both", expand=True)
            for k, (_, text, width) in enumerate(columns):      # the header shares the grid of the rows
                lab = ttk.Label(scroll.inner, text=text, style="Head.TLabel")
                lab.grid(row=0, column=k, padx=1, sticky="w")
                if text in HELP:
                    Tooltip(lab, HELP[text])
            ttk.Button(box, text=add_text, command=lambda: (add_command(), self.form_changed())).pack(anchor="w", pady=(4, 0))
            box.scroll = scroll
            box.next_row = 1
            return box

        # ------------------------------------------------------------------ rows
        def add_node_row(self, name="", spec=None):
            spec = spec or {}
            parent, row = self.nodes_box.scroll.inner, self.nodes_box.next_row
            self.nodes_box.next_row += 1
            meas = spec.get("measured") or ["", ""]
            values = {"name": name, "guess": fmt(spec.get("guess", "")), "meas": fmt(meas[0]) if meas else "",
                      "sigma": fmt(meas[1]) if len(meas) > 1 else "", "expected": fmt(spec.get("expected", "")),
                      "tol": fmt(spec.get("tolerance", ""))}
            widgets = {"frame": row, "unit": spec.get("unit", ""), "cells": []}
            for k, (key, _, width) in enumerate(NODE_COLUMNS):
                if key == "scale":
                    w = ttk.Combobox(parent, values=["log", "lin"], width=width - 1, state="readonly")
                    w.set(spec.get("scale", "log"))
                    w.bind("<<ComboboxSelected>>", lambda e: self.form_changed())
                elif key == "fixed":
                    var = tk.BooleanVar(value=bool(spec.get("fixed", False)))
                    w = ttk.Checkbutton(parent, variable=var, command=self.form_changed, style="Panel.TCheckbutton")
                    widgets["fixed_var"] = var
                else:
                    w = ttk.Entry(parent, width=width)
                    w.insert(0, values[key])
                    w.bind("<KeyRelease>", lambda e: self.form_changed())
                w.grid(row=row, column=k, padx=1, pady=1, sticky="w")
                widgets[key] = w
                widgets["cells"].append(w)
            b = ttk.Button(parent, text="✕", width=2, style="Small.TButton",
                           command=lambda: self._delete(self.node_rows, row))
            b.grid(row=row, column=len(NODE_COLUMNS), padx=2)
            widgets["cells"].append(b)
            self.node_rows.append(widgets)

        def add_relation_row(self, rel=None):
            rel = rel or {"type": "log", "sigma": 1e-9}
            parent, row = self.rels_box.scroll.inner, self.rels_box.next_row
            self.rels_box.next_row += 1
            kind = rel.get("type", "log")
            if kind == "fn":
                terms = rel.get("expr", "")
            else:
                terms = ", ".join(f"{k}:{fmt(float(v))}" for k, v in (rel.get("terms") or {}).items())
            pw = ", ".join(f"{k}:{fmt(float(v))}" for k, v in (rel.get("pow") or {}).items())
            values = {"name": rel.get("name", ""), "terms": terms, "pow": pw,
                      "rhs": fmt(rel.get("K", 0.0) if kind == "sum" else rel.get("rhs", 0.0)) if kind != "fn" else "",
                      "sigma": fmt(rel.get("sigma", 1e-9))}
            widgets = {"frame": row, "cells": []}
            for k, (key, _, width) in enumerate(REL_COLUMNS):
                if key == "type":
                    w = ttk.Combobox(parent, values=["log", "sum", "fn"], width=width - 1, state="readonly")
                    w.set(kind)
                    w.bind("<<ComboboxSelected>>", lambda e, r=widgets: (self._type_changed(r), self.form_changed()))
                else:
                    w = ttk.Entry(parent, width=width)
                    w.insert(0, values[key])
                    w.bind("<KeyRelease>", lambda e: self.form_changed())
                w.grid(row=row, column=k, padx=1, pady=1, sticky="w")
                widgets[key] = w
                widgets["cells"].append(w)
            b = ttk.Button(parent, text="✕", width=2, style="Small.TButton",
                           command=lambda: self._delete(self.rel_rows, row))
            b.grid(row=row, column=len(REL_COLUMNS), padx=2)
            widgets["cells"].append(b)
            self.rel_rows.append(widgets)
            self._type_changed(widgets)

        def _type_changed(self, r):
            kind = r["type"].get()
            r["pow"].configure(state="normal" if kind == "sum" else "disabled")
            r["rhs"].configure(state="disabled" if kind == "fn" else "normal")

        def _delete(self, rows, row):
            for r in [r for r in rows if r["frame"] == row]:
                for w in r["cells"]:
                    w.destroy()
            rows[:] = [r for r in rows if r["frame"] != row]
            self.form_changed()

        def _clear_rows(self):
            for r in self.node_rows + self.rel_rows:
                for w in r["cells"]:
                    w.destroy()
            self.node_rows.clear()
            self.rel_rows.clear()
            self.nodes_box.next_row = self.rels_box.next_row = 1

        # ------------------------------------------------------------------ forms <-> JSON
        @staticmethod
        def _parse_pairs(text):
            out = {}
            for part in text.split(","):
                if ":" in part:
                    k, v = part.split(":", 1)
                    v = v.strip()
                    try:
                        out[k.strip()] = float(v)
                    except ValueError:
                        out[k.strip()] = v
            return out

        @staticmethod
        def _maybe_number(text):
            text = text.strip()
            if text == "":
                return None
            try:
                return float(text)
            except ValueError:
                return text

        def document_from_forms(self):
            doc = dict(self.meta)
            doc["nodes"], doc["relations"] = {}, []
            for r in self.node_rows:
                name = r["name"].get().strip()
                if not name:
                    continue
                spec = {"guess": self._maybe_number(r["guess"].get()), "scale": r["scale"].get() or "log"}
                if spec["guess"] is None:
                    del spec["guess"]
                m, s = self._maybe_number(r["meas"].get()), self._maybe_number(r["sigma"].get())
                if m is not None:
                    spec["measured"] = [m, s if s is not None else 1e-4]
                e = self._maybe_number(r["expected"].get())
                if e is not None:
                    spec["expected"] = e
                t = self._maybe_number(r["tol"].get())
                if t is not None:
                    spec["tolerance"] = t
                if r["fixed_var"].get():
                    spec["fixed"] = True
                if r.get("unit"):
                    spec["unit"] = r["unit"]
                doc["nodes"][name] = spec
            for r in self.rel_rows:
                kind = r["type"].get() or "log"
                rel = {"name": r["name"].get().strip(), "type": kind}
                if kind == "fn":
                    rel["expr"] = r["terms"].get().strip()
                else:
                    rel["terms"] = self._parse_pairs(r["terms"].get())
                    rhs = self._maybe_number(r["rhs"].get())
                    if kind == "sum":
                        pw = self._parse_pairs(r["pow"].get())
                        if pw:
                            rel["pow"] = pw
                        rel["K"] = 0.0 if rhs is None else rhs
                    else:
                        rel["rhs"] = 0.0 if rhs is None else rhs
                sg = self._maybe_number(r["sigma"].get())
                rel["sigma"] = 1e-3 if sg is None else sg
                doc["relations"].append(rel)
            return doc

        def forms_from_document(self, doc):
            self._syncing = True
            try:
                self._clear_rows()
                self.meta = {k: v for k, v in doc.items() if k not in ("nodes", "relations")}
                for name, spec in doc.get("nodes", {}).items():
                    self.add_node_row(name, spec)
                for rel in doc.get("relations", []):
                    self.add_relation_row(rel)
                self._show_meta()
            finally:
                self._syncing = False

        def _write_json(self, doc):
            text = json.dumps(doc, indent=2, ensure_ascii=False)
            if self.json_text.get("1.0", "end").strip() != text:
                pos = self.json_text.index("insert")
                self.json_text.delete("1.0", "end")
                self.json_text.insert("1.0", text)
                self.json_text.mark_set("insert", pos)
            self.json_status.configure(text="● In sync", foreground=COLORS["ok"])

        def form_changed(self):
            if self._syncing:
                return
            self._syncing = True
            try:
                self._write_json(self.document_from_forms())
            finally:
                self._syncing = False
            self._schedule_solve()

        def _schedule_json(self):
            if self._json_job:
                self.root.after_cancel(self._json_job)
            self._json_job = self.root.after(350, self._json_changed)

        def _json_changed(self):
            self._json_job = None
            text = self.json_text.get("1.0", "end").strip()
            if not text:
                return
            try:
                doc = normalize(json.loads(text))
            except (json.JSONDecodeError, AttributeError, TypeError) as err:
                msg = err.msg if isinstance(err, json.JSONDecodeError) else "not a network"
                where = f" line {err.lineno}" if isinstance(err, json.JSONDecodeError) else ""
                self.json_status.configure(text=f"⚠ JSON not valid yet ({msg}{where})", foreground=COLORS["warn"])
                return
            self.json_status.configure(text="● In sync", foreground=COLORS["ok"])
            self.forms_from_document(doc)
            self._schedule_solve()

        # ------------------------------------------------------------------ presets and files
        def _show_meta(self):
            cat = self.meta.get("category")
            if cat == "open":
                self.badge.configure(text="OPEN PROBLEM", background=COLORS["open"])
            elif cat == "known":
                self.badge.configure(text="KNOWN ANSWER", background=COLORS["ok"])
            else:
                self.badge.configure(text="CUSTOM", background=COLORS["muted"])
            text = self.meta.get("title", "Custom network")
            if self.meta.get("description"):
                text += "  —  " + self.meta["description"]
            if self.meta.get("sources"):
                text += "\nSources: " + " · ".join(self.meta["sources"])
            self.description.configure(text=text)

        def load_preset(self, preset):
            doc = preset_document(preset)
            self.preset_box.current(PRESETS.index(preset))
            self.forms_from_document(doc)
            self._syncing = True
            try:
                self._write_json(doc)
            finally:
                self._syncing = False
            self.solve()

        def new_network(self):
            doc = {"title": "Custom network", "nodes": {"x": {"guess": 1.0, "measured": [2.0, 1e-4]},
                                                        "y": {"guess": 1.0, "expected": 4.0}},
                   "relations": [{"name": "y = x^2", "type": "log", "terms": {"y": 1, "x": -2}, "rhs": 0.0, "sigma": 1e-9}]}
            self.preset_var.set("")
            self.forms_from_document(normalize(doc))
            self._syncing = True
            try:
                self._write_json(normalize(doc))
            finally:
                self._syncing = False
            self.solve()

        def import_json(self):
            path = filedialog.askopenfilename(filetypes=[("GRM network", "*.json"), ("All files", "*.*")])
            if not path:
                return
            try:
                with open(path, encoding="utf-8") as f:
                    doc = normalize(json.load(f))
            except (OSError, ValueError, AttributeError) as err:
                messagebox.showerror("Open", f"Could not read {path}:\n{err}")
                return
            self.preset_var.set("")
            self.forms_from_document(doc)
            self._syncing = True
            try:
                self._write_json(doc)
            finally:
                self._syncing = False
            self.solve()

        def export_json(self):
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("GRM network", "*.json")],
                                                initialfile="network.json")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.document_from_forms(), f, indent=2, ensure_ascii=False)
                self.status.configure(text=f"Saved {path}")

        # ------------------------------------------------------------------ solve and show
        def _schedule_solve(self):
            if not self.live.get():
                return
            if self._solve_job:
                self.root.after_cancel(self._solve_job)
            self._solve_job = self.root.after(400, self.solve)

        def solve(self, leave_one_out=False):
            self._solve_job = None
            doc = self.document_from_forms()
            try:
                report = solve_document(doc, leave_one_out=leave_one_out)
            except Exception as err:          # the message goes to the banner: the user is typing
                self.last_report = None
                self._show_error(str(err))
                return
            self.last_report = report
            self._show(report, doc)

        def _show_error(self, message):
            self.verdict.configure(text="⚠  Cannot solve", background="#fff8c5", foreground=COLORS["warn"])
            self.verdict_detail.configure(text=message, background="#fff8c5")
            for t in (self.tree, self.pulls):
                t.delete(*t.get_children())
            self._draw()

        def _show(self, report, doc):
            res = report["result"]
            checks = {c["node"]: c for c in report["checks"]}
            undetermined = set(res.get("undetermined", []))
            # banner
            if report["valid"] is True:
                head, bg, fg = f"✓  VALID — {len(checks)} expected value(s) reproduced", "#dafbe1", COLORS["ok"]
            elif report["valid"] is False:
                bad = sum(1 for c in checks.values() if not c["ok"])
                head, bg, fg = f"✗  NOT VALID — {bad} of {len(checks)} expected value(s) missed", "#ffebe9", COLORS["bad"]
            elif not report["consistent"]:
                head, bg, fg = "⚠  TENSION — the data disagree (no expected value to check)", "#fff1e5", COLORS["warn"]
            else:
                head, bg, fg = "Solved — consistent (no expected value to check)", "#eaeef2", COLORS["ink"]
            lines = []
            dof, chi2 = res["dof"], res["cost"]
            if dof and dof > 0:
                state = "consistent" if report["consistent"] else "TENSION: the data and relations disagree"
                lines.append(f"χ² = {chi2:.3g} for {dof} degree(s) of freedom (χ²/dof = {chi2 / dof:.3g}): {state}.")
            else:
                lines.append("No redundancy (dof = 0): every measurement is used to fix a node, nothing is checked twice.")
            if report["pulls"]:
                what, p = report["pulls"][0]
                lines.append(f"Largest pull: {what} at {p:+.2f} σ.")
            if not res["converged"]:
                lines.append("The solver did not converge: change the guesses or loosen a relation.")
            if undetermined:
                lines.append("Not determined by the network (value = guess): " + ", ".join(sorted(undetermined)) + ".")
            if self.meta.get("category") == "open":
                lines.append("Open problem: a result here measures a tension or the size of a hypothesis; it is not a solution.")
            if "loo" in report:
                parts = [f"{k}: predicted {fmt(v['predicted'])} vs measured {fmt(v['measured'])} ({v['pull']:+.2f} σ)"
                         for k, v in report["loo"].items() if v["determined"]]
                lines.append("Leave one out — " + ("; ".join(parts) if parts else "no measurement can be predicted from the others."))
            self.verdict.configure(text=head, background=bg, foreground=fg)
            self.verdict_detail.configure(text="\n".join(lines), background=bg)
            # values
            self.tree.delete(*self.tree.get_children())
            nodes = normalize(doc)["nodes"]
            for name, v in res["values"].items():
                lin = nodes.get(name, {}).get("scale") == "lin"
                unc = res["uncertainty"][name]
                unit = nodes.get(name, {}).get("unit", "")
                unc_text = (fmt(unc) if lin else (f"{unc * 100:.2g} %" if unc >= 1e-4 else f"{unc:.1e}"))
                c = checks.get(name)
                tag, check = (), ""
                if c:
                    tag = ("ok",) if c["ok"] else ("bad",)
                    check = ("✓ " if c["ok"] else "✗ ") + f"{c['deviation']:.1e}"
                elif name in undetermined:
                    tag, check = ("undetermined",), "undetermined"
                self.tree.insert("", "end", values=(name, fmt(v), unit, unc_text, check,
                                                    fmt(c["expected"]) if c else ""), tags=tag)
            self.pulls.delete(*self.pulls.get_children())
            for what, p in report["pulls"]:
                tag = ("bad",) if abs(p) >= 3 else ("warn",) if abs(p) >= 2 else ()
                self.pulls.insert("", "end", values=(what, f"{p:+.2f}"), tags=tag)
            self.status.configure(text=f"{len(res['values'])} nodes, {len(doc['relations'])} relations, "
                                       f"{len(report['measured'])} measurements · {res['iterations']} iteration(s)")
            self._draw()

        # ------------------------------------------------------------------ the network as a picture
        def _draw(self):
            c = self.canvas
            c.delete("all")
            w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 160)
            doc = self.document_from_forms() if (self.node_rows or self.rel_rows) else {"nodes": {}, "relations": []}
            names = list(doc["nodes"])
            if not names:
                return
            report = self.last_report
            checks = {k["node"]: k for k in report["checks"]} if report else {}
            undetermined = set(report["result"].get("undetermined", [])) if report else set()
            pulls = report["result"]["relation_pulls"] if report else {}
            cx, cy = w / 2, h / 2
            rn = min(cx - 60, cy - 30)
            pos = {n: (cx + rn * math.cos(2 * math.pi * k / len(names) - math.pi / 2),
                       cy + rn * math.sin(2 * math.pi * k / len(names) - math.pi / 2)) for k, n in enumerate(names)}
            rels = doc["relations"]
            # relations as small squares between their nodes (a factor graph)
            for k, rel in enumerate(rels):
                if rel.get("type") == "fn":
                    try:
                        _, members = compile_expression(rel.get("expr", ""), set(names))
                    except (ValueError, SyntaxError):
                        members = []
                else:
                    members = [n for n in (rel.get("terms") or {}) if n in pos]
                if not members:
                    continue
                mx = sum(pos[n][0] for n in members) / len(members)
                my = sum(pos[n][1] for n in members) / len(members)
                if len(members) == 1:
                    mx, my = cx + (pos[members[0]][0] - cx) * 0.55, cy + (pos[members[0]][1] - cy) * 0.55
                mx, my = mx + 6 * math.cos(k), my + 6 * math.sin(k)
                p = abs(pulls.get(rel.get("name") or f"relation {k + 1}", 0.0))
                col = COLORS["bad"] if p >= 3 else COLORS["warn"] if p >= 2 else COLORS["edge"]
                for n in members:
                    c.create_line(mx, my, *pos[n], fill=col, width=2 if p >= 2 else 1)
                c.create_rectangle(mx - 6, my - 6, mx + 6, my + 6, fill=col, outline="")
                label = rel.get("name", "")
                c.create_text(mx, my - 12, text=label if len(label) <= 22 else label[:21] + "…", fill=COLORS["muted"],
                              font=("Segoe UI", 8))
            for n, (x, y) in pos.items():
                spec = doc["nodes"][n]
                fill = "#ffffff"
                if n in checks:
                    fill = "#dafbe1" if checks[n]["ok"] else "#ffebe9"
                elif n in undetermined:
                    fill = "#fff8c5"
                outline = COLORS["accent"] if spec.get("measured") else COLORS["ink"]
                r = max(20, 4 * len(n) + 6)
                c.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=outline, width=3 if spec.get("measured") else 1)
                c.create_text(x, y, text=n, fill=COLORS["ink"], font=("Segoe UI", 9, "bold"))
            c.create_text(8, h - 8, anchor="sw", fill=COLORS["muted"], font=("Segoe UI", 8),
                          text="blue ring: measured · green / red: check passes / fails · yellow: undetermined · "
                               "orange / red link: relation pulled beyond 2 / 3 σ")


def main():
    if tk is None:
        raise SystemExit("tkinter is not available in this Python")
    root = tk.Tk()
    GRMExplorer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
