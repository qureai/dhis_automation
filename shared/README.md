# Shared Browser Launcher

Simple browser launcher with Firefox fallback. Used by birth and death report automations.

## Usage

```python
from shared import launch_browser, close_browser

# Launch
playwright, browser, page = await launch_browser(headless=False, slow_mo=100)

# Use page...

# Close
await close_browser(playwright, browser, page)
```

## Installation

```bash
python -m playwright install chromium firefox
```

That's it.

