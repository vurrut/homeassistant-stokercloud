"""Tests for v3.1 features: options, pellet energy, hopper, service, diagnostics."""
import json
from pathlib import Path

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from stokercloud import ControllerData

from custom_components.hass_stokercloud.const import DOMAIN
from custom_components.hass_stokercloud.diagnostics import async_get_config_entry_diagnostics

from .conftest import SAMPLE


async def _setup(hass, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="testuser", title="Stokercloud (testuser)",
        data={CONF_USERNAME: "testuser", CONF_PASSWORD: "secret"}, options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_pellet_energy_and_hopper(hass: HomeAssistant, mock_client) -> None:
    await _setup(hass, {"calorific_value": 5.0})
    energy = hass.states.get("sensor.nbe_pellet_energy")
    assert float(energy.state) == 10370 * 5.0
    assert energy.attributes["device_class"] == "energy"
    assert energy.attributes["state_class"] == "total_increasing"
    assert hass.states.get("sensor.nbe_hopper_content").state == "-10362"

    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.nbe_hopper_content", "value": 300}, blocking=True
    )
    mock_client.async_set_value.assert_awaited_once_with("hopper.content", 300)


async def test_zone_sensors_only_when_active(hass: HomeAssistant, mock_client) -> None:
    data = json.loads(json.dumps(SAMPLE))
    data["weathercomp"]["zone1active"] = 1
    data["weathercomp"]["zone1-wanted"] = {"val": 51.5, "unit": "lng_degree"}
    data["weathercomp"]["zone1-valve"] = {"val": "49", "unit": "lng_pct"}
    mock_client.async_get_controller_data.return_value = ControllerData(data)
    await _setup(hass)
    assert hass.states.get("sensor.nbe_zone_1_wanted_temperature").state == "51.5"
    assert hass.states.get("sensor.nbe_zone_1_valve").state == "49.0"
    assert hass.states.get("sensor.nbe_zone_2_valve") is None


async def test_options_flow_reloads(hass: HomeAssistant, mock_client) -> None:
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 120, "calorific_value": 4.5}
    )
    await hass.async_block_till_done()
    assert entry.options == {"scan_interval": 120, "calorific_value": 4.5}
    assert entry.runtime_data.update_interval.total_seconds() == 120
    assert float(hass.states.get("sensor.nbe_pellet_energy").state) == 10370 * 4.5


async def test_set_value_service(hass: HomeAssistant, mock_client) -> None:
    await _setup(hass)
    resp = await hass.services.async_call(
        DOMAIN, "set_value", {"setting": "regulation.boiler_gain_p", "value": 3.04},
        blocking=True, return_response=True,
    )
    mock_client.async_set_value.assert_awaited_once_with("regulation.boiler_gain_p", 3.0)
    assert resp["response"]["status"] == "0"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_value", {"setting": "boiler.temp", "value": 120}, blocking=True
        )


async def test_diagnostics_redacts(hass: HomeAssistant, mock_client) -> None:
    entry = await _setup(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(diag)
    assert "secret" not in text and "testuser" not in text and "Sample Town" not in text
    assert diag["controller"]["serial"] == "**REDACTED**"
