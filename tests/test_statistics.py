"""Statistics import against a real (in-memory) recorder."""
from datetime import timedelta

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import get_last_statistics
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

import pytest

from custom_components.hass_stokercloud.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    """Override conftest: the recorder must be set up before hass."""
    yield


async def test_import_and_continue(recorder_mock: Recorder, hass: HomeAssistant, mock_client) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="testuser",
        data={CONF_USERNAME: "testuser", CONF_PASSWORD: "secret"},
        options={"calorific_value": 5.0},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    def last(stat_id):
        return get_last_statistics(hass, 1, stat_id, False, {"sum", "state"})[stat_id][0]

    mass = await hass.async_add_executor_job(last, f"{DOMAIN}:pellet_consumption_testuser")
    energy = await hass.async_add_executor_job(last, f"{DOMAIN}:pellet_energy_testuser")
    # fixture: 23 complete hours x 1 kg + daily backfill rows of 10 kg
    assert mass["state"] == 1.0
    assert energy["sum"] == mass["sum"] * 5.0
    first_sum = mass["sum"]
    assert first_sum >= 23

    # a second import with the same history adds nothing (no double counting)
    coordinator = entry.runtime_data
    await coordinator.history_listeners[0](coordinator.data.history)
    await async_wait_recording_done(hass)
    mass2 = await hass.async_add_executor_job(last, f"{DOMAIN}:pellet_consumption_testuser")
    assert mass2["sum"] == first_sum
