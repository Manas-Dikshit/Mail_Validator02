from app.validators.unicode_checks import analyze_unicode


class TestUnicodeChecks:
    def test_plain_ascii_no_unicode(self):
        r = analyze_unicode("john@example.com")
        assert not r.has_unicode
        assert not r.mixed_scripts
        assert not r.has_invisible_chars

    def test_detects_invisible_zero_width(self):
        r = analyze_unicode("john\u200bdoe@example.com")
        assert r.has_invisible_chars

    def test_detects_rtl_marker(self):
        r = analyze_unicode("john\u202edoe@example.com")
        assert r.has_rtl_markers

    def test_cyrillic_homograph_flagged(self):
        # Cyrillic 'а' (U+0430) mixed with Latin letters, mimicking "gmail"
        spoofed = "john@gm\u0430il.com"
        r = analyze_unicode(spoofed)
        assert r.has_unicode
        assert r.possible_homograph

    def test_legitimate_full_unicode_domain_not_flagged_as_mixed(self):
        # Entirely CJK - not a mixed-script homograph pattern
        r = analyze_unicode("用户@例え.jp")
        assert r.has_unicode
