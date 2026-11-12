# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Writing to the GRM machine: the colours of a line of GRML (tokens), what Tab completes, what each word is
(DOCS: its form, a few words, an example), the line of help under the prompt (hint), the menu of words (suggest),
and the banner.

Nothing here depends on the window: the window (body.py) and the terminal (grm_vm.py, readline) use the same
functions.
"""
import glob
import os
import re

from i18n import tr
from language import SHORT as SHORT_STATEMENTS

STATEMENTS = ("node", "relate", "observe", "forget", "keep", "network", "call", "use", "end", "var", "set",
              "learn", "input", "output", "fuse")

# the short forms of the commands (the statements' are in language.SHORT)
SHORT_COMMANDS = {
    "t": "tick", "ld": "load", "outs": "outputs", "ins": "inspect", "ms": "master", "chk": "check",
    "cap": "capacity", "clk": "clock", "h": "help", "q": "quit", "progs": "programs", "rd": "read", "o": "open",
    "ed": "edit", "sv": "save", "st": "step", "wt": "watch", "uw": "unwatch",
}
SHORT = dict(SHORT_STATEMENTS, **SHORT_COMMANDS)
LONG = {v: k for k, v in SHORT.items()}


def whole(word):
    """The whole word for a short one (obs -> observe), the word itself otherwise."""
    return SHORT.get(word.lower(), word.lower())


# what each word is: its form, a few words (the menu and the line under the prompt), an example (help WORD)
DOCS = {
    # statements: the network
    "node": ("node NAME [= value] [fixed] [signed] [M L T Q K]", "a quantity", "node mass = 2 [1 0 0 0 0]"),
    "relate": ("relate NAME: left = right [+/- sigma] [when ...]", "a relation: products, powers, sums",
               "relate fall: 2 * height = g * t^2"),
    "observe": ("observe NAME = value [+/- 1% | +/- 0.004 dex]", "a measurement", "observe g = 9.81 +/- 0.1%"),
    "forget": ("forget NAME", "drop a measurement", "forget g"),
    "keep": ("keep NAME: node >= bound [when ...]", "a contact: a bound held", "keep floor: height >= 0"),
    "network": ("network NAME(p1, p2) ... end", "a network to call (a function)", "network circle(id, radius)"),
    "call": ("call NAME(p1=.., p2=..)", "put a network in, with its values", "call circle(id=small, radius=1)"),
    "use": ("use FILE.grm", "every statement of a file", "use programs/fall.grm"),
    "end": ("end", "the end of a network", "end"),
    "var": ("var NAME [= value]", "a variable, held until written again", "var n = 0"),
    "set": ("set NAME = expression [when ...]", "written at each tick: loops, choices", "set n = n + 1"),
    "learn": ("learn NAME [= value]", "a weight: it keeps what it learns", "learn k = 1"),
    "input": ("input NAME [= value]", "an input, given at each moment", "input x"),
    "output": ("output NAME", "an output: shown, drawn, heard", "output height"),
    "fuse": ("fuse A B [inverse]", "B was A under another name", "fuse period T inverse"),
    # commands: running
    "tick": ("tick [n]", "n ticks (Enter alone, F10: one)", "tick 10"),
    "put": ("put NAME = value [+/- sigma]", "give an input its value", "put x = 3"),
    "run": ("run [FILE.grm]", "a file (no file: the open tab)", "run programs/fall.grm"),
    "load": ("load FILE.csv | FILE.json", "data row by row: it learns", "load programs/falling.csv"),
    "clock": ("clock HZ", "ticks by themselves (0: stop)", "clock 10"),
    # seeing it work
    "play": ("play [HZ]", "the clock runs (F8: play / pause)", "play 5"),
    "pause": ("pause", "the clock stops", "pause"),
    "step": ("step [n]", "n rounds, one at a time (F11)", "step 3"),
    "watch": ("watch NODE in LO .. HIGH | NODE | RELATION", "stop when it is met", "watch n in 5 .. inf"),
    "unwatch": ("unwatch [N | all]", "take a watch away", "unwatch 1"),
    "why": ("why NODE", "what makes its value", "why height"),
    # looking
    "ask": ("ask NODE", "a node's value", "ask height"),
    "outputs": ("outputs", "the outputs and the surprise", "outputs"),
    "show": ("show", "what the network is", "show"),
    "inspect": ("inspect NAME", "what a node or a relation holds", "inspect fall"),
    "master": ("master [n]", "the master equation, now or n ticks ago", "master 5"),
    "check": ("check", "everything wrong now", "check"),
    # inside
    "mood": ("mood", "pleasure, flourishing, room", "mood"),
    "capacity": ("capacity [N | auto]", "the links it may hold", "capacity auto"),
    "prune": ("prune", "forget now what a night would", "prune"),
    # memory
    "sleep": ("sleep [FILE.json]", "to its memory", "sleep"),
    "wake": ("wake [FILE.json]", "back from its memory", "wake"),
    "blank": ("blank", "forget everything", "blank"),
    # programs
    "programs": ("programs", "the programs and what they do", "programs"),
    "read": ("read PROGRAM", "a program, in the answers", "read fall"),
    "open": ("open PROGRAM", "a program in a tab", "open fall"),
    "tab": ("tab N | NAME", "go to a tab", "tab 2"),
    "close": ("close [N | NAME]", "close a tab", "close"),
    "new": ("new NAME", "a new program, in a tab", "new orbit"),
    "edit": ("edit [PROGRAM]", "write in a tab (Esc: back here)", "edit fall"),
    "save": ("save [FILE.grm]", "save the tab (Ctrl+S)", "save"),
    "find": ("find WORDS", "search the tab (Ctrl+F)", "find height"),
    # the body, help
    "sound": ("sound on | off", "hear the outputs", "sound on"),
    "lang": ("lang fr | en", "the language of the machine", "lang fr"),
    "help": ("help [WORD | on | off]", "help on a word; the typing help on or off", "help relate"),
    "tour": ("tour [N | end]", "a guided tour, a step at a time", "tour"),
    "quit": ("quit", "to sleep, and goodbye", "quit"),
}
LITTLE = ("when", "in", "and", "fixed", "signed", "positive", "inverse", "dex", "ln")
CONSTANTS = ("pi", "e", "tau", "inf")

TOKEN = re.compile(r"""
    (?P<comment>\#.*$)
  | (?P<number>(?<![A-Za-z0-9_~])[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?%?)
  | (?P<name>[A-Za-z_~][A-Za-z0-9_]*)
  | (?P<range>\.\.)
  | (?P<sigma>±|\+/-)
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
            low = whole(text)
            if first and low in STATEMENTS:
                kind = "statement"
            elif first and (low in commands or text.lower() in commands):
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
        head = whole(words[0])
        if head in ("use", "run", "load", "open", "read", "edit"):
            if head in ("open", "read", "edit") and "/" not in word:
                return start, sorted({n for n in program_names(base) if n.startswith(word) and n != word})
            return start, files(word, base, (".grm",) if head != "load" else (".csv", ".json"))
        if head == "call":
            pool = sorted(networks)
        elif head in ("help",):
            pool = sorted(DOCS)
        elif head in ("lang",):
            pool = ["en", "fr"]
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


def program_names(base):
    """The names of the programs in programs/ (fall for programs/fall.grm)."""
    folder = os.path.join(base, "programs")
    try:
        return sorted(f[:-4] for f in os.listdir(folder) if f.endswith(".grm"))
    except OSError:
        return []


def describe(word):
    """A few words on what a word is, in the language of the machine ('' when it is not a word of the machine)."""
    w = whole(word)
    if w not in DOCS:
        return ""
    return tr(DOCS[w][1])


def hint(line, cursor, nodes=None, relations=(), commands=()):
    """The line of help under the prompt: what is being typed, in a few words."""
    left = line[:cursor].split(";")[-1]
    words = left.split()
    if not words:
        return tr("type a statement or a command (Tab completes; help; tour: a guided tour)")
    head = words[0]
    w = whole(head)
    typing_head = len(words) == 1 and not left.endswith(" ")
    if w in DOCS:
        form, what, _ = DOCS[w]
        if head.lower() != w:
            name = f"{head.lower()} = {w}"                 # a short form: what it stands for
        else:
            name = w + (f" ({LONG[w]})" if w in LONG else "")
        return f"{name} — {tr(what)}   {form}"
    if typing_head:
        found = [d for d in sorted(set(DOCS) | set(SHORT)) if d.startswith(head.lower())]
        if found:
            return tr("{n} word(s): {words}", n=len(found), words=", ".join(found[:8]) + (" ..." if len(found) > 8
                                                                                          else ""))
        return tr("'{word}' is not a word of the machine (help: the list)", word=head)
    return ""


def suggest(line, cursor, nodes=(), relations=(), commands=(), networks=(), base=".", max_names=12):
    """The menu under the prompt: [(word, a few words)]. Words of the machine from the first letter; names of nodes
    and relations from the second letter, and only when there are at most max_names of them (not to crowd the
    screen)."""
    start, found = complete(line, cursor, nodes=nodes, relations=relations, commands=commands, networks=networks,
                            base=base)
    word = line[start:cursor]
    left = line[:start].split(";")[-1]
    if not left.split():                                  # the first word: statements, commands and short forms
        if not word:
            return []
        shorts = [s for s in SHORT if s.startswith(word.lower()) and s != word.lower()]
        out = [(w, describe(w)) for w in found if whole(w) in DOCS or w in DOCS]
        out += [(s, f"= {SHORT[s]}") for s in shorts if s not in found]
        return out[:12]
    head = whole(left.split()[0])
    if head in ("help",):
        return [(w, describe(w)) for w in found][:12]
    if head in ("use", "run", "load", "open", "read", "edit", "lang", "call"):
        return [(w, "") for w in found][:12]
    if len(word) < 2 or len(found) > max_names:
        return []
    names = set(nodes)
    return [(w, tr("node") if w in names else tr("relation") if w in set(relations) else "") for w in found]


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
