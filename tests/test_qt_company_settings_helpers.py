from genimail_qt.window import GeniMailQtWindow


class _FakeConfig:
    def __init__(self, payload):
        self.payload = dict(payload)

    def get(self, key, default=None):
        return self.payload.get(key, default)

    def set(self, key, value):
        self.payload[key] = value


class _FakeWindow:
    def __init__(self, payload):
        self.config = _FakeConfig(payload)


def test_get_company_domain_set_normalizes_values():
    fake = _FakeWindow({"company_favorites": [" Acme.com ", "ACME.com", "", None, "Contoso.com"]})

    domains = GeniMailQtWindow._get_company_domain_set(fake, "company_favorites")

    assert domains == {"acme.com", "contoso.com"}


def test_save_company_domain_set_sorts_and_dedupes():
    fake = _FakeWindow({})

    GeniMailQtWindow._save_company_domain_set(fake, "company_hidden", {"x.com", " Acme.com ", "acme.com"})

    assert fake.config.payload["company_hidden"] == ["acme.com", "x.com"]
