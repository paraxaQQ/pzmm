"""Lightweight GitHub-releases check for pzmm.

One GET to api.github.com/releases/latest, simple semver compare against
core.__version__. No telemetry, no auto-download — we just surface a link
to the release page. Silent-fail on network errors; cached for 6 hours
via config.
"""
from __future__ import annotations
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from core import __version__ as CURRENT_VERSION


REPO_OWNER = "paraxaQQ"
REPO_NAME  = "pzmm"
API_URL    = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

MIN_CHECK_INTERVAL_S = 6 * 60 * 60   # 6 hours


@dataclass
class UpdateInfo:
    tag:       str         # e.g. "v0.3.0"
    version:   str         # e.g. "0.3.0" (tag minus leading 'v')
    url:       str         # html_url on github.com
    name:      str         # release name ("pzmm v0.3.0")
    body:      str         # release notes


def _parse_version(v: str) -> tuple[int, ...]:
    """Very small semver: 'v0.3.0' → (0, 3, 0). Non-numeric tails are dropped."""
    v = v.strip().lstrip("vV")
    nums = re.findall(r"\d+", v)
    return tuple(int(n) for n in nums) or (0,)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def fetch_latest(timeout: float = 3.0) -> Optional[UpdateInfo]:
    """Hit GitHub. Returns None on any error."""
    req = urllib.request.Request(
        API_URL,
        headers={
            "Accept":     "application/vnd.github+json",
            "User-Agent": f"pzmm/{CURRENT_VERSION}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None

    tag = data.get("tag_name") or ""
    if not tag:
        return None
    return UpdateInfo(
        tag=tag,
        version=tag.lstrip("vV"),
        url=data.get("html_url") or f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases",
        name=data.get("name") or tag,
        body=data.get("body") or "",
    )


def check_for_update(force: bool = False) -> Optional[UpdateInfo]:
    """Returns an UpdateInfo when a newer release exists, else None.

    Respects the 6-hour cache unless `force=True`. Updates config bookkeeping.
    Dismissed tags are honored — if the user said "don't nag me about v0.3.0"
    and that's still the latest, we return None.
    """
    # Lazy-import so config.py doesn't need to exist at module import time
    # if we're ever tested in isolation.
    from core import config as config_mod

    cfg = config_mod.load()
    now = time.time()
    if not force and cfg.last_update_check_ts:
        if (now - cfg.last_update_check_ts) < MIN_CHECK_INTERVAL_S:
            # Use cached answer: if we recently saw a newer tag, keep offering it
            if cfg.last_known_latest and _is_newer(cfg.last_known_latest, CURRENT_VERSION):
                if cfg.last_known_latest != cfg.dismissed_update:
                    return UpdateInfo(
                        tag=cfg.last_known_latest,
                        version=cfg.last_known_latest.lstrip("vV"),
                        url=f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/tag/{cfg.last_known_latest}",
                        name=cfg.last_known_latest,
                        body="",
                    )
            return None

    info = fetch_latest()
    cfg.last_update_check_ts = now
    if info is not None:
        cfg.last_known_latest = info.tag
    config_mod.save(cfg)

    if info is None:
        return None
    if not _is_newer(info.tag, CURRENT_VERSION):
        return None
    if info.tag == cfg.dismissed_update:
        return None
    return info


def dismiss(tag: str) -> None:
    """Remember that the user dismissed this particular tag — don't nag."""
    from core import config as config_mod
    cfg = config_mod.load()
    cfg.dismissed_update = tag
    config_mod.save(cfg)
