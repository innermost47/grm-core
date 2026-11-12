# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The programs of the GRM machine: where they are, what they say of themselves, a new one.

A program may begin with a header, lines starting with `#!` (a comment for the machine):

    #! name: fall
    #! does: a fall from rest: the height from g and t
    #! try: use programs/fall.grm ; ask height

`does` (or `about`) says what it does, `try` what to type to see it. The inputs, outputs and networks are read from
the program itself (input / output / network statements), not written in the header.
"""
import os
import re

from i18n import tr
from language import normal

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(HERE, "programs")


def find(name, base=HERE):
    """The file of a program: a path as given, or programs/NAME.grm, or NAME.grm. None if there is none."""
    name = name.strip().strip('"')
    if not name:
        return None
    candidates = [name, name + ".grm", os.path.join("programs", name + ".grm"),
                  os.path.join(base, name), os.path.join(base, name + ".grm"),
                  os.path.join(base, "programs", name), os.path.join(base, "programs", name + ".grm")]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None


def header(path):
    """{key: value} of a program's #! lines, with what is read from its statements: inputs, outputs, networks."""
    meta = {"name": os.path.splitext(os.path.basename(path))[0], "inputs": [], "outputs": [], "networks": []}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return meta
    inside = False                  # in a network: its inputs and outputs are those of its calls
    for line in lines:
        m = re.match(r"\s*#!\s*([A-Za-z_]+)\s*:\s*(.*)$", line)
        if m:
            key = m.group(1).lower()
            meta["does" if key == "about" else key] = m.group(2).strip()
            continue
        body = normal(line.split("#", 1)[0]).strip()
        word, _, rest = body.partition(" ")
        word = word.lower()
        if word == "end":
            inside = False
            continue
        if inside:
            continue
        if word in ("input", "output"):
            name = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", rest.strip())
            if name:
                meta[word + "s"].append(name.group(1))
        elif word == "network":
            name = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", rest.strip())
            if name:
                meta["networks"].append(name.group(1))
            inside = True
    if "does" not in meta:          # no header: the first comment says what it does
        for line in lines:
            m = re.match(r"\s*#(?!!)\s*(.+)$", line)
            if m:
                meta["does"] = m.group(1).strip()
                break
    return meta


def listing(folder=FOLDER):
    """[header] of every program of a folder, by name."""
    try:
        files = sorted(f for f in os.listdir(folder) if f.endswith(".grm"))
    except OSError:
        return []
    return [dict(header(os.path.join(folder, f)), file=os.path.join(folder, f)) for f in files]


def template(name):
    """A new program: its header, and a few lines to start from."""
    return tr("""#! name: {name}
#! does: (what it does, in a few words)
#! try: use programs/{name}.grm ; ask y
#
# A program is a network: write relations, not steps. Each line is a statement (help WORD for one).

input x = 2
relate model: y = 3 * x +/- 0.1
output y
""", name=name)
