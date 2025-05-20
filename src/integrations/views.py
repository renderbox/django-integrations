from django.views.generic import TemplateView

class DjangoIntegrationsIndexView(TemplateView):
    template_name = "integrations/index.html"
