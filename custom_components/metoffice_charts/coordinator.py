"""Data update coordinator for MAVIS Aviation Charts."""
from __future__ import annotations

from datetime import timedelta
import logging
import os
import re
from typing import Any

import aiofiles
import aiohttp

from .auth import authenticate
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    STORAGE_DIR,
    MAVIS_BASE_URL,
    CHART_DEFINITIONS,
)

_LOGGER = logging.getLogger(__name__)

REPAIR_ISSUE_ID = "auth_token_expired"
PDF_DPI = 150


class MavisChartsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage chart downloads and PDF->PNG conversion for MAVIS Aviation Charts."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        charts: list[str],
        scan_interval: int,
        entry_id: str = "",
        auth_token: str = "",
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.session = session
        self.username = username
        self.password = password
        self.charts = charts
        self.entry_id = entry_id
        self._auth_token = auth_token
        self._auth_expired_mid_cycle = False

        self.storage_path = hass.config.path(STORAGE_DIR)
        os.makedirs(self.storage_path, exist_ok=True)

        # Fall back to file-persisted token if none provided (e.g. after HA restart
        # where the config entry token may be stale)
        if not self._auth_token:
            self._auth_token = self._load_persisted_token() or ""
        if self._auth_token:
            self._inject_cookie()

    def _inject_cookies(self, cookies: dict[str, str]) -> None:
        """Inject all MAVIS session cookies into the aiohttp session."""
        url = aiohttp.client.URL(MAVIS_BASE_URL)
        self.session.cookie_jar.update_cookies(cookies, response_url=url)
        auth_present = any(c.key == "auth_token" for c in self.session.cookie_jar)
        _LOGGER.debug(
            "Injected %d MAVIS cookies. auth_token present: %s",
            len(cookies), auth_present,
        )

    def _inject_cookie(self) -> None:
        """Inject just the auth_token cookie (used on startup from saved token)."""
        self._inject_cookies({"auth_token": self._auth_token})

    def update_charts(self, charts: list[str]) -> None:
        """Update the chart list, cleaning up files for removed charts."""
        removed = set(self.charts) - set(charts)
        for chart_key in removed:
            self._cleanup_chart_files(chart_key)
        self.charts = charts

    def _cleanup_chart_files(self, chart_key: str) -> None:
        """Remove files for a chart that is no longer configured."""
        for suffix in ("pdf", "png", "gif"):
            path = os.path.join(self.storage_path, f"{chart_key}.{suffix}")
            if os.path.exists(path):
                try:
                    os.remove(path)
                    _LOGGER.debug("Removed obsolete chart file: %s", path)
                except OSError as err:
                    _LOGGER.warning("Could not remove %s: %s", path, err)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate_sync(self) -> tuple[str, dict[str, str]] | None:
        """Run B2C login synchronously via auth.py. Called via async_add_executor_job."""
        return authenticate(self.username, self.password)

    async def _refresh_auth_token(self) -> bool:
        """Run B2C login in executor and establish session with aiohttp.

        The urllib-based login sets the auth_token cookie in a urllib session.
        We then use that token to make a request via our aiohttp session so
        MAVIS's server associates the auth_token with our aiohttp session.

        Retries up to 3 times with a short delay.
        """
        import asyncio
        for attempt in range(1, 4):
            result = await self.hass.async_add_executor_job(self._authenticate_sync)
            if result:
                token, all_cookies = result
                self._auth_token = token
                self._inject_cookies(all_cookies)
                await self._persist_token(token)

                # Warm up the aiohttp session by GETting MAVIS home page.
                # This causes MAVIS to associate the auth_token with our
                # aiohttp session via its own session management.
                try:
                    async with self.session.get(
                        MAVIS_BASE_URL,
                        allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        _LOGGER.debug(
                            "Session warmup response: %d, cookies now: %d",
                            resp.status,
                            sum(1 for _ in self.session.cookie_jar),
                        )
                except aiohttp.ClientError as err:
                    _LOGGER.warning("Session warmup request failed: %s", err)

                return True
            if attempt < 3:
                _LOGGER.warning(
                    "MAVIS authentication attempt %d failed, retrying in 5s", attempt
                )
                await asyncio.sleep(5)
        _LOGGER.error("MAVIS authentication failed after 3 attempts")
        return False

    async def _persist_token(self, token: str) -> None:
        """Save the refreshed token to a file so it survives HA restarts.

        We deliberately avoid async_update_entry here because that fires
        the update listener and triggers a full integration reload, which
        would interrupt any in-progress download cycle.
        """
        token_file = os.path.join(self.storage_path, ".auth_token")
        try:
            async with aiofiles.open(token_file, "w") as f:
                await f.write(token)
            _LOGGER.debug("Persisted refreshed auth_token to file")
        except OSError as err:
            _LOGGER.warning("Could not persist auth_token to file: %s", err)

    def _load_persisted_token(self) -> str | None:
        """Load a previously saved auth token from file."""
        token_file = os.path.join(self.storage_path, ".auth_token")
        try:
            with open(token_file) as f:
                token = f.read().strip()
                return token if token else None
        except OSError:
            return None

    # ------------------------------------------------------------------
    # Auth check
    # ------------------------------------------------------------------

    async def _check_auth(self) -> bool:
        """Verify the auth token is still valid.

        We disable redirect following so that a 302 to the login domain
        does not cause aiohttp to clear our session cookies.
        """
        if not self._auth_token:
            return False
        try:
            async with self.session.get(
                f"{MAVIS_BASE_URL}/reports/f214",
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                # 200 = authenticated, 302 to login domain = expired
                if resp.status == 302:
                    location = resp.headers.get("Location", "")
                    if "login.auth.metoffice.cloud" in location:
                        return False
                return resp.status == 200
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error checking MAVIS auth: %s", err)
            return False

    def _raise_repair_issue(self) -> None:
        """Create a HA repair issue if auth refresh failed."""
        async_create_issue(
            self.hass,
            DOMAIN,
            REPAIR_ISSUE_ID,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key=REPAIR_ISSUE_ID,
        )

    # ------------------------------------------------------------------
    # Issue time extraction
    # ------------------------------------------------------------------

    async def _get_issue_time_and_url(
        self, report_path: str, ext: str, region: str | None
    ) -> tuple[str, str] | tuple[None, None]:
        """Fetch the report page and extract the current issue time and download URL."""
        page_url = f"{MAVIS_BASE_URL}/reports/{report_path}"
        if region:
            page_url = f"{page_url}?region={region}"

        try:
            # Debug: check cookie is present before request
            cookies_present = {c.key: c.value[:10] for c in self.session.cookie_jar
                               if c.key == "auth_token"}
            _LOGGER.debug("Cookies before request for %s: %s", report_path, cookies_present)
            async with self.session.get(
                page_url,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=False,
            ) as resp:
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location", "")
                    if "login.auth.metoffice.cloud" in location:
                        _LOGGER.warning(
                            "Auth expired fetching report page for %s", report_path
                        )
                        self._auth_expired_mid_cycle = True
                    else:
                        _LOGGER.warning(
                            "Unexpected redirect for %s: %s", report_path, location
                        )
                    return None, None
                if resp.status == 403:
                    _LOGGER.warning("Access denied (403) for %s", report_path)
                    return None, None
                if resp.status != 200:
                    _LOGGER.warning(
                        "Report page for %s returned HTTP %s", report_path, resp.status
                    )
                    return None, None
                html = await resp.text()

            html_decoded = html.replace("&amp;", "&")

            if ext == "gif":
                match = re.search(
                    r'data-report-issue-time-utc="([^"]+)"[^>]*checked',
                    html_decoded,
                )
                if not match:
                    match = re.search(
                        r'data-report-issue-time-utc="([^"]+)"', html_decoded
                    )
                if not match:
                    _LOGGER.warning(
                        "Could not find issue time in report page for %s", report_path
                    )
                    return None, None
                issue_time = match.group(1)
                download_url = (
                    f"{MAVIS_BASE_URL}/report/{report_path}"
                    f"?issue-time-utc={issue_time}"
                )
            else:
                match = re.search(
                    r'pdf-src="(/report/[^"]+issue-time-utc=([^"&]+)[^"]*)"',
                    html_decoded,
                )
                if not match:
                    _LOGGER.warning(
                        "Could not find pdf-src in report page for %s. Snippet: %s",
                        report_path, html[:300],
                    )
                    return None, None
                pdf_src = match.group(1)
                issue_time = match.group(2)
                download_url = f"{MAVIS_BASE_URL}{pdf_src}"

            _LOGGER.debug("Parsed issue time for %s: %s", report_path, issue_time)
            return issue_time, download_url

        except aiohttp.ClientError as err:
            _LOGGER.error(
                "Network error fetching report page for %s: %s", report_path, err
            )
            return None, None

    # ------------------------------------------------------------------
    # PDF -> PNG conversion
    # ------------------------------------------------------------------

    def _convert_pdf_to_png(self, pdf_path: str, png_path: str) -> bool:
        """Convert first page of a PDF to PNG using pymupdf."""
        try:
            import fitz  # pymupdf — imported here so module loads before package installs
            doc = fitz.open(pdf_path)
            page = doc[0]
            mat = fitz.Matrix(PDF_DPI / 72, PDF_DPI / 72)
            pix = page.get_pixmap(matrix=mat)
            pix.save(png_path)
            doc.close()
            _LOGGER.debug("Converted %s -> %s", pdf_path, png_path)
            return True
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("PDF->PNG conversion failed for %s: %s", pdf_path, err)
            return False

    # ------------------------------------------------------------------
    # Regional pressure scraping
    # ------------------------------------------------------------------

    async def _fetch_regional_pressure(
        self,
        chart_key: str,
        data: dict[str, Any],
    ) -> None:
        """Scrape regional pressure values from the MAVIS RPS page."""
        page_url = f"{MAVIS_BASE_URL}/products/rps"
        try:
            async with self.session.get(
                page_url,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=False,
            ) as resp:
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location", "")
                    if "login.auth.metoffice.cloud" in location:
                        _LOGGER.warning("Auth expired fetching RPS page")
                        self._auth_expired_mid_cycle = True
                    return
                if resp.status != 200:
                    _LOGGER.warning("RPS page returned HTTP %s", resp.status)
                    return
                html = await resp.text()

            validity_match = re.search(r"starting from ([^.]+)[.]", html)
            validity = validity_match.group(1).strip() if validity_match else None

            regions: dict[str, dict[str, str]] = {}
            cur_pat = re.compile(
                r'data-testid="map-current-pressure-([^"]+)"[^>]*>[^0-9]*([0-9]+)[^0-9]*<'
            )
            nxt_pat = re.compile(
                r'data-testid="map-next-pressure-([^"]+)"[^>]*>[^0-9]*([0-9]+)[^0-9]*<'
            )
            for m in cur_pat.finditer(html):
                regions.setdefault(m.group(1), {})["current_hpa"] = m.group(2)
            for m in nxt_pat.finditer(html):
                regions.setdefault(m.group(1), {})["next_hpa"] = m.group(2)

            if not regions:
                _LOGGER.warning("Could not find any pressure data on RPS page")
                return

            _LOGGER.debug("Scraped RPS data for %d regions", len(regions))

            data[chart_key] = {
                "downloaded_at": dt_util.now(),
                "issue_time": validity,
                "pdf_path": None,
                "pdf_url": None,
                "png_path": None,
                "png_url": None,
                "size_bytes": len(html),
                "chart_name": "Regional Pressure",
                "description": "UK regional pressure — current and next hour values",
                "png_ok": False,
                "regions": regions,
            }

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error fetching RPS page: %s", err)

    # ------------------------------------------------------------------
    # Chart download
    # ------------------------------------------------------------------

    async def _download_chart(
        self,
        chart_key: str,
        data: dict[str, Any],
    ) -> None:
        """Download a chart, convert if needed, and store metadata."""
        chart_name, description, report_path, ext, region = CHART_DEFINITIONS[chart_key]

        issue_time, download_url = await self._get_issue_time_and_url(
            report_path, ext, region
        )
        if not issue_time or not download_url:
            _LOGGER.warning(
                "Could not determine issue time/URL for %s, skipping", chart_key
            )
            return

        _LOGGER.debug("Fetching %s from %s", chart_name, download_url)

        try:
            async with self.session.get(
                download_url,
                timeout=aiohttp.ClientTimeout(total=60),
                allow_redirects=False,
            ) as resp:
                if resp.status in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location", "")
                    if "login.auth.metoffice.cloud" in location:
                        _LOGGER.warning("Auth expired downloading %s", chart_key)
                        self._auth_expired_mid_cycle = True
                    return
                if resp.status == 404:
                    _LOGGER.warning(
                        "%s returned 404 for issue time %s", chart_key, issue_time
                    )
                    return
                if resp.status != 200:
                    _LOGGER.warning(
                        "Failed to download %s: HTTP %s", chart_key, resp.status
                    )
                    return
                chart_bytes = await resp.read()

            if ext == "gif":
                gif_path = os.path.join(self.storage_path, f"{chart_key}.gif")
                async with aiofiles.open(gif_path, "wb") as f:
                    await f.write(chart_bytes)

                data[chart_key] = {
                    "downloaded_at": dt_util.now(),
                    "issue_time": issue_time,
                    "pdf_path": None,
                    "pdf_url": None,
                    "png_path": gif_path,
                    "png_url": f"/local/mavis_charts/{chart_key}.gif",
                    "size_bytes": len(chart_bytes),
                    "chart_name": chart_name,
                    "description": description,
                    "png_ok": True,
                }
                _LOGGER.debug(
                    "Downloaded %s (%s): %d bytes (GIF)",
                    chart_key, issue_time, len(chart_bytes),
                )
            else:
                pdf_path = os.path.join(self.storage_path, f"{chart_key}.pdf")
                async with aiofiles.open(pdf_path, "wb") as f:
                    await f.write(chart_bytes)

                png_path = os.path.join(self.storage_path, f"{chart_key}.png")
                png_ok = await self.hass.async_add_executor_job(
                    self._convert_pdf_to_png, pdf_path, png_path
                )

                data[chart_key] = {
                    "downloaded_at": dt_util.now(),
                    "issue_time": issue_time,
                    "pdf_path": pdf_path,
                    "pdf_url": f"/local/mavis_charts/{chart_key}.pdf",
                    "png_path": png_path if png_ok else None,
                    "png_url": f"/local/mavis_charts/{chart_key}.png" if png_ok else None,
                    "size_bytes": len(chart_bytes),
                    "chart_name": chart_name,
                    "description": description,
                    "png_ok": png_ok,
                }
                _LOGGER.debug(
                    "Downloaded %s (%s): %d bytes, PNG: %s",
                    chart_key, issue_time, len(chart_bytes),
                    "OK" if png_ok else "FAILED",
                )

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error downloading %s: %s", chart_key, err)
        except OSError as err:
            _LOGGER.error("File I/O error saving %s: %s", chart_key, err)

    # ------------------------------------------------------------------
    # Update cycle
    # ------------------------------------------------------------------

    async def _run_downloads(self, data: dict[str, Any]) -> None:
        """Download all configured charts into data dict."""
        for chart_key in self.charts:
            if chart_key not in CHART_DEFINITIONS:
                _LOGGER.warning("Unknown chart key '%s', skipping", chart_key)
                continue
            _, _, _, ext, _ = CHART_DEFINITIONS[chart_key]
            if ext == "rps":
                await self._fetch_regional_pressure(chart_key, data)
            else:
                await self._download_chart(chart_key, data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Ensure auth is valid, refreshing via B2C if needed, then download charts."""
        if not await self._check_auth():
            _LOGGER.info("MAVIS auth_token invalid, refreshing via B2C")
            if not await self._refresh_auth_token():
                self._raise_repair_issue()
                raise UpdateFailed(
                    "MAVIS authentication failed. "
                    "Check your username and password in the integration settings."
                )

        self._auth_expired_mid_cycle = False
        data: dict[str, Any] = {}
        await self._run_downloads(data)

        # If auth expired mid-cycle, re-auth and retry
        if self._auth_expired_mid_cycle:
            _LOGGER.info("Auth expired mid-cycle, re-authenticating and retrying")
            if await self._refresh_auth_token():
                self._auth_expired_mid_cycle = False
                data = {}
                await self._run_downloads(data)
            else:
                self._raise_repair_issue()
                raise UpdateFailed(
                    "MAVIS session expired and re-authentication failed."
                )

        return data
