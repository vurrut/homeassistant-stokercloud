"""Tests for NBE StokerCloud setup, entities, writes and config flow."""
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from stokercloud import StokerCloudAuthError, StokerCloudWriteError

from custom_components.hass_stokercloud.const import DOMAIN


def _entry(hass, password="secret"):
    data = {CONF_USERNAME: "testuser"}
    if password:
        data[CONF_PASSWORD] = password
    entry = MockConfigEntry(domain=DOMAIN, unique_id="testuser", data=data, title="Stokercloud (testuser)")
    entry.add_to_hass(hass)
    return entry


async def test_setup_creates_entities(hass: HomeAssistant, mock_client) -> None:
    entry = _entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.nbe_boiler_temperature").state == "57.7"
    assert hass.states.get("sensor.nbe_state").state == "Stopped by external contact"
    assert hass.states.get("sensor.nbe_total_consumption").attributes["unit_of_measurement"] == "kg"
    assert hass.states.get("binary_sensor.nbe_running").state == "on"
    num = hass.states.get("number.nbe_wanted_boiler_temperature")
    assert num.state == "70.0"
    assert num.attributes["max"] == 85
    assert hass.states.get("number.nbe_wanted_dhw_temperature").state == "60.0"
    assert hass.states.get("switch.nbe_burner").state == "on"
    assert hass.states.get("button.nbe_reset_alarm") is not None

    # unique_id format kept from v2 ("<username>-<old name>")
    reg = er.async_get(hass)
    assert reg.async_get_entity_id("number", DOMAIN, "testuser-Wanted Boiler Temperature")
    assert reg.async_get_entity_id("sensor", DOMAIN, "testuser-Boiler Temperature")

    # one poll for all entities
    assert mock_client.async_get_controller_data.await_count == 1


async def test_set_boiler_temperature(hass: HomeAssistant, mock_client) -> None:
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.nbe_wanted_boiler_temperature", "value": 72},
        blocking=True,
    )
    mock_client.async_set_boiler_temp.assert_awaited_once_with(72.0)
    # optimistic until the cloud confirms
    assert hass.states.get("number.nbe_wanted_boiler_temperature").state == "72.0"

    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.nbe_wanted_dhw_temperature", "value": 55},
        blocking=True,
    )
    mock_client.async_set_dhw_temp.assert_awaited_once_with(55.0)


async def test_write_error_surfaces(hass: HomeAssistant, mock_client) -> None:
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_client.async_set_boiler_temp.side_effect = StokerCloudWriteError("rejected")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": "number.nbe_wanted_boiler_temperature", "value": 72},
            blocking=True,
        )
    assert hass.states.get("number.nbe_wanted_boiler_temperature").state == "70.0"


async def test_switch_and_button(hass: HomeAssistant, mock_client) -> None:
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.nbe_burner"}, blocking=True)
    mock_client.async_turn_off.assert_awaited_once()
    assert hass.states.get("switch.nbe_burner").state == "off"
    await hass.services.async_call("button", "press", {"entity_id": "button.nbe_reset_alarm"}, blocking=True)
    mock_client.async_reset_alarm.assert_awaited_once()


async def test_old_entry_without_password_starts_reauth(hass: HomeAssistant, mock_client) -> None:
    entry = _entry(hass, password=None)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1 and flows[0]["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {CONF_PASSWORD: "secret"})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "secret"
    assert entry.state is ConfigEntryState.LOADED


async def test_bad_password_on_poll_starts_reauth(hass: HomeAssistant, mock_client) -> None:
    mock_client.async_get_controller_data.side_effect = StokerCloudAuthError("bad")
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_config_flow(hass: HomeAssistant, mock_client) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    mock_client.async_get_data.side_effect = StokerCloudAuthError("bad")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "testuser", CONF_PASSWORD: "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.async_get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "testuser", CONF_PASSWORD: "secret"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_USERNAME: "testuser", CONF_PASSWORD: "secret"}
