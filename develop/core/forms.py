from django import forms

from integrations.models import Credential


class ZoomForm(forms.ModelForm):

    class Meta:
        model = Credential
        fields = ["public_key", "private_key"]
        labels = {"public_key": "Zoom Key", "private_key": "Zoom Secret"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["public_key"].required = True
        self.fields["private_key"].required = True


class VoucheryForm(forms.ModelForm):

    class Meta:
        model = Credential
        fields = ["client_url", "private_key"]
        labels = {"client_url": "Vouchery URL", "private_key": "Vouchery Barrer Key"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client_url"].required = True
        self.fields["private_key"].required = True


class AuthorizeNetForm(forms.ModelForm):

    class Meta:
        model = Credential
        fields = ["client_id", "public_key", "private_key"]
        labels = {
            "client_id": "API ID",
            "public_key": "Transaction Key",
            "private_key": "Signiture ID",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client_id"].required = True
        self.fields["public_key"].required = True
        self.fields["private_key"].required = True
