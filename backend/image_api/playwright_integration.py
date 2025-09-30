import asyncio
import threading
import os
import re
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any
from playwright.async_api import Playwright, async_playwright, expect

logger = logging.getLogger(__name__)

class DHISDataEntry:
    """
    Automates data entry into DHIS2 system using Playwright
    """

    def __init__(self, base_url: str = "http://172.236.165.102/dhis-test/apps/capture#/",
                 username: str = "admin",
                 password: str = "district"):
        self.base_url = base_url
        self.username = username
        self.password = password

    async def enter_patient_data(self, patient_data: Dict[str, Any]) -> bool:
        """
        Enter a single patient's data into DHIS2

        Args:
            patient_data: Dictionary containing patient information

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Starting data entry for patient: {patient_data.get('first_name', 'N/A')} {patient_data.get('last_name', 'N/A')}")
        logger.debug(f"Patient data: {patient_data}")
        async with async_playwright() as playwright:
            try:
                logger.debug("Launching browser...")
                prefer_headful = os.environ.get('PLAYWRIGHT_HEADFUL', '0').lower() in ('1', 'true', 'yes')
                if prefer_headful:
                    # Try headful with system Chrome first (more stable on macOS). Then default headful. Finally, headless fallback.
                    try:
                        browser = await playwright.chromium.launch(headless=False, channel=os.environ.get('PLAYWRIGHT_CHANNEL', 'chrome'))
                        context = await browser.new_context()
                        page = await context.new_page()
                    except Exception as chrome_channel_error:
                        logger.warning(
                            f"Headful launch with channel='chrome' failed. Trying bundled Chromium headful. Error: {chrome_channel_error}"
                        )
                        if 'browser' in locals():
                            try:
                                await browser.close()
                            except Exception:
                                pass
                        try:
                            browser = await playwright.chromium.launch(headless=False)
                            context = await browser.new_context()
                            page = await context.new_page()
                        except Exception as launch_or_page_error:
                            logger.warning(
                                f"Headful Chromium failed to start or create a page. Falling back to headless. Error: {launch_or_page_error}"
                            )
                            if 'browser' in locals():
                                try:
                                    await browser.close()
                                except Exception:
                                    pass
                            browser = await playwright.chromium.launch(
                                headless=True,
                                args=[
                                    "--disable-gpu",
                                    "--disable-dev-shm-usage",
                                ],
                            )
                            context = await browser.new_context()
                            page = await context.new_page()
                else:
                    # Default to headless for stability unless explicitly overridden
                    browser = await playwright.chromium.launch(
                        headless=True,
                        args=[
                            "--disable-gpu",
                            "--disable-dev-shm-usage",
                        ],
                    )
                    context = await browser.new_context()
                    page = await context.new_page()
                page.set_default_timeout(60000)

                # Navigate and login
                logger.info(f"Navigating to DHIS2: {self.base_url}")
                await page.goto(self.base_url)

                # Login
                logger.debug("Filling in username and password fields.")
                await page.get_by_role("textbox", name="Username").click()
                await page.get_by_role("textbox", name="Username").fill(self.username)
                await page.get_by_role("textbox", name="Password").click()
                await page.get_by_role("textbox", name="Password").fill(self.password)
                await page.locator("[data-test=\"dhis2-uicore-button\"]").click()

                # Wait for login to complete
                logger.debug("Waiting for login to complete...")
                await page.wait_for_timeout(2000)

                # Get the iframe element and its content frame
                logger.debug("Locating iframe for DHIS2 app...")
                iframe_locator = page.locator("iframe")
                iframe_element = await iframe_locator.element_handle()
                if not iframe_element:
                    logger.error("Could not find iframe on the page.")
                    await context.close()
                    await browser.close()
                    return False
                frame = await iframe_element.content_frame()
                if not frame:
                    logger.error("Could not get content frame from iframe.")
                    await context.close()
                    await browser.close()
                    return False

                # Select Malaria program
                logger.debug("Selecting Malaria program...")
                await frame.locator("[data-test=\"program-selector-container\"]").click()
                await frame.get_by_role("textbox", name="Search for a program").fill("mala")
                await frame.locator("a").filter(has_text="Malaria case diagnosis,").click()

                # Select organization unit
                logger.debug("Selecting organization unit: Ngelehun CHC")
                await frame.locator("[data-test=\"org-unit-selector-container\"]").click()
                await frame.get_by_role("textbox", name="Search").click()
                await frame.get_by_role("textbox", name="Search").fill("Ngelehun CHC")
                await frame.locator("[data-test=\"dhis2-uiwidgets-orgunittree-node-label\"]").get_by_text("Ngelehun CHC").click()
                await frame.locator("[data-test=\"new-button-button\"]").click()

                # Fill patient details
                # First name
                first_name = patient_data.get('first_name', f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                logger.debug(f"Filling first name: {first_name}")
                await frame.locator("(//input[@type='text'])[4]").click()
                await frame.locator("(//input[@type='text'])[4]").fill(first_name)

                # Last name
                last_name = patient_data.get('last_name', f"user_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                if not last_name:
                    last_name = f"user_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                logger.debug(f"Filling last name: {last_name}")
                await frame.locator("(//input[@type='text'])[5]").click()
                await frame.locator("(//input[@type='text'])[5]").fill(last_name)

                # Date of birth
                date_of_birth = patient_data.get('date_of_birth', '2000-01-01')
                if not date_of_birth:
                    date_of_birth = '2000-01-01'
                if date_of_birth and date_of_birth != 'Not Found':
                    # Ensure date is in yyyy-mm-dd format
                    if '/' in date_of_birth:
                        parts = date_of_birth.split('/')
                        if len(parts) == 3:
                            date_of_birth = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    logger.debug(f"Filling date of birth: {date_of_birth}")
                    await frame.locator("(//input[@placeholder='yyyy-mm-dd'])[2]").click()
                    await frame.locator("(//input[@placeholder='yyyy-mm-dd'])[2]").fill(date_of_birth)
                

                await page.wait_for_timeout(500)
                logger.debug("Clicking create and link button.")
                await frame.locator("[data-test=\"create-and-link-button\"]").click()
                await page.wait_for_timeout(1000)
                await page.screenshot(path="second_page.png")

                # Date of diagnosis
                date_of_diagnosis = patient_data.get('date_of_diagnosis')
                if date_of_diagnosis and date_of_diagnosis != 'Not Found':
                    if '/' in date_of_diagnosis:
                        parts = date_of_diagnosis.split('/')
                        if len(parts) == 3:
                            date_of_diagnosis = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    logger.debug(f"Filling date of diagnosis: {date_of_diagnosis}")
                    # Try to click on the specific date if available
                    await frame.locator("(//input[@placeholder='yyyy-mm-dd'])[1]").click()
                    await frame.locator("(//input[@placeholder='yyyy-mm-dd'])[1]").fill(date_of_diagnosis)
                
                await page.screenshot(path="post_date_of_diagnosis.png")

                # Case detection option
                case_detection = patient_data.get('case_detection_options', 'Reactive (ACD)')
                logger.debug(f"Selecting case detection option: {case_detection}")
                await frame.locator("(//div[@class='Select-placeholder'])[1]").first.click()

                # Map case detection options
                detection_map = {
                    'reactive': 'Reactive (ACD)',
                    'active': 'Active (ACD)',
                    'passive': 'Passive (PCD)',
                    'acd': 'Active (ACD)',
                    'pcd': 'Passive (PCD)'
                }
                if not case_detection and case_detection == 'null':
                    case_detection = "passive"
                else:
                    case_detection = case_detection.lower()
                case_detection = "reactive"

                detection_option = detection_map.get(case_detection.lower(), case_detection)
                logger.debug(f"Resolved detection option: {detection_option}")
                await frame.get_by_role("option", name=detection_option).click()
                await page.screenshot(path="post_case_detection.png")
                

                # # Additional fields if available
                # # Gender
                # if 'gender' in patient_data and patient_data['gender']:
                #     try:
                #         logger.debug(f"Setting gender: {patient_data['gender']}")
                #         await frame.locator("//label[contains(text(),'Gender')]/..//div[@class='Select-placeholder']").click()
                #         await frame.get_by_role("option", name=patient_data['gender'].capitalize()).click()
                #     except Exception as e:
                #         logger.warning(f"Could not set gender: {patient_data['gender']}. Error: {e}")

                # # Temperature
                # if 'temperature' in patient_data and patient_data['temperature'] and patient_data['temperature'] > 0:
                #     try:
                #         logger.debug(f"Setting temperature: {patient_data['temperature']}")
                #         await frame.locator("//input[@placeholder='Temperature']").fill(str(patient_data['temperature']))
                #     except Exception as e:
                #         logger.warning(f"Could not set temperature: {patient_data['temperature']}. Error: {e}")

                # # Weight
                # if 'weight' in patient_data and patient_data['weight'] and patient_data['weight'] > 0:
                #     try:
                #         logger.debug(f"Setting weight: {patient_data['weight']}")
                #         await frame.locator("//input[@placeholder='Weight']").fill(str(patient_data['weight']))
                #     except Exception as e:
                #         logger.warning(f"Could not set weight: {patient_data['weight']}. Error: {e}")

                await page.wait_for_timeout(1000)

                # Save the entry
                logger.debug("Clicking Save button.")
                await frame.get_by_role("button", name="Save").click()
                await page.wait_for_timeout(5000)

                logger.info(f"Successfully entered data for patient: {first_name} {last_name}")

                await context.close()
                await browser.close()
                return True

            except Exception as e:
                logger.exception(f"Error entering patient data: {str(e)}")
                logger.error(f"Patient data: {patient_data}")
                if 'browser' in locals():
                    await browser.close()
                return False

    async def enter_multiple_patients(self, patients_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Enter multiple patients' data into DHIS2

        Args:
            patients_list: List of patient data dictionaries

        Returns:
            Dict with success count and failed entries
        """
        results = {
            'total': len(patients_list),
            'successful': 0,
            'failed': 0,
            'failed_patients': []
        }

        for i, patient in enumerate(patients_list, 1):
            logger.info(f"Processing patient {i}/{len(patients_list)}")
            success = await self.enter_patient_data(patient)

            if success:
                results['successful'] += 1
            else:
                results['failed'] += 1
                results['failed_patients'].append(patient)

            # Add delay between entries to avoid overwhelming the system
            if i < len(patients_list):
                await asyncio.sleep(2)

        logger.info(f"Completed data entry: {results['successful']}/{results['total']} successful")
        return results


