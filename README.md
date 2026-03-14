# InkyPi-Synology-Photos

**InkyPi-Synology-Photos** is a plugin for [InkyPi](https://github.com/fatihak/InkyPi) that displays random photos from a [Synology Photos](https://www.synology.com/en-global/dsm/feature/photos) public shared album on your e-ink display.

No API keys required — it works entirely through Synology Photos **public sharing links**, making setup as simple as pasting a URL.

## Features

- Fetches photos from a Synology Photos public shared album via sharing link
- Randomly selects a photo on each refresh
- No API key or login required — uses the public sharing passphrase
- Supports self-signed SSL certificates (common on internal NAS devices)
- Image enhancement controls: saturation, brightness, contrast, sharpness
- Scale-to-fit with blur or solid color background padding
- Works with all InkyPi-supported e-ink displays (4" to 13.3")

## Installation

Install the plugin using the InkyPi CLI:

```bash
inkypi plugin install synology_photos https://github.com/chriswoj/InkyPi-Synology-Photos
```

No `.env` keys or API credentials are needed.

## Configuration

### Plugin Settings

| Setting | Description | Required | Default |
|---|---|---|---|
| **Sharing URL** | Full Synology Photos public sharing link | Yes | — |
| **Verify SSL** | Enable SSL certificate verification | No | Off (allows self-signed certs) |
| **Image Size** | Photo quality to fetch (`sm`, `m`, `xl`, or `original`) | No | `xl` |
| **Scale to Fit** | Pad image to fill display instead of cropping | No | Off |
| **Background** | Padding style when Scale to Fit is on: Blur or solid Color | No | Blur |
| **Saturation** | Image saturation adjustment (0.0–2.0) | No | 1.0 |
| **Brightness** | Image brightness adjustment (0.0–2.0) | No | 1.0 |
| **Contrast** | Image contrast adjustment (0.0–2.0) | No | 1.0 |
| **Sharpness** | Image sharpness adjustment (0.0–2.0) | No | 1.0 |

### Creating a Synology Photos Sharing Link

1. Open **Synology Photos** on your NAS (DSM 7+)
2. Navigate to the album you want to display
3. Click **Share** and enable **Public sharing**
4. Copy the generated link (e.g., `https://your-nas:5001/mo/sharing/XXXXXXX`)
5. Paste this link into the plugin's **Sharing URL** field

### SSL Certificates

Most home NAS devices use self-signed SSL certificates. The plugin disables SSL verification by default to support this. If your NAS has a valid certificate (e.g., via Let's Encrypt / DDNS), you can enable the **Verify SSL** toggle.

## How It Works

1. The plugin parses the sharing URL to extract the NAS base URL and sharing passphrase
2. It authenticates via the Synology sharing API to obtain a session cookie
3. It lists all photos in the shared album
4. A random photo is selected and downloaded
5. Image enhancements are applied before rendering on the e-ink screen

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE.md) file for details.

## Credits

- [InkyPi](https://github.com/fatihak/InkyPi) by fatihak — the e-ink display platform
- [InkyPi-Plugin-Template](https://github.com/fatihak/InkyPi-Plugin-Template) — plugin scaffold
