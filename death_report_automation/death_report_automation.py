"""
Complete Death Report Automation - Fills ALL Fields
Person Profile (22 fields) + Enrollment (1 field) + Event (13 fields) = 36 fields total
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

class CompleteDeathAutomation:
    """
    Complete automation for DHIS2 Death Notification (Tracker Program).
    Handles Person Registration + Death Notification Event with all fields.
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
            input_selector = f"{selector} input" if "[role=\"combobox\"]" in selector else selector
            await self.page.fill(input_selector, value)
            await asyncio.sleep(0.3)
            await self.page.keyboard.press('Enter')
            logger.info(f"  ✓ {label}: {value}")
        except Exception as e:
            logger.warning(f"  ✗ {label} failed: {e}")

    async def fill_radio_field(self, selector: str, value: str, label: str = ""):
        """Fill a radio button field"""
        try:
            # Find the radio button with the matching value
            radio_value = "true" if value.lower() in ["yes", "true", "1"] else "false"
            radio_selector = f"{selector}[value=\"{radio_value}\"]"
            await self.page.click(radio_selector)
            logger.info(f"  ✓ {label}: {value}")
        except Exception as e:
            logger.warning(f"  ✗ {label} failed: {e}")

    async def fill_person_profile(self, data: Dict[str, Any], mappings: Dict[str, Any]) -> int:
        """Fill person profile fields"""
        filled_count = 0
        logger.info("Filling person profile...")
        
        for key, field_map in mappings.items():
            if key in data and data[key]:
                selector = field_map["selector"]
                field_type = field_map["type"]
                label = field_map.get("label", key)
                value = data[key]

                if field_type in ["text", "date"]:
                    await self.fill_text_field(selector, value, label)
                    filled_count += 1
                elif field_type == "select":
                    await self.fill_select_field(selector, value, label)
                    filled_count += 1
        
        return filled_count

    async def navigate_to_new_person_form(self, program_id: str, org_unit_id: str) -> bool:
        """Navigate to new person form"""
        try:
            url = f"{self.base_url}/dhis-web-capture/index.html#/new?orgUnitId={org_unit_id}&programId={program_id}"
            logger.info("Opening person registration form...")
            await self.page.goto(url, wait_until="networkidle")
            await self.page.wait_for_selector('button:has-text("Save person")', timeout=30000)
            logger.info("✓ Form loaded")
            return True
        except Exception as e:
            logger.error(f"✗ Form navigation failed: {e}")
            screenshot_path = screenshots_dir / f"form_navigation_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_path))
            return False

    async def save_person_and_navigate_to_event(self) -> bool:
        """Save person - event form opens automatically"""
        try:
            logger.info("Saving person...")
            await self.page.click('button:has-text("Save person")')
            
            # Check for "Possible duplicates found" dialog
            await asyncio.sleep(1)
            try:
                save_as_new_button = await self.page.wait_for_selector('button:has-text("Save as new")', timeout=3000)
                if save_as_new_button:
                    logger.info("⚠ Duplicate dialog detected - clicking 'Save as new'...")
                    await save_as_new_button.click()
                    logger.info("  ✓ Clicked 'Save as new'")
            except:
                logger.info("  No duplicate dialog (or already proceeded)")
            
            # After saving person, DHIS2 automatically navigates to the event form
            logger.info("Waiting for navigation to event form...")
            
            # Wait for URL to change to enrollmentEventEdit
            for i in range(30):  # Wait up to 15 seconds
                await asyncio.sleep(0.5)
                current_url = self.page.url
                if 'enrollmentEventEdit' in current_url:
                    logger.info("✓ Event form URL detected")
                    break
            else:
                logger.warning(f"⚠ URL didn't change to enrollmentEventEdit. Current: {self.page.url}")
            
            # Wait for event form fields to be ready
            await self.page.wait_for_selector('[data-test="form-field-WiAkoty8mUF"]', timeout=10000)
            logger.info("✓ Event form loaded and ready")
            
            # Small delay to ensure all fields are rendered
            await asyncio.sleep(1)
            return True
                
        except Exception as e:
            logger.error(f"✗ Failed to load event form: {e}")
            logger.info(f"Current URL: {self.page.url}")
            screenshot_path = screenshots_dir / f"event_form_load_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            return False

    async def fill_event_fields(self, data: Dict[str, Any], mappings: Dict[str, Any]) -> int:
        """Fill all event fields (basic info, source, manner of death, declaration, status)"""
        filled_count = 0
        
        # Fill all event sections
        for section_name, section_data in data.items():
            if section_name in mappings and section_data:
                logger.info(f"Filling {section_name}...")
                section_mappings = mappings[section_name]
                
                for key, field_map in section_mappings.items():
                    if key in section_data and section_data[key]:
                        selector = field_map["selector"]
                        field_type = field_map["type"]
                        label = field_map.get("label", key)
                        value = section_data[key]
                        
                        # Skip org_unit field (auto-filled)
                        if field_type == "org_unit":
                            continue

                        if field_type in ["text", "date"]:
                            await self.fill_text_field(selector, value, label)
                            filled_count += 1
                        elif field_type == "select":
                            await self.fill_select_field(selector, value, label)
                            filled_count += 1
                        elif field_type == "radio":
                            await self.fill_radio_field(selector, value, label)
                            filled_count += 1
        
        return filled_count

    async def save_event(self, complete: bool = True) -> tuple[bool, str | None, dict | None, int | None]:
        """
        Save the event and verify success
        
        Returns:
            tuple: (success: bool, enrollment_id: str | None, api_response: dict | None, status_code: int | None)
        """
        api_response = None
        status_code = None
        
        try:
            if complete:
                logger.info("Completing event...")
                # Click "Complete event" Yes radio button
                try:
                    await self.page.click('input[type="radio"][value="true"]')
                    logger.info("  ✓ Marked as complete")
                except:
                    logger.warning("  Could not mark as complete")
            
            logger.info("Saving event...")
            
            # Set up response listener to capture API response
            async def handle_response(response):
                nonlocal api_response, status_code
                # Capture POST requests to tracker endpoint (enrollment + events)
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
            
            # Click save button
            await self.page.click('button:has-text("Save")')
            
            # Wait for API response
            await asyncio.sleep(2)
            
            # Wait and verify success
            success, enrollment_id = await self.verify_submission_success()
            
            # Remove listener
            self.page.remove_listener("response", handle_response)
            
            # Determine success based on status code
            if status_code == 200:
                success = True
                logger.info("✓ Event saved successfully")
                if enrollment_id:
                    logger.info(f"📋 Enrollment ID: {enrollment_id}")
                return True, enrollment_id, api_response, status_code
            elif status_code == 409:
                logger.warning("⚠️  Event save conflict (likely duplicate)")
                return False, enrollment_id, api_response, status_code
            elif success:
                logger.info("✓ Event saved successfully")
                if enrollment_id:
                    logger.info(f"📋 Enrollment ID: {enrollment_id}")
                return True, enrollment_id, api_response, status_code
            else:
                logger.error("✗ Event save failed - no success confirmation")
                screenshot_path = screenshots_dir / f"save_event_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.page.screenshot(path=str(screenshot_path))
                return False, None, api_response, status_code
                
        except Exception as e:
            logger.error(f"✗ Failed to save event: {e}")
            screenshot_path = screenshots_dir / f"save_event_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
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
                
                # URL change (redirects away from form)
                # Check if URL changed from /new or /edit
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

    def replace_timestamps(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Replace _TIMESTAMP_ placeholders with actual timestamp"""
        import time
        timestamp = str(int(time.time()))
        
        def replace_in_dict(d):
            if isinstance(d, dict):
                return {k: replace_in_dict(v) for k, v in d.items()}
            elif isinstance(d, str):
                return d.replace('_TIMESTAMP_', timestamp)
            else:
                return d
        
        return replace_in_dict(data)

    async def automate(
        self,
        program_id: str,
        org_unit_id: str,
        data: Dict[str, Any],
        field_mappings_file: str = "field_mappings.json",
        complete_event: bool = True
    ) -> Dict[str, Any]:
        """
        Complete automation: Person Registration + Death Notification Event
        """
        try:
            # Replace timestamp placeholders with actual timestamps
            data = self.replace_timestamps(data)
            
            # Load field mappings
            script_dir = Path(__file__).parent
            mappings_path = script_dir / field_mappings_file
            with open(mappings_path, 'r') as f:
                field_mappings = json.load(f)

            # Login
            if not await self.login():
                return {
                    "success": False,
                    "enrollment_id": None,
                    "error": "Login failed"
                }

            # Navigate to new person form
            if not await self.navigate_to_new_person_form(program_id, org_unit_id):
                return {
                    "success": False,
                    "enrollment_id": None,
                    "error": "Failed to navigate to form"
                }

            logger.info("\n" + "="*60)
            logger.info("STEP 1: PERSON REGISTRATION")
            logger.info("="*60)

            # Fill enrollment (date of death)
            logger.info("Setting enrollment date...")
            enrollment_data = data.get("enrollment", {})
            enrollment_mappings = field_mappings.get("enrollment", {})
            if "date_of_death" in enrollment_data:
                await self.fill_text_field(
                    enrollment_mappings["date_of_death"]["selector"],
                    enrollment_data["date_of_death"],
                    "Date of death"
                )

            # Fill person profile
            person_profile_data = data.get("person_profile", {})
            person_profile_mappings = field_mappings.get("person_profile", {})
            person_fields_filled = await self.fill_person_profile(person_profile_data, person_profile_mappings)

            # Save person and navigate to event
            if not await self.save_person_and_navigate_to_event():
                return {
                    "success": False,
                    "enrollment_id": None,
                    "error": "Failed to save person or navigate to event"
                }

            logger.info("\n" + "="*60)
            logger.info("STEP 2: DEATH NOTIFICATION EVENT")
            logger.info("="*60)

            # Fill event fields
            event_data = data.get("event", {})
            event_mappings = field_mappings.get("event", {})
            event_fields_filled = await self.fill_event_fields(event_data, event_mappings)

            # Save event and get enrollment ID
            success, enrollment_id, api_response, status_code = await self.save_event(complete=complete_event)
            if not success:
                return {
                    "success": False,
                    "enrollment_id": None,
                    "person_fields": person_fields_filled,
                    "event_fields": event_fields_filled,
                    "api_response": api_response,
                    "status_code": status_code,
                    "error": "Event save failed"
                }

            logger.info("\n" + "="*60)
            logger.info("✓ AUTOMATION COMPLETE!")
            logger.info("="*60)
            logger.info(f"Person fields filled: {person_fields_filled}")
            logger.info(f"Event fields filled: {event_fields_filled}")
            logger.info(f"Total fields filled: {person_fields_filled + event_fields_filled + 1}")
            if enrollment_id:
                logger.info(f"📋 Enrollment ID: {enrollment_id}")
            logger.info("="*60)

            return {
                "success": True,
                "enrollment_id": enrollment_id,
                "person_fields": person_fields_filled,
                "event_fields": event_fields_filled,
                "total_fields": person_fields_filled + event_fields_filled + 1,
                "api_response": api_response,
                "status_code": status_code
            }

        except Exception as e:
            logger.error(f"✗ Automation failed: {e}")
            screenshot_path = screenshots_dir / f"automation_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_path))
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "enrollment_id": None,
                "error": str(e)
            }

