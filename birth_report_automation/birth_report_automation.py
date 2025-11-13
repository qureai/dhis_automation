"""
Complete Birth Report Automation - Fills ALL Fields
Event-based program (38+ fields in single form)
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from playwright.async_api import Page, Browser, Playwright
from datetime import datetime

# Add parent directory to path for shared module
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared import launch_browser, close_browser

# Create logs and screenshots folders
script_dir = Path(__file__).parent
logs_dir = script_dir / "logs"
screenshots_dir = script_dir / "screenshots"
logs_dir.mkdir(exist_ok=True)
screenshots_dir.mkdir(exist_ok=True)

# Setup logging with date-based filename
log_file = logs_dir / f"automation_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BirthReportAutomation:
    """
    Complete automation for DHIS2 Birth Notification (Event Program).
    Handles single event form with all fields.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        headless: bool = False,
        slow_mo: int = 100
    ):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def initialize(self):
        """Initialize browser using shared launcher"""
        self.playwright, self.browser, self.page = await launch_browser(
            headless=self.headless,
            slow_mo=self.slow_mo
        )

    async def close(self):
        """Close browser using shared cleanup"""
        await close_browser(self.playwright, self.browser, self.page)

    async def login(self) -> bool:
        """Login to DHIS2"""
        try:
            logger.info(f"Logging in to {self.base_url}...")
            await self.page.goto(f"{self.base_url}/dhis-web-login/", wait_until="networkidle")
            await self.page.fill("#username", self.username)
            await self.page.fill("#password", self.password)
            await self.page.click('button[data-test="dhis2-uicore-button"]')
            await self.page.wait_for_url("**/dhis-web-dashboard/**", timeout=15000)
            await asyncio.sleep(2)
            logger.info("✓ Logged in")
            return True
        except Exception as e:
            logger.error(f"✗ Login failed: {e}")
            screenshot_path = screenshots_dir / f"login_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_path))
            return False

    async def fill_text_field(self, selector: str, value: str, label: str = ""):
        """Fill a text input field"""
        try:
            await self.page.fill(selector, str(value))
            logger.info(f"  ✓ {label}: {value}")
        except Exception as e:
            logger.warning(f"  ✗ {label} failed: {e}")

    async def fill_select_field(self, selector: str, value: str, label: str = ""):
        """Fill a select dropdown (virtualized-select)"""
        try:
            # Birth forms use input#ID for selects
            # Type slowly to allow dropdown to filter properly
            await self.page.fill(selector, "")  # Clear first
            await asyncio.sleep(0.2)
            await self.page.fill(selector, value)
            await asyncio.sleep(0.5)  # Wait for dropdown to show options
            
            # Wait for the matching option to be visible in the dropdown
            try:
                # Look for the option with exact text match in the dropdown list
                await self.page.wait_for_selector(f'[role="option"]:has-text("{value}")', timeout=2000)
                await asyncio.sleep(0.3)  # Extra wait to ensure it's highlighted
            except:
                logger.debug(f"  Option '{value}' not found in dropdown, pressing Enter anyway")
            
            await self.page.keyboard.press('Enter')
            await asyncio.sleep(0.3)  # Wait for selection to commit
            logger.info(f"  ✓ {label}: {value}")
        except Exception as e:
            logger.warning(f"  ✗ {label} failed: {e}")

    async def fill_radio_field(self, selector: str, value: str, label: str = ""):
        """Fill a radio button field"""
        try:
            radio_value = "true" if value.lower() in ["yes", "true", "1"] else "false"
            radio_selector = f"{selector}[value=\"{radio_value}\"]"
            await self.page.click(radio_selector)
            logger.info(f"  ✓ {label}: {value}")
        except Exception as e:
            logger.warning(f"  ✗ {label} failed: {e}")

    async def replace_timestamps(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Replace _TIMESTAMP_ placeholders with actual timestamp"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        data_str = json.dumps(data)
        data_str = data_str.replace('_TIMESTAMP_', timestamp)
        return json.loads(data_str)

    def flatten_data(self, data: Dict[str, Any], parent_key: str = '') -> Dict[str, Any]:
        """Flatten nested dict for easy field lookup"""
        items = []
        for k, v in data.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_data(v, new_key).items())
            else:
                items.append((new_key, v))
        return dict(items)

    async def fill_event_form(self, data: Dict[str, Any], mappings: Dict[str, Any]) -> int:
        """Fill event form fields using data-path-to-field mapping"""
        filled_count = 0
        skipped_count = 0
        flattened_data = self.flatten_data(data)
        
        logger.info("Filling birth notification form...")
        
        # mappings format: {"data.path": {"field_id": "...", "selector": "...", "type": "..."}}
        for data_path, field_config in mappings.items():
            # Skip special fields
            if data_path.startswith("_"):
                continue
                
            # Get value from flattened data
            value = flattened_data.get(data_path)
            
            if value is not None and value != "":
                selector = field_config["selector"]
                field_type = field_config["type"]
                field_id = field_config.get("field_id", data_path)

                try:
                    if field_type in ["text", "date"]:
                        await self.fill_text_field(selector, str(value), field_id)
                        filled_count += 1
                    elif field_type == "select":
                        await self.fill_select_field(selector, str(value), field_id)
                        filled_count += 1
                    elif field_type == "radio":
                        await self.fill_radio_field(selector, str(value), field_id)
                        filled_count += 1
                except Exception as e:
                    logger.warning(f"  ⚠ Failed to fill {field_id}: {e}")
                    skipped_count += 1
            else:
                skipped_count += 1
        
        logger.info(f"✓ Filled {filled_count}/{len(mappings)-1} fields ({skipped_count} skipped/empty)")
        return filled_count

    async def navigate_to_new_event_form(self, program_id: str, org_unit_id: str) -> bool:
        """Navigate to new event form"""
        try:
            url = f"{self.base_url}/dhis-web-capture/index.html#/new?orgUnitId={org_unit_id}&programId={program_id}"
            logger.info("Opening birth notification form...")
            await self.page.goto(url, wait_until="networkidle")
            await self.page.wait_for_selector('[data-test="dhis2-uicore-splitbutton"]', timeout=30000)
            logger.info("✓ Form loaded")
            return True
        except Exception as e:
            logger.error(f"✗ Form navigation failed: {e}")
            screenshot_path = screenshots_dir / f"form_navigation_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_path))
            return False

    async def submit_form(self) -> tuple[bool, str | None, dict | None, int | None]:
        """
        Submit the birth notification form and verify success
        
        Returns:
            tuple: (success: bool, enrollment_id: str | None, api_response: dict | None, status_code: int | None)
        """
        api_response = None
        status_code = None
        
        try:
            logger.info("Submitting form...")
            
            # Set up response listener to capture API response
            async def handle_response(response):
                nonlocal api_response, status_code
                # Capture only POST requests to tracker endpoint
                if (response.request.method == 'POST' and 
                    '/api/' in response.url and 
                    'tracker' in response.url):
                    try:
                        status_code = response.status
                        api_response = await response.json()
                        
                        # Log based on status code
                        if status_code == 200:
                            logger.info(f"📡 API Response: {status_code} - ✓ Created successfully")
                        elif status_code == 409:
                            logger.warning(f"📡 API Response: {status_code} - ⚠️  Conflict/Duplicate")
                        else:
                            logger.error(f"📡 API Response: {status_code} - ✗ Failed")
                            
                        logger.debug(f"📡 Full API Response JSON: {json.dumps(api_response, indent=2)}")
                    except:
                        pass
            
            self.page.on("response", handle_response)
            
            # Click submit button
            await self.page.click('[data-test="dhis2-uicore-splitbutton-button"]')
            
            # Wait for API response
            await asyncio.sleep(2)
            
            # Wait and verify success
            success, enrollment_id = await self.verify_submission_success()
            
            # Remove listener
            self.page.remove_listener("response", handle_response)
            
            # Determine success based on status code
            if status_code == 200:
                success = True
                logger.info("✓ Form submitted successfully")
                if enrollment_id:
                    logger.info(f"📋 Enrollment ID: {enrollment_id}")
                return True, enrollment_id, api_response, status_code
            elif status_code == 409:
                logger.warning("⚠️  Form submission conflict (likely duplicate)")
                return False, enrollment_id, api_response, status_code
            else:
                logger.error("✗ Form save failed - no success confirmation")
                screenshot_path = screenshots_dir / f"submit_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(screenshot_path))
                return False, None, api_response, status_code
                
        except Exception as e:
            logger.error(f"✗ Form submission failed: {e}")
            screenshot_path = screenshots_dir / f"submit_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_path))
            return False, None, api_response, status_code
    
    async def verify_submission_success(self) -> tuple[bool, str | None]:
        """
        Verify that form submission was successful and extract enrollment ID
        
        Returns:
            tuple: (success: bool, enrollment_id: str | None)
        """
        try:
            # Check for multiple success indicators
            success_indicators = [
                # Success snackbar/alert
                'div:has-text("successfully")',
                'div:has-text("saved")',
                '[data-test*="success"]',
                '.alert-success',
            ]
            
            # Wait for any success indicator (5 second timeout)
            for indicator in success_indicators:
                try:
                    await self.page.wait_for_selector(indicator, timeout=5000)
                    logger.info(f"✓ Success indicator found: {indicator}")
                    await asyncio.sleep(1)  # Brief pause to see the message
                    return True, None
                except:
                    continue
            
            # Check if URL changed (redirect = success)
            await asyncio.sleep(2)
            current_url = self.page.url
            enrollment_id = None
            
            if 'enrollmentEventNew' not in current_url and 'new' not in current_url:
                # Extract enrollment ID from URL
                import re
                match = re.search(r'enrollmentId=([^&]+)', current_url)
                if match:
                    enrollment_id = match.group(1)
                    logger.info(f"✓ URL redirect detected (enrollment ID: {enrollment_id})")
                else:
                    logger.info(f"✓ URL changed to: {current_url} (redirect = success)")
                return True, enrollment_id
            
            # Check for error indicators
            error_indicators = [
                'div:has-text("error")',
                'div:has-text("failed")',
                '[data-test*="error"]',
                '.alert-danger',
            ]
            
            for indicator in error_indicators:
                try:
                    await self.page.wait_for_selector(indicator, timeout=1000)
                    logger.error(f"✗ Error indicator found: {indicator}")
                    return False, None
                except:
                    continue
            
            # If no indicators found, check page state
            logger.warning("⚠ No clear success/error indicator found")
            await asyncio.sleep(1)
            return True, None  # Assume success if no errors
            
        except Exception as e:
            logger.warning(f"Could not verify submission: {e}")
            return True, None  # Assume success if verification fails

    async def automate(self, program_id: str, org_unit_id: str, data: dict) -> dict:
        """
        Main automation method - orchestrates the entire birth notification process
        
        Args:
            program_id: DHIS2 program ID for birth notification
            org_unit_id: Organization unit ID
            data: Birth notification data (includes _meta and form fields)
        
        Returns:
            dict: Result with success status, enrollment_id, and field counts
        """
        try:
            # Replace timestamps
            data = await self.replace_timestamps(data)
            
            # Load field mappings (use new data-to-field mapping)
            mappings_file = script_dir / 'field_data_mapping.json'
            if not mappings_file.exists():
                # Fallback to old file
                mappings_file = script_dir / 'field_mappings.json'
                if not mappings_file.exists():
                    logger.error("✗ field_data_mapping.json or field_mappings.json not found!")
                    logger.error("  Run birth_report_discovery.py first to generate mappings")
                    return {
                        "success": False,
                        "enrollment_id": None,
                        "error": "Field mappings file not found"
                    }
            
            with open(mappings_file, 'r') as f:
                field_mappings = json.load(f)
            
            # Step 1: Login
            logger.info("\nStep 1: Logging in...")
            if not await self.login():
                logger.error("✗ Login failed")
                return {
                    "success": False,
                    "enrollment_id": None,
                    "error": "Login failed"
                }
            logger.info("✓ Login successful")
            await asyncio.sleep(1)
            
            # Step 2: Navigate to new event form
            logger.info("\nStep 2: Navigating to birth notification form...")
            if not await self.navigate_to_new_event_form(program_id, org_unit_id):
                logger.error("✗ Navigation failed")
                return {
                    "success": False,
                    "enrollment_id": None,
                    "error": "Failed to navigate to form"
                }
            logger.info("✓ Navigation successful")
            await asyncio.sleep(2)
            
            # Step 3: Take screenshot before filling
            screenshot_before = screenshots_dir / f"01_before_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_before))
            logger.info(f"✓ Screenshot: {screenshot_before.name}")
            
            # Step 4: Fill form
            logger.info("\nStep 3: Filling birth notification form...")
            filled = await self.fill_event_form(data, field_mappings)
            logger.info(f"✓ Filled {filled}/{len(field_mappings)} fields")
            
            # Step 5: Take screenshot after filling
            screenshot_after = screenshots_dir / f"02_after_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_after))
            logger.info(f"✓ Screenshot: {screenshot_after.name}")
            
            # Step 6: Submit form and get enrollment ID
            logger.info("\nStep 4: Submitting form...")
            success, enrollment_id, api_response, status_code = await self.submit_form()
            
            if success:
                screenshot_submit = screenshots_dir / f"03_submitted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(screenshot_submit))
                logger.info(f"✓ Screenshot: {screenshot_submit.name}")
            else:
                return {
                    "success": False,
                    "enrollment_id": None,
                    "fields_filled": filled,
                    "api_response": api_response,
                    "status_code": status_code,
                    "error": "Form submission failed"
                }
            
            # Keep browser open briefly for inspection
            await asyncio.sleep(3)
            
            return {
                "success": True,
                "enrollment_id": enrollment_id,
                "fields_filled": filled,
                "total_fields": len(field_mappings),
                "api_response": api_response,
                "status_code": status_code
            }
            
        except Exception as e:
            logger.error(f"✗ Automation failed: {e}")
            screenshot_error = screenshots_dir / f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_error))
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "enrollment_id": None,
                "error": str(e)
            }
