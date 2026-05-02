from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.cms_lag_loader import load_pipeline_outputs


def test_cms_pipeline_outputs_present():
    base = ROOT / "data" / "cms_lag_engine"
    loaded = load_pipeline_outputs(base)
    assert "basis_action_panel" in loaded
    assert not loaded["basis_action_panel"].empty
