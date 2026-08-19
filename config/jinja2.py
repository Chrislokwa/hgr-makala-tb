from datetime import datetime

from django.templatetags.static import static
from django.urls import reverse
from jinja2 import Environment


_MOIS_FR = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]


def date_fr(valeur):
    """Formate une date (ou datetime) en français, ex. « 12 mai 1990 »."""
    if valeur is None:
        return ''
    texte = f"{valeur.day} {_MOIS_FR[valeur.month - 1]} {valeur.year}"
    if isinstance(valeur, datetime):
        texte += f" à {valeur.strftime('%H:%M')}"
    return texte


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
    env.filters.update({
        'date_fr': date_fr,
    })
    return env
