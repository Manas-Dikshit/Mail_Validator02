from app.services.catch_all import estimate_catch_all
from app.models.enums import CatchAllStatus


class TestCatchAllEstimation:
    def test_no_mx_hosts_unknown(self):
        assert estimate_catch_all([]) == CatchAllStatus.UNKNOWN

    def test_known_catch_all_prone_provider(self):
        assert estimate_catch_all(["mx1.improvmx.com"]) == CatchAllStatus.POSSIBLE_CATCH_ALL

    def test_generic_mx_returns_unknown_not_confirmed(self):
        # Must never claim certainty - only UNKNOWN or POSSIBLE_CATCH_ALL
        result = estimate_catch_all(["aspmx.l.google.com"])
        assert result in (CatchAllStatus.UNKNOWN, CatchAllStatus.POSSIBLE_CATCH_ALL)
        assert result != "CONFIRMED"
