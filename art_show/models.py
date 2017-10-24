from . import *


@Session.model_mixin
class SessionMixin:
    def art_show_apps(self):
        return self.query(ArtShowApplication).options(joinedload('attendee')).all()

    def attendee_from_art_show_app(self, **params):
        message = ''
        if params.get('attendee_id', ''):
            try:
                attendee = self.attendee(id=params['attendee_id'])
            except:
                try:
                    attendee = self.attendee(public_id=params['attendee_id'])
                except:
                    return None, 'The confirmation number you entered is not valid, or there is no matching badge.'

            if attendee.badge_status in [c.INVALID_STATUS, c.WATCHED_STATUS]:
                return None, 'This badge is invalid. Please contact registration.'
            elif attendee.art_show_application:
                return None, 'There is already an art show application for that badge!'
        else:
            attendee_params = {attr: params.get(attr, '') for attr in ['first_name', 'last_name', 'email']}
            attendee = self.attendee(attendee_params, restricted=True, ignore_csrf=True)
            attendee.placeholder = True
            if params.get('not_attending', ''):
                attendee.badge_status = c.NOT_ATTENDING
            if not params.get('email', ''):
                message = 'Email address is a required field.'
        return attendee, message


class ArtShowApplication(MagModel):
    attendee_id = Column(UUID, ForeignKey('attendee.id', ondelete='SET NULL'), nullable=True)
    artist_name = Column(UnicodeText)
    panels = Column(Integer, default=0)
    tables = Column(Integer, default=0)
    description = Column(UnicodeText)
    website = Column(UnicodeText)
    special_needs = Column(UnicodeText)
    status = Column(Choice(c.ART_SHOW_STATUS_OPTS), default=c.UNAPPROVED)
    admin_notes = Column(UnicodeText, admin_only=True)

    base_price = Column(Integer, default=0, admin_only=True)
    overridden_price = Column(Integer, nullable=True, admin_only=True)

    email_model_name = 'app'

    @presave_adjustment
    def _cost_adjustments(self):
        self.base_price = self.default_cost

        if self.overridden_price == '':
            self.overridden_price = None

    @property
    def total_cost(self):
        if self.status != c.APPROVED:
            return 0
        else:
            return self.potential_cost

    @property
    def potential_cost(self):
        if self.overridden_price is not None:
            return self.overridden_price
        else:
            return self.base_price or self.default_cost or 0

    @property
    def email(self):
        return self.attendee.email

    @cost_property
    def panels_cost(self):
        return self.panels * c.COST_PER_PANEL

    @cost_property
    def tables_cost(self):
        return self.tables * c.COST_PER_TABLE

    @property
    def is_unpaid(self):
        return self.attendee.amount_unpaid > 0


@Session.model_mixin
class Attendee:
    art_show_application = relationship('ArtShowApplication', backref='attendee', uselist=False)

    @presave_adjustment
    def not_attending_need_not_pay(self):
        if self.badge_status == c.NOT_ATTENDING:
            self.paid = c.NEED_NOT_PAY

    @cost_property
    def art_show_app_cost(self):
        if self.art_show_application:
            return self.art_show_application.total_cost
        else:
            return 0
