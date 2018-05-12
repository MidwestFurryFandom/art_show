from uber.automated_emails import AutomatedEmailFixture
from .models import ArtShowApplication
from uber.config import c
from sqlalchemy.orm import subqueryload
from uber.utils import days_before


AutomatedEmailFixture.queries.update({
    ArtShowApplication:
        lambda session: session.query(ArtShowApplication)
            .options(subqueryload(ArtShowApplication.attendee))
})


class ArtShowAppEmailFixture(AutomatedEmailFixture):
    def __init__(self, subject, template, filter, ident, **kwargs):
        AutomatedEmailFixture.__init__(self, ArtShowApplication, subject,
                                       template,
                                       lambda app: True and filter(app),
                                       ident,
                                       sender=c.ART_SHOW_EMAIL, **kwargs)


ArtShowAppEmailFixture(
    'Your {EVENT_NAME} Art Show application has been approved',
    'art_show/approved.html',
    lambda a: a.status == c.APPROVED,
    needs_approval=False,
    ident='art_show_approved')

ArtShowAppEmailFixture(
    'Your {EVENT_NAME} Art Show application has been waitlisted',
    'art_show/waitlisted.txt',
    lambda a: a.status == c.WAITLISTED,
    needs_approval=False,
    ident='art_show_waitlisted')

ArtShowAppEmailFixture(
    'Your {EVENT_NAME} Art Show application has been declined',
    'art_show/declined.txt',
    lambda a: a.status == c.DECLINED,
    needs_approval=False,
    ident='art_show_declined')

ArtShowAppEmailFixture(
    'Reminder to pay for your {EVENT_NAME} Art Show application',
    'art_show/payment_reminder.txt',
    lambda a: a.status == c.APPROVED and a.is_unpaid,
    when=days_before(14, c.ART_SHOW_PAYMENT_DUE),
    needs_approval=False,
    ident='art_show_payment_reminder')
