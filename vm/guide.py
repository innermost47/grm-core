# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Help for a new way of programming: the list of words, one word explained, and a guided tour.

The texts are English templates; i18n.tr gives them in the language of the machine.
"""
from editor import DOCS, LONG
from i18n import label, tr

GROUPS = [
    ("the network", ["node", "relate", "observe", "forget", "keep", "var", "set", "learn", "input", "output", "fuse",
                     "network", "call", "end", "use"]),
    ("running", ["tick", "put", "run", "load", "clock"]),
    ("seeing it work", ["play", "pause", "step", "watch", "unwatch", "why"]),
    ("looking", ["ask", "outputs", "show", "inspect", "master", "check"]),
    ("inside", ["mood", "capacity", "prune"]),
    ("programs", ["programs", "read", "open", "tab", "close", "new", "edit", "save", "find"]),
    ("memory", ["sleep", "wake", "blank", "quit"]),
    ("help", ["help", "tour", "lang", "sound"]),
]


def overview():
    """Every word of the machine, by group, with its short form and a few words."""
    lines = [tr("  The GRM machine is programmed with relations, not steps: a program is a network. Enter alone: "
                "one tick."), tr("  help WORD: one word, with an example.  tour: a guided tour.  +/- can be "
                                 "written for ±.")]
    for group, words in GROUPS:
        lines.append("")
        lines.append(f"  {tr(group)}")
        for w in words:
            short = f" ({LONG[w]})" if w in LONG else ""
            lines.append(f"    {(w + short):<20} {tr(DOCS[w][1])}")
    return lines


def word(w):
    """One word: its form, what it is, an example, its short form."""
    form, what, example = DOCS[w]
    lines = [f"  {w}" + (f"   ({label('short')}{LONG[w]})" if w in LONG else "") + f" — {tr(what)}",
             f"    {form}",
             f"    {label('for example')} {example}"]
    more = MORE.get(w)
    if more:
        lines.append(f"    {tr(more)}")
    return lines


# what is worth saying of a word beyond its few words
MORE = {
    "relate": "A relation holds both ways: give any of its nodes and the others are found. Products, powers and sums; "
              "+/- says how exact it is (none: exact).",
    "observe": "A measured node: the network moves the others to fit it. +/- 1% for a positive quantity, +/- 0.1 in "
               "its own unit for a signed one.",
    "set": "Written at the next tick, from the values before the tick: all the writes of a tick at once (loops, "
           "counters, choices with `when`).",
    "learn": "A weight: it keeps what each row of data taught it (load), and remembers it at the next session.",
    "input": "Given from outside at each moment (put, load). Its surprise is what the network did not expect.",
    "network": "The lines up to `end` are a network that can be called, as a function: {p} in them is replaced by "
               "what the call gives.",
    "tick": "A tick: the writes (set), then the network settles (every relation answers what is new, round after "
            "round).",
    "open": "Opens a program in the programs window, a tab per program. tab N to go to one, edit to write in it, "
            "Ctrl+F to search, F5 to run it.",
    "edit": "The tab can be written; Ctrl+S saves, F5 runs it (an error turns its line red), Esc comes back here.",
    "step": "A tick is a few rounds: in each, the nodes that heard something new tell their relations, and the "
            "relations that heard something new answer. step shows that conversation, round after round: who worked, "
            "who moved, and the writes at the end of the tick.",
    "watch": "A breakpoint. NODE in LO .. HIGH stops when the condition becomes true, NODE when its value changes, "
             "RELATION when it no longer holds. The clock pauses, and tick n stops there.",
    "why": "A node's value is what all its relations say of it, each weighted by how sure it is (the precisions add "
           "up). why shows each message, its share, and what that relation heard from its other nodes.",
    "master": "pygrm's master invariant: the equation the network holds or implies that ties the widest span of "
              "scales.",
    "help": "help on / off: the menu of words while typing (the line of help under the prompt stays).",
}

TOUR = [
    ("A network, not steps",
     "In the GRM machine you write relations between quantities; the network finds what is missing, in every "
     "direction. Type:",
     "relate fall: 2 * height = g * t^2"),
    ("Measurements",
     "Give it what is known (obs is short for observe, +/- for ±). Type:",
     "obs g = 9.81 +/- 0.1% ; obs t = 2"),
    ("Ask",
     "The network has settled: ask what you did not give. Type:",
     "ask height"),
    ("The other way",
     "A relation holds both ways. Give the height, forget the time, ask it:",
     "obs height = 30 ; fgt t ; ask t"),
    ("Look at it",
     "In the middle of the window, the network: a round per node, a square per relation. Put the mouse on the square "
     "`fall`, or type:",
     "inspect fall"),
    ("Time",
     "A variable is held until written again; set writes it at each tick. Enter alone is a tick. Type, then press "
     "Enter a few times:",
     "var n = 0 ; set n = n + 1 ; out n"),
    ("Learning",
     "A weight (learn) keeps what it learns from the inputs. Type:",
     "inp x ; inp y ; lrn k = 1 ; rel model: y = k * x +/- 0.1 ; put x = 2 ; put y = 6 ; tick ; ask k"),
    ("Programs",
     "Programs are files of statements. List them, open one in a tab (tab N to change), run it (F5 in its tab):",
     "programs ; open fall"),
    ("Step by step",
     "A tick is a conversation in rounds. Set a breakpoint, run, and ask why a value is what it is (F8 play, F10 a "
     "tick, F11 a round in the window):",
     "watch n in 3 .. inf ; tick 10 ; step ; why height"),
    ("Inside",
     "What it feels (pleasure, flourishing), its master equation, what is wrong:",
     "mood ; master ; check"),
    ("Help",
     "help WORD for any word, help on / off for the menu while typing, lang fr / lang en. The tour is over: tour 1 "
     "to see it again.",
     "help relate"),
]


def tour_step(n):
    """The lines of step n (1 .. len(TOUR))."""
    title, text, typed = TOUR[n - 1]
    return [f"  {tr('tour')} {n}/{len(TOUR)} — {tr(title)}", f"    {tr(text)}", f"      {typed}",
            "    " + (tr("tour: the next step") if n < len(TOUR) else tr("tour end: the end of the tour"))]
