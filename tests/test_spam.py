from app.validators.spam import compute_spam_score


class TestSpamScore:
    def test_normal_name_low_score(self):
        score, _ = compute_spam_score("john.smith")
        assert score < 30

    def test_keyword_hit_raises_score(self):
        score, reasons = compute_spam_score("casino_winner_bonus")
        assert score > 30
        assert reasons

    def test_high_digit_ratio_raises_score(self):
        score, _ = compute_spam_score("user1234567890")
        assert score > 0

    def test_random_string_flagged(self):
        score, _ = compute_spam_score("xjqzvbnmklpq")
        assert score > 0

    def test_score_bounded_0_100(self):
        score, _ = compute_spam_score("casino" * 20)
        assert 0 <= score <= 100
