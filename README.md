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
| sensor | Boiler Temperature, Boiler Temperature Requested, DHW Temperature, DHW Temperature Requested, Smoke Temperature, Outdoor Temperature, Boiler Effect (kW), Boiler Power (%), Output Percentage, Oxygen, Total Consumption, Consumption 24h, Hopper Distance, State, Boiler Photo Sensor, Chamber Pressure |
| binary_sensor | Running, Alarm, Circulate Pump, DHW Valve, Connected |
| number | Wanted Boiler Temperature (`boiler.temp`), Wanted DHW Temperature (`hot_water.temp`) |
| switch | Burner (start/stop, same as the web app's on/off button) |
| button | Reset Alarm |

The controller's limits (min/max) for the setpoints are read from StokerCloud.
After a write, the integration refreshes once the cloud reports that the boiler has synced.

## Example: change the boiler temperature from an automation

```yaml
action: number.set_value
target:
  entity_id: number.nbe_wanted_boiler_temperature
data:
  value: 72
```

Thanks to https://github.com/KristianOellegaard for the original integration.
