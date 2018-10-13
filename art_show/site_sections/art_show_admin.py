import cherrypy
import treepoem
import os
import re

from sqlalchemy import or_, and_
from io import BytesIO

from uber.config import c
from uber.decorators import ajax, all_renderable, credit_card, unrestricted
from uber.errors import HTTPRedirect
from uber.models import Attendee, Tracking, ArbitraryCharge
from uber.utils import Charge, check, localized_now

from art_show.config import config
from art_show.models import ArtShowPiece

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
                    session.add(attendee)
                    app.attendee = attendee
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
        attendee_attrs = session.query(Attendee.id, Attendee.full_name,
                                       Attendee.badge_type, Attendee.badge_num) \
            .filter(Attendee.first_name != '',
                    Attendee.badge_status not in [c.INVALID_STATUS,
                                                  c.WATCHED_STATUS])

        attendees = [
            (id, '{} - {}{}'.format(name.title(), c.BADGES[badge_type],
                                    ' #{}'.format(
                                        badge_num) if badge_num else ''))
            for id, name, badge_type, badge_num in attendee_attrs]

        return {
            'message': message,
            'applications': session.art_show_apps(),
            'all_attendees': sorted(attendees, key=lambda tup: tup[1]),
        }

    @ajax
    def save_and_check_in_out(self, session, **params):
        app = session.art_show_application(params['app_id'])
        attendee = app.attendee

        app.apply(params, restricted=False)

        message = check(app)
        if message:
            session.rollback()
            return {'error': message}
        else:
            if 'check_in' in params and params['check_in']:
                app.checked_in = localized_now()
            if 'check_out' in params and params['check_out']:
                app.checked_out = localized_now()
            session.commit()

        attendee.apply(params, restricted=False)

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

        for id in params.get('piece_ids', []):
            piece = session.art_show_piece(id)
            piece_params = dict()
            for field_name in ['gallery', 'status', 'name', 'opening_bid', 'quick_sale_price']:
                piece_params[field_name] = params.get('{}{}'.format(field_name, id), '')

            # Correctly handle admins entering '0' for a price
            try:
                opening_bid = int(piece_params['opening_bid'])
            except:
                opening_bid = piece_params['opening_bid']
            try:
                quick_sale_price = int(piece_params['quick_sale_price'])
            except:
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
                session.commit() # We save as we go so it's less annoying if there's an error

        return {'error': message,
                'success': 'Application updated'}

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
                     txt=(piece.app.banner_name or piece.app.artist_name or piece.app.attendee.full_name),
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
