"""JWM desktop tools. The suite currently uses English for its interface."""

import os

# Keep GTK stock labels and application pickers consistent with suite text.
# Do not change LC_NUMERIC or other formatting conventions.
os.environ["LANGUAGE"] = "en"

__version__ = "0.1"

COMMANDS = ("jwm_audio", "jwm_menu", "jwm_ram", "jwm_style", "jwm_keys", "jwm_startup")
