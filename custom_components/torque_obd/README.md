# Torque OBD-II for Home Assistant

Full documentation (French, with an English summary): see the
[repository README](https://github.com/Marlboro62/Home-Assistant-Torque-OBDII-2027#readme).

## How data is received

Each configured vehicle gets its own **Home Assistant webhook** with a random id
(`webhook.async_generate_id()`), registered with `webhook.async_register` for `GET` and `POST`
(Torque Pro sends a query string by default). The full address is shown:

- at the end of the config flow;
- in the vehicle options: **Address to enter in Torque Pro**.

Enter it in Torque Pro → Settings → Data Logging & Upload → **Webserver URL**.

The address acts as a key: anyone who knows it can send data for the vehicle. It is never stored
in an entity state or attribute and is redacted from diagnostics. If it leaks, use
**Generate a new address** in the vehicle options: the previous one stops working immediately.

One address is enough for a phone with several Torque profiles: the vehicle is chosen from the
Torque profile name (see the repository README).

## Upgrading from 2027.1.x

The former `/api/torque-<vehicle-name>` endpoint required no authentication and has been removed.
Existing entries are migrated (config entry version 1 → 2): a webhook id is generated and a
warning is raised in **Settings → Repairs** until the new address has been displayed from the
vehicle options. The former "Torque URL" diagnostic sensor is removed.

## Diagnostics

Downloadable from the integration page. Phone ids (`id`, `routed_devices`), the webhook id,
e-mail and GPS position are redacted, in the entry data, the options and the last payload.
