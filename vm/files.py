# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The human's files, as a Unix shell has them: where it is (pwd, cd), what is there (ls), what a file says (head,
tail, cat), and the usual moves (mkdir, cp, mv, rm). The machine really moves into the folder (cd changes the working
directory of the process), so every relative path (use, load, run, open) starts from there; the machine's own
programs (vm/programs) are still found from anywhere.

Each function returns what is to be said, or raises FileError with the reason. Nothing is deleted without being asked
first: rm only says what it would delete (Shell asks, then calls remove).
"""
import glob
import os
import shutil
import stat
import time

from i18n import tr

HEAD = 10          # head and tail: lines shown by default
CAT = 2000         # cat: at most this many lines
KINDS = {".grm": "program", ".csv": "data", ".json": "data", ".tsv": "data"}


class FileError(Exception):
    pass


def where(path=None):
    """A path as a human reads it: the home folder is ~, separators as the system has them."""
    path = os.path.abspath(path or os.getcwd())
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        return "~" + os.sep + path[len(home) + 1:]
    return path


def short(path=None, room=32):
    """where(), cut to its last folders when it is long (for the prompt)."""
    w = where(path)
    if len(w) <= room:
        return w
    parts = w.split(os.sep)
    tail = parts[-1]
    if len(parts) > 2 and len(parts[-2]) + len(tail) + 5 <= room:
        tail = parts[-2] + os.sep + tail
    return "…" + os.sep + tail


def expand(arg):
    """~ and $VARIABLES made whole."""
    return os.path.expandvars(os.path.expanduser(arg))


def paths(args):
    """The paths named, wildcards (* ? [..]) opened."""
    out = []
    for a in args:
        a = expand(a)
        if any(ch in a for ch in "*?["):
            found = sorted(glob.glob(a))
            if not found:
                raise FileError(tr("nothing matches {pattern}", pattern=a))
            out += found
        else:
            out.append(a)
    return out


def split(arg):
    """Words and flags: ("-l -a dir" ->) ({"l", "a"}, ["dir"]). A quoted path keeps its spaces."""
    import shlex
    try:
        words = shlex.split(arg, posix=os.name != "nt")
    except ValueError:
        words = arg.split()
    words = [w[1:-1] if len(w) > 1 and w[0] == w[-1] and w[0] in "\"'" else w for w in words]
    flags, rest = set(), []
    for w in words:
        if w.startswith("-") and len(w) > 1 and not w[1].isdigit() and w != "-":
            flags |= set(w[1:])
        else:
            rest.append(w)
    return flags, rest


# ---------------------------------------------------------------------- where
_previous = [None]


def cd(arg):
    """cd [DIR | .. | ~ | -]: into a folder (alone: the home folder; -: the one before)."""
    target = arg.strip() or "~"
    if target == "-":
        if _previous[0] is None:
            raise FileError(tr("no folder before"))
        target = _previous[0]
    target = expand(target.strip("\"'"))
    if not os.path.isdir(target):
        raise FileError(tr("no folder {name}", name=target) if not os.path.exists(target) else
                        tr("{name} is a file, not a folder", name=target))
    before = os.getcwd()
    try:
        os.chdir(target)
    except OSError as e:
        raise FileError(str(e))
    _previous[0] = before
    return where()


# ---------------------------------------------------------------------- what is there
def kind(path):
    if os.path.isdir(path):
        return "folder"
    return KINDS.get(os.path.splitext(path)[1].lower(), "file")


def ls(arg, width=78):
    """ls [-l] [-a] [PATH...]: [(text, kind)] lines; kind: folder, program, data, file, or None (plain text)."""
    flags, names = split(arg)
    targets = paths(names) if names else ["."]
    lines = []
    for k, target in enumerate(targets):
        if not os.path.exists(target):
            raise FileError(tr("no file or folder {name}", name=target))
        if os.path.isdir(target):
            entries = sorted(os.listdir(target), key=str.lower)
            if "a" not in flags:
                entries = [e for e in entries if not e.startswith(".")]
            entries = [os.path.join(target, e) for e in entries]
            if len(targets) > 1:
                lines.append([(("" if k == 0 else "\n") + target + ":", None)])
        else:
            entries = [target]
        if not entries:
            continue
        if "l" in flags:
            for e in entries:
                lines.append(_long(e))
        else:
            lines += _columns(entries, width)
    return lines


def _label(path):
    name = os.path.basename(path.rstrip(os.sep)) or path
    return name + (os.sep if os.path.isdir(path) else "")


def _columns(entries, width):
    labels = [(_label(e), kind(e)) for e in entries]
    w = max(len(t) for t, _ in labels) + 2
    per = max(1, width // w)
    rows = (len(labels) + per - 1) // per
    out = []
    for r in range(rows):
        row = []
        for c in range(per):
            i = c * rows + r
            if i < len(labels):
                t, kd = labels[i]
                row.append((t.ljust(w) if c < per - 1 else t, kd))
        out.append(row)
    return out


def _size(n):
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n}"


def _long(path):
    try:
        st = os.stat(path)
        mode = stat.filemode(st.st_mode)
        size = "-" if os.path.isdir(path) else _size(st.st_size)
        date = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
    except OSError:
        mode, size, date = "?" * 10, "?", "?"
    return [(f"{mode}  {size:>7}  {date}  ", None), (_label(path), kind(path))]


# ---------------------------------------------------------------------- what a file says
def _read(path):
    if not os.path.exists(path):
        raise FileError(tr("no file {name}", name=path))
    if os.path.isdir(path):
        raise FileError(tr("{name} is a folder (ls {name})", name=path))
    with open(path, "rb") as f:
        raw = f.read()
    if b"\0" in raw[:8192]:
        raise FileError(tr("{name} is not a text file", name=path))
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc).splitlines()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace").splitlines()


def _count(flags, names, default):
    """-n N, -N or N before the file."""
    n = default
    rest = []
    it = iter(names)
    for w in it:
        if w.isdigit() and not rest:
            n = int(w)
        else:
            rest.append(w)
    return n, rest


def head(arg, last=False):
    """head [-n N] FILE: its first N lines (tail: its last)."""
    import re
    arg = re.sub(r"(^|\s)-n\s*(\d+)", r"\1\2", arg)
    arg = re.sub(r"(^|\s)-(\d+)\b", r"\1\2", arg)
    flags, names = split(arg)
    n, names = _count(flags, names, HEAD)
    if not names:
        raise FileError(tr("which file? ({word} [-n N] FILE)", word="tail" if last else "head"))
    out = []
    files = paths(names)
    for k, p in enumerate(files):
        lines = _read(p)
        if len(files) > 1:
            out.append(("" if k == 0 else "\n") + f"==> {p} <==")
        out += lines[-n:] if last and n else lines[:n]
    return out


def cat(arg):
    flags, names = split(arg)
    if not names:
        raise FileError(tr("which file? ({word} FILE)", word="cat"))
    out = []
    for p in paths(names):
        out += _read(p)
    if len(out) > CAT:
        out = out[:CAT] + [tr("... {n} more lines (head, tail)", n=len(out) - CAT)]
    return out


# ---------------------------------------------------------------------- moves
def mkdir(arg):
    flags, names = split(arg)
    if not names:
        raise FileError(tr("which folder? (mkdir [-p] FOLDER)"))
    for n in names:
        n = expand(n)
        try:
            os.makedirs(n, exist_ok="p" in flags) if "p" in flags else os.mkdir(n)
        except FileExistsError:
            raise FileError(tr("{name} already exists", name=n))
        except OSError as e:
            raise FileError(str(e))
    return [tr("made {names}", names=", ".join(names))]


def _two(arg, word):
    flags, names = split(arg)
    if len(names) < 2:
        raise FileError(tr("from where to where? ({word} FROM... TO)", word=word))
    sources = paths(names[:-1])
    dest = expand(names[-1])
    if len(sources) > 1 and not os.path.isdir(dest):
        raise FileError(tr("{name} is not a folder", name=dest))
    for s in sources:
        if not os.path.exists(s):
            raise FileError(tr("no file or folder {name}", name=s))
    return flags, sources, dest


def cp(arg):
    """cp [-r] FROM... TO"""
    flags, sources, dest = _two(arg, "cp")
    for s in sources:
        to = os.path.join(dest, os.path.basename(s.rstrip(os.sep))) if os.path.isdir(dest) else dest
        try:
            if os.path.isdir(s):
                if "r" not in flags:
                    raise FileError(tr("{name} is a folder: cp -r", name=s))
                shutil.copytree(s, to)
            else:
                shutil.copy2(s, to)
        except FileError:
            raise
        except OSError as e:
            raise FileError(str(e))
    return [tr("copied {names} -> {to}", names=", ".join(sources), to=dest)]


def mv(arg):
    """mv FROM... TO"""
    flags, sources, dest = _two(arg, "mv")
    for s in sources:
        try:
            shutil.move(s, dest)
        except OSError as e:
            raise FileError(str(e))
    return [tr("moved {names} -> {to}", names=", ".join(sources), to=dest)]


def to_remove(arg):
    """rm [-r] PATH...: what would be deleted, (paths, recursive); nothing is deleted here."""
    flags, names = split(arg)
    if not names:
        raise FileError(tr("which file? (rm [-r] FILE...)"))
    found = paths(names)
    for p in found:
        if not os.path.lexists(p):
            raise FileError(tr("no file or folder {name}", name=p))
        if os.path.isdir(p) and not os.path.islink(p) and "r" not in flags:
            raise FileError(tr("{name} is a folder: rm -r", name=p))
    return found, "r" in flags


def remove(found):
    """Deletes them (asked first)."""
    for p in found:
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
        except OSError as e:
            raise FileError(str(e))
    return [tr("deleted {names}", names=", ".join(found))]
