from . import *
from uber.model_checks import ignore_unassigned_and_placeholders


ArtShowApplication.required = [('description', 'Description')]


@validation.ArtShowApplication
def need_some_space(app):
    if not app.panels and not app.tables:
        return 'Please select how many panels and/or tables you would like.'
