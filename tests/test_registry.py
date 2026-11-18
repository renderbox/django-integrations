import pytest

from integrations import Integration, registry
from integrations.exceptions import (
    DuplicateIntegrationError,
    IntegrationNotRegisteredError,
)
from integrations.fields import TextField


class FooIntegration(Integration):
    slug = "foo"
    name = "Foo"
    fields = [TextField("account_id")]


class BarIntegration(Integration):
    slug = "bar"
    name = "Bar"
    fields = [TextField("account_id")]


class TestRegister:
    def test_register_returns_class_unchanged(self, clean_registry):
        result = registry.register(FooIntegration)
        assert result is FooIntegration

    def test_works_as_bare_decorator(self, clean_registry):
        @registry.register
        class DecoratedIntegration(Integration):
            slug = "decorated"
            name = "Decorated"

        assert registry.get("decorated") is DecoratedIntegration

    def test_reregistering_same_class_is_a_noop(self, clean_registry):
        registry.register(FooIntegration)
        registry.register(FooIntegration)  # should not raise
        assert registry.get("foo") is FooIntegration

    def test_different_class_same_slug_raises(self, clean_registry):
        registry.register(FooIntegration)

        class OtherIntegration(Integration):
            slug = "foo"
            name = "Other"

        with pytest.raises(DuplicateIntegrationError) as exc_info:
            registry.register(OtherIntegration)
        assert exc_info.value.slug == "foo"


class TestGet:
    def test_get_returns_registered_class(self, clean_registry):
        registry.register(FooIntegration)
        assert registry.get("foo") is FooIntegration

    def test_get_unknown_slug_raises(self, clean_registry):
        with pytest.raises(IntegrationNotRegisteredError) as exc_info:
            registry.get("does-not-exist")
        assert exc_info.value.slug == "does-not-exist"


class TestAll:
    def test_all_returns_sorted_by_slug(self, clean_registry):
        registry.register(BarIntegration)
        registry.register(FooIntegration)
        assert registry.all() == [BarIntegration, FooIntegration]

    def test_all_empty_registry(self, clean_registry):
        assert registry.all() == []


class TestUnregister:
    def test_unregister_removes_entry(self, clean_registry):
        registry.register(FooIntegration)
        registry.unregister("foo")
        with pytest.raises(IntegrationNotRegisteredError):
            registry.get("foo")

    def test_unregister_unknown_slug_raises(self, clean_registry):
        with pytest.raises(IntegrationNotRegisteredError) as exc_info:
            registry.unregister("does-not-exist")
        assert exc_info.value.slug == "does-not-exist"
