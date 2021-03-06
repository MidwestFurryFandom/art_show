from datetime import datetime

from uber.automated_emails import AutomatedEmailFixture
from .models import ArtShowApplication
from uber.config import c
from sqlalchemy.orm import subqueryload
from uber.utils import after, days_before


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
    '{EVENT_NAME} Art Show Application Confirmation',
    'art_show/application.html',
    lambda a: a.status == c.UNAPPROVED,
    ident='art_show_confirm')

ArtShowAppEmailFixture(
    'Your {EVENT_NAME} Art Show application has been approved',
    'art_show/approved.html',
    lambda a: a.status == c.APPROVED,
    ident='art_show_approved')

ArtShowAppEmailFixture(
    'Your {EVENT_NAME} Art Show application has been waitlisted',
    'art_show/waitlisted.txt',
    lambda a: a.status == c.WAITLISTED,
    ident='art_show_waitlisted')

ArtShowAppEmailFixture(
    'Your {EVENT_NAME} Art Show application has been declined',
    'art_show/declined.txt',
    lambda a: a.status == c.DECLINED,
    ident='art_show_declined')

ArtShowAppEmailFixture(
    'Reminder to pay for your {EVENT_NAME} Art Show application',
    'art_show/payment_reminder.txt',
    lambda a: a.status == c.APPROVED and a.is_unpaid,
    when=days_before(14, c.ART_SHOW_PAYMENT_DUE),
    ident='art_show_payment_reminder')

ArtShowAppEmailFixture(
    '{EVENT_NAME} Art Show piece entry needed',
    'art_show/pieces_reminder.txt',
    lambda a: a.status == c.PAID and not a.art_show_pieces,
    when=days_before(15, c.EPOCH),
    ident='art_show_pieces_reminder')

ArtShowAppEmailFixture(
    'Reminder to assign an agent for your {EVENT_NAME} Art Show application',
    'art_show/agent_reminder.html',
    lambda a: a.status == c.PAID and not a.agent,
    when=after(c.EVENT_TIMEZONE.localize(datetime(int(c.EVENT_YEAR), 11, 1))),
    ident='art_show_agent_reminder')

ArtShowAppEmailFixture(
    '{EVENT_NAME} Art Show MAIL IN Instructions',
    'art_show/mailing_in.html',
    lambda a: a.status == c.PAID and a.delivery_method == c.BY_MAIL,
    when=days_before(40, c.ART_SHOW_DEADLINE),
    ident='art_show_mail_in')
