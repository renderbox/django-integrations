import pytest

from integrations import registry


@pytest.fixture
def clean_registry():
    """
    Snapshot and restore the process-global integration registry around a
    test. Opt in explicitly for any test that registers/unregisters
    integrations, so it doesn't leak state into unrelated tests.
    """
    original = dict(registry._registry)
    registry._registry.clear()
    try:
        yield
    finally:
        registry._registry.clear()
        registry._registry.update(original)
