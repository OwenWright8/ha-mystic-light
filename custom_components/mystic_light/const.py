"""Constants for the MSI Mystic Light integration."""

from datetime import timedelta

DOMAIN = "mystic_light"
DEFAULT_PORT = 8765
SCAN_INTERVAL = timedelta(seconds=15)

# Styles that show a single solid colour, in order of preference.
SOLID_STYLES = ("Steady", "Static", "Always On", "Direct")
