from app.models.enums import ValidationStatus, Recommendation, SendDecision
from app.services.risk_scoring import (
    compute_risk_score,
    compute_deliverability_score,
    determine_recommendation,
    determine_send_decision,
)


class TestRiskScore:
    def test_invalid_syntax_max_risk(self):
        score = compute_risk_score(
            syntax_valid=False,
            domain_exists=False,
            mx_exists=False,
            disposable=False,
            role_based=False,
            free_provider=False,
            business_email=False,
            spam_score=0,
            has_unicode=False,
            possible_homograph=False,
            has_typo_suggestion=False,
        )
        assert score == 100

    def test_clean_business_email_low_risk(self):
        score = compute_risk_score(
            syntax_valid=True,
            domain_exists=True,
            mx_exists=True,
            disposable=False,
            role_based=False,
            free_provider=False,
            business_email=True,
            spam_score=0,
            has_unicode=False,
            possible_homograph=False,
            has_typo_suggestion=False,
        )
        assert score < 20

    def test_disposable_email_high_risk(self):
        score = compute_risk_score(
            syntax_valid=True,
            domain_exists=True,
            mx_exists=True,
            disposable=True,
            role_based=False,
            free_provider=False,
            business_email=False,
            spam_score=0,
            has_unicode=False,
            possible_homograph=False,
            has_typo_suggestion=False,
        )
        assert score >= 30

    def test_score_bounded(self):
        score = compute_risk_score(
            syntax_valid=True,
            domain_exists=False,
            mx_exists=False,
            disposable=True,
            role_based=True,
            free_provider=False,
            business_email=False,
            spam_score=100,
            has_unicode=True,
            possible_homograph=True,
            has_typo_suggestion=True,
        )
        assert 0 <= score <= 100


class TestRecommendation:
    def test_low_risk_safe_to_send(self):
        assert determine_recommendation(ValidationStatus.VALID_BUSINESS, 5) == (
            Recommendation.SAFE_TO_SEND
        )

    def test_high_risk_do_not_send(self):
        assert determine_recommendation(ValidationStatus.SUSPICIOUS, 90) == (
            Recommendation.DO_NOT_SEND
        )

    def test_invalid_status_maps_to_invalid_recommendation(self):
        assert determine_recommendation(ValidationStatus.INVALID_SYNTAX, 0) == (
            Recommendation.INVALID
        )


class TestSendDecision:
    def test_safe_to_send_maps_to_send(self):
        assert determine_send_decision(Recommendation.SAFE_TO_SEND) == SendDecision.SEND

    def test_do_not_send_maps_to_skip(self):
        assert determine_send_decision(Recommendation.DO_NOT_SEND) == SendDecision.SKIP

    def test_caution_maps_to_review(self):
        assert determine_send_decision(Recommendation.SEND_WITH_CAUTION) == SendDecision.REVIEW


class TestDeliverabilityScore:
    def test_good_signals_raise_score(self):
        low_signal = compute_deliverability_score(
            risk_score=20, has_spf=False, has_dmarc=False, has_dkim_indicator=False, mx_exists=True
        )
        high_signal = compute_deliverability_score(
            risk_score=20, has_spf=True, has_dmarc=True, has_dkim_indicator=True, mx_exists=True
        )
        assert high_signal >= low_signal

    def test_no_mx_lowers_score(self):
        with_mx = compute_deliverability_score(
            risk_score=20, has_spf=False, has_dmarc=False, has_dkim_indicator=False, mx_exists=True
        )
        without_mx = compute_deliverability_score(
            risk_score=20, has_spf=False, has_dmarc=False, has_dkim_indicator=False, mx_exists=False
        )
        assert without_mx < with_mx
