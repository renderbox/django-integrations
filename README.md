![Django Integrations CI](https://github.com/renderbox/django-integrations/workflows/Django%20Integrations%20CI/badge.svg)

![Django Integrations CI](https://github.com/renderbox/django-integrations/workflows/Django%20Integrations%20Develop/badge.svg)

# Django Integrations

Tools for creating and managing multi-site integrations like API Keys and Tokens

## Prerequisites
This pakcage makes use of Encrypted Fields that come form the [django-fernet-fields](https://github.com/orcasgit/django-fernet-fields) packages. Make sure to checkout their documentation for any questions related to Field Encryption. 

This package makes use of JSON fields so you'll need Download and install Postgresql. This will change with Django 3.1+ and the universal JSON field.

## Installation
```
> pip install django-integration
```

## For Developers
Make sure you run the following command to ensure you have all the requirements needed to us the develop example project:
```
pip install -e .[dev]
```
Then run the migration command inside the develop folder
```
./manage.py migrate
```
finally create a super user:
```
./manage.py createsuperuser
```
### Example
In the develop django project you will find a core application that has three Forms each with its view to show case how to use the Credential Model in the integration package.

For example you have a ZoomForm to present the user with the fields Zoom gives to use their API with you project. The ZoomForm is responsible for presenting and validating the fields and linking it to the credentials Model just like a normal ModelForm would.
```
class ZoomForm(forms.ModelForm):

    class Meta:
        model = Credential
        fields = ['public_key', 'private_key']
        labels = {
            'public_key': "Zoom Key",
            'private_key': "Zoom Secret"
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['public_key'].required = True
        self.fields['private_key'].required = True
```

It is in the view where it creates a Credential Model instance form the form submitted and saved. If you need to add additional fields or logic you can do it here, for example settting the site field in the Credential Model.

```
class ZoomFormView(FormView):
    template_name = "core/form.html"
    form_class = ZoomForm
    success_url = reverse_lazy('integration-list')

    def form_valid(self, form):
        zoom = form.save(commit=False)
        zoom.name = 'Zoom Integration'
        zoom.site = Site.objects.get_current()
        zoom.save()
        return super().form_valid(form)
```