"""
Simple browser launcher with Firefox fallback
"""

import logging
import subprocess
import sys
import os
import signal
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Page, Browser, Playwright

logger = logging.getLogger(__name__)


def kill_orphaned_browsers():
    """Kill any orphaned Playwright browser processes"""
    try:
        if sys.platform == 'darwin':  # macOS
            # Kill orphaned Chromium/Firefox processes
            subprocess.run(['pkill', '-9', '-f', 'Chromium'], stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-9', '-f', 'firefox'], stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-9', '-f', 'playwright'], stderr=subprocess.DEVNULL)
            logger.info("Cleaned up any orphaned browser processes")
    except Exception as e:
        logger.debug(f"Could not kill orphaned processes: {e}")


def check_and_install_browsers():
    """Check if browsers are installed, install if missing"""
    try:
        logger.info("Checking browser installation...")
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium", "firefox", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # If dry-run shows browsers need installation, install them
        if "is not installed" in result.stdout or result.returncode != 0:
            logger.info("Installing browsers (one-time setup)...")
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium", "firefox"],
                check=True,
                timeout=300  # 5 minutes timeout
            )
            logger.info("✓ Browsers installed")
        else:
            logger.info("✓ Browsers already installed")
            
    except subprocess.TimeoutExpired:
        logger.warning("Browser installation check timed out, continuing anyway...")
    except Exception as e:
        logger.warning(f"Could not verify browser installation: {e}")


async def launch_browser(headless: bool = False, slow_mo: int = 100) -> Tuple[Playwright, Browser, Page]:
    """
    Launch browser with automatic installation and Firefox fallback
    
    Returns:
        Tuple of (playwright, browser, page)
    """
    # Kill any orphaned browser processes first
    kill_orphaned_browsers()
    
    # Check and install browsers if needed
    check_and_install_browsers()
    
    playwright = await async_playwright().start()
    
    # Try system Chrome first (more stable on macOS)
    try:
        logger.info(f"Launching system Chrome ({'headless' if headless else 'visible for demo'})...")
        browser = await playwright.chromium.launch(
            channel="chrome",  # Use system Chrome
            headless=headless,
            slow_mo=slow_mo
        )
        page = await browser.new_page()
        page.set_default_timeout(30000)
        logger.info("✓ Browser ready (Chrome)")
        return playwright, browser, page
        
    except Exception as e:
        logger.warning(f"System Chrome failed, trying bundled Chromium...")
        try:
            browser = await playwright.chromium.launch(
                headless=headless,
                slow_mo=slow_mo,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            page = await browser.new_page()
            page.set_default_timeout(30000)
            logger.info("✓ Browser ready (Chromium)")
            return playwright, browser, page
            
        except Exception as e2:
            logger.warning(f"Chromium failed, trying Firefox...")
            try:
                browser = await playwright.firefox.launch(
                    headless=headless,
                    slow_mo=slow_mo
                )
                page = await browser.new_page()
                page.set_default_timeout(30000)
                logger.info("✓ Browser ready (Firefox)")
                return playwright, browser, page
            
            except Exception as e3:
                logger.error(f"✗ All browsers failed")
                logger.error(f"System Chrome: {str(e)[:80]}")
                logger.error(f"Chromium: {str(e2)[:80]}")
                logger.error(f"Firefox: {str(e3)[:80]}")
                logger.error("")
                logger.error("Visible mode not working on this macOS version.")
                logger.error("For demo, try: python death_report_cli.py --headless")
                await playwright.stop()
                raise Exception("All browsers failed in visible mode")


async def close_browser(playwright: Playwright, browser: Browser, page: Page):
    """Close browser and cleanup"""
    if page:
        await page.close()
    if browser:
        await browser.close()
    if playwright:
        await playwright.stop()
    logger.info("✓ Browser closed")

