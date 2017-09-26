from uber.common import *

ATTENDEE_FIELDS = ['first_name', 'last_name', 'email']


@all_renderable()
class Root:
    def index(self, session, message='', **params):
        app = session.art_show_application(params, restricted=True, ignore_csrf=True)
        attendee = None

        if params.get('attendee_id', ''):
            try:
                attendee = session.attendee(id=params['attendee_id'])
            except:
                message = 'The confirmation number you entered is not valid, or there is no matching badge.'

        if cherrypy.request.method == 'POST':
            if not attendee and not message:
                attendee_params = {attr: params.get(attr, '') for attr in ATTENDEE_FIELDS}
                attendee = attendee or session.attendee(attendee_params, restricted=True, ignore_csrf=True)
                attendee.placeholder = True
                if params.get('not_attending', ''):
                    attendee.badge_status = c.NOT_ATTENDING
                if not params.get('email', ''):
                    message = 'We need your email address to send you your application confirmation.'
                else:
                    message = check(attendee)

            message = message or check(app)
            if not message:
                session.add(attendee)
                app.attendee = attendee
                session.add(app)
                raise HTTPRedirect('confirmation?id={}', app.id)

        return {
            'message': message,
            'app': app,
            'attendee': attendee,
            'attendee_id': app.attendee_id or params.get('attendee_id', ''),
            'not_attending': params.get('not_attending', ''),
            'new_badge': params.get('new_badge', '')
        }

    def edit(self, session, message='', **params):
        app = session.art_show_application(params, restricted=True, ignore_csrf=True)

        if cherrypy.request.method == 'POST':
            message = check(app)
            if not message:
                session.add(app)
                raise HTTPRedirect('edit?id={}&message={}', app.id, 'Your application has been updated')

        return {
            'message': message,
            'app': app,
            'charge': Charge(app.attendee)
        }

    def confirmation(self, session, id):
        return {'app': session.art_show_application(id)}

    @credit_card
    def process_art_show_payment(self, session, payment_id, stripeToken):
        charge = Charge.get(payment_id)
        message = charge.charge_cc(session, stripeToken)
        if message:
            raise HTTPRedirect('edit?id={}&message={}', app.id, message)
        else:
            attendee.amount_paid += charge.dollar_amount
            session.add(attendee)
            raise HTTPRedirect('edit?id={}&message={}', app.id, 'Your payment has been accepted!')
