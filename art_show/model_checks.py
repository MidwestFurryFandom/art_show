from .models import ArtShowApplication
from uber.decorators import prereg_validation, validation
from uber.config import c


ArtShowApplication.required = [('description', 'Description')]


@prereg_validation.ArtShowApplication
def max_panels(app):
    if app.panels > c.MAX_ART_PANELS:
        return 'You cannot have more than {} panels.'.format(c.MAX_ART_PANELS)


@prereg_validation.ArtShowApplication
def min_panels(app):
    if app.panels < 0:
        return 'You cannot have fewer than 0 panels.'


@prereg_validation.ArtShowApplication
def max_tables(app):
    if app.tables > c.MAX_ART_TABLES:
        return 'You cannot have more than {} tables.'.format(c.MAX_ART_TABLES)


@prereg_validation.ArtShowApplication
def min_tables(app):
    if app.tables < 0:
        return 'You cannot have fewer than 0 tables.'


@validation.ArtShowApplication
def cant_ghost_art_show(app):
    if app.attendee and app.delivery_method == c.BRINGING_IN \
            and app.attendee.badge_status == c.NOT_ATTENDING:
        return 'You cannot bring your own art if you are not attending.'


@validation.ArtShowApplication
def need_some_space(app):
    if not app.panels and not app.tables:
        return 'Please select how many panels and/or tables to include' \
               ' on this application.'


@validation.ArtShowApplication
def discounted_price(app):
    try:
        cost = int(float(app.overridden_price if app.overridden_price else 0))
        if cost < 0:
            return 'Overridden Price must be a number that is 0 or higher.'
    except Exception:
        return "What you entered for Overridden Price ({}) " \
               "isn't even a number".format(app.overridden_price)
