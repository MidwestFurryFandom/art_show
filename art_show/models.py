import random
import string

from uber.config import c
from uber.models import Session
from uber.models import MagModel
from uber.decorators import cost_property, presave_adjustment, render
from uber.models.types import Choice, DefaultColumn as Column,\
    default_relationship as relationship

from residue import CoerceUTF8 as UnicodeText, UUID
from sqlalchemy.orm import backref
from sqlalchemy.types import Integer, Boolean
from sqlalchemy.orm import joinedload
from sqlalchemy.schema import ForeignKey, Index


@Session.model_mixin
class SessionMixin:
    def art_show_apps(self):
        return self.query(ArtShowApplication)\
            .options(joinedload('attendee')).all()

    def attendee_from_art_show_app(self, **params):
        message = ''
        if params.get('attendee_id', ''):
            try:
                attendee = self.attendee(id=params['attendee_id'])
            except Exception:
                try:
                    attendee = self.attendee(public_id=params['attendee_id'])
                except Exception:
                    return \
                        None, \
                        'The confirmation number you entered is not valid, ' \
                        'or there is no matching badge.'

            if attendee.badge_status in [c.INVALID_STATUS, c.WATCHED_STATUS]:
                return None, \
                       'This badge is invalid. Please contact registration.'
            elif attendee.art_show_applications:
                return None, \
                       'There is already an art show application ' \
                       'for that badge!'
        else:
            attendee_params = {
                attr: params.get(attr, '')
                for attr in ['first_name', 'last_name', 'email']}
            attendee = self.attendee(attendee_params, restricted=True,
                                     ignore_csrf=True)
            attendee.placeholder = True
            if params.get('not_attending', ''):
                attendee.badge_status = c.NOT_ATTENDING
            if not params.get('email', ''):
                message = 'Email address is a required field.'
        return attendee, message

    def lookup_agent_code(self, code):
        return self.query(ArtShowApplication).filter_by(agent_code=code).all()


class ArtShowApplication(MagModel):
    attendee_id = Column(UUID, ForeignKey('attendee.id', ondelete='SET NULL'),
                         nullable=True)
    attendee = relationship('Attendee', foreign_keys=attendee_id, cascade='save-update, merge',
                                  backref=backref('art_show_applications', cascade='save-update, merge'))
    agent_id = Column(UUID, ForeignKey('attendee.id', ondelete='SET NULL'),
                         nullable=True)
    agent = relationship('Attendee', foreign_keys=agent_id, cascade='save-update, merge',
                            backref=backref('art_agent_applications', cascade='save-update, merge'))
    agent_code = Column(UnicodeText)
    artist_name = Column(UnicodeText)
    artist_id = Column(UnicodeText, admin_only=True)
    banner_name = Column(UnicodeText)
    check_payable = Column(UnicodeText)
    hotel_name = Column(UnicodeText)
    hotel_room_num = Column(UnicodeText)
    panels = Column(Integer, default=0)
    panels_ad = Column(Integer, default=0)
    tables = Column(Integer, default=0)
    tables_ad = Column(Integer, default=0)
    description = Column(UnicodeText)
    website = Column(UnicodeText)
    special_needs = Column(UnicodeText)
    status = Column(Choice(c.ART_SHOW_STATUS_OPTS), default=c.UNAPPROVED)
    delivery_method = Column(Choice(c.ART_SHOW_DELIVERY_OPTS), default=c.BRINGING_IN)
    admin_notes = Column(UnicodeText, admin_only=True)
    base_price = Column(Integer, default=0, admin_only=True)
    overridden_price = Column(Integer, nullable=True, admin_only=True)

    email_model_name = 'app'

    @presave_adjustment
    def _cost_adjustments(self):
        self.base_price = self.default_cost

        if self.overridden_price == '':
            self.overridden_price = None

    @presave_adjustment
    def add_artist_id(self):
        if self.status == c.APPROVED and not self.artist_id:
            from uber.models import Session
            with Session() as session:
                # Kind of inefficient, but doing one big query for all the existing
                # codes will be faster than a separate query for each new code.
                old_codes = set(
                    s for (s,) in session.query(ArtShowApplication.artist_id).all())

            code_candidate = self._get_code_from_name(self.artist_name, old_codes) \
                             or self._get_code_from_name(self.attendee.last_name, old_codes) \
                             or self._get_code_from_name(self.attendee.first_name, old_codes)

            if not code_candidate:
                # We're out of manual alternatives, time for a random code
                code_candidates = ''.join([random.choice(string.ascii_uppercase) for _ in range(100)])
                for code_candidate in code_candidates:
                    if code_candidate not in old_codes:
                        break

            self.artist_id = code_candidate.upper()

    def _get_code_from_name(self, name, old_codes):
        name = "".join(list(filter(lambda char: char.isalpha(), name)))
        if len(name) >= 3:
            return name[:3] if name[:3].upper() not in old_codes else None

    @presave_adjustment
    def add_new_agent_code(self):
        if not self.agent_code and self.delivery_method == c.AGENT:
            self.agent_code = self.new_agent_code()

    def new_agent_code(self):
        from uber.models import PromoCode
        new_agent_code = PromoCode.generate_random_code()

        self.session.add(PromoCode(
            discount=0,
            discount_type=PromoCode._FIXED_DISCOUNT,
            code=new_agent_code))

        return new_agent_code

    @property
    def incomplete_reason(self):
        if self.status != c.APPROVED:
            return self.status_label
        if self.delivery_method == c.BY_MAIL \
                and not self.attendee.full_address:
            return "Mailing address required"
        if self.attendee.badge_status == c.NEW_STATUS:
            return "Missing registration info"

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

    @cost_property
    def panels_ad_cost(self):
        return self.panels_ad * c.COST_PER_PANEL

    @cost_property
    def tables_ad_cost(self):
        return self.tables_ad * c.COST_PER_TABLE

    @cost_property
    def mailing_fee(self):
        return c.ART_MAILING_FEE if self.delivery_method == c.BY_MAIL else 0

    @property
    def is_unpaid(self):
        return self.attendee.amount_unpaid > 0

    @property
    def highest_piece_id(self):
        if len(self.art_show_pieces) > 1:
            return sorted([piece for piece in self.art_show_pieces if piece.piece_id], key=lambda piece: piece.piece_id, reverse=True)[0].piece_id
        else:
            return 0


