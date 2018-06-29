from .models import ArtShowApplication
from uber.decorators import prereg_validation, validation
from uber.config import c
from uber.models import Session


ArtShowApplication.required = [('description', 'Description'),('website','Website URL')]


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
    if not app.panels and not app.tables \
            and not app.panels_ad and not app.tables_ad:
        return 'Please select how many panels and/or tables to include' \
               ' on this application.'


@prereg_validation.ArtShowApplication
def too_late_now(app):
    if app.status != c.UNAPPROVED:
        return 'Your app has been {} and may no longer be updated'\
            .format(app.status_label)


@validation.ArtShowApplication
def discounted_price(app):
    try:
        cost = int(float(app.overridden_price if app.overridden_price else 0))
        if cost < 0:
            return 'Overridden Price must be a number that is 0 or higher.'
    except Exception:
        return "What you entered for Overridden Price ({}) " \
               "isn't even a number".format(app.overridden_price)


@prereg_validation.Attendee
def promo_code_is_useful(attendee):
    if attendee.promo_code:
        with Session() as session:
            if session.lookup_agent_code(attendee.promo_code.code):
                return
        if not attendee.is_unpaid:
            return "You can't apply a promo code after you've paid or if you're in a group."
        elif attendee.overridden_price:
            return "You already have a special badge price, you can't use a promo code on top of that."
        elif attendee.badge_cost >= attendee.badge_cost_without_promo_code:
            return "That promo code doesn't make your badge any cheaper. You may already have other discounts."


@prereg_validation.Attendee
def agent_code_already_used(attendee):
    if attendee.promo_code:
        with Session() as session:
            apps_with_code = session.lookup_agent_code(attendee.promo_code.code)
            for app in apps_with_code:
                if not app.agent_id or app.agent_id == attendee.id:
                    return
            return "That agent code has already been used."
