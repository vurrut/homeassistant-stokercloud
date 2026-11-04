"""Tests for v3.2: fast updates, history, hopper low, events, water heater, advanced numbers."""
from datetime import datetime, timedelta, timezone
import json

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from stokercloud import ControllerData

from custom_components.hass_stokercloud.const import DOMAIN, EVENT_STOKERCLOUD
from custom_components.hass_stokercloud.coordinator import ConsumptionHistory
from custom_components.hass_stokercloud.statistics import build_rows

from .conftest import SAMPLE


async def _setup(hass, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="testuser", title="Stokercloud (testuser)",
        data={CONF_USERNAME: "testuser", CONF_PASSWORD: "secret"},
        options={"import_statistics": False, **(options or {})},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _data(**changes):
    data = json.loads(json.dumps(SAMPLE))
    for path, value in changes.items():
        node = data
        *parents, leaf = path.split("__")
        for key in parents:
            node = node[key]
        node[leaf] = value
    return ControllerData(data)


async def test_fast_updates_skip_full_fetch_when_unchanged(
    hass: HomeAssistant, mock_client, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    assert coordinator.update_interval == timedelta(seconds=10)
    assert mock_client.async_get_controller_data.await_count == 1

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_client.async_get_status.await_count >= 2
    assert mock_client.async_get_controller_data.await_count == 1  # status unchanged

    mock_client.async_get_status.return_value = "2026-11-04 18:44:10"
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_client.async_get_controller_data.await_count == 2


async def test_history_sensors(hass: HomeAssistant, mock_client) -> None:
    await _setup(hass)
    assert hass.states.get("sensor.nbe_consumption_this_month").state == "41.0"
    assert hass.states.get("sensor.nbe_consumption_last_month").state == "112.0"
    assert hass.states.get("sensor.nbe_consumption_this_year").state == "2100.0"
    month = hass.states.get("sensor.nbe_consumption_this_month")
    assert month.attributes["state_class"] == "total"
    assert hass.states.get("sensor.nbe_average_daily_consumption").state == "10.0"
    # hopper content not tracked (negative) -> unknown
    assert hass.states.get("sensor.nbe_pellets_days_left").state == "unknown"


async def test_days_left_and_hopper_low(hass: HomeAssistant, mock_client) -> None:
    mock_client.async_get_controller_data.return_value = _data()
    cd = _data()
    cd.hoppercontent.value = 40
    mock_client.async_get_controller_data.return_value = cd
    await _setup(hass, {"low_hopper_kg": 50})
    assert hass.states.get("sensor.nbe_pellets_days_left").state == "4.0"
    low = hass.states.get("binary_sensor.nbe_hopper_low")
    assert low.state == "on" and low.attributes["threshold_kg"] == 50


async def test_hopper_low_unknown_without_tracking(hass: HomeAssistant, mock_client) -> None:
    await _setup(hass)
    assert hass.states.get("binary_sensor.nbe_hopper_low").state == "unknown"


async def test_events_on_state_and_alarm_change(
    hass: HomeAssistant, mock_client, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass, {"fast_updates": False})
    bus_events = []

    @callback
    def _listener(event):
        bus_events.append(event)

    hass.bus.async_listen(EVENT_STOKERCLOUD, _listener)

    mock_client.async_get_controller_data.return_value = _data(
        miscdata__state={"id": "state", "value": "lng_state_13"}, miscdata__alarm=1
    )
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    types = [e.data["type"] for e in bus_events]
    assert types == ["state_changed", "alarm"]
    assert bus_events[0].data["to_state"] == "Fault ignition"
    assert bus_events[0].data["config_entry_id"] == entry.entry_id
    ev = hass.states.get("event.nbe_boiler_event")
    assert ev.attributes["event_type"] == "alarm"


async def test_water_heater(hass: HomeAssistant, mock_client) -> None:
    await _setup(hass)
    wh = hass.states.get("water_heater.nbe_hot_water")
    assert wh.attributes["current_temperature"] == 49.7
    assert wh.attributes["temperature"] == 60
    assert wh.attributes["max_temp"] == 70
    await hass.services.async_call(
        "water_heater", "set_temperature",
        {"entity_id": "water_heater.nbe_hot_water", "temperature": 55}, blocking=True,
    )
    mock_client.async_set_dhw_temp.assert_awaited_once_with(55.0)
    assert hass.states.get("water_heater.nbe_hot_water").attributes["temperature"] == 55


async def test_advanced_numbers_disabled_by_default(hass: HomeAssistant, mock_client) -> None:
    await _setup(hass)
    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id("number", DOMAIN, "testuser-O2 Target Low Power")
    assert entity_id and reg.async_get(entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    # settings missing from the menus -> no entity at all
    assert reg.async_get_entity_id("number", DOMAIN, "testuser-Boiler Start Difference") is None


async def test_advanced_number_write(hass: HomeAssistant, mock_client) -> None:
    reg = er.async_get(hass)
    reg.async_get_or_create("number", DOMAIN, "testuser-O2 Target Low Power", suggested_object_id="nbe_o2_target_low_power")
    await _setup(hass)
    st = hass.states.get("number.nbe_o2_target_low_power")
    assert st.state == "17.0" and st.attributes["step"] == 0.1 and st.attributes["min"] == 10
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.nbe_o2_target_low_power", "value": 16.53}, blocking=True
    )
    mock_client.async_set_value.assert_awaited_once_with("oxygen.o2_low", 16.5)


def test_build_rows_backfill_then_hourly() -> None:
    now = datetime(2026, 11, 4, 18, 30, tzinfo=timezone.utc)
    hour0 = now.replace(minute=0)
    hist = ConsumptionHistory(
        hourly=[(hour0 - timedelta(hours=i), 1.0) for i in range(24)],
        # rolling 24 h windows; the reported timestamps are meaningless
        daily=[(hour0.replace(hour=4) - timedelta(days=i), 24.0 if i == 0 else 10.5) for i in range(24)],
    )
    rows = build_rows(hist, None, now)
    oldest_hour = hour0 - timedelta(hours=23)
    hourly = [r for r in rows if r[1] == 1.0]
    daily = [r for r in rows if r[1] == 10.5]
    assert len(hourly) == 23  # current hour is still running
    assert len(daily) == 23  # daily[0] is the same window as the hourly data
    assert daily[-1][0] == oldest_hour - timedelta(days=1)
    assert daily[0][0] == oldest_hour - timedelta(days=23)
    assert rows == sorted(rows)
    assert sum(kg for _, kg in rows) == 23 * 10.5 + 23 * 1.0

    # next run: only hours after the last imported one
    later = build_rows(hist, hourly[-2][0], now)
    assert later == [hourly[-1]]
