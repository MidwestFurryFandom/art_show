from sideboard.lib import parse_config

from uber.config import c
from uber.menu import MenuItem

config = parse_config(__file__)
c.include_plugin_config(config)


# This can go away if/when we implement plugin enum merging
c.ACCESS.update(c.ART_SHOW_ACCESS_LEVELS)
c.ACCESS_OPTS.extend(c.ART_SHOW_ACCESS_LEVEL_OPTS)
c.ACCESS_VARS.extend(c.ART_SHOW_ACCESS_LEVEL_VARS)


c.MENU.append_menu_item(MenuItem(name='Art Show', access=c.ART_SHOW, submenu=[
    MenuItem(name='Applications', href='../art_show_admin/'),
    MenuItem(name='Link to Apply', href='../art_show_applications/'),
    MenuItem(name='Sales Charge Form',
             href='../art_show_admin/sales_charge_form'),
                                 ]))
