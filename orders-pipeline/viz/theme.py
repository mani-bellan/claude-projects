"""Chart theme: the validated data-viz palette, applied to Altair.

Colors come straight from the data-viz skill's reference palette
(`references/palette.md`) and were run through its validator:
- 5 currency series (categorical slots 1-5) pass light + dark, with the
  relief rule satisfied because every chart ships a legend + tooltips.
- Batch status uses the reserved status palette (never a categorical slot),
  always paired with an icon/label so color never carries meaning alone.

Altair can't see the browser theme, so we expose a single `dark` flag and let
the app toggle it. Text always wears ink tokens, never a series color.
"""

from __future__ import annotations

import altair as alt

# --- Categorical: currencies (fixed order, never cycled) -------------------
# Assigned in the palette's validated slot order 1-5 (blue, aqua, yellow,
# green, violet). Order is fixed so a currency keeps its hue across filters.
CURRENCY_ORDER = ["INR", "USD", "EUR", "GBP", "SGD"]
_CURRENCY_LIGHT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7"]
_CURRENCY_DARK = ["#3987e5", "#199e70", "#c98500", "#008300", "#9085e9"]

# --- Sequential single hue: blue (used for the single-series funnel) --------
_ACCENT_LIGHT = "#2a78d6"
_ACCENT_DARK = "#3987e5"

# --- Status palette (reserved, never themed as a series) --------------------
# Batch outcomes map onto good/warning/critical. Paired with an icon in the UI.
STATUS_COLORS = {
    "promoted": "#0ca30c",   # good
    "quarantined": "#fab219",  # warning
    "halted": "#d03b3b",     # critical
}
STATUS_ICONS = {"promoted": "✓", "quarantined": "⚠", "halted": "✕"}

# --- Chart chrome & ink -----------------------------------------------------
_INK = {
    False: {"surface": "#fcfcfb", "primary": "#0b0b0b", "secondary": "#52514e",
            "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7"},
    True: {"surface": "#1a1a19", "primary": "#ffffff", "secondary": "#c3c2b7",
           "muted": "#898781", "grid": "#2c2c2a", "axis": "#383835"},
}


def currency_scale(dark: bool) -> alt.Scale:
    """Color scale binding each currency to its fixed hue (entity, not rank)."""
    return alt.Scale(
        domain=CURRENCY_ORDER,
        range=_CURRENCY_DARK if dark else _CURRENCY_LIGHT,
    )


def accent(dark: bool) -> str:
    return _ACCENT_DARK if dark else _ACCENT_LIGHT


def status_scale() -> alt.Scale:
    return alt.Scale(
        domain=list(STATUS_COLORS), range=list(STATUS_COLORS.values())
    )


def apply_theme(dark: bool) -> None:
    """Register + enable a lightweight Altair theme matching the ink tokens."""
    ink = _INK[dark]

    def _theme() -> dict:
        return {
            "config": {
                "background": ink["surface"],
                "font": 'system-ui, -apple-system, "Segoe UI", sans-serif',
                "view": {"stroke": "transparent"},
                "axis": {
                    "labelColor": ink["muted"],
                    "titleColor": ink["secondary"],
                    "gridColor": ink["grid"],
                    "domainColor": ink["axis"],
                    "tickColor": ink["axis"],
                    "labelFontSize": 11,
                    "titleFontSize": 12,
                },
                "legend": {
                    "labelColor": ink["secondary"],
                    "titleColor": ink["secondary"],
                },
                "title": {"color": ink["primary"], "fontSize": 14},
            }
        }

    alt.themes.register("orders_viz", _theme)
    alt.themes.enable("orders_viz")
