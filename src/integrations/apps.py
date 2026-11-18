from django.apps import AppConfig


class DjangoIntegrationsConfig(AppConfig):
    name = "integrations"

    def ready(self) -> None:
        from integrations import checks  # noqa: F401
