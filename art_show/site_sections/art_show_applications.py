import cherrypy

from uber.config import c
from uber.decorators import all_renderable, render, credit_card
from uber.errors import HTTPRedirect
from uber.tasks.email import send_email
from uber.utils import Charge, check


@all_renderable()
class Root:
    def index(self, session, message='', **params):
        app = session.art_show_application(params, restricted=True,
                                           ignore_csrf=True)
        attendee = None

        if cherrypy.request.method == 'GET' and params.get('attendee_id', ''):
            try:
                attendee = session.attendee(id=params['attendee_id'])
            except Exception:
                message = \
                    'We could not find you by your confirmation number. ' \
                    'Is the URL correct?'

        if cherrypy.request.method == 'POST':
            attendee, message = session.attendee_from_art_show_app(**params)

            # We do an extra check here to handle new attendees
            if attendee and attendee.badge_status == c.NOT_ATTENDING \
                    and app.delivery_method == c.BRINGING_IN:
                message = 'You cannot bring your own art ' \
                          'if you are not attending.'

            message = message or check(attendee) or check(app, prereg=True)
            if not message:
                if c.AFTER_ART_SHOW_WAITLIST:
                    app.status = c.WAITLISTED
                session.add(attendee)
                app.attendee = attendee
                attendee.art_show_application = app
                session.add(app)
                send_email(
                    c.ART_SHOW_EMAIL,
                    app.email,
                    'Art Show Application Received',
                    render('emails/art_show/application.html',
                           {'app': app}), 'html',
                    model=app)
                send_email(
                    c.ART_SHOW_EMAIL,
                    c.ART_SHOW_EMAIL,
                    'Art Show Application Received',
                    render('emails/art_show/reg_notification.txt',
                           {'app': app}), model=app)
                session.commit()
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
        app = session.art_show_application(params, restricted=True,
                                           ignore_csrf=True)

        if cherrypy.request.method == 'POST':
            message = check(app, prereg=True)
            if not message:
                session.add(app)
                send_email(
                    c.ART_SHOW_EMAIL,
                    app.email,
                    'Art Show Application Updated',
                    render('emails/art_show/appchange_notification.html',
                           {'app': app}), model=app)
                raise HTTPRedirect('edit?id={}&message={}', app.id,
                                   'Your application has been updated')
            else:
                session.rollback()

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
        [attendee] = charge.attendees
        attendee = session.merge(attendee)
        app = attendee.art_show_application
        message = charge.charge_cc(session, stripeToken)
        if message:
            raise HTTPRedirect('edit?id={}&message={}',
                               attendee.art_show_application.id, message)
        else:
            attendee.amount_paid += charge.dollar_amount
            session.add(attendee)
            send_email(
                c.ART_SHOW_EMAIL,
                c.ART_SHOW_EMAIL,
                'Art Show Payment Received',
                render('emails/art_show/payment_notification.txt',
                       {'app': app}), model=app)
            send_email(
                c.ART_SHOW_EMAIL,
                app.email,
                'Art Show Payment Received',
                render('emails/art_show/payment_confirmation.txt',
                       {'app': app}), model=app)
            raise HTTPRedirect('edit?id={}&message={}',
                               attendee.art_show_application.id,
                               'Your payment has been accepted!')
