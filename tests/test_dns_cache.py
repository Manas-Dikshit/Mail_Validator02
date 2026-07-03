import time

from app.dns.cache import TTLCache


class TestTTLCache:
    def test_set_and_get(self):
        cache = TTLCache(max_size=10, default_ttl=60)
        cache.set("a", "value-a")
        assert cache.get("a") == "value-a"

    def test_missing_key_returns_none(self):
        cache = TTLCache(max_size=10, default_ttl=60)
        assert cache.get("missing") is None

    def test_expired_entry_returns_none(self):
        cache = TTLCache(max_size=10, default_ttl=1)
        cache.set("a", "value-a", ttl=0)
        time.sleep(0.01)
        assert cache.get("a") is None

    def test_max_size_evicts_oldest(self):
        cache = TTLCache(max_size=2, default_ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_clear(self):
        cache = TTLCache(max_size=10, default_ttl=60)
        cache.set("a", 1)
        cache.clear()
        assert cache.get("a") is None