async def process_and_enter_data(patient_records: List[Dict[str, Any]],
                                 base_url: str = None,
                                 username: str = None,
                                 password: str = None) -> Dict[str, Any]:
    """
    Main function to process extracted patient records and enter them into DHIS2

    Args:
        patient_records: List of patient records extracted by LLM
        base_url: Optional DHIS2 URL
        username: Optional username
        password: Optional password

    Returns:
        Results dictionary
    """
    logger.info(f"Starting DHIS2 data entry for {len(patient_records)} patients")

    # Initialize DHIS data entry
    dhis = DHISDataEntry(
        base_url=base_url or "http://172.236.165.102/dhis-test/apps/capture#/",
        username=username or "admin",
        password=password or "district"
    )

    # Enter data for all patients
    results = await dhis.enter_multiple_patients(patient_records)

    return results


def sync_process_and_enter_data(patient_records: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    """
    Synchronous wrapper for the async process_and_enter_data function
    """
    # If called from a context that already has a running event loop (ASGI/DRF),
    # run the coroutine in a separate thread with its own loop to avoid InvalidStateError
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop.is_running():
        result_holder: Dict[str, Any] = {}
        exc_holder: Dict[str, BaseException] = {}

        def runner():
            try:
                result_holder['result'] = asyncio.run(process_and_enter_data(patient_records, **kwargs))
            except BaseException as e:  # capture to re-raise in caller thread
                exc_holder['exc'] = e

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if 'exc' in exc_holder:
            raise exc_holder['exc']
        return result_holder.get('result', {})
    else:
        return asyncio.run(process_and_enter_data(patient_records, **kwargs))