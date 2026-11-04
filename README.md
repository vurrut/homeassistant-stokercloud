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
| sensor | Boiler Temperature, Boiler Temperature Requested, DHW Temperature, DHW Temperature Requested, Smoke Temperature, Outdoor Temperature, Boiler Effect (kW), Boiler Power (%), Output Percentage, Oxygen, Total Consumption, Consumption 24h, Pellet Energy (kWh), Hopper Content, Hopper Distance, State, Boiler Photo Sensor, Chamber Pressure; Zone N Wanted/Forward Temperature and Zone N Valve for each active weather-compensation zone |
| binary_sensor | Running, Alarm, Circulate Pump, DHW Valve, Connected |
| number | Wanted Boiler Temperature (`boiler.temp`), Wanted DHW Temperature (`hot_water.temp`), Hopper Content (`hopper.content`) |
| switch | Burner (start/stop, same as the web app's on/off button) |
| button | Reset Alarm |

The controller's limits (min/max) for the setpoints are read from StokerCloud.
After a write, the integration refreshes once the cloud reports that the boiler has synced.

## Options

**Settings → Devices & services → NBE Stoker Cloud → Configure**

- **Update interval:** how often to poll StokerCloud (default 60 s, minimum 30 s).
- **Pellet calorific value:** kWh per kg, used by the Pellet Energy sensor (default 4.8).

## Energy dashboard

**Pellet Energy** is the total pellet consumption multiplied by the calorific value, in kWh.
To add it, open **Settings → Dashboards → Energy → Gas consumption** and select
`sensor.nbe_pellet_energy`. To track cost, enter your pellet price per kWh there. For example,
pellets at 0.38 €/kg with 4.8 kWh/kg cost about 0.079 €/kWh.

## Hopper level

If you fill the hopper by hand, set **Hopper Content** (`number.nbe_hopper_content`) to the
amount of pellets in it after each refill. The controller subtracts what it burns, and
**Hopper Content** (sensor) shows what is left. Use it in an automation to get a notification
before the hopper runs empty.

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
