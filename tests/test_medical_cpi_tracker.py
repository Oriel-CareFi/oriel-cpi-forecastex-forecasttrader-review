from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.medical_cpi_tracker import load_medical_cpi_panel, load_seed_medical_cpi_history


def test_seed_history_loads():
    df = load_seed_medical_cpi_history()
    assert not df.empty
    assert {"component", "series_id", "date", "level", "weight", "group"}.issubset(df.columns)


def test_panel_has_expected_components_and_breadth():
    panel = load_medical_cpi_panel(prefer_live=False)
    latest = panel.latest_table
    assert len(latest) == 7
    assert "Medical care" in set(latest["component"])
    assert panel.breadth["component_count"] == 6
    assert panel.breadth["weighted_share_above_threshold"] is not None
    assert panel.breadth["dispersion_std"] is not None
