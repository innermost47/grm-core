# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The interface in English and in French.

Everything the machine says goes through tr(template, **values): the template is the English text (with str.format
fields), the catalogue of a language gives it in that language (fr.py). A template a catalogue does not have is said
in English. The language of the programs (node, relate, observe...) stays English in both: a program runs anywhere.

    tr("observed {name} = {value:g}", name="g", value=9.81)
    set_lang("fr")   # or lang fr / lang en in the machine; remembered in settings.json
"""
import json
import locale
import os

LANGS = ("en", "fr")
_lang = "en"


def lang():
    return _lang


def set_lang(code):
    global _lang
    code = (code or "en").lower()[:2]
    _lang = code if code in LANGS else "en"
    return _lang


def system_lang():
    """The language of the system the machine runs on (fr or en)."""
    for key in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        v = os.environ.get(key)
        if v:
            return "fr" if v.lower().startswith("fr") else "en"
    try:
        code = locale.getlocale()[0] or ""
    except ValueError:
        code = ""
    if not code and os.name == "nt":
        try:
            import ctypes
            code = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
        except Exception:  # noqa: BLE001
            code = ""
    return "fr" if code.lower().startswith("fr") else "en"


def catalogue(code=None):
    code = code or _lang
    if code == "fr":
        from fr import FR
        return FR
    return {}


def tr(template, **values):
    """template in the current language, its fields filled with values."""
    text = catalogue().get(template, template) if _lang != "en" else template
    if values:
        try:
            return text.format(**values)
        except (KeyError, IndexError, ValueError):     # a translation that does not fit: the English one
            return template.format(**values)
    return text


def label(word):
    """A word followed by its colon, as each language writes it ("error: ", "erreur : ")."""
    return tr(word) + (" : " if _lang == "fr" else ": ")


# ---------------------------------------------------------------------- settings (language, typing help)
DEFAULTS = {"lang": None, "help": True}


def load_settings(path):
    s = dict(DEFAULTS)
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                s.update(json.load(f))
        except (OSError, ValueError):
            pass
    return s


def save_settings(path, settings):
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=1)
    except OSError:
        pass
