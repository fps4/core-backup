from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

import requests

from .config import ConfigError

DEFAULT_API_URL = "https://api.github.com"
DEFAULT_ACCEPT_HEADER = "application/vnd.github+json"


class GitHubAPI:
    def __init__(self, token: Optional[str], base_url: str = DEFAULT_API_URL) -> None:
        if not token:
            raise ConfigError("GitHub token must be provided via environment variable")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": DEFAULT_ACCEPT_HEADER,
                "User-Agent": "github-backup-service",
            }
        )
        self._base_url = base_url.rstrip("/")
        self._log = logging.getLogger(self.__class__.__name__)

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        response = self._session.get(url, params=params, timeout=30)
        if response.status_code >= 400:
            self._log.error("GitHub API request failed: %s %s", response.status_code, response.text)
            response.raise_for_status()
        return response.json()

    def iterate(self, path: str, params: Optional[Dict[str, Any]] = None) -> Iterable[Dict[str, Any]]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        next_url: Optional[str] = url
        request_params = params.copy() if params else {}
        request_params.setdefault("per_page", 100)

        while next_url:
            response = self._session.get(next_url, params=request_params, timeout=30)
            if response.status_code >= 400:
                self._log.error("GitHub API pagination failed: %s %s", response.status_code, response.text)
                response.raise_for_status()

            for item in response.json():
                yield item

            next_url = self._extract_next_link(response.headers.get("Link"))
            request_params = {}

    @staticmethod
    def _extract_next_link(link_header: Optional[str]) -> Optional[str]:
        if not link_header:
            return None
        parts = [p.strip() for p in link_header.split(",")]
        for part in parts:
            if 'rel="next"' in part:
                start = part.find("<") + 1
                end = part.find(">")
                return part[start:end]
        return None
