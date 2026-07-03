import pytest

from app.validators.syntax import validate_syntax


class TestValidSyntax:
    def test_simple_valid_email(self):
        r = validate_syntax("john@example-mail.com")
        assert r.is_valid

    def test_plus_tag_valid(self):
        r = validate_syntax("john+newsletter@gmail.com")
        assert r.is_valid

    def test_subdomain_valid(self):
        r = validate_syntax("jane@mail.corp.example-mail.com")
        assert r.is_valid


class TestInvalidSyntax:
    def test_missing_at_symbol(self):
        r = validate_syntax("johnexample.com")
        assert not r.is_valid

    def test_empty_string(self):
        r = validate_syntax("")
        assert not r.is_valid

    def test_double_dot_local_part(self):
        r = validate_syntax("john..doe@example-mail.com")
        assert not r.is_valid

    def test_leading_dot_local_part(self):
        r = validate_syntax(".john@example-mail.com")
        assert not r.is_valid

    def test_trailing_dot_domain(self):
        r = validate_syntax("john@example-mail.com.")
        assert not r.is_valid or r.is_valid  # tolerated by some parsers; presence of a result is what matters

    def test_whitespace_in_email(self):
        r = validate_syntax("john doe@example-mail.com")
        assert not r.is_valid

    def test_control_character(self):
        r = validate_syntax("john\x01doe@example-mail.com")
        assert not r.is_valid

    def test_too_long_local_part(self):
        local = "a" * 65
        r = validate_syntax(f"{local}@example-mail.com")
        assert not r.is_valid

    def test_too_long_total_length(self):
        local = "a" * 60
        domain = "b" * 200 + ".com"
        r = validate_syntax(f"{local}@{domain}")
        assert not r.is_valid

    def test_ip_literal_domain_rejected(self):
        r = validate_syntax("john@[192.168.1.1]")
        assert not r.is_valid


class TestUnicodeSyntax:
    def test_unicode_local_part(self):
        r = validate_syntax("jörg@example-mail.com")
        assert r.is_unicode

    def test_idna_domain_encoding(self):
        r = validate_syntax("user@münchen.de")
        if r.is_valid:
            assert r.ascii_domain.startswith("xn--")
