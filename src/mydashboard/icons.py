"""Turn a Dynacat/Glance icon reference ('sh:jellyfin', 'di:x', ...) into an image URL."""

from __future__ import annotations

_CDN = {
    "sh": "https://cdn.jsdelivr.net/gh/selfhst/icons/svg/{}.svg",
    "di": "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/{}.svg",
    "si": "https://cdn.simpleicons.org/{}",
    "mdi": "https://cdn.jsdelivr.net/npm/@mdi/svg/svg/{}.svg",
}


def icon_url(icon: str | None) -> str | None:
    if not icon:
        return None
    if icon.startswith(("http://", "https://", "/")):
        return icon
    prefix, _, name = icon.partition(":")
    if name and prefix in _CDN:
        return _CDN[prefix].format(name)
    return None
