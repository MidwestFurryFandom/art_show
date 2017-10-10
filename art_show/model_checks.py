from . import *
from uber.model_checks import ignore_unassigned_and_placeholders


ArtShowApplication.required = [('description', 'Description')]


@prereg_validation.ArtShowApplication
def max_panels(app):
    if app.panels > c.MAX_ART_PANELS:
        return 'You cannot have more than {} panels.'.format(c.MAX_ART_PANELS)


@prereg_validation.ArtShowApplication
def max_tables(app):
    if app.tables > c.MAX_ART_TABLES:
        return 'You cannot have more than {} tables.'.format(c.MAX_ART_TABLES)


@validation.ArtShowApplication
def need_some_space(app):
    if not app.panels and not app.tables:
        return 'Please select how many panels and/or tables to include on this application.'
