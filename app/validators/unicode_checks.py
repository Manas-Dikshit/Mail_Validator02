from __future__ import annotations

import unicodedata

from app.models.schemas import UnicodeResult

_INVISIBLE_CODEPOINTS = {
    0x200B,  # zero width space
    0x200C,  # zero width non-joiner
    0x200D,  # zero width joiner
    0x2060,  # word joiner
    0xFEFF,  # zero width no-break space / BOM
}

_RTL_MARKERS = {0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E}

# Very small, well-known confusable set for local-part homograph screening.
# This is deliberately conservative - a full Unicode confusables table (UTS
# #39) would be the production choice; wiring in the real table is left as
# an extension point (see README limitations).
_CYRILLIC_LATIN_CONFUSABLES = set("аеорсух")  # Cyrillic letters that look Latin


def _script_of(ch: str) -> str:
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return "UNKNOWN"
    if "CYRILLIC" in name:
        return "CYRILLIC"
    if "GREEK" in name:
        return "GREEK"
    if "LATIN" in name:
        return "LATIN"
    if "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name or "HANGUL" in name:
        return "CJK"
    if "ARABIC" in name:
        return "ARABIC"
    if "HEBREW" in name:
        return "HEBREW"
    if "DEVANAGARI" in name:
        return "DEVANAGARI"
    return "OTHER"


def analyze_unicode(email: str) -> UnicodeResult:
    has_unicode = any(ord(ch) > 127 for ch in email)
    notes: list[str] = []

    invisible = any(ord(ch) in _INVISIBLE_CODEPOINTS for ch in email)
    if invisible:
        notes.append("Contains zero-width/invisible characters")

    rtl = any(ord(ch) in _RTL_MARKERS for ch in email)
    if rtl:
        notes.append("Contains RTL/bidi override markers")

    scripts = {
        _script_of(ch)
        for ch in email
        if ch.isalpha() and _script_of(ch) not in ("UNKNOWN", "OTHER")
    }
    # Ignore purely-ASCII structural chars like '@' and '.' when deciding
    mixed_scripts = len(scripts) > 1

    possible_homograph = False
    if mixed_scripts and "LATIN" in scripts:
        # Mixing Latin with Cyrillic/Greek in the same label is the classic
        # homograph attack pattern (e.g. "gооgle.com" with Cyrillic o's).
        if scripts & {"CYRILLIC", "GREEK"}:
            possible_homograph = True
            notes.append("Mixed Latin + Cyrillic/Greek scripts (possible homograph)")
    elif not mixed_scripts:
        cyr_hits = [ch for ch in email if ch in _CYRILLIC_LATIN_CONFUSABLES]
        if cyr_hits and any(ch.isascii() and ch.isalpha() for ch in email):
            possible_homograph = True
            notes.append("Contains Cyrillic look-alike characters mixed with ASCII")

    return UnicodeResult(
        has_unicode=has_unicode,
        mixed_scripts=mixed_scripts,
        has_invisible_chars=invisible,
        has_rtl_markers=rtl,
        possible_homograph=possible_homograph,
        notes=notes,
    )
