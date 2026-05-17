"""B2C authentication for MAVIS Aviation Charts.

Performs a direct HTTP login to the Met Office Azure AD B2C endpoint
without requiring a browser.  Returns the MAVIS auth_token cookie value
on success, or None on failure.

This module is intentionally self-contained (stdlib only) so it can be
called from both the coordinator (via async_add_executor_job) and the
config flow without any circular imports.
"""
from __future__ import annotations

import http.cookiejar
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

_LOGGER = logging.getLogger(__name__)

_AUTH_BASE = "https://login.auth.metoffice.cloud"
_TENANT = "dce84ec6-ce0f-45d1-ba16-e36b817081eb"
_POLICY = "B2C_1A_warrior_susi"
_MAVIS_BASE = "https://mavis.metoffice.gov.uk"
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def authenticate(username: str, password: str) -> str | None:
    """Log into MAVIS via Azure B2C and return the auth_token cookie.

    This function is synchronous and blocking — run it in an executor:

        token = await hass.async_add_executor_job(authenticate, username, password)

    The flow:
        1. GET MAVIS home  →  follows redirect to B2C login page
        2. Extract CSRF token and transaction ID from the login page
        3. POST credentials to the SelfAsserted endpoint
        4. GET the confirmed endpoint to complete the B2C flow
        5. Parse the self-submitting form and POST it to the MAVIS callback
        6. Extract and return the auth_token cookie

    Returns the auth_token string on success, or None on any failure.
    """
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [
        ("User-Agent", _USER_AGENT),
        ("Accept-Language", "en-GB,en;q=0.9"),
    ]

    try:
        # ------------------------------------------------------------------
        # Step 1 — GET MAVIS home, follow redirect to B2C login page
        # ------------------------------------------------------------------
        resp = opener.open(_MAVIS_BASE, timeout=30)
        login_url = resp.geturl()
        login_page = resp.read().decode("utf-8", errors="replace")
        _LOGGER.debug("B2C login page: %s", login_url[:100])

        # ------------------------------------------------------------------
        # Step 2 — Extract CSRF token and transaction ID
        # ------------------------------------------------------------------
        csrf_match = re.search(r'"csrf"\s*:\s*"([^"]+)"', login_page)
        tx_match = re.search(r'"transId"\s*:\s*"([^"]+)"', login_page)

        if not csrf_match or not tx_match:
            _LOGGER.error("Could not extract CSRF/transId from B2C login page")
            return None

        csrf_token = csrf_match.group(1)
        tx_id = tx_match.group(1)

        # ------------------------------------------------------------------
        # Step 3 — POST credentials to SelfAsserted endpoint
        # ------------------------------------------------------------------
        selfasserted_url = (
            f"{_AUTH_BASE}/{_TENANT}/{_POLICY}/SelfAsserted"
            f"?tx={tx_id}&p={_POLICY}"
        )
        creds = urllib.parse.urlencode({
            "request_type": "RESPONSE",
            "signInName": username,
            "password": password,
        }).encode()

        req = urllib.request.Request(
            selfasserted_url,
            data=creds,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-CSRF-TOKEN": csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": login_url,
                "Origin": _AUTH_BASE,
            },
        )
        try:
            resp = opener.open(req, timeout=30)
            post_body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            post_body = e.read().decode("utf-8", errors="replace")

        _LOGGER.debug("SelfAsserted response: %s", post_body[:100])
        if '"status":"200"' not in post_body:
            _LOGGER.warning("B2C credential validation failed: %s", post_body[:200])
            return None

        # ------------------------------------------------------------------
        # Step 4 — GET confirmed endpoint
        # ------------------------------------------------------------------
        confirmed_url = (
            f"{_AUTH_BASE}/{_TENANT}/{_POLICY}"
            f"/api/CombinedSigninAndSignup/confirmed"
            f"?rememberMe=false&csrf_token={urllib.parse.quote(csrf_token)}"
            f"&tx={tx_id}&p={_POLICY}&status=200"
        )
        resp = opener.open(confirmed_url, timeout=30)
        confirmed_html = resp.read().decode("utf-8", errors="replace")

        # ------------------------------------------------------------------
        # Step 5 — Parse self-submitting form and POST to MAVIS callback
        # ------------------------------------------------------------------
        form_action_match = re.search(
            r"<form[^>]+action=[\"'](https://mavis\.metoffice\.gov\.uk[^\"']*)[\"']",
            confirmed_html,
        )
        if not form_action_match:
            _LOGGER.error("Could not find callback form in B2C confirmed response")
            return None

        form_action = form_action_match.group(1).replace("&amp;", "&")

        hidden_fields: dict[str, str] = {}
        for m in re.finditer(r"<input[^>]*>", confirmed_html, re.IGNORECASE):
            tag = m.group(0)
            if "hidden" not in tag.lower():
                continue
            name_m = re.search(r'name=["\']([^"\']+)["\']', tag)
            val_m = re.search(r'value=["\']([^"\']*)["\']', tag)
            if name_m:
                hidden_fields[name_m.group(1)] = val_m.group(1) if val_m else ""

        _LOGGER.debug("Callback form fields: %s", list(hidden_fields.keys()))

        form_data = urllib.parse.urlencode(hidden_fields).encode()
        req = urllib.request.Request(
            form_action,
            data=form_data,
            headers={"Referer": confirmed_url},
        )
        try:
            resp = opener.open(req, timeout=30)
            resp.read()
        except urllib.error.HTTPError as e:
            e.read()  # consume response body

        # ------------------------------------------------------------------
        # Step 6 — Extract auth_token from cookie jar
        # ------------------------------------------------------------------
        for cookie in jar:
            if cookie.name == "auth_token":
                _LOGGER.info("MAVIS authentication successful")
                return cookie.value

        _LOGGER.error(
            "auth_token not found after B2C login. Cookies present: %s",
            [c.name for c in jar],
        )
        return None

    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.error("MAVIS B2C authentication error: %s", err)
        return None
