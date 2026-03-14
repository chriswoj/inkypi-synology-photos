import io
import logging
import random
import re

import requests
from PIL import Image, ImageOps

from plugins.base_plugin.base_plugin import BasePlugin
from utils.image_utils import apply_image_enhancements, pad_image_blur

logger = logging.getLogger(__name__)


class SynologyPhotosProvider:
    """Stateless client for the Synology Photos public sharing API."""

    def __init__(self, base_url, passphrase, verify_ssl=False):
        self.base_url = base_url.rstrip("/")
        self.passphrase = passphrase
        self.verify_ssl = verify_ssl
        self.sharing_sid = None

    def _get_sharing_sid(self):
        """Authenticate via the sharing login endpoint to obtain a sharing_sid cookie."""
        url = f"{self.base_url}/photo/webapi/entry.cgi"
        data = {
            "api": "SYNO.Core.Sharing.Login",
            "method": "login",
            "version": 1,
            "sharing_id": self.passphrase,
        }

        try:
            resp = requests.post(url, data=data, verify=self.verify_ssl, timeout=15)
            resp.raise_for_status()
        except requests.exceptions.SSLError:
            raise RuntimeError(
                "SSL certificate error. Try disabling 'Verify SSL' in plugin settings."
            )
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Cannot connect to NAS. Check the sharing URL and network connectivity."
            )

        result = resp.json()
        if not result.get("success"):
            raise RuntimeError(
                "Failed to authenticate. Check that the sharing URL is correct and the share is still active."
            )

        self.sharing_sid = result["data"]["sharing_sid"]
        return self.sharing_sid

    def _request_headers(self):
        """Build headers required for sharing API requests."""
        return {
            "Cookie": f"sharing_sid={self.sharing_sid}",
            "x-syno-sharing": self.passphrase,
        }

    def list_items(self, limit=1000):
        """List all photos in the shared album using pagination."""
        url = f"{self.base_url}/photo/mo/sharing/webapi/entry.cgi"
        all_items = []
        offset = 0

        while True:
            data = {
                "api": "SYNO.Foto.Browse.Item",
                "method": "list",
                "version": 1,
                "passphrase": f'"{self.passphrase}"',
                "offset": offset,
                "limit": limit,
                "additional": '["thumbnail","resolution"]',
            }

            try:
                resp = requests.post(
                    url,
                    data=data,
                    headers=self._request_headers(),
                    verify=self.verify_ssl,
                    timeout=30,
                )
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Failed to list photos: {e}")

            result = resp.json()
            if not result.get("success"):
                raise RuntimeError(
                    "Failed to list photos. The sharing link may be invalid or expired."
                )

            items = result.get("data", {}).get("list", [])
            all_items.extend(items)

            if len(items) < limit:
                break

            offset += limit

        return all_items

    def get_thumbnail_url(self, item, size="xl"):
        """Build the thumbnail download URL for a photo item."""
        item_id = item["id"]
        thumbnail = item.get("additional", {}).get("thumbnail", {})
        cache_key = thumbnail.get("cache_key", f"{item_id}_0")

        params = {
            "api": "SYNO.Foto.Thumbnail",
            "method": "get",
            "version": 1,
            "id": item_id,
            "cache_key": cache_key,
            "type": "unit",
            "size": size,
            "passphrase": self.passphrase,
        }

        return f"{self.base_url}/photo/mo/sharing/webapi/entry.cgi", params

    def download_photo(self, item, size="xl"):
        """Download photo bytes. Uses thumbnail API for sized versions, download API for originals."""
        if size == "original":
            return self._download_original(item)

        url, params = self.get_thumbnail_url(item, size=size)

        try:
            resp = requests.get(
                url,
                params=params,
                headers=self._request_headers(),
                verify=self.verify_ssl,
                timeout=60,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to download photo: {e}")

        if resp.headers.get("Content-Type", "").startswith("application/json"):
            raise RuntimeError("Failed to download photo. The server returned an error.")

        return resp.content

    def _download_original(self, item):
        """Download the original full-resolution photo."""
        url = f"{self.base_url}/photo/mo/sharing/webapi/entry.cgi"
        data = {
            "api": "SYNO.Foto.Download",
            "method": "download",
            "version": 1,
            "passphrase": f'"{self.passphrase}"',
            "unit_id": f"[{item['id']}]",
        }

        try:
            resp = requests.post(
                url,
                data=data,
                headers=self._request_headers(),
                verify=self.verify_ssl,
                timeout=120,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to download original photo: {e}")

        if resp.headers.get("Content-Type", "").startswith("application/json"):
            raise RuntimeError("Failed to download original photo. The server returned an error.")

        return resp.content


def parse_sharing_url(url):
    """Parse a Synology Photos sharing URL into base_url and passphrase.

    Accepts URLs like:
        https://hostname:5001/mo/sharing/1e9WU4WZr#/
        https://hostname:5001/photo/mo/sharing/1e9WU4WZr
        http://192.168.1.100:5000/mo/sharing/AbCdEfG
    """
    url = url.strip()
    # Strip fragment
    url = url.split("#")[0].rstrip("/")

    match = re.match(
        r"^(https?://[^/]+)(?:/photo)?/mo/sharing/([A-Za-z0-9_-]+)", url
    )
    if not match:
        raise RuntimeError(
            "Invalid sharing URL. Expected format: https://your-nas:5001/mo/sharing/XXXXXXX"
        )

    base_url = match.group(1)
    passphrase = match.group(2)
    return base_url, passphrase


class SynologyPhotos(BasePlugin):
    """InkyPi plugin that displays random photos from a Synology Photos shared album."""

    def generate_image(self, settings, device_config):
        # Parse sharing URL
        sharing_url = settings.get("sharing_url", "").strip()
        if not sharing_url:
            raise RuntimeError("Sharing URL is required. Enter your Synology Photos sharing link in plugin settings.")

        base_url, passphrase = parse_sharing_url(sharing_url)

        # Display dimensions
        width, height = device_config.get_resolution()
        orientation = device_config.get_config("orientation")
        if orientation == "vertical":
            width, height = height, width
        dimensions = (width, height)

        # Settings
        verify_ssl = settings.get("verify_ssl", "false").lower() == "true"
        image_size = settings.get("image_size", "xl")
        scale_to_fit = settings.get("scale_to_fit", "false").lower() == "true"
        bg_option = settings.get("background", "blur")
        bg_color = settings.get("bg_color", "#000000")

        # Connect and fetch photos
        provider = SynologyPhotosProvider(base_url, passphrase, verify_ssl=verify_ssl)
        provider._get_sharing_sid()

        items = provider.list_items()
        if not items:
            raise RuntimeError("No photos found in the shared album.")

        # Pick a random photo
        item = random.choice(items)
        logger.info("Selected photo id=%s from %d available", item.get("id"), len(items))

        # Download
        photo_bytes = provider.download_photo(item, size=image_size)
        img = Image.open(io.BytesIO(photo_bytes))
        img = img.convert("RGB")

        # Resize to fit display
        if scale_to_fit:
            if bg_option == "blur":
                img = pad_image_blur(img, dimensions)
            else:
                img = ImageOps.pad(
                    img,
                    dimensions,
                    color=bg_color,
                    method=Image.Resampling.LANCZOS,
                )
        else:
            img = ImageOps.fit(img, dimensions, method=Image.Resampling.LANCZOS)

        # Apply image enhancements
        img = apply_image_enhancements(img, settings)

        return img
