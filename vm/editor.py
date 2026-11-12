# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Writing to the GRM machine: the colours of a line of GRML (tokens), what Tab completes, and the banner.

Nothing here depends on the window: the window (body.py) and the terminal (grm_vm.py, readline) use the same
functions.
"""
import glob
import os
import re

STATEMENTS = ("node", "relate", "observe", "forget", "keep", "network", "call", "use", "end", "var", "set",
              "learn", "input", "output", "fuse")
LITTLE = ("when", "in", "and", "fixed", "signed", "positive", "inverse", "dex", "ln")
CONSTANTS = ("pi", "e", "tau", "inf")

TOKEN = re.compile(r"""
    (?P<comment>\#.*$)
  | (?P<number>(?<![A-Za-z0-9_~])[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?%?)
  | (?P<name>[A-Za-z_~][A-Za-z0-9_]*)
  | (?P<range>\.\.)
  | (?P<sigma>±)
  | (?P<dim>\[[^\]]*\])
  | (?P<op>[=*/^+\-:(),<>;{}])
""", re.VERBOSE)


def tokens(line, nodes=(), relations=(), commands=()):
    """[(start, end, kind)] for a line typed to the machine. kinds: statement, command, keyword, constant, node,
    relation, new (a name the network does not know yet), number, sigma, range, dim, op, comment."""
    nodes, relations, commands = set(nodes), set(relations), set(commands)
    out = []
    first = True
    for m in TOKEN.finditer(line):
        kind = m.lastgroup
        text = m.group(0)
        if kind == "name":
            low = text.lower()
            if first and low in STATEMENTS:
                kind = "statement"
            elif first and low in commands:
                kind = "command"
            elif text in LITTLE:
                kind = "keyword"
            elif text in CONSTANTS:
                kind = "constant"
            elif text in nodes:
                kind = "node"
            elif text in relations:
                kind = "relation"
            else:
                kind = "new"
        if kind == "op" and text == ";":
            first = True
            out.append((m.start(), m.end(), kind))
            continue
        out.append((m.start(), m.end(), kind))
        if kind != "comment":
            first = False
    return out


COLOURS = {   # dark background
    "statement": "#c792ea", "command": "#82aaff", "keyword": "#89ddff", "constant": "#f78c6c",
    "node": "#c3e88d", "relation": "#ffcb6b", "new": "#e6e8ec", "number": "#f78c6c", "sigma": "#89ddff",
    "range": "#89ddff", "dim": "#7fdbca", "op": "#7d838d", "comment": "#5c6370",
}


def complete(line, cursor, nodes=(), relations=(), commands=(), networks=(), base="."):
    """What Tab can put at the cursor. Returns (start, candidates): the word from `start` to the cursor is replaced
    by a candidate. First word: statements and commands; after use / run / load: files; after call: networks;
    elsewhere: nodes, relations, keywords."""
    left = line[:cursor]
    m = re.search(r"[A-Za-z0-9_~./\\-]*$", left)
    start = m.start()
    word = left[start:]
    before = left[:start]
    part = before.split(";")[-1]
    words = part.split()
    if not words:
        pool = sorted(set(STATEMENTS) | set(commands))
    else:
        head = words[0].lower()
        if head in ("use", "run", "load"):
            return start, files(word, base, (".grm",) if head != "load" else (".csv", ".json"))
        if head == "call":
            pool = sorted(networks)
        elif head in ("ask", "inspect", "forget"):
            pool = sorted(nodes)
        else:
            pool = sorted(set(nodes) | set(relations)) + [w for w in LITTLE + CONSTANTS]
    return start, [w for w in pool if w.startswith(word) and w != word] or ([word] if word in pool else [])


def files(prefix, base, endings):
    found = set()
    for root in (".", base):
        pattern = os.path.join(root, prefix + "*")
        for path in glob.glob(pattern):
            rel = os.path.relpath(path, root)
            if os.path.isdir(path):
                found.add(rel + "/")
            elif path.lower().endswith(endings):
                found.add(rel.replace(os.sep, "/"))
    return sorted(found)


def common(words):
    """The longest beginning all the candidates share."""
    if not words:
        return ""
    return os.path.commonprefix(words)


BANNER = r"""
     ██████╗ ██████╗ ███╗   ███╗      o───o
    ██╔════╝ ██╔══██╗████╗ ████║     / \ / \
    ██║  ███╗██████╔╝██╔████╔██║    o───o───o
    ██║   ██║██╔══██╗██║╚██╔╝██║     \ / \ /
    ╚██████╔╝██║  ██║██║ ╚═╝ ██║      o───o
     ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝
      the Global Relational Model machine
"""

BANNER_ASCII = r"""
      ____  ____   __  __        o---o
     / ___||  _ \ |  \/  |      / \ / \
    | |  _ | |_) || |\/| |     o---o---o
    | |_| ||  _ < | |  | |      \ / \ /
     \____||_| \_\|_|  |_|       o---o
      the Global Relational Model machine
"""


def banner(encoding="utf-8"):
    """The banner, in what the terminal can print."""
    try:
        BANNER.encode(encoding or "ascii")
        return BANNER
    except (UnicodeEncodeError, LookupError):
        return BANNER_ASCII
