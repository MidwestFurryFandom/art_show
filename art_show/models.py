from . import *


class ArtShowApplication(MagModel):
    attendee_id = Column(UUID, ForeignKey('attendee.id', ondelete='SET NULL'), nullable=True)
    panels = Column(Integer, default=0)
    tables = Column(Integer, default=0)
    description = Column(UnicodeText)
    website = Column(UnicodeText)
    special_needs = Column(UnicodeText)
    status = Column(Choice(c.ART_SHOW_STATUS_OPTS), default=c.UNAPPROVED)
    admin_notes = Column(UnicodeText, admin_only=True)

    base_price = Column(Integer, default=0, admin_only=True)
    overridden_price = Column(Integer, nullable=True, admin_only=True)

    @presave_adjustment
    def _cost_adjustments(self):
        if not self.base_price:
            self.base_price = self.total_cost

    @property
    def total_cost(self):
        if self.status != c.APPROVED:
            return 0
        elif self.overridden_price is not None:
            return self.overridden_price
        else:
            return self.base_price or self.default_cost

    @cost_property
    def panels_cost(self):
        return self.panels * c.COST_PER_PANEL

    @cost_property
    def tables_cost(self):
        return self.tables * c.COST_PER_TABLE


@Session.model_mixin
class Attendee:
    art_show_application = relationship('ArtShowApplication', backref='attendee')

    @presave_adjustment
    def not_attending_need_not_pay(self):
        if self.badge_status == c.NOT_ATTENDING:
            self.paid = c.NEED_NOT_PAY

    @cost_property
    def art_show_app_cost(self):
        if self.art_show_application:
            return self.art_show_application.total_cost
        return 0
