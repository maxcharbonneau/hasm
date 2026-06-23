<p align="center">
  <img src="custom_components/hasm/brand/icon.png" alt="HASM logo" width="120" height="120" />
</p>

# Home Assistant Site Manager (HASM)

HASM is a Home Assistant integration that lets you supervise and control a fleet
of remote Home Assistant instances from your own Home Assistant. Each remote
instance becomes a device with connectivity, version, update and error
information, and you can trigger restarts, reloads, and updates from one place.

## Features
- Each remote instance is exposed as a single device with: connectivity, Core/OS/Supervisor versions, number of available updates, and error count.
- Remote updates are surfaced as native `update.*` entities (Install + backup + progress support).
- Buttons: Restart and Reload configuration.
- A `hasm.call_remote_service` service to relay any service call to a remote instance.
- Polling interval, SSL verification, and the per-instance update entity cap are all configurable.

## Installation (HACS, custom repository)
1. In HACS, open the menu and choose **Custom repositories**, then add `https://github.com/maxcharbonneau/hasm` as an **Integration**.
2. Install **Home Assistant Site Manager (HASM)**, then restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration → HASM**.

## Adding an instance
When adding an instance you provide:
- **URL** of the remote instance (for example `https://home.example.com` or your Nabu Casa URL).
- A **Long-Lived Access Token** created on the remote instance (user profile → Long-Lived Access Tokens → Create Token).
- The **Verify SSL certificate** checkbox (leave it enabled unless the remote instance uses a self-signed certificate).

## Entities
For each configured instance HASM creates:
- A connectivity `binary_sensor` reporting whether the instance is reachable.
- Diagnostic sensors: Core version, OS version, Supervisor version, available updates, and error count.
- Native `update.*` entities mirroring the remote updates (Core, OS, Supervisor, add-ons, ...), supporting install, backup, and progress where the remote update supports them.
- Buttons to restart the remote instance and to reload its configuration.

## Service: `hasm.call_remote_service`
Relays an arbitrary service call to a remote Home Assistant managed by HASM.

```yaml
service: hasm.call_remote_service
data:
  config_entry_id: <your HASM instance entry id>
  remote_domain: homeassistant
  remote_service: restart
  service_data: {}
```

## Automation example (offline alert)
```yaml
automation:
  - alias: Remote instance offline alert
    trigger:
      - platform: state
        entity_id: binary_sensor.maison_connectivity
        to: "off"
        for: "00:10:00"
    action:
      - service: notify.notify
        data:
          message: "The Maison instance has been offline for 10 minutes."
```

## Security
The Long-Lived Access Token is stored in Home Assistant's encrypted store. TLS
certificates are verified by default (the verification can be disabled per
instance for self-signed certificates). HASM only talks to the remote instances
you configure: nothing leaves your Home Assistant.

## Roadmap
See [ROADMAP.md](ROADMAP.md) for the project direction — planned work, ideas, and non-goals.