class ArtShowPiece(MagModel):
    app_id = Column(UUID, ForeignKey('art_show_application.id',
                                     ondelete='SET NULL'), nullable=True)
    app = relationship('ArtShowApplication', foreign_keys=app_id,
                         cascade='save-update, merge',
                         backref=backref('art_show_pieces',
                                         cascade='save-update, merge'))
    piece_id = Column(Integer)
    name = Column(UnicodeText)
    for_sale = Column(Boolean, default=False)
    type = Column(Choice(c.ART_PIECE_TYPE_OPTS), default=c.PRINT)
    gallery = Column(Choice(c.ART_PIECE_GALLERY_OPTS), default=c.GENERAL)
    media = Column(UnicodeText)
    print_run_num = Column(Integer, default=0, nullable=True)
    print_run_total = Column(Integer, default=0, nullable=True)
    opening_bid = Column(Integer, default=0, nullable=True)
    quick_sale_price = Column(Integer, default=0, nullable=True)
    no_quick_sale = Column(Boolean, default=False)

    status = Column(Choice(c.ART_PIECE_STATUS_OPTS), default=c.EXPECTED,
                    admin_only=True)

    @presave_adjustment
    def create_piece_id(self):
        if not self.piece_id:
            self.piece_id = int(self.app.highest_piece_id) + 1


@Session.model_mixin
class Attendee:

    @presave_adjustment
    def not_attending_need_not_pay(self):
        if self.badge_status == c.NOT_ATTENDING:
            self.paid = c.NEED_NOT_PAY

    @presave_adjustment
    def add_as_agent(self):
        if self.promo_code:
            art_apps = self.session.lookup_agent_code(self.promo_code.code)
            for app in art_apps:
                app.agent_id = self.id

    @cost_property
    def art_show_app_cost(self):
        cost = 0
        if self.art_show_applications:
            for app in self.art_show_applications:
                cost += app.total_cost
        return cost

    @property
    def full_address(self):
        if self.country and self.city \
                and (self.region
                     or self.country not in ['United States', 'Canada']) \
                and self.address1:
            return True
