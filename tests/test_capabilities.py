import pytest

from integrations import Integration
from integrations.capabilities import ConnectionTestResult
from integrations.fields import TextField


class TestConnectionTestResult:
    def test_construction(self):
        result = ConnectionTestResult(success=True, message="ok")
        assert result.success is True
        assert result.message == "ok"

    def test_default_message_is_blank(self):
        assert ConnectionTestResult(success=False).message == ""

    def test_equality(self):
        assert ConnectionTestResult(success=True, message="ok") == ConnectionTestResult(
            success=True, message="ok"
        )


class TestDefaultTestConnection:
    def test_raises_not_implemented_naming_the_class(self, clean_registry):
        class NoTestConnectionIntegration(Integration):
            slug = "no-test-connection"
            name = "No Test Connection"
            fields = [TextField("account_id", required=False)]

        config = NoTestConnectionIntegration.clean({})
        with pytest.raises(NotImplementedError) as exc_info:
            NoTestConnectionIntegration.test_connection(config)
        assert "NoTestConnectionIntegration" in str(exc_info.value)
