# Torque OBD-II Integration for Home Assistant

This integration allows Home Assistant to receive vehicle data from the [Torque Pro](https://torque-bhp.com/) Android application via OBD-II.

## 📚 Documentation Quick Links

- **[PID Reference Guide](../../PIDS.md)** - Complete database of 151+ supported OBD-II PIDs
- **[Troubleshooting Guide](../../TROUBLESHOOTING.md)** - Solutions to common issues
- **[Architecture Documentation](ARCHITECTURE.md)** - Technical details for developers

## Features

- Real-time vehicle data monitoring
- Support for 151+ vehicle parameters including:
  - Vehicle speed and GPS speed
  - Engine RPM
  - Engine coolant, oil, and intake air temperatures
  - Fuel level and consumption
  - Throttle position and engine load
  - Battery voltage
  - GPS location data (latitude, longitude, altitude, bearing)
  - Trip distance and time
  - And many more OBD-II parameters

## Installation

1. Copy the `torque_obd` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to Configuration → Integrations
4. Click the "+ ADD INTEGRATION" button
5. Search for "Torque OBD-II"
6. Follow the configuration steps

## Configuration

### Home Assistant Setup

1. Add the Torque OBD-II integration through the UI
2. Enter a descriptive **Vehicle Name** (e.g., "2025 Ford Escape" or "2017 Ford Fusion")
3. Optionally enter an **Email Address** (note: Torque does not reliably send email in payloads, so this is optional)
4. Home Assistant will create a unique API endpoint for this vehicle based on the name

### Torque App Setup

Each vehicle gets its own unique API endpoint based on the vehicle name you configured.

**Example**: If you named your vehicle "2025 Ford Escape", the endpoint will be:
`http://YOUR_HA_IP:8123/api/torque-2025-ford-escape`

**Example**: If you named your vehicle "2017 Ford Fusion", the endpoint will be:
`http://YOUR_HA_IP:8123/api/torque-2017-ford-fusion`

#### Configuration Steps:

1. Open Torque Pro on your Android device
2. Go to Settings → Data Logging & Upload
3. Select "Webserver" or "Web Upload"
4. Configure the following:
   - **Web Upload URL**: Use the unique endpoint shown in Home Assistant after configuration
   - **Email Address**: Optional (Torque does not reliably send this field)
   - **Enable Logging**: Turn on
5. Select the PIDs you want to log
6. Save settings
7. **⚠️ CRITICAL - First Time Setup**: After configuring both Home Assistant and Torque for the first time:
   - Go to Android Settings → Apps → Torque Pro
   - Tap **Force Stop**
   - Reopen Torque Pro
   - Reconnect to your OBD-II adapter
   - This ensures Torque starts sending data to the new endpoint

**Note**: Replace `YOUR_HA_IP` with your Home Assistant IP address. If using HTTPS, use `https://` instead.

### Several vehicles on ONE phone (Torque profiles)

Torque Pro has a single, global upload URL shared by all vehicle profiles.
Uploads are routed to the right HA vehicle as follows:

1. **Profile name**: Torque sends the active profile (`profileName`). Name each Torque
   profile like the HA vehicle (case/spaces ignored): "Car" → "Car", "Van" → "Van".
   The vehicle name, the integration entry title and the device name (even renamed
   in HA) are all accepted, and so is a profile that CONTAINS the vehicle name as a
   whole word ("My CAR" → "Car", "Daily car" → "Car") when only one
   vehicle matches. Uploads for a **disabled** vehicle are ignored.
   Phones that never sent a recognised profile name (e.g. a friend's phone using its
   own vehicle URL) are NOT affected: their uploads always go straight to their URL.
2. **Numeric profile IDs**: at the start of a trip Torque sometimes sends a number
   (e.g. `1966413…`) instead of the name. Such uploads are **held** (per Torque session)
   until the real name arrives, then delivered to the right vehicle. The number is
   **learned** as an alias of that vehicle, so next trips are routed immediately.
3. If the same number is seen for two vehicles, it is marked ambiguous and never used.
4. Aliases can be viewed/edited: Settings → Devices & services → Torque OBD-II →
   the vehicle → **Configure**.
5. No session info, or no recognised profile after 10 min: vehicle of the URL (warning in logs).

### Finding Your Vehicle's API Endpoint

After configuring a vehicle in Home Assistant:
1. Go to Configuration → Integrations
2. Find your Torque OBD-II vehicle entry
3. The API endpoint will be shown in the integration details or check the logs

The endpoint format is: `/api/torque-<vehicle-name-in-lowercase-with-dashes>`

### Example URL Configuration

For a vehicle named "2025 Ford Escape":
```
http://192.168.1.100:8123/api/torque-2025-ford-escape
```

For a vehicle named "2017 Ford Fusion":
```
http://192.168.1.100:8123/api/torque-2017-ford-fusion
```

Or if using SSL:
```
https://your-domain.com/api/torque-2025-ford-escape
```

## Entities created per vehicle

| Entity | Description |
|---|---|
| `sensor.*` | One sensor per PID received from Torque (created automatically) |
| `sensor.<vehicle>_url_torque` | URL to paste in Torque Pro (internal/external in attributes) |
| `binary_sensor.<vehicle>_torque_connecte` | ON while Torque is uploading (OFF after 120 s without data) |
| `device_tracker.<vehicle>_position` | Vehicle GPS position (kff1006/kff1005), usable on the map and in zones |

**Diagnostics**: Settings → Devices & Services → Torque OBD-II → ⋮ → *Download diagnostics* gives the last raw payload received (email and GPS redacted), including Torque's `defaultUnit*`/`userUnit*` fields — useful to check the real unit of a PID.

## Sensors

The integration **dynamically creates sensors** based on data received from Torque. Sensor names are automatically extracted from the Torque payload when available, providing accurate, vehicle-specific names for each parameter.

### How Sensor Names Work

1. **Dynamic Naming**: The integration uses sensor names provided by Torque in the payload (`userFullName{PID}` or `userShortName{PID}`)
2. **Fallback to Definitions**: If Torque doesn't provide a name, the integration falls back to predefined sensor names
3. **Generic Naming**: If neither is available, sensors are created with a generic "PID {key}" name

This means sensor names will automatically match what you see in the Torque app!

### Entity ID Format

All sensor entity IDs are prefixed with the vehicle name to ensure uniqueness and organization:

**Format**: `sensor.<vehicle_name>_<sensor_name>`

**Examples**:
- Vehicle: "2025 Ford Escape", Sensor: "Fuel Level" → `sensor.2025_ford_escape_fuel_level`
- Vehicle: "2025 Ford Escape", Sensor: "Engine RPM" → `sensor.2025_ford_escape_engine_rpm`
- Vehicle: "2017 Ford Fusion", Sensor: "Coolant Temperature" → `sensor.2017_ford_fusion_coolant_temperature`

This makes it easy to identify which vehicle each sensor belongs to!

**Important Note on Units**: Torque sends sensor values in **metric units only**, regardless of the unit settings displayed in the app. This means:
- Temperatures are always in Celsius (°C)
- Speeds are always in kilometers per hour (km/h)
- Distances are always in kilometers (km)
- Fuel volumes are always in liters (L)
- Pressures are always in kilopascals (kPa)

The integration assumes all incoming values are metric and sets the units accordingly. Home Assistant will handle any necessary conversions based on your system's unit preferences.

### Custom Sensor Definitions (Optional)

While the integration now automatically uses sensor names from Torque, you can still customize sensor definitions or override defaults by creating a `torque_sensor_definitions.yaml` file in your Home Assistant configuration directory.

**Note**: With dynamic sensor naming, custom definitions are mainly useful for:
- Overriding units of measurement
- Setting custom icons
- Configuring device classes and state classes
- Supporting PIDs that Torque doesn't name

#### Creating Custom Sensor Definitions

1. Create a file named `torque_sensor_definitions.yaml` in your Home Assistant config directory (same location as `configuration.yaml`)
2. Add your custom sensor definitions in YAML format
3. Restart Home Assistant to load the new definitions

#### YAML File Format

```yaml
# Override an existing sensor
kd:
  name: "My Car Speed"
  unit: "km/h"
  icon: "mdi:speedometer"
  device_class: null
  state_class: "measurement"

# Add a custom sensor for a new PID
kff5001:
  name: "Custom Boost Pressure"
  unit: "psi"
  icon: "mdi:gauge"
  device_class: "pressure"
  state_class: "measurement"
```

#### Sensor Definition Fields

- **name** (required): Human-readable name for the sensor (only used if Torque doesn't provide a name)
- **unit** (optional): Unit of measurement (e.g., "km/h", "°C", "RPM", "%") - should be metric
- **icon** (optional): Material Design Icon name (e.g., "mdi:speedometer"). Defaults to "mdi:car-info"
- **device_class** (optional): Home Assistant device class (e.g., "temperature", "voltage", "pressure", null)
- **state_class** (optional): Home Assistant state class:
  - `"measurement"`: For values that can go up or down
  - `"total_increasing"`: For monotonically increasing values (like trip distance)
  - `null`: For values without a state class

#### PID Naming Convention

Torque uses the following PID naming convention:

**Standard OBD-II PIDs**: "k" + hex value
- `k4`: Engine Load (OBD-II PID 0x04)
- `k5`: Engine Coolant Temperature (OBD-II PID 0x05)
- `kc`: Engine RPM (OBD-II PID 0x0C)
- `kd`: Vehicle Speed (OBD-II PID 0x0D)
- `kf`: Intake Air Temperature (OBD-II PID 0x0F)
- `k10`: MAF Air Flow Rate (OBD-II PID 0x10)
- `k11`: Throttle Position (OBD-II PID 0x11)
- `k2f`: Fuel Level (OBD-II PID 0x2F)

**Torque Custom PIDs**: "kff" + number
- `kff1001`: GPS Speed (km/h)
- `kff1005`: GPS Longitude
- `kff1006`: GPS Latitude
- `kff1007`: GPS Bearing
- `kff1010`: GPS Altitude
- `kff1238`: Voltage (OBD adapter)
- `kff1204`: Trip Distance
- `kff1266`: Trip Time (since journey start)

#### Example Configuration File

An example configuration file is included in the integration: `torque_sensor_definitions.yaml.example`. Copy this file to your config directory and modify it to suit your needs:

```bash
cp custom_components/torque_obd/torque_sensor_definitions.yaml.example /config/torque_sensor_definitions.yaml
```

#### How It Works

1. The integration loads default sensor definitions at startup (as fallbacks)
2. If `torque_sensor_definitions.yaml` exists in your config directory, it loads the custom definitions
3. Custom definitions **override** default definitions for the same PID
4. New PIDs in the custom file are **added** to the available sensors
5. **When Torque sends data**: Sensor names from the Torque payload (`userFullName{PID}`) take priority over all definitions
6. Any PIDs received from Torque that aren't in either file will create a generic sensor automatically

### Supported Sensors

- **Speed**: Vehicle speed (OBD-II), GPS speed
- **Engine**: RPM, coolant temperature, oil temperature, intake air temperature
- **Fuel**: Fuel level, fuel remaining, fuel used (trip), average fuel economy, instant fuel economy
- **Throttle & Load**: Throttle position, engine load
- **Battery**: Battery voltage
- **GPS**: Latitude, longitude, altitude, bearing
- **Distance & Time**: Trip distance, trip time
- **Other**: Ambient air temperature, MAF air flow rate, timing advance, barometric pressure, fuel pressure, intake manifold pressure

## Security Considerations

The integration creates vehicle-specific HTTP endpoints (e.g., `/api/torque-<vehicle-name>`) that **do not require authentication**. This is necessary because the Torque app does not support authenticated requests. To mitigate security risks:

1. **Network Security**: Use this integration only on a trusted local network
2. **Email Identifier**: If an email is configured AND Torque sends `eml`, uploads with a different email are ignored (uploads without `eml` are still accepted)
3. **Firewall**: Consider using firewall rules to restrict access to the Home Assistant instance
4. **Internal Network**: For best security, keep Home Assistant on an internal network and use a VPN for remote access

If you need to expose Home Assistant externally, consider using:
- A reverse proxy with additional authentication
- Network segmentation to isolate the Home Assistant instance
- VPN access instead of direct internet exposure

## Troubleshooting

📖 **[View Complete Troubleshooting Guide](../../TROUBLESHOOTING.md)** - Comprehensive solutions to all common issues.

### Quick Troubleshooting

#### No Data Appearing in Home Assistant

**⚠️ MOST COMMON ISSUE**: After initial setup, you must **force stop** the Torque app and reopen it:
1. Go to Android Settings → Apps → Torque Pro
2. Tap **Force Stop**
3. Reopen Torque Pro and reconnect to OBD adapter

**Other checks**:
1. **Check the Torque app is sending data**:
   - Ensure "Enable Logging" is turned on
   - Verify the URL is correct (including port 8123)
   - Check your device has network connectivity

2. **Check Home Assistant logs**:
   - Go to Configuration → Logs
   - Look for errors related to "torque"

3. **Verify endpoint URL**:
   - Make sure the Torque app URL matches your vehicle's unique endpoint
   - Check for typos in the vehicle name portion of the URL

4. **Network connectivity**:
   - Ensure your Android device can reach Home Assistant
   - Try accessing `http://YOUR_HA_IP:8123` in a browser on your Android device
   - Check firewall settings

#### Sensors Show "Unavailable"

- Sensors will show as "Unavailable" until the first data is received from Torque
- Start driving with the Torque app running and logging enabled
- Data should appear within a few seconds once logging starts

📖 For more issues and detailed solutions, see the **[Complete Troubleshooting Guide](../../TROUBLESHOOTING.md)**.

## Technical Details

### API Endpoints

Each configured vehicle gets its own unique HTTP endpoint at `/api/torque-<vehicle-name>` that accepts both GET and POST requests with form data containing OBD-II parameters.

The endpoint is created automatically when you configure a vehicle, using the vehicle name you provide (converted to lowercase with spaces replaced by dashes).

**Examples**:
- Vehicle "2025 Ford Escape" → `/api/torque-2025-ford-escape`
- Vehicle "2017 Ford Fusion" → `/api/torque-2017-ford-fusion`
- Vehicle "My Car" → `/api/torque-my-car`

### Data Format

Torque sends data using parameter keys like:
- `kd`: Vehicle speed
- `kc`: Engine RPM
- `k2f`: Fuel level
- `kff1001`: GPS speed
- And many more...

The integration automatically maps these keys to human-readable sensor names.

### Multiple Vehicles

You can add multiple vehicles by creating additional integration instances with different vehicle names and email addresses. Each vehicle will have:
- Its own unique API endpoint
- Its own set of sensors
- Its own device in Home Assistant

This allows you to monitor multiple vehicles simultaneously without any conflicts.

## Credits

This integration receives data from the Torque Pro Android application. Torque is a trademark of Ian Hawkins.

## License

This integration is provided as-is under the MIT License.
