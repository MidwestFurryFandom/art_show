from uber.common import *

config = parse_config(__file__)
c.include_plugin_config(config)


# This can go away if/when we implement plugin enum merging
c.ACCESS.update(c.ART_SHOW_ACCESS_LEVELS)
c.ACCESS_OPTS.extend(c.ART_SHOW_ACCESS_LEVEL_OPTS)
c.ACCESS_VARS.extend(c.ART_SHOW_ACCESS_LEVEL_VARS)
