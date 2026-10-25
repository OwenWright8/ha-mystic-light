# MSI Mystic Light for Home Assistant

Control the RGB lighting (fans, ARGB/JRGB headers, onboard zones) of an MSI PC from Home Assistant.

It has two parts:

1. **Bridge** (`bridge/`): a small HTTP service on the Windows PC that wraps MSI's official
   [Mystic Light SDK](https://www.msi.com/Landing/mystic-light-rgb-gaming-pc/download). It talks to
   MSI Center's Mystic Light service, so anything MSI Center can control, this can too.
2. **Integration** (`custom_components/mystic_light`): one HA light entity per LED area, with
   on/off, colour, brightness and MSI's lighting styles as effects.

## 1. Install the bridge (Windows)

Requires MSI Center with the Mystic Light component installed.

1. Copy the `bridge` folder somewhere permanent, e.g. `C:\Users\<you>\MysticLightBridge`.
2. In an **elevated** PowerShell run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File C:\Users\<you>\MysticLightBridge\install.ps1
   ```

   This downloads MSI's signed SDK DLL (if missing), creates `config.json` with a random token,
   registers a logon task named *Mystic Light Bridge* that runs elevated (the SDK requires admin),
   and opens TCP 8765 in Windows Firewall for the local subnet only.

`uninstall.ps1` removes the task and firewall rule.

## 2. Install the integration (HACS)

1. HACS → ⋮ → **Custom repositories** → add this repo's URL, category **Integration**.
2. Download **MSI Mystic Light**, restart Home Assistant.
3. Settings → Devices & services → **Add integration** → *MSI Mystic Light*.
   Enter the PC's IP, port `8765`, and the `token` from `config.json`.

## Notes

- Brightness is applied by scaling the colour, which works on every device the SDK supports.
- **Power cap** (integration options, default 60%): bright white can draw more current than an ARGB
  header supplies, which makes fans flicker. Total R+G+B output is capped at this share of full white;
  saturated colours keep full brightness, and HA still shows the brightness you asked for.
- Turning a light off uses the device's `Off` style when available, otherwise black.
- Picking a colour while an animated style (e.g. Rainbow) is active switches to a solid style.
- State is polled every 15 seconds, so changes made in MSI Center show up shortly after.
- The bridge runs under a small supervisor (`MysticLightBridge.ps1`) that restarts it within seconds
  if MSI's SDK crashes the process, which has been seen after days of polling.
