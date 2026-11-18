"""
Example Integration definitions for the demo project.

Two integrations are enough to cover every pattern the project's docs
describe:

- WebhookNotifier: the simplest possible shape - a single required secret.
- ExampleCRM: config + secret together, a cross-field validate() override,
  and a real (stdlib, no extra dependency) test_connection().

Registered via CoreConfig.ready() importing this module - see apps.py.
"""

import urllib.error
import urllib.parse
import urllib.request

from integrations import Integration, register
from integrations.capabilities import TEST_CONNECTION, ConnectionTestResult
from integrations.exceptions import IntegrationValidationError
from integrations.fields import SecretField, TextField, URLField


@register
class WebhookNotifier(Integration):
    slug = "webhook-notifier"
    name = "Webhook Notifier"
    description = "Sends notifications to a webhook using a bearer token."
    fields = [
        SecretField(
            "api_key",
            label="API Key",
            required=True,
            help_text="Bearer token used to authenticate outbound webhook calls.",
        ),
    ]


@register
class ExampleCRM(Integration):
    slug = "example-crm"
    name = "Example CRM"
    description = (
        "A representative provider integration: an account id and API base "
        "URL as configuration, an API key as a secret."
    )
    capabilities = (TEST_CONNECTION,)
    fields = [
        TextField("account_id", label="Account ID", required=True),
        URLField(
            "api_base_url",
            label="API Base URL",
            required=True,
            help_text="test_connection() checks connectivity against this URL.",
        ),
        SecretField("api_key", label="API Key", required=True),
    ]

    @classmethod
    def validate(cls, config, secrets):
        # Cross-field example: this fake provider's sandbox environment
        # requires a matching "sandbox-" prefixed account id.
        api_base_url = config.get("api_base_url", "")
        account_id = config.get("account_id", "")
        if api_base_url.startswith("https://sandbox.") and not account_id.startswith(
            "sandbox-"
        ):
            raise IntegrationValidationError(
                {
                    "account_id": [
                        "Sandbox API URLs require an account id starting "
                        "with 'sandbox-'."
                    ]
                }
            )

    @classmethod
    def test_connection(cls, config):
        # Tests connectivity to whatever URL was actually configured,
        # rather than a hardcoded external host - the more honest, reusable
        # pattern for an example that isn't a real provider. Only ever
        # references config.config (the URL) - never config.secrets.
        url = config.config.get("api_base_url")

        # Only ever follow http(s) - URLField's own validation is broader
        # (it also accepts ftp/ftps), and urlopen() would happily act on
        # whatever scheme it's given.
        if urllib.parse.urlparse(url).scheme not in ("http", "https"):
            return ConnectionTestResult(
                success=False, message=f"Unsupported URL scheme for {url}."
            )

        request = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:  # nosec B310
                return ConnectionTestResult(
                    success=True, message=f"Reached {url} ({response.status})."
                )
        except (urllib.error.URLError, ValueError, TimeoutError) as exc:
            return ConnectionTestResult(
                success=False, message=f"Could not reach {url}: {exc}"
            )
