from app.validators.classification import (
    is_disposable,
    free_provider_name,
    is_role_based,
    is_business_email,
)


class TestDisposable:
    def test_known_disposable_domain(self):
        assert is_disposable("mailinator.com")

    def test_disposable_subdomain(self):
        assert is_disposable("mail.mailinator.com")

    def test_legit_domain_not_disposable(self):
        assert not is_disposable("acmecorp.com")


class TestFreeProvider:
    def test_gmail_is_free(self):
        assert free_provider_name("gmail.com") == "gmail.com"

    def test_custom_domain_not_free(self):
        assert free_provider_name("acmecorp.com") is None


class TestRoleBased:
    def test_admin_is_role(self):
        assert is_role_based("admin")

    def test_support_is_role(self):
        assert is_role_based("support")

    def test_plus_tagged_role(self):
        assert is_role_based("info+campaign")

    def test_personal_name_not_role(self):
        assert not is_role_based("john.smith")


class TestBusinessEmail:
    def test_business_when_not_disposable_not_free_has_mx(self):
        assert is_business_email(disposable=False, free=False, mx_exists=True)

    def test_not_business_when_disposable(self):
        assert not is_business_email(disposable=True, free=False, mx_exists=True)

    def test_not_business_when_free(self):
        assert not is_business_email(disposable=False, free=True, mx_exists=True)

    def test_not_business_without_mx(self):
        assert not is_business_email(disposable=False, free=False, mx_exists=False)
