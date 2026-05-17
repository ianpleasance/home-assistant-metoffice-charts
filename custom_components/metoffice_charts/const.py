"""Constants for the MAVIS Aviation Charts integration."""

DOMAIN = "mavis_charts"

# Configuration keys
CONF_AUTH_TOKEN = "auth_token"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_CHARTS = "charts"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_SCAN_INTERVAL = 60  # minutes
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 1440
# Storage
STORAGE_DIR = "www/mavis_charts"

# MAVIS URL
MAVIS_BASE_URL = "https://mavis.metoffice.gov.uk"

# Browserless puppeteer script to log into MAVIS and return the auth_token cookie.
# Uses v1 /function API (module.exports style).
BROWSERLESS_LOGIN_SCRIPT = """
module.exports = async ({ page, context }) => {
    const { username, password } = context;

    const delay = ms => new Promise(r => setTimeout(r, ms));

    async function findElement(selectors) {
        for (const sel of selectors) {
            const el = await page.$(sel);
            if (el) return el;
        }
        return null;
    }

    await page.goto('https://mavis.metoffice.gov.uk', {
        waitUntil: 'domcontentloaded',
        timeout: 30000,
    });

    // Wait for email and password fields (confirmed field types from Browserless)
    await page.waitForFunction(
        () => !!document.querySelector('input[type="email"]') &&
              !!document.querySelector('input[type="password"]'),
        { timeout: 20000 }
    );

    await delay(500);

    const usernameField = await page.$('input[type="email"]');
    if (!usernameField) throw new Error('Could not find email input field');
    await usernameField.click({ clickCount: 3 });
    await delay(100);
    await usernameField.type(username, { delay: 30 });

    const passwordField = await page.$('input[type="password"]');
    if (!passwordField) throw new Error('Could not find password input field');
    await passwordField.click();
    await delay(100);
    await passwordField.type(password, { delay: 30 });

    // Press Enter to submit (most reliable across B2C policy versions)
    await passwordField.press('Enter');

    await page.waitForFunction(
        () => window.location.hostname.includes('mavis.metoffice.gov.uk'),
        { timeout: 30000 }
    );

    const cookies = await page.cookies();
    const authCookie = cookies.find(c => c.name === 'auth_token');

    if (!authCookie) {
        const cookieNames = cookies.map(c => c.name).join(', ');
        throw new Error('auth_token not found. Available: ' + cookieNames);
    }

    return { data: authCookie.value, type: 'application/json' };
};
"""

# Chart definitions
# key: (display_name, description, report_path, file_extension, region)
CHART_DEFINITIONS = {
    "f214": (
        "F214 UK Spot Winds",
        "UK low level spot wind chart - wind direction, speed and temperature",
        "f214",
        "pdf",
        None,
    ),
    "f215": (
        "F215 UK Low-Level Significant Weather",
        "UK low level significant weather chart - cloud, visibility, fronts and hazards",
        "f215",
        "pdf",
        None,
    ),
    "f414": (
        "F414 European Spot Winds",
        "European low level spot wind chart",
        "f414",
        "pdf",
        None,
    ),
    "f415": (
        "F415 European Low-Level Significant Weather",
        "European low level significant weather chart",
        "f415",
        "pdf",
        None,
    ),
    "london_cta_helicopter_forecast": (
        "London CTA Helicopter Forecast",
        "London CTA helicopter forecast",
        "london_cta_helicopter_forecast",
        "pdf",
        None,
    ),
    "rps": (
        "Regional Pressure",
        "UK regional pressure — current and next hour values for 20 regions",
        "rps",
        "rps",  # special type: scraped HTML, not a downloadable file
        None,
    ),
    "gamets_central": (
        "GAMETs Central",
        "General Aviation Meteorological area forecast - Central region",
        "gamets",
        "pdf",
        "central",
    ),
    "gamets_north": (
        "GAMETs North",
        "General Aviation Meteorological area forecast - North region",
        "gamets",
        "pdf",
        "north",
    ),
    "gamets_south_east": (
        "GAMETs South East",
        "General Aviation Meteorological area forecast - South East region",
        "gamets",
        "pdf",
        "south_east",
    ),
    "gamets_south_west": (
        "GAMETs South West",
        "General Aviation Meteorological area forecast - South West region",
        "gamets",
        "pdf",
        "south_west",
    ),
    "surface_pressure_charts_north_atlantic_asxx": (
        "Surface Pressure",
        "North Atlantic surface pressure analysis chart",
        "surface_pressure_charts_north_atlantic_asxx",
        "gif",
        None,
    ),
}

DEFAULT_CHARTS = ["f214", "f215"]
