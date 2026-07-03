from app.validators.domain import check_reserved_or_invalid_domain


class TestReservedDomains:
    def test_example_com_is_reserved(self):
        is_reserved, reason = check_reserved_or_invalid_domain("example.com")
        assert is_reserved
        assert reason

    def test_localhost_is_reserved(self):
        is_reserved, _ = check_reserved_or_invalid_domain("localhost")
        assert is_reserved

    def test_invalid_tld_reserved(self):
        is_reserved, _ = check_reserved_or_invalid_domain("something.invalid")
        assert is_reserved

    def test_legit_domain_not_reserved(self):
        is_reserved, _ = check_reserved_or_invalid_domain("acmecorp.com")
        assert not is_reserved
