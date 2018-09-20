from .models import ArtShowApplication, ArtShowPiece
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
        for field in ['artist_name',
                      'panels',
                      'panels_ad',
                      'tables',
                      'tables_ad',
                      'description',
                      'website',
                      'special_needs',
                      'status',
                      'delivery_method',
                      'admin_notes']:
            if app.orig_value_of(field) != getattr(app, field):
                return 'Your application has been {} and may no longer be updated'\
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


ArtShowPiece.required = [('name', 'Name'),
                         ('for_sale','If this piece is for sale'),
                         ('gallery', 'Gallery'),
                         ('type', 'Type'),
                         ('media', 'Media')]


@validation.ArtShowPiece
def print_run_if_print(piece):
    if piece.type == c.PRINT:
        if not piece.print_run_num:
            return "Please enter the piece's edition number"
        if not piece.print_run_total:
            return "Please enter the total number of prints for this piece's print run"

        try:
            num = int(piece.print_run_num)
            total = int(piece.print_run_total)
            if total <= 0:
                return "Print runs must have at least 1 print"
            if num <= 0:
                return "A piece must be at least edition 1 of {}".format(total)
            if total < num:
                return "A piece's edition number cannot be higher than the total print run"
        except Exception:
            return "What you entered for the print edition or run total ({}/{}) isn't even a number".format(piece.print_run_num, piece.print_run_total)


@validation.ArtShowPiece
def price_checks_if_for_sale(piece):
    if piece.for_sale:
        if not piece.opening_bid:
            return "Please enter an opening bid for this piece"

        try:
            price = int(piece.opening_bid)
            if price <= 0:
                return "A piece must cost more than $0"
        except Exception:
            return "What you entered for the opening bid ({}) isn't even a number".format(piece.opening_bid)


        if not piece.no_quick_sale:
            if not piece.quick_sale_price:
                "Please enter a quick sale price"

            try:
                price = int(piece.quick_sale_price)
                if price <= 0:
                    return "A piece must cost more than $0, even after bidding ends"
            except Exception:
                return "What you entered for the quick sale price ({}) isn't even a number".format(piece.quick_sale_price)


@validation.ArtShowPiece
def name_max_length(piece):
    if len(piece.name) > c.PIECE_NAME_LENGTH:
        return "Piece names must be {} characters or fewer.".format(c.PIECE_NAME_LENGTH)


@validation.ArtShowPiece
def media_max_length(piece):
    if len(piece.media) > 15:
        return "The description of the piece's media must be 15 characters or fewer."


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
