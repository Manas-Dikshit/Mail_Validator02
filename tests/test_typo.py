from app.validators.typo import suggest_domain_correction


class TestTypoDetection:
    def test_known_typo_map_hit(self):
        assert suggest_domain_correction("gmail.con") == "gmail.com"

    def test_known_typo_gamil(self):
        assert suggest_domain_correction("gamil.com") == "gmail.com"

    def test_known_typo_hotnail(self):
        assert suggest_domain_correction("hotnail.com") == "hotmail.com"

    def test_known_typo_yahho(self):
        assert suggest_domain_correction("yahho.com") == "yahoo.com"

    def test_correct_domain_no_suggestion(self):
        assert suggest_domain_correction("gmail.com") is None

    def test_unrelated_business_domain_no_suggestion(self):
        assert suggest_domain_correction("acmecorporation.com") is None
