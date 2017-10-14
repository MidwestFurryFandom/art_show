from uber.common import *


@all_renderable(c.ART_SHOW)
class Root:
    def index(self, session, message=''):
        return {
            'message': message,
            'applications': session.art_show_apps()
        }

    def form(self, session, new_app='', message='', **params):
        app = session.art_show_application(params)
        attendee = None
        if cherrypy.request.method == 'POST':
            if new_app:
                attendee, message = session.attendee_from_art_show_app(**params)
            else:
                attendee = app.attendee
            message = message or check(app)
            if not message:
                if attendee:
                    attendee.badge_status = params.get('badge_status', '')
                    session.add(attendee)
                    app.attendee = attendee
                session.add(app)
                if params.get('save') == 'save_return_to_search':
                    return_to = 'index?'
                else:
                    return_to = 'form?id=' + app.id + '&'
                raise HTTPRedirect(return_to + 'message={}', 'Application updated')
        return {
            'message': message,
            'app': app,
            'attendee': attendee,
            'attendee_id': app.attendee_id or params.get('attendee_id', ''),
            'all_attendees': session.all_attendees_opts(),
            'new_app': new_app
        }

    def history(self, session, id):
            app = session.art_show_application(id)
            return {
                'app': app,
                'changes': session.query(Tracking)
                    .filter(or_(Tracking.links.like('%art_show_application({})%'.format(id)),
                                and_(Tracking.model == 'ArtShowApplication', Tracking.fk_id == id)))
                    .order_by(Tracking.when).all()
            }
