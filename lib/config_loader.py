# lib/config_loader.py — Merge config_defaults with user config overrides.
import config_defaults

try:
    import config as _user_config
    for attr in dir(_user_config):
        if not attr.startswith('_'):
            setattr(config_defaults, attr, getattr(_user_config, attr))
except ImportError:
    pass

config = config_defaults
