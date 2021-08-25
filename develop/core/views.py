from django.contrib.sites.models import Site
from django.shortcuts import render
from django.views.generic import FormView
from django.views.generic.edit import ModelFormMixin

from core.forms import ZoomForm, VoucheryForm, AuthorizeNetForm


class ZoomFormView(FormView):
    template_name = "core/form.html"
    form_class = ZoomForm

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context['name'] = "Zoom"
        return context
    
    def form_valid(self, form):
        zoom = form.save(commit=False)
        zoom.name = 'Zoom Integration'
        zoom.site = Site.objects.get_current()
        zoom.save()
        return super().form_valid(form)


class VoucheryFormView(FormView):
    template_name = "core/form.html"
    form_class = VoucheryForm

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context['name'] = "Vouchery"
        return context
    
    def form_valid(self, form):
        vouchery = form.save(commit=False)
        vouchery.name = 'Vouchery Integration'
        vouchery.site = Site.objects.get_current()
        vouchery.save()
        return super().form_valid(form)


class AuthorizeNetFormView(FormView):
    template_name = "core/form.html"
    form_class = AuthorizeNetForm

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context['name'] = "AuthorizeNet"
        return context
    
    def form_valid(self, form):
        authorizenet = form.save(commit=False)
        authorizenet.name = 'AuthorizeNet Integration'
        authorizenet.site = Site.objects.get_current()
        authorizenet.save()
        return super().form_valid(form)