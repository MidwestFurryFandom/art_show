from uber.config import c
from uber.decorators import all_renderable
from uber.utils import localized_now

from sqlalchemy import func

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

    def artist_invoices(self, session, message=''):
        apps = session.query(ArtShowApplication).join(ArtShowApplication.art_show_pieces)\
            .filter(ArtShowApplication.art_show_pieces.any(ArtShowPiece.status.in_([c.SOLD, c.PAID]))).all()
        if not apps:
            message = "No invoices found!"

        return {
            'message': message,
            'apps': apps,
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
            try:
                no_status = [int(params['no_status'])]
            except Exception:
                no_status = list(params['no_status'])
            filters.append(~ArtShowApplication.art_show_pieces.any(ArtShowPiece.status.in_(no_status)))

        apps = session.query(ArtShowApplication).join(ArtShowApplication.art_show_pieces).filter(*filters).all()

        if not apps:
            message = 'No pieces found!'
        return {
            'message': message,
            'apps': apps,
        }

    def summary(self, session, message=''):
        general_pieces = session.query(ArtShowPiece).filter(ArtShowPiece.gallery == c.GENERAL)
        mature_pieces = session.query(ArtShowPiece).filter(ArtShowPiece.gallery == c.MATURE)

        general_sold = general_pieces.filter(ArtShowPiece.status == c.SOLD)
        mature_sold = mature_pieces.filter(ArtShowPiece.status == c.SOLD)

        artists_with_pieces = session.query(ArtShowApplication).filter(ArtShowApplication.art_show_pieces != None)

        all_apps = session.query(ArtShowApplication).all()

        return {
            'message': message,
            'general_sales_sum': sum([piece.sale_price for piece in general_sold]),
            'mature_sales_sum': sum([piece.sale_price for piece in mature_sold]),
            'general_count': general_pieces.count(),
            'mature_count': mature_pieces.count(),
            'general_sold_count': general_sold.count(),
            'mature_sold_count': mature_sold.count(),
            'artist_count': artists_with_pieces.count(),
            'general_panels_count': sum([app.panels for app in all_apps]),
            'mature_panels_count': sum([app.panels_ad for app in all_apps]),
            'general_tables_count': sum([app.tables for app in all_apps]),
            'mature_tables_count': sum([app.tables_ad for app in all_apps]),
            'now': localized_now(),
        }

    def auction_report(self, session, message='', mature=None):
        filters = [ArtShowPiece.status == c.VOICE_AUCTION]

        if mature:
            filters.append(ArtShowPiece.gallery == c.MATURE)
        else:
            filters.append(ArtShowPiece.gallery == c.GENERAL)

        return {
            'message': message,
            'pieces': session.query(ArtShowPiece).filter(*filters).join(ArtShowPiece.app).all(),
            'mature': mature,
            'now': localized_now(),
        }