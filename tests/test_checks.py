from django.test import override_settings

from integrations import Integration, checks, registry
from integrations.fields import TextField


class ValidIntegration(Integration):
    slug = "valid"
    name = "Valid"
    fields = [TextField("account_id")]


def _error_ids(errors):
    return {error.id for error in errors}


class TestCheckUniqueSlugs:
    def test_no_errors_for_valid_registry(self, clean_registry):
        registry.register(ValidIntegration)
        assert checks.check_unique_slugs(None) == []

    def test_no_errors_for_empty_registry(self, clean_registry):
        assert checks.check_unique_slugs(None) == []

    def test_flags_two_classes_sharing_a_slug(self, clean_registry):
        # register() itself refuses this; construct it directly to exercise
        # the check's defense-in-depth path.
        class A(Integration):
            slug = "dup"
            name = "A"

        class B(Integration):
            slug = "dup"
            name = "B"

        registry._registry["key-a"] = A
        registry._registry["key-b"] = B

        assert "integrations.E001" in _error_ids(checks.check_unique_slugs(None))


class TestCheckSlugs:
    def test_no_errors_for_valid_registry(self, clean_registry):
        registry.register(ValidIntegration)
        assert checks.check_slugs(None) == []

    def test_flags_missing_slug(self, clean_registry):
        class NoSlugIntegration(Integration):
            name = "No Slug"

        registry._registry["no-slug"] = NoSlugIntegration
        assert "integrations.E002" in _error_ids(checks.check_slugs(None))

    def test_flags_invalid_slug_format(self, clean_registry):
        class BadSlugIntegration(Integration):
            slug = "Not A Valid Slug!"
            name = "Bad Slug"

        registry._registry["bad-slug"] = BadSlugIntegration
        assert "integrations.E002" in _error_ids(checks.check_slugs(None))


class TestCheckNames:
    def test_no_errors_for_valid_registry(self, clean_registry):
        registry.register(ValidIntegration)
        assert checks.check_names(None) == []

    def test_flags_missing_name(self, clean_registry):
        class NoNameIntegration(Integration):
            slug = "no-name"

        registry._registry["no-name"] = NoNameIntegration
        assert "integrations.E003" in _error_ids(checks.check_names(None))

    def test_flags_blank_name(self, clean_registry):
        class BlankNameIntegration(Integration):
            slug = "blank-name"
            name = "   "

        registry._registry["blank-name"] = BlankNameIntegration
        assert "integrations.E003" in _error_ids(checks.check_names(None))


class TestCheckFieldDefinitions:
    def test_no_errors_for_valid_registry(self, clean_registry):
        registry.register(ValidIntegration)
        assert checks.check_field_definitions(None) == []

    def test_flags_blank_field_name(self, clean_registry):
        class BlankFieldNameIntegration(Integration):
            slug = "blank-field"
            name = "Blank Field"
            fields = [TextField("")]

        registry._registry["blank-field"] = BlankFieldNameIntegration
        assert "integrations.E005" in _error_ids(checks.check_field_definitions(None))

    def test_flags_duplicate_field_name(self, clean_registry):
        class DuplicateFieldIntegration(Integration):
            slug = "dup-field"
            name = "Dup Field"
            fields = [TextField("x")]

        # __init_subclass__ already refuses this at class-definition time;
        # mutate after the fact to exercise the check's defense-in-depth path.
        DuplicateFieldIntegration.fields = [TextField("x"), TextField("x")]
        registry._registry["dup-field"] = DuplicateFieldIntegration

        assert "integrations.E004" in _error_ids(checks.check_field_definitions(None))


class TestCheckEncryptionConfiguration:
    def test_no_errors_for_valid_keys(self):
        # tests.settings already provides a valid ENCRYPTED_FIELD_KEYS by
        # default; just confirm the happy path returns no errors.
        assert checks.check_encryption_configuration(None) == []

    @override_settings(ENCRYPTED_FIELD_KEYS=[])
    def test_flags_missing_keys(self):
        errors = checks.check_encryption_configuration(None)
        assert "integrations.E006" in _error_ids(errors)

    @override_settings(ENCRYPTED_FIELD_KEYS=["not-a-valid-fernet-key"])
    def test_flags_malformed_keys(self):
        errors = checks.check_encryption_configuration(None)
        assert "integrations.E006" in _error_ids(errors)


class TestCheckScopeResolver:
    def test_no_errors_for_default_resolver(self):
        assert checks.check_scope_resolver(None) == []

    @override_settings(INTEGRATIONS_SCOPE_RESOLVER="not.a.real.module.path")
    def test_flags_bad_dotted_path(self):
        errors = checks.check_scope_resolver(None)
        assert "integrations.E007" in _error_ids(errors)


class TestCheckPermissionPolicy:
    def test_no_errors_for_default_policy(self):
        assert checks.check_permission_policy(None) == []

    @override_settings(INTEGRATIONS_PERMISSION_POLICY="not.a.real.module.Path")
    def test_flags_bad_dotted_path(self):
        errors = checks.check_permission_policy(None)
        assert "integrations.E008" in _error_ids(errors)
