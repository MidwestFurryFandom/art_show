from uber.config import c
from uber.decorators import all_renderable

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