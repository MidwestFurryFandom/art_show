import cherrypy
from sqlalchemy import or_, and_

from uber.config import c
from uber.decorators import all_renderable, credit_card, unrestricted
from uber.errors import HTTPRedirect
from uber.models import Tracking, ArbitraryCharge
from uber.utils import Charge, check


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
