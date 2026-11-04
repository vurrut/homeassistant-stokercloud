<img src="icon.png" alt="" width="96" align="right">

# homeassistant-stokercloud

Home Assistant integration for NBE pellet boilers connected to [StokerCloud](https://v16.stokercloud.dk/).

## Install

Install through HACS:

1. Open HACS → Integrations.
2. Click the three dots in the top right → **Custom repositories**.
3. Add `https://github.com/vurrut/homeassistant-stokercloud/` with category **Integration**.
4. Install **NBE Stoker Cloud** and restart Home Assistant.

## Setup

Requires Home Assistant 2025.11 or newer.

Go to **Settings → Devices & services → Add integration → NBE Stoker Cloud** and enter
the **user name and password** you use on https://v16.stokercloud.dk/.

Starting with v3 the password is required. The integration uses only the authenticated
API (`credentials: full`), which can both read and write. If you are upgrading from v1/v2
and your entry has no password, Home Assistant shows a **re-authentication** notification.
Enter the password there and keep your existing entities.

## Entities

All entities belong to one device, **NBE**.

| Platform | Entities |
|---|---|
| sensor | **History:** Consumption This Month / Last Month / This Year / Last Year, Average Daily Consumption (last 7 days), Pellets Days Left. **Live:** Boiler Temperature, Boiler Temperature Requested, DHW Temperature, DHW Temperature Requested, Smoke Temperature, Outdoor Temperature, Boiler Effect (kW), Boiler Power (%), Output Percentage, Oxygen, Total Consumption, Consumption 24h, Pellet Energy (kWh), Hopper Content, Hopper Distance, State, Boiler Photo Sensor, Chamber Pressure; Zone N Wanted/Forward Temperature and Zone N Valve for each active weather-compensation zone |
| binary_sensor | Running, Alarm, Circulate Pump, DHW Valve, Connected, Hopper Low |
| number | Wanted Boiler Temperature (`boiler.temp`), Wanted DHW Temperature (`hot_water.temp`), Hopper Content (`hopper.content`). **Advanced, disabled by default:** boiler/DHW start and stop differences, minimum return temperature, temperature reduction, boiler/DHW minimum and maximum power, O2 targets |
| water_heater | Hot Water: current and target DHW temperature; shows "heating" while the boiler heats hot water |
| event | Boiler Event: `state_changed`, `alarm`, `alarm_cleared` |
| switch | Burner (start/stop, same as the web app's on/off button) |
| button | Reset Alarm |

The controller's limits (min/max) for the setpoints are read from StokerCloud.
After a write, the integration refreshes once the cloud reports that the boiler has synced.

Advanced settings are disabled by default. To use one, open the NBE device, select the
entity and enable it. Each one uses the min/max and step size the controller reports.

## Options

**Settings → Devices & services → NBE Stoker Cloud → Configure**

- **Update interval:** maximum time between full data fetches (default 60 s, minimum 30 s).
- **Pellet calorific value:** kWh per kg, used for Pellet Energy and the imported statistics (default 4.8).
- **Fast updates** (on by default): every 10 s, check whether the boiler has sent new data
  (a very small request), and fetch it right away. The controller reports about once a
  minute, so changes appear within about 10 s instead of up to a minute late.
- **Low hopper threshold:** Hopper Low turns on at or below this amount (default 50 kg).
- **Import consumption history** (on by default): see below.

## Energy dashboard

You can use either of these sources under **Settings → Dashboards → Energy → Gas consumption**:

- **NBE pellet energy (`hass_stokercloud:pellet_energy_<user>`)** (recommended). This is
  imported from StokerCloud's consumption history: the last 24 days on the first start,
  then each completed hour. Your dashboard has history from day one. A kg version,
  `hass_stokercloud:pellet_consumption_<user>`, is also created for statistics graphs.
- **Pellet Energy (`sensor.nbe_pellet_energy`)**: the controller's total consumption
  multiplied by the calorific value. It only has history from when you installed the integration.

Use only one of them, or the consumption is counted twice. To track cost, enter your pellet
price per kWh. For example, pellets at 0.38 €/kg with 4.8 kWh/kg cost about 0.079 €/kWh.

## Automations

Each state change or alarm triggers `event.nbe_boiler_event`. It is also fired on the
event bus as `hass_stokercloud_event` with `type`, `from_state`, `to_state` and `code`.

```yaml
triggers:
  - trigger: state
    entity_id: event.nbe_boiler_event
    attribute: event_type
    to: alarm
actions:
  - action: notify.notify
    data:
      message: "Boiler alarm: {{ states('sensor.nbe_state') }}"
```

StokerCloud's own event log (`geteventdata.php`) currently times out, so the integration
detects events by comparing consecutive data updates.

## Hopper level

If you fill the hopper by hand, set **Hopper Content** (`number.nbe_hopper_content`) to the
amount of pellets in it after each refill. The controller subtracts what it burns, and
**Hopper Content** (sensor) shows what is left. **Pellets Days Left** divides it by the
average daily consumption of the last 7 days. **Hopper Low** turns on at the threshold set in
the options. If you don't track the content but have a hopper distance sensor, Hopper Low
uses the controller's own warning level instead.

## Service: `hass_stokercloud.set_value`

Writes any numeric controller setting by its StokerCloud id. The value is checked against
the min/max that the controller reports.

```yaml
action: hass_stokercloud.set_value
data:
  setting: boiler.diff_under
  value: 5
```

## Diagnostics

**Settings → Devices & services → NBE Stoker Cloud → ⋮ → Download diagnostics** exports the
raw controller data and settings. Your user name, password, serial number and city are removed.

## Example: change the boiler temperature from an automation

```yaml
action: number.set_value
target:
  entity_id: number.nbe_wanted_boiler_temperature
data:
  value: 72
```

Thanks to https://github.com/KristianOellegaard for the original integration.
