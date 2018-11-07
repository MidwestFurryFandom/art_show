import cherrypy
import treepoem
import os
import re
import math

from decimal import Decimal
from sqlalchemy import or_, and_
from io import BytesIO

from uber.config import c
from uber.decorators import ajax, all_renderable, credit_card, unrestricted
from uber.errors import HTTPRedirect
from uber.models import Attendee, Tracking, ArbitraryCharge
from uber.utils import Charge, check, localized_now, Order

from art_show.config import config
from art_show.models import ArtShowApplication, ArtShowBidder, ArtShowPayment, ArtShowPiece, ArtShowReceipt

@all_renderable(c.ART_SHOW)
class Root:
    def index(self, session, message=''):
        return {
            'message': message,
            'applications': session.art_show_apps()
        }

    def form(self, session, new_app='', message='', **params):
        if new_app and 'attendee_id' in params:
            app = session.art_show_application(params, ignore_csrf=True)
        else:
            app = session.art_show_application(params)
        attendee = None
        app_paid = max(0, app.attendee.amount_paid - (app.attendee.total_cost - app.total_cost))
        if cherrypy.request.method == 'POST':
            if new_app:
                attendee, message = \
                    session.attendee_from_art_show_app(**params)
            else:
                attendee = app.attendee
            message = message or check(app)
            if not message:
                if attendee:
                    if params.get('badge_status', ''):
                        attendee.badge_status = params['badge_status']
                    if 'app_paid' in params \
                            and int(params['app_paid']) != app_paid \
                            and int(params['app_paid']) > 0:
                        attendee.amount_paid -= app_paid
                        attendee.amount_paid += int(params['app_paid'])
                    session.add(attendee)
                    app.attendee = attendee

                if 'mark_paid' in params:
                    app.status = c.APPROVED if int(params['mark_paid']) == 0 else c.PAID
                session.add(app)
                if params.get('save') == 'save_return_to_search':
                    return_to = 'index?'
                else:
                    return_to = 'form?id=' + app.id + '&'
                raise HTTPRedirect(
                    return_to + 'message={}', 'Application updated')
        return {
            'message': message,
            'app': app,
            'attendee': attendee,
            'app_paid': app_paid,
            'attendee_id': app.attendee_id or params.get('attendee_id', ''),
            'all_attendees': session.all_attendees(),
            'new_app': new_app
        }

    def pieces(self, session, id, message=''):
        app = session.art_show_application(id)
        return {
            'app': app,
            'message': message,
        }

    def history(self, session, id):
        app = session.art_show_application(id)
        return {
            'app': app,
            'changes': session.query(Tracking).filter(
                or_(Tracking.links.like('%art_show_application({})%'
                                        .format(id)),
                and_(Tracking.model == 'ArtShowApplication',
                     Tracking.fk_id == id)))
                .order_by(Tracking.when).all()
        }

    def ops(self, session, message=''):
        return {
            'message': message,
        }

    def close_out(self, session, message='', piece_code='', bidder_num='', **params):
        found_piece, found_bidder, data_error = None, None, ''

        if piece_code:
            if len(piece_code.split('-')) != 2:
                data_error = 'Please enter just one piece code.'
            else:
                artist_id, piece_id = piece_code.split('-')
                try:
                    piece_id = int(piece_id)
                except Exception:
                    data_error = 'Please use the format XXX-# for the piece code.'

            if not data_error:
                piece = session.query(ArtShowPiece).join(ArtShowPiece.app).filter(
                    ArtShowApplication.artist_id.ilike('%{}%'.format(artist_id)),
                    ArtShowPiece.piece_id == piece_id
                )
                if not piece.count():
                    message = 'Could not find piece with code {}.'.format(piece_code)
                elif piece.count() > 1:
                    message = 'Multiple pieces matched the code you entered for some reason.'
                else:
                    found_piece = piece.one()

                if bidder_num:
                    bidder = session.query(ArtShowBidder).filter(ArtShowBidder.bidder_num.ilike(bidder_num))
                    if not bidder.count():
                        message = 'Could not find bidder with number {}.'.format(bidder_num)
                    elif bidder.count() > 1:
                        message = 'Multiple bidders matched the number you entered for some reason.'
                    else:
                        found_bidder = bidder.one().attendee
            else:
                message = data_error

        return {
            'message': message,
            'piece_code': piece_code,
            'bidder_num': bidder_num,
            'piece': found_piece,
            'bidder': found_bidder
        }

    def close_out_piece(self, session, message='', **params):
        if 'id' not in params:
            raise HTTPRedirect('close_out?piece_code={}&bidder_num={}&message={}',
                               params['piece_code'], params['bidder_num'], 'Error: no piece ID submitted.')

        piece = session.art_show_piece(params)
        session.add(piece)

        if piece.status == c.QUICK_SALE and not piece.valid_quick_sale:
            message = 'This piece does not have a valid quick-sale price.'

        if piece.status == c.RETURN and piece.valid_quick_sale:
            message = 'This piece has a quick-sale price and so cannot yet be marked as Return to Artist.'

        if 'bidder_id' not in params:
            if piece.status == c.SOLD:
                message = 'You cannot mark a piece as Sold without a bidder. Please add a bidder number in step 1.'
            if piece.winning_bid:
                message = 'You cannot enter a winning bid without a bidder. Please add a bidder number in step 1.'

        if piece.status != c.SOLD:
            if 'bidder_id' in params:
                message = 'You cannot assign a piece to a bidder\'s receipt without marking it as Sold.'
            if piece.winning_bid:
                message = 'You cannot enter a winning bid for a piece without also marking it as Sold.'

        if piece.status == c.SOLD and not piece.winning_bid:
            message = 'Please enter the winning bid for this piece.'

        if piece.status == c.PAID:
            message = 'Please process sales via the sales page.'

        if 'bidder_id' in params:
            attendee = session.attendee(params['bidder_id'])
            if not attendee:
                message = 'Attendee not found for some reason.'
            elif not attendee.art_show_receipt:
                receipt = ArtShowReceipt(attendee=attendee)
                session.add(receipt)
                session.commit()
            else:
                receipt = attendee.art_show_receipt

            if not message:
                piece.receipt = receipt

        if message:
            session.rollback()
            raise HTTPRedirect('close_out?piece_code={}&bidder_num={}&message={}',
                               params['piece_code'], params['bidder_num'], message)
        else:
            raise HTTPRedirect('close_out?message={}',
                               'Close-out successful for piece {}'.format(piece.artist_and_piece_id))

    def artist_check_in_out(self, session, checkout=False, message=''):
        filters = []
        if checkout:
            filters.append(ArtShowApplication.checked_in != None)
        else:
            filters.append(ArtShowApplication.checked_out == None)

        applications = session.query(ArtShowApplication).join(ArtShowApplication.attendee).filter(
            ArtShowApplication.status == c.PAID).filter(*filters).all()

        return {
            'message': message,
            'applications': applications,
            'checkout': checkout,
        }

    def print_check_in_out_form(self, session, id, checkout='', **params):
        app = session.art_show_application(id)

        return {
            'model': app,
            'type': 'artist',
            'checkout': checkout,
        }

    @ajax
    def save_and_check_in_out(self, session, **params):
        app = session.art_show_application(params['app_id'])
        attendee = app.attendee
        success = 'Application updated'

        app.apply(params, restricted=False)

        message = check(app)
        if message:
            session.rollback()
            return {'error': message}
        else:
            if 'check_in' in params and params['check_in']:
                app.checked_in = localized_now()
                success = 'Artist successfully checked-in'
            if 'check_out' in params and params['check_out']:
                app.checked_out = localized_now()
                success = 'Artist successfully checked-out'
            session.commit()

        if 'check_in' in params:
            attendee_params = dict(params)
            for field_name in ['country', 'region', 'zip_code', 'address1', 'address2', 'city']:
                attendee_params[field_name] = params.get('attendee_{}'.format(field_name), '')

            attendee.apply(attendee_params, restricted=False)

            if c.COLLECT_FULL_ADDRESS and attendee.country == 'United States':
                attendee.international = False
            elif c.COLLECT_FULL_ADDRESS:
                attendee.international = True

            message = check(attendee)
            if message:
                session.rollback()
                return {'error': message}
            else:
                session.commit()

        piece_ids = params.get('piece_ids' + app.id)

        if piece_ids:
            try:
                session.art_show_piece(piece_ids)
            except Exception:
                pieces = piece_ids
            else:
                pieces = [piece_ids]

            for id in pieces:
                piece = session.art_show_piece(id)
                piece_params = dict()
                for field_name in ['gallery', 'status', 'name', 'opening_bid', 'quick_sale_price']:
                    piece_params[field_name] = params.get('{}{}'.format(field_name, id), '')

                # Correctly handle admins entering '0' for a price
                try:
                    opening_bid = int(piece_params['opening_bid'])
                except Exception:
                    opening_bid = piece_params['opening_bid']
                try:
                    quick_sale_price = int(piece_params['quick_sale_price'])
                except Exception:
                    quick_sale_price = piece_params['quick_sale_price']

                piece_params['for_sale'] = True if opening_bid else False
                piece_params['no_quick_sale'] = False if quick_sale_price else True

                piece.apply(piece_params, restricted=False)
                message = check(piece)
                if message:
                    session.rollback()
                    break
                else:
                    if 'check_in' in params and params['check_in'] and piece.status == c.EXPECTED:
                        piece.status = c.HUNG
                    elif 'check_out' in params and params['check_out'] and piece.status == c.HUNG:
                        piece.status = c.RETURN
                    session.commit()  # We save as we go so it's less annoying if there's an error

        return {
            'id': app.id,
            'error': message,
            'success': success,
        }

    @unrestricted
    def bid_sheet_barcode_generator(self, data):
        bid_sheet_barcode = treepoem.generate_barcode(
            barcode_type='code39',
            data=data,
            options={},
        )
        buffer = BytesIO()
        bid_sheet_barcode.save(buffer, "PNG")
        buffer.seek(0)
        png_file_output = cherrypy.lib.file_generator(buffer)

        # set response headers last so that exceptions are displayed properly to the client
        cherrypy.response.headers['Content-Type'] = "image/png"

        return png_file_output

    def bid_sheet_pdf(self, session, id, **params):
        import fpdf

        app = session.art_show_application(id)

        if 'piece_id' in params:
            pieces = [session.art_show_piece(params['piece_id'])]
        elif 'piece_ids' in params and params['piece_ids']:
            expanded_ids = re.sub(
                r'(\d+)-(\d+)',
                lambda match: ','.join(
                    str(i) for i in range(
                        int(match.group(1)),
                        int(match.group(2)) + 1
                    )
                ), params['piece_ids']
            )
            id_list = [id.strip() for id in expanded_ids.split(',')]
            pieces = session.query(ArtShowPiece)\
                .filter(ArtShowPiece.piece_id.in_(id_list))\
                .filter(ArtShowPiece.app_id == app.id)\
                .all()
        else:
            pieces = app.art_show_pieces

        pdf = fpdf.FPDF(unit='pt', format='letter')
        pdf.add_font('3of9', '', os.path.join(config['module_root'], 'free3of9.ttf'), uni=True)
        for index, piece in enumerate(sorted(pieces, key=lambda piece: piece.piece_id)):
            sheet_num = index % 4
            xplus = yplus = 0
            if sheet_num == 0:
                pdf.add_page()
            if sheet_num in [1, 3]:
                xplus = 306
            if sheet_num in [2, 3]:
                yplus = 396

            # Location, Piece ID, and barcode
            pdf.image(os.path.join(config['module_root'], 'bidsheet.png'), x=0 + xplus, y=0 + yplus, w=306)
            pdf.set_font("Arial", size=10)
            pdf.set_xy(81 + xplus, 27 + yplus)
            pdf.cell(80, 16, txt=piece.app.locations, ln=1, align="C")
            pdf.set_font("3of9", size=22)
            pdf.set_xy(163 + xplus, 15 + yplus)
            pdf.cell(132, 22, txt=piece.barcode_data, ln=1, align="C")
            pdf.set_font("Arial", size=8, style='B')
            pdf.set_xy(163 + xplus, 32 + yplus)
            pdf.cell(132, 12, txt=piece.barcode_data, ln=1, align="C")

            # Artist, Title, Media
            pdf.set_font("Arial", size=12)
            pdf.set_xy(81 + xplus, 54 + yplus)
            pdf.cell(160, 24,
                     txt=(piece.app.display_name),
                     ln=1, align="C")
            pdf.set_xy(81 + xplus, 80 + yplus)
            pdf.cell(160, 24, txt=piece.name, ln=1, align="C")
            pdf.set_xy(81 + xplus, 105 + yplus)
            pdf.cell(
                160, 24,
                txt=piece.media +
                    (' ({} of {})'.format(piece.print_run_num, piece.print_run_total) if piece.type == c.PRINT else ''),
                ln=1, align="C"
            )

            # Type, Minimum Bid, QuickSale Price
            pdf.set_font("Arial", size=10)
            pdf.set_xy(242 + xplus, 54 + yplus)
            pdf.cell(53, 24, txt=piece.type_label, ln=1, align="C")
            pdf.set_font("Arial", size=8)
            pdf.set_xy(242 + xplus, 90 + yplus)
            pdf.cell(53, 14, txt=('${:,.2f}'.format(piece.opening_bid)) if piece.valid_for_sale else 'N/A', ln=1)
            pdf.set_xy(242 + xplus, 116 + yplus)
            pdf.cell(
                53, 14, txt=('${:,.2f}'.format(piece.quick_sale_price)) if piece.valid_quick_sale else 'N/A', ln=1)


        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=bidsheets.pdf'
        return pdf.output(dest='S').encode('latin-1')

    def bidder_signup(self, session, message='', page=1, search_text='', order=''):
        filters = []
        search_text = search_text.strip()
        if search_text:
            order = order or 'badge_printed_name'
            if re.match('\w-[0-9]{4}', search_text):
                attendees = session.query(Attendee).join(Attendee.art_show_bidder).filter(
                    ArtShowBidder.bidder_num.ilike('%{}%'.format(search_text[2:])))
            else:
                # Sorting by bidder number requires a join, which would filter out anyone without a bidder number
                order = 'badge_printed_name' if order == 'bidder_num' else order
                try:
                    badge_num = int(search_text)
                except:
                    filters.append(Attendee.badge_printed_name.ilike('%{}%'.format(search_text)))
                else:
                    filters.append(or_(Attendee.badge_num == badge_num,
                                       Attendee.badge_printed_name.ilike('%{}%'.format(search_text))))
                attendees = session.query(Attendee).filter(*filters)
        else:
            attendees = session.query(Attendee).join(Attendee.art_show_bidder)

        if 'bidder_num' in str(order) or not order:
            attendees = attendees.join(Attendee.art_show_bidder).order_by(
                ArtShowBidder.bidder_num.desc() if '-' in str(order) else ArtShowBidder.bidder_num)
        else:
            attendees = attendees.order(order)

        count = attendees.count()
        page = int(page) or 1

        if not count:
            message = 'No matches found'

        pages = range(1, int(math.ceil(count / 100)) + 1)
        attendees = attendees[-100 + 100*page: 100*page]

        return {
            'message':        message,
            'page':           page,
            'pages':          pages,
            'search_text':    search_text,
            'search_results': bool(search_text),
            'attendees':      attendees,
            'order':          Order(order),
        }

    @ajax
    def sign_up_bidder(self, session, **params):
        attendee = session.attendee(params['attendee_id'])
        success = 'Bidder saved'
        if params['id']:
            bidder = session.art_show_bidder(params)
        else:
            params.pop('id')
            if 'cellphone' in params and params['cellphone']:
                attendee.cellphone = params.pop('cellphone')
            bidder = ArtShowBidder()
            bidder.apply(params, restricted=False)
            attendee.art_show_bidder = bidder

        if params['complete']:
            bidder.signed_up = localized_now()
            success = 'Bidder signup complete'

        message = check(attendee)
        if not message:
            message = check(bidder)
        if message:
            session.rollback()
            return {'error': message}
        else:
            session.commit()

        return {
            'id': bidder.id,
            'attendee_id': attendee.id,
            'bidder_num': bidder.bidder_num,
            'error': message,
            'success': success
        }

    def print_bidder_form(self, session, id, **params):
        bidder = session.art_show_bidder(id)
        attendee = bidder.attendee

        return {
            'model': attendee,
            'type': 'bidder'
        }

    def sales_search(self, session, message='', page=1, search_text='', order=''):
        filters = []
        search_text = search_text.strip()
        if search_text:
            order = order or 'badge_num'
            if re.match('\w-[0-9]{4}', search_text):
                attendees = session.query(Attendee).join(Attendee.art_show_bidder).filter(
                    ArtShowBidder.bidder_num.ilike('%{}%'.format(search_text[2:])))
            else:
                # Sorting by bidder number requires a join, which would filter out anyone without a bidder number
                order = 'badge_num' if order == 'bidder_num' else order
                try:
                    badge_num = int(search_text)
                except:
                    raise HTTPRedirect('sales_search?message={}', 'Please search by bidder number or badge number.')
                else:
                    filters.append(or_(Attendee.badge_num == badge_num))
                attendees = session.query(Attendee).filter(*filters)
        else:
            attendees = session.query(Attendee).join(Attendee.art_show_receipts)

        if 'bidder_num' in str(order):
            attendees = attendees.join(Attendee.art_show_bidder).order_by(
                ArtShowBidder.bidder_num.desc() if '-' in str(order) else ArtShowBidder.bidder_num)
        else:
            attendees = attendees.order(order or 'badge_num')

        count = attendees.count()
        page = int(page) or 1

        if not count:
            message = 'No matches found'

        if not search_text:
            attendees = [a for a in attendees if a.art_show_receipt and a.art_show_receipt.pieces]

        pages = range(1, int(math.ceil(count / 100)) + 1)
        attendees = attendees[-100 + 100*page: 100*page]

        return {
            'message':        message,
            'page':           page,
            'pages':          pages,
            'search_text':    search_text,
            'search_results': bool(search_text),
            'attendees':      attendees,
            'order':          Order(order),
        }

    def pieces_bought(self, session, id, search_text='', message='', **params):
        try:
            receipt = session.art_show_receipt(id)
        except:
            attendee = session.attendee(id)
            if not attendee.art_show_receipt:
                receipt = ArtShowReceipt(attendee=attendee)
                session.add(receipt)
                session.commit()
            else:
                receipt = attendee.art_show_receipt
        else:
            attendee = receipt.attendee

        must_choose = False
        unclaimed_pieces = []
        unpaid_pieces = []
        charge = None

        if search_text:
            if re.match('\w+-[0-9]+', search_text):
                artist_id, piece_id = search_text.split('-')
                pieces = session.query(ArtShowPiece).join(ArtShowPiece.app).filter(
                    ArtShowPiece.piece_id == int(piece_id),
                    ArtShowApplication.artist_id == artist_id.upper()
                )
            else:
                pieces = session.query(ArtShowPiece).filter(ArtShowPiece.name.ilike('%{}%'.format(search_text)))

            unclaimed_pieces = pieces.filter(ArtShowPiece.buyer == None,
                                             ArtShowPiece.status != c.RETURN)
            unclaimed_pieces = [piece for piece in unclaimed_pieces if piece.sale_price > 0]
            unpaid_pieces = pieces.join(ArtShowReceipt).filter(ArtShowReceipt.closed != None,
                                                               ArtShowPiece.status != c.PAID)
            unpaid_pieces = [piece for piece in unpaid_pieces if piece.sale_price > 0]

            if pieces.count() == 0:
                message = "No pieces found with ID or title {}.".format(search_text)
            elif len(unclaimed_pieces) == 0 and len(unpaid_pieces) == 0:
                if pieces.count() == 1:
                    msg_piece = pieces.one()
                    if msg_piece.receipt == receipt:
                        message = "That piece ({}) is already on this receipt.".format(msg_piece.artist_and_piece_id)
                    elif msg_piece.sale_price <= 0:
                        message = "That piece ({}) doesn't have a valid sale price." \
                            .format(msg_piece.artist_and_piece_id)
                    elif msg_piece.status == c.RETURN:
                        message = "That piece ({}) is marked {}.".format(msg_piece.artist_and_piece_id,
                                                                         msg_piece.status_label)
                    elif msg_piece in attendee.art_show_purchases:
                        message = "That piece ({}) was already sold to this buyer."\
                            .format(msg_piece.artist_and_piece_id)
                    else:
                        message = "That piece ({}) was already sold to another buyer."\
                            .format(msg_piece.artist_and_piece_id)
                else:
                    message = "None of the matching pieces for '{}' can be claimed.".format(search_text)
            elif len(unclaimed_pieces) > 1 or (len(unclaimed_pieces) == 0 and len(unpaid_pieces) > 1):
                message = "There were multiple pieces found matching '{}.' Please choose one.".format(search_text)
                must_choose = True

            if not message:
                if len(unclaimed_pieces) == 0 and len(unpaid_pieces) == 1:
                    piece = unpaid_pieces[0]
                elif len(unclaimed_pieces) == 1:
                    piece = unclaimed_pieces[0]
                else:
                    message = "Something went wrong! Try again?"

                if not message:
                    piece.receipt = receipt
                    session.add(piece)
                    message = 'Piece {} successfully claimed'.format(piece.artist_and_piece_id)

            if not must_choose:
                raise HTTPRedirect('pieces_bought?id={}&message={}', receipt.id, message)
        elif 'amount' in params:
            if params['amount']:
                amount = int(Decimal(params['amount']) * 100)
            else:
                amount = receipt.owed

            charge = Charge(targets=[attendee],
                            amount=amount,
                            description='{}ayment for {}\'s art show purchases'.format(
                                'P' if amount == receipt.total else 'Partial p',
                                attendee.full_name))

        return {
            'receipt': receipt,
            'message': message,
            'must_choose': must_choose,
            'pieces': unclaimed_pieces or unpaid_pieces,
            'charge': charge,
        }

    def unclaim_piece(self, session, id, piece_id, **params):
        receipt = session.art_show_receipt(id)
        piece = session.art_show_piece(piece_id)

        if piece.receipt != receipt:
            raise HTTPRedirect('pieces_bought?id={}&message={}',
                               receipt.id,
                               "Can't unclaim piece: it already doesn't belong to this buyer.")
        elif (receipt.owed - piece.sale_price < 0) and receipt.art_show_payments:
            raise HTTPRedirect('pieces_bought?id={}&message={}',
                               receipt.id,
                               "Can't unclaim piece: it's already been paid for.")
        else:
            piece.receipt = None
            session.add(piece)
            raise HTTPRedirect('pieces_bought?id={}&message={}',
                               receipt.id,
                               'Piece {} successfully unclaimed'.format(piece.artist_and_piece_id))

    def record_payment(self, session, id, amount='', type=c.CASH):
        receipt = session.art_show_receipt(id)

        if amount:
            amount = int(Decimal(amount) * 100)

        if type == str(c.CASH):
            amount = amount or receipt.owed
            message = 'Cash payment of ${} recorded'.format('%0.2f' % float(amount / 100))
        else:
            amount = amount or receipt.paid
            message = 'Refund of ${} recorded'.format('%0.2f' % float(amount / 100))

        session.add(ArtShowPayment(
            receipt=receipt,
            amount=amount,
            type=type,
        ))

        raise HTTPRedirect('pieces_bought?id={}&message={}', receipt.attendee.id, message)

    def print_receipt(self, session, id, **params):
        receipt = session.art_show_receipt(id)

        if not receipt.closed:
            receipt.closed = localized_now()
            for piece in receipt.pieces:
                piece.status = c.PAID
                session.add(piece)

            session.add(receipt)
            session.commit()

        return {
            'receipt': receipt,
        }

    @unrestricted
    @credit_card
    def purchases_charge(self, session, payment_id, stripeToken):
        charge = Charge.get(payment_id)
        message = charge.charge_cc(session, stripeToken)
        attendee_id = charge.attendees[0].id
        attendee = session.attendee(attendee_id)
        receipt = attendee.art_show_receipt
        if message:
            raise HTTPRedirect('pieces_bought?id={}&message={}', attendee.id, message)
        else:
            session.add(ArtShowPayment(
                receipt=receipt,
                amount=charge.amount,
                type=c.STRIPE,
            ))
            raise HTTPRedirect('pieces_bought?id={}&message={}', attendee.id, 'Charge successfully processed')

    @unrestricted
    def sales_charge_form(self, message='', amount=None, description='',
                          sale_id=None):
        charge = None
        if amount is not None:
            if not description:
                message = "You must enter a brief description " \
                          "of what's being sold"
            else:
                charge = Charge(amount=int(100 * float(amount)),
                                description=description)

        return {
            'charge': charge,
            'message': message,
            'amount': amount,
            'description': description,
            'sale_id': sale_id
        }

    @unrestricted
    @credit_card
    def sales_charge(self, session, payment_id, stripeToken):
        charge = Charge.get(payment_id)
        message = charge.charge_cc(session, stripeToken)
        if message:
            raise HTTPRedirect('sales_charge_form?message={}', message)
        else:
            session.add(ArbitraryCharge(
                amount=charge.dollar_amount,
                what=charge.description
            ))
            raise HTTPRedirect('sales_charge_form?message={}',
                               'Charge successfully processed')
