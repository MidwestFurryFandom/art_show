from uber.config import c
from uber.decorators import all_renderable
from uber.models import Attendee
from uber.utils import localized_now

from art_show.config import config
from art_show.models import ArtShowApplication, ArtShowBidder, ArtShowPayment, ArtShowPiece, ArtShowReceipt

@all_renderable(c.ART_SHOW)
class Root:
    def index(self, session, message=''):
        return {
            'message': message,
        }

    def sales_invoices(self, session, message='', start=1, end=''):
        receipts = []
        try:
            start = int(start)
        except:
            message = "Starting invoice number must be an integer."
        if end:
            try:
                end = int(end)
            except:
                message = "Ending invoice number must be an integer or blank."

        if not message:
            filters = [ArtShowReceipt.invoice_num >= start, ArtShowReceipt.closed != None]
            if end:
                filters.append(ArtShowReceipt.invoice_num <= end)

            receipts = session.query(ArtShowReceipt).join(ArtShowReceipt.attendee)\
                .filter(*filters).order_by(ArtShowReceipt.closed.desc()).all()
            if not receipts:
                message = "No invoices found!"

        return {
            'message': message,
            'receipts': receipts,
            'start': start,
            'end': end,
        }

    def high_bids(self, session, message='', admin_report=None):
        return {
            'message': message,
            'won_pieces': session.query(ArtShowPiece).join(ArtShowPiece.buyer).join(Attendee.art_show_bidder)
                .filter(ArtShowPiece.winning_bid.isnot(None), ArtShowPiece.status == c.SOLD),
            'admin_report': admin_report,
            'now': localized_now(),
        }

    def pieces_by_status(self, session, message='', **params):
        filters = []
        if 'yes_status' in params:
            try:
                yes_status = [int(params['yes_status'])]
            except Exception:
                yes_status = list(params['yes_status'])
            filters.append(ArtShowApplication.art_show_pieces.any(ArtShowPiece.status.in_(yes_status)))
        if 'no_status' in params:
            filters.append(~ArtShowApplication.art_show_pieces.any(ArtShowPiece.status.in_(params['no_status'])))

        apps = session.query(ArtShowApplication).join(ArtShowApplication.art_show_pieces).filter(*filters).all()

        if not apps:
            message = 'No pieces found!'
        return {
            'message': message,
            'apps': apps,
        }