"""Constants for the MSI Mystic Light integration."""

from datetime import timedelta

DOMAIN = "mystic_light"
DEFAULT_PORT = 8765
SCAN_INTERVAL = timedelta(seconds=15)

# Max LED output as a percentage of full white (R+G+B). Full white can exceed what an
# ARGB header supplies, which makes fans flicker.
CONF_MAX_POWER = "max_power"
DEFAULT_MAX_POWER = 60

# Styles that show a single solid colour, in order of preference.
SOLID_STYLES = ("Steady", "Static", "Always On", "Direct")
