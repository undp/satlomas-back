from django.apps import AppConfig


class ScopesConfig(AppConfig):
    name = "scopes"

    def ready(self):
        import scopes.signals
