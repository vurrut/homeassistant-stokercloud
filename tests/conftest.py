"""Fixtures for NBE StokerCloud tests."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from stokercloud import ControllerData

SAMPLE = json.loads((Path(__file__).parent / "controllerdata.json").read_text())
MENUS = {
    "boiler": {"boiler.temp": {"min": 0, "max": 85, "factor": 1, "val": "70"}},
    "hot_water": {"hot_water.temp": {"min": 0, "max": 70, "factor": 1, "val": "60"}},
    "hopper": {"hopper.content": {"min": -30000, "max": 30000, "factor": 1, "val": "-10362"}},
    "regulation": {
        "regulation.boiler_gain_p": {"min": 0.5, "max": 20, "factor": 10, "val": "2.5"},
        "regulation.boiler_power_max": {"min": 10, "max": 100, "factor": 1, "val": "100"},
    },
    "oxygen": {"oxygen.o2_low": {"min": 10, "max": 18, "factor": 10, "val": "17.0"}},
}


def _history():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    day0 = now.replace(hour=4)
    return {
        # newest first; index 0 is the current, partial bucket
        "hours": [(now - timedelta(hours=i), 1.0) for i in range(24)],
        "days": [(day0 - timedelta(days=i), 10.0) for i in range(24)],
        "months": [(datetime(2026, 10, 31, 23, tzinfo=timezone.utc), 41.0), (datetime(2026, 10, 1, 23, tzinfo=timezone.utc), 112.0)],
        "years": [(datetime(2025, 12, 31, 23, tzinfo=timezone.utc), 2100.0), (datetime(2025, 1, 1, 23, tzinfo=timezone.utc), 2766.0)],
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_client():
    """Patch the library client everywhere the integration uses it."""
    with patch(
        "custom_components.hass_stokercloud.Client", autospec=True
    ) as cls, patch("custom_components.hass_stokercloud.config_flow.Client", new=cls):
        client = cls.return_value
        client.async_get_data = AsyncMock(return_value=SAMPLE)
        client.async_get_controller_data = AsyncMock(return_value=ControllerData(SAMPLE))
        client.async_get_menu = AsyncMock(side_effect=lambda m: MENUS[m])
        ok = {"status": "0", "onlineandsaved": 1, "secs_to_next_update": 5}
        client.async_set_boiler_temp = AsyncMock(return_value=ok)
        client.async_set_dhw_temp = AsyncMock(return_value=ok)
        client.async_turn_on = AsyncMock(return_value=ok)
        client.async_turn_off = AsyncMock(return_value=ok)
        client.async_reset_alarm = AsyncMock(return_value=ok)
        client.async_set_value = AsyncMock(return_value=ok)
        client.async_get_status = AsyncMock(return_value="2026-11-04 18:43:14")
        history = _history()
        client.async_get_consumption = AsyncMock(side_effect=lambda p: history[p])
        yield client
