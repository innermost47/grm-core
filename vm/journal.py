# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The machine's logbook: what it lived, day after day, in words a human likes to read. Not a log of everything: the
moments that count. It wakes, it is given a program or a file, it finds a law by itself, it is surprised, it sleeps
and keeps or forgets.

Each entry is kept with its memory (net.journal) as what happened and its numbers. It is said in the language of the
machine when it is read, so a logbook written in English reads in French the next day.

    write(net, kind, **what)     an entry
    days(net)                    [(date, [entry])], the most recent day last
    say(entry)                   (icon, a sentence, more lines)
"""
import time

from i18n import tr

KEEP = 3000          # entries kept
ICONS = {"born": "☀", "woke": "☀", "program": "◆", "file": "⇣", "discovery": "✦", "found": "✧", "surprise": "≈",
         "night": "☾", "kept": "⧉"}


def write(net, kind, **what):
    """An entry, now."""
    j = net.__dict__.setdefault("journal", [])
    j.append({"kind": kind, "when": time.time(), "tick": getattr(net, "ticks", 0), **what})
    del j[:-KEEP]
    return j[-1]


def entries(net):
    return list(getattr(net, "journal", None) or [])


def day_of(entry):
    return time.strftime("%Y-%m-%d", time.localtime(entry["when"]))


def days(net, find=None):
    """[(date, [entry])]: the entries by day, oldest first; find: only those whose words hold it."""
    out = []
    for e in entries(net):
        if find:
            icon, sentence, more = say(e)
            if find.lower() not in (sentence + " " + " ".join(more)).lower():
                continue
        d = day_of(e)
        if not out or out[-1][0] != d:
            out.append((d, []))
        out[-1][1].append(e)
    return out


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")


def pretty(day):
    """2026-11-12 as a human writes it: Thursday 12 November 2026 (jeudi 12 novembre 2026)."""
    t = time.strptime(day, "%Y-%m-%d")
    return tr("{weekday} {day} {month} {year}", weekday=tr(WEEKDAYS[t.tm_wday]), day=t.tm_mday,
              month=tr(MONTHS[t.tm_mon - 1]), year=t.tm_year)


def hour(entry):
    return time.strftime("%H:%M", time.localtime(entry["when"]))


def say(e):
    """(icon, a sentence, more lines) of an entry, in the language of the machine."""
    k = e["kind"]
    icon = ICONS.get(k, "·")
    if k == "born":
        return icon, (tr("born with its base: {n} points of the world", n=e.get("nodes", 0)) if e.get("nodes")
                      else tr("born blank")), []
    if k == "woke":
        return icon, tr("woke up; it remembers {nodes} nodes and {relations} relations", nodes=e.get("nodes", 0),
                        relations=e.get("relations", 0)), []
    if k == "program":
        return icon, tr("read the program {name}: {nodes} node(s), {relations} relation(s)", name=e.get("name", "?"),
                        nodes=e.get("nodes", 0), relations=e.get("relations", 0)), []
    if k == "file":
        cols = e.get("columns") or []
        return icon, tr("learned from {name}: {rows} rows", name=e.get("name", "?"), rows=e.get("rows", 0)), (
            [", ".join(cols[:10]) + (" ..." if len(cols) > 10 else "")] if cols else [])
    if k == "discovery":
        more = [e.get("sentence") or ""]
        if e.get("r2") is not None:
            more.append(f"r² {e['r2']:.4f} · {e.get('rows', '?')} " + tr("rows"))
        return icon, tr("found by itself: {text}", text=e.get("text", "")), [m for m in more if m]
    if k == "surprise":
        where = ", ".join(f"{n} ({v:.2g}σ)" for n, v in e.get("where", []))
        return icon, tr("it did not expect that: {s} sigma from what it thought", s=f"{e.get('sigma', 0):.2g}"), (
            [where] if where else [])
    if k == "night":
        more = list(e.get("done") or [])
        return icon, tr("a night: {d} found, {f} files, {s} surprises today; flourishing {fl}",
                        d=e.get("discoveries", 0), f=e.get("files", 0), s=e.get("surprises", 0),
                        fl=f"{e.get('flourishing', 1.0):.2f}"), more
    if k == "kept":
        return icon, tr("kept from the sandbox: {what}", what=", ".join(e.get("names", []))), []
    return icon, e.get("text", ""), []


def today(net):
    """The entries since it last woke (for the night's summary)."""
    out = []
    for e in reversed(entries(net)):
        if e["kind"] in ("woke", "born", "night"):
            break
        out.append(e)
    return list(reversed(out))
