from uber.common import *


@all_renderable()
class Root:
    def index(self, session, message='', **params):
        app = session.art_show_application(params, restricted=True, ignore_csrf=True)

        if cherrypy.request.method == 'POST':
            session.add(app)

        return {
            'message': message,
            'app': app
        }
