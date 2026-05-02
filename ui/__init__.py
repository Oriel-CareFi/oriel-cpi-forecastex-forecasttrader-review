"""
ui/ — Oriel shared UI infrastructure.

Re-exports design tokens, chart/table builders, and CSS injection
so tab renderers can do `from ui import GOLD, _layout, _plotly_desk_table`.
"""
from ui.tokens import *  # noqa: F401,F403 — all design token constants
from ui.plotly_theme import ORIEL_TEMPLATE, PLOTLY_CONFIG  # noqa: F401
from ui.tables import (  # noqa: F401
    _plotly_desk_table,
    desk_table_content_height_px,
    desk_table_viewport_height_px,
)
from ui.charts import (  # noqa: F401
    _layout, _xaxis, _yaxis,
    make_forward_curve, make_distribution,
    _maturity_label, _prior_curve_demo,
)
from ui.css import inject_css  # noqa: F401
