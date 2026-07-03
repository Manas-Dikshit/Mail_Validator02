from app.services.validation_service import validate_single_email
from app.models.enums import ValidationStatus, MailboxStatus


class TestValidateSingleEmailNoDns:
    def test_valid_business_style_email(self):
        r = validate_single_email("jane.doe@acmecorporation.com", check_dns=False)
        assert r.syntax_valid
        assert r.validation_status == ValidationStatus.VALID

    def test_disposable_flagged_without_dns(self):
        r = validate_single_email("user@mailinator.com", check_dns=False)
        assert r.disposable
        assert r.validation_status == ValidationStatus.INVALID_DISPOSABLE

    def test_role_based_flagged(self):
        r = validate_single_email("support@acmecorporation.com", check_dns=False)
        assert r.role_based
        assert r.validation_status == ValidationStatus.INVALID_ROLE

    def test_free_provider_flagged(self):
        r = validate_single_email("someone@gmail.com", check_dns=False)
        assert r.free_provider
        assert r.free_provider_name == "gmail.com"

    def test_mailbox_never_claimed_to_exist(self):
        r = validate_single_email("jane.doe@acmecorporation.com", check_dns=False)
        assert r.mailbox_status == MailboxStatus.MAILBOX_UNKNOWN

    def test_reserved_domain_rejected(self):
        r = validate_single_email("user@example.com", check_dns=False)
        assert r.validation_status in (
            ValidationStatus.INVALID_EXAMPLE_DOMAIN,
            ValidationStatus.INVALID_RESERVED_DOMAIN,
        )

    def test_invalid_syntax_rejected(self):
        r = validate_single_email("not-an-email", check_dns=False)
        assert not r.syntax_valid
        assert r.validation_status == ValidationStatus.INVALID_SYNTAX

    def test_empty_input_rejected(self):
        r = validate_single_email("", check_dns=False)
        assert not r.syntax_valid

    def test_typo_domain_suggested(self):
        r = validate_single_email("user@gmail.con", check_dns=False)
        assert r.typo_suggestion == "gmail.com"

    def test_risk_score_within_bounds(self):
        r = validate_single_email("jane.doe@acmecorporation.com", check_dns=False)
        assert 0 <= r.risk_score <= 100
        assert 0 <= r.deliverability_score <= 100
