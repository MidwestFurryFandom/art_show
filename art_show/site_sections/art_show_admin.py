import cherrypy
from sqlalchemy import or_, and_

from uber.config import c
from uber.decorators import ajax, all_renderable, credit_card, unrestricted
from uber.errors import HTTPRedirect
from uber.models import Attendee, Tracking, ArbitraryCharge
from uber.utils import Charge, check, localized_now


@all_renderable(c.ART_SHOW)
class Root:
    def index(self, session, message=''):
        return {
            'message': message,
            'applications': session.art_show_apps()
        }

    def form(self, session, new_app='', message='', **params):
        if new_app and 'attendee_id' in params:
            app = session.art_show_application(params, ignore_csrf=True)
        else:
            app = session.art_show_application(params)
        attendee = None
        if cherrypy.request.method == 'POST':
            if new_app:
                attendee, message = \
                    session.attendee_from_art_show_app(**params)
            else:
                attendee = app.attendee
            message = message or check(app)
            if not message:
                if attendee:
                    if params.get('badge_status', ''):
                        attendee.badge_status = params['badge_status']
                    session.add(attendee)
                    app.attendee = attendee
                session.add(app)
                if params.get('save') == 'save_return_to_search':
                    return_to = 'index?'
                else:
                    return_to = 'form?id=' + app.id + '&'
                raise HTTPRedirect(
                    return_to + 'message={}', 'Application updated')
        return {
            'message': message,
            'app': app,
            'attendee': attendee,
            'attendee_id': app.attendee_id or params.get('attendee_id', ''),
            'all_attendees': session.all_attendees(),
            'new_app': new_app
        }

    def pieces(self, session, id, message=''):
        app = session.art_show_application(id)
        return {
            'app': app,
            'message': message,
        }

    def history(self, session, id):
        app = session.art_show_application(id)
        return {
            'app': app,
            'changes': session.query(Tracking).filter(
                or_(Tracking.links.like('%art_show_application({})%'
                                        .format(id)),
                and_(Tracking.model == 'ArtShowApplication',
                     Tracking.fk_id == id)))
                .order_by(Tracking.when).all()
        }

    def ops(self, session, message=''):
        attendee_attrs = session.query(Attendee.id, Attendee.full_name,
                                       Attendee.badge_type, Attendee.badge_num) \
            .filter(Attendee.first_name != '',
                    Attendee.badge_status not in [c.INVALID_STATUS,
                                                  c.WATCHED_STATUS])

        attendees = [
            (id, '{} - {}{}'.format(name.title(), c.BADGES[badge_type],
                                    ' #{}'.format(
                                        badge_num) if badge_num else ''))
            for id, name, badge_type, badge_num in attendee_attrs]

        return {
            'message': message,
            'applications': session.art_show_apps(),
            'all_attendees': sorted(attendees, key=lambda tup: tup[1]),
        }

    @ajax
    def save_and_check_in_out(self, session, **params):
        app = session.art_show_application(params['app_id'])
        attendee = app.attendee

        app.apply(params, restricted=False)

        message = check(app)
        if message:
            session.rollback()
            return {'error': message}
        else:
            if 'check_in' in params and params['check_in']:
                app.checked_in = localized_now()
            if 'check_out' in params and params['check_out']:
                app.checked_out = localized_now()
            session.commit()

        attendee.apply(params, restricted=False)

        message = check(attendee)
        if message:
            session.rollback()
            return {'error': message}
        else:
            session.commit()

        for id in params['piece_ids']:
            piece = session.art_show_piece(id)
            piece_params = dict()
            for field_name in ['gallery', 'status', 'name', 'opening_bid', 'quick_sale_price']:
                piece_params[field_name] = params.get('{}{}'.format(field_name, id), '')

            piece_params['for_sale'] = True if piece_params['opening_bid'] else False
            piece_params['no_quick_sale'] = False if piece_params['quick_sale_price'] else True

            piece.apply(piece_params, restricted=False)
            message = check(piece)
            if message:
                session.rollback()
                break
            else:
                if 'check_in' in params and params['check_in'] and piece.status == c.EXPECTED:
                    piece.status = c.HUNG
                session.commit() # We save as we go so it's less annoying if there's an error

        return {'error': message,
                'success': 'Application updated'}

    @unrestricted
    def sales_charge_form(self, message='', amount=None, description='',
                          sale_id=None):
        charge = None
        if amount is not None:
            if not description:
                message = "You must enter a brief description " \
                          "of what's being sold"
            else:
                charge = Charge(amount=int(100 * float(amount)),
                                description=description)

        return {
            'charge': charge,
            'message': message,
            'amount': amount,
            'description': description,
            'sale_id': sale_id
        }

    @unrestricted
    @credit_card
    def sales_charge(self, session, payment_id, stripeToken):
        charge = Charge.get(payment_id)
        message = charge.charge_cc(session, stripeToken)
        if message:
            raise HTTPRedirect('sales_charge_form?message={}', message)
        else:
            session.add(ArbitraryCharge(
                amount=charge.dollar_amount,
                what=charge.description
            ))
            raise HTTPRedirect('sales_charge_form?message={}',
                               'Charge successfully processed')
