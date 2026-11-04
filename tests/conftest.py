"""Fixtures for NBE StokerCloud tests."""
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
    "regulation": {"regulation.boiler_gain_p": {"min": 0.5, "max": 20, "factor": 10, "val": "2.5"}},
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
        yield client
