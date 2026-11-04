"""Import StokerCloud consumption history into Home Assistant long-term statistics.

Creates two external statistics per account, usable in the Energy dashboard
(Gas consumption) and in statistics graphs:

* ``hass_stokercloud:pellet_energy_<user>``       kWh
* ``hass_stokercloud:pellet_consumption_<user>``  kg

On the first run the last 24 days are back-filled (one row per 24 h window,
the granularity StokerCloud offers), then completed hours are added as they come.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfEnergy, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN
from .coordinator import ConsumptionHistory

_LOGGER = logging.getLogger(__name__)

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


def statistic_ids(username: str) -> tuple[str, str]:
    user = slugify(username) or "account"
    return f"{DOMAIN}:pellet_energy_{user}", f"{DOMAIN}:pellet_consumption_{user}"


def _hour_floor(ts: datetime) -> datetime:
    return ts.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def build_rows(
    history: ConsumptionHistory,
    last_start: datetime | None,
    now: datetime,
) -> list[tuple[datetime, float]]:
    """Return ``(hour start, kg)`` rows to add after ``last_start``, oldest first.

    StokerCloud's "days" are rolling 24 h windows that end with the hourly
    window (``daily[0]`` equals the sum of the 24 hourly values; the
    timestamps it reports for days are not the window boundaries). So on the
    first import ``daily[i]`` (i >= 1) is booked as one row at
    ``oldest_hour - i days``, followed by the complete hours. The newest hour
    is still running and is skipped until it is complete.
    """
    hourly = sorted(((_hour_floor(t), kg) for t, kg in history.hourly), key=lambda r: r[0])
    complete = [(t, kg) for t, kg in hourly if t + HOUR <= now]
    rows: list[tuple[datetime, float]] = []

    if last_start is None and hourly:
        oldest_hour = hourly[0][0]
        for i, (_, kg) in enumerate(history.daily):
            if i == 0:
                continue  # same window as the hourly data
            rows.append((oldest_hour - i * DAY, kg))

    rows.extend((t, kg) for t, kg in complete if last_start is None or t > last_start)
    rows.sort(key=lambda r: r[0])
    return rows


class StatisticsImporter:
    """Keeps the external statistics in sync with StokerCloud's history."""

    def __init__(self, hass: HomeAssistant, username: str, calorific_value: float) -> None:
        self.hass = hass
        self.calorific_value = calorific_value
        self.energy_id, self.mass_id = statistic_ids(username)
        self._name = username

    async def _last(self, statistic_id: str) -> tuple[datetime | None, float]:
        result = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, statistic_id, False, {"sum"}
        )
        rows = result.get(statistic_id)
        if not rows:
            return None, 0.0
        row = rows[0]
        start = row["start"]
        if isinstance(start, (int, float)):
            start = datetime.fromtimestamp(start, tz=timezone.utc)
        return start, float(row.get("sum") or 0.0)

    async def async_import(self, history: ConsumptionHistory) -> None:
        last_start, mass_sum = await self._last(self.mass_id)
        _, energy_sum = await self._last(self.energy_id)
        rows = build_rows(history, last_start, dt_util.utcnow())
        if not rows:
            return

        mass_stats: list[StatisticData] = []
        energy_stats: list[StatisticData] = []
        for start, kg in rows:
            mass_sum += kg
            energy_sum += kg * self.calorific_value
            mass_stats.append(StatisticData(start=start, state=kg, sum=round(mass_sum, 3)))
            energy_stats.append(
                StatisticData(
                    start=start, state=kg * self.calorific_value, sum=round(energy_sum, 3)
                )
            )

        common = {
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "source": DOMAIN,
        }
        async_add_external_statistics(
            self.hass,
            StatisticMetaData(
                **common,
                name=f"NBE pellet consumption ({self._name})",
                statistic_id=self.mass_id,
                unit_class="mass",
                unit_of_measurement=UnitOfMass.KILOGRAMS,
            ),
            mass_stats,
        )
        async_add_external_statistics(
            self.hass,
            StatisticMetaData(
                **common,
                name=f"NBE pellet energy ({self._name})",
                statistic_id=self.energy_id,
                unit_class="energy",
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            ),
            energy_stats,
        )
        _LOGGER.debug("Imported %d consumption rows up to %s", len(rows), rows[-1][0])
