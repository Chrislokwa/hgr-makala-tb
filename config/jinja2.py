from django.templatetags.static import static
from django.urls import reverse
from jinja2 import Environment


def url(name, **kwargs):
    """Version compatible Jinja2 de django.urls.reverse.

    Les mots-clés passés dans le template (ex. pk=..., uidb64=...) sont
    transmis comme `kwargs` à reverse().
    """
    return reverse(name, kwargs=kwargs)


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'url': url,
        'static': static,
    })
    return env
