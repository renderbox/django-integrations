# Built-in HTML UI

A complete server-rendered alternative to the JSON API, for applications
that don't want to build an SPA management screen. Mount it the same way:

```python
# yourproject/urls.py
urlpatterns = [
    path("", include("integrations.urls")),
]
```

Unlike the API, there's no version prefix - server-rendered pages evolve
with the package itself, not as a separately-versioned contract external
consumers depend on.

| Path | |
|---|---|
| `` | list registered integrations, with configured status |
| `{slug}/` | detail: current configuration, safe (no secret values) |
| `{slug}/configure/` | generated form (GET), submit (POST) |
| `{slug}/delete/` | confirm (GET), remove (POST) |
| `{slug}/test/` | POST only - runs the connection test, flashes the result |

Requires an authenticated session (`LoginRequiredMixin` - redirects to
`settings.LOGIN_URL`) and checks the configured permission policy on
every view (a real, host-overridable `403`/`404` page, not a JSON body -
see [scopes-and-permissions.md](scopes-and-permissions.md)).

## The generated form

Built from the integration's own field definitions
(`integrations.forms.build_configuration_form`) - there's no
provider-specific `ModelForm` to write. A few things worth knowing if
you're building your own view on top of the same forms module:

- Secret fields are always optional at the form-validation layer,
  regardless of the domain field's own `required` - leaving one blank
  means "don't change it," and the form has to allow submitting that.
  The *actual* requiredness is enforced once the view merges the
  submission with whatever's already stored.
- Secret fields never receive a stored value as `initial` - not even
  via the password input's `render_value` behavior; the value simply
  isn't passed to the form at all.
- Optional secret fields get a companion `{name}__clear` checkbox
  (there's no HTML equivalent of the API's `null`-clears-a-secret).

## Templates

Ship under `integrations/templates/integrations/*.html` - plain,
unstyled HTML with a small inline `<style>` block, not a CSS framework.
Override any of them in your own project the normal Django way: put a
template at the same path (`yourapp/templates/integrations/detail.html`,
etc.) earlier in your template loader's search order.

Flash messages (connection-test results) use Django's own
`django.contrib.messages` framework - if you override `base.html`, keep
rendering `{% if messages %}` somewhere, or results won't be visible.
