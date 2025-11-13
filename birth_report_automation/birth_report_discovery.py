"""
Automated Field Discovery Tool for Birth Notifications
Automatically detects ALL fields in event form and compares with existing mappings
"""

import json
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import logging
from typing import Dict, List, Any
from datetime import datetime

# Load environment variables
root_dir = Path(__file__).parent.parent
load_dotenv(root_dir / '.env')

# Create logs and screenshots folders
script_dir = Path(__file__).parent
logs_dir = script_dir / "logs"
screenshots_dir = script_dir / "screenshots"
logs_dir.mkdir(exist_ok=True)
screenshots_dir.mkdir(exist_ok=True)

# Setup logging with date-based filename
log_file = logs_dir / f"discovery_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BirthFieldDiscovery:
    """Automatically discover ALL fields in DHIS2 birth notification form"""
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.discovered_fields = {}
        
    async def initialize(self):
        """Initialize browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            slow_mo=500
        )
        self.page = await self.browser.new_page()
        logger.info("✓ Browser initialized")
        
    async def close(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()
        logger.info("✓ Browser closed")
        
    async def login(self, base_url: str, username: str, password: str):
        """Login to DHIS2"""
        try:
            await self.page.goto(f"{base_url}/dhis-web-login/")
            await self.page.fill("#username", username)
            await self.page.fill("#password", password)
            await self.page.click('button[data-test="dhis2-uicore-button"]')
            await asyncio.sleep(3)
            logger.info("✓ Logged in")
            return True
        except Exception as e:
            logger.error(f"✗ Login failed: {e}")
            return False
            
    async def discover_event_fields(self, program_id: str, org_unit_id: str, base_url: str):
        """Discover all event form fields"""
        try:
            url = f"{base_url}/dhis-web-capture/index.html#/new?orgUnitId={org_unit_id}&programId={program_id}"
            await self.page.goto(url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            logger.info("\n" + "="*70)
            logger.info("DISCOVERING BIRTH NOTIFICATION FIELDS")
            logger.info("="*70)
            
            # Take screenshot
            screenshot_path = screenshots_dir / f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=str(screenshot_path))
            logger.info(f"✓ Screenshot saved: {screenshot_path.name}")
            
            # Discover text/date fields with data-test attributes
            text_fields = await self.page.query_selector_all('[data-test^="form-field-"] input[type="text"]')
            logger.info(f"\nFound {len(text_fields)} text fields")
            
            for field_elem in text_fields:
                parent = await field_elem.evaluate_handle('el => el.closest("[data-test^=\'form-field-\']")')
                field_id = await parent.get_attribute('data-test')
                field_id = field_id.replace('form-field-', '')
                
                # Get label
                label_elem = await parent.query_selector('.label_labelContainer__xTbRt')
                label = await label_elem.inner_text() if label_elem else field_id
                label = label.replace('*', '').strip()
                
                self.discovered_fields[field_id] = {
                    "selector": f"[data-test='form-field-{field_id}'] input",
                    "type": "text",
                    "label": label
                }
                logger.info(f"  ✓ {label} ({field_id})")
            
            # Discover select fields (virtualized-select with input#ID)
            select_fields = await self.page.query_selector_all('[data-test^="form-field-"] input[role="combobox"]')
            logger.info(f"\nFound {len(select_fields)} select fields")
            
            for field_elem in select_fields:
                field_id = await field_elem.get_attribute('id')
                parent = await field_elem.evaluate_handle('el => el.closest("[data-test^=\'form-field-\']")')
                
                label_elem = await parent.query_selector('.label_labelContainer__xTbRt')
                label = await label_elem.inner_text() if label_elem else field_id
                label = label.replace('*', '').strip()
                
                self.discovered_fields[field_id] = {
                    "selector": f"input#{field_id}",
                    "type": "select",
                    "label": label
                }
                logger.info(f"  ✓ {label} ({field_id})")
            
            # Discover date fields
            date_fields = await self.page.query_selector_all('[data-test^="dataentry-field-"] input[placeholder="yyyy-mm-dd"]')
            logger.info(f"\nFound {len(date_fields)} date fields")
            
            for field_elem in date_fields:
                parent = await field_elem.evaluate_handle('el => el.closest("[data-test^=\'dataentry-field-\']")')
                field_id = await parent.get_attribute('data-test')
                field_id = field_id.replace('dataentry-field-', '')
                
                label_elem = await parent.query_selector('.label_labelContainer__xTbRt')
                label = await label_elem.inner_text() if label_elem else field_id
                label = label.replace('*', '').strip()
                
                self.discovered_fields[field_id] = {
                    "selector": f"[data-test='dataentry-field-{field_id}'] input",
                    "type": "date",
                    "label": label
                }
                logger.info(f"  ✓ {label} ({field_id})")
            
            # Discover radio buttons
            radio_fields = await self.page.query_selector_all('input[type="radio"]')
            logger.info(f"\nFound {len(radio_fields)} radio buttons")
            
            radio_groups = {}
            for field_elem in radio_fields:
                name = await field_elem.get_attribute('name')
                if name and name not in radio_groups:
                    parent = await field_elem.evaluate_handle('el => el.closest(".withLabel_container__2GaWB")')
                    label_elem = await parent.query_selector('.label_labelContainer__xTbRt')
                    label = await label_elem.inner_text() if label_elem else name
                    label = label.replace('*', '').strip()
                    
                    self.discovered_fields[name] = {
                        "selector": f"input[name='{name}']",
                        "type": "radio",
                        "label": label
                    }
                    radio_groups[name] = True
                    logger.info(f"  ✓ {label} ({name})")
            
            logger.info("\n" + "="*70)
            logger.info(f"TOTAL DISCOVERED: {len(self.discovered_fields)} fields")
            logger.info("="*70)
            
            return self.discovered_fields
            
        except Exception as e:
            logger.error(f"✗ Discovery failed: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def compare_with_existing(self, existing_file: str = "field_mappings.json"):
        """Compare discovered fields with existing mappings"""
        try:
            if not Path(existing_file).exists():
                logger.warning(f"⚠ {existing_file} not found. All fields are NEW.")
                return
            
            with open(existing_file, 'r') as f:
                existing = json.load(f)
            
            discovered_ids = set(self.discovered_fields.keys())
            existing_ids = set(existing.keys())
            
            new_fields = discovered_ids - existing_ids
            missing_fields = existing_ids - discovered_ids
            common_fields = discovered_ids & existing_ids
            
            logger.info("\n" + "="*70)
            logger.info("COMPARISON WITH EXISTING MAPPINGS")
            logger.info("="*70)
            logger.info(f"✓ Common fields: {len(common_fields)}")
            logger.info(f"+ New fields: {len(new_fields)}")
            logger.info(f"- Missing fields: {len(missing_fields)}")
            
            if new_fields:
                logger.info("\nNEW FIELDS (not in existing mappings):")
                for field_id in sorted(new_fields):
                    field = self.discovered_fields[field_id]
                    logger.info(f"  + {field['label']} ({field_id}) - {field['type']}")
            
            if missing_fields:
                logger.info("\nMISSING FIELDS (in mappings but not discovered):")
                for field_id in sorted(missing_fields):
                    logger.info(f"  - {field_id}")
            
        except Exception as e:
            logger.error(f"✗ Comparison failed: {e}")
    
    def save_discovered_fields(self, output_file: str = None):
        """Save discovered fields to JSON"""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"discovered_fields_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.discovered_fields, f, indent=2)
        
        logger.info(f"\n✓ Discovered fields saved to: {output_file}")
        logger.info(f"  You can use this to update field_mappings.json")


async def main():
    """Main discovery process"""
    # Get credentials from environment
    base_url = os.getenv('BIRTH_DHIS_URL') or os.getenv('DHIS_URL')
    username = os.getenv('BIRTH_DHIS_USERNAME') or os.getenv('DHIS_USERNAME')
    password = os.getenv('BIRTH_DHIS_PASSWORD') or os.getenv('DHIS_PASSWORD')
    
    if not all([base_url, username, password]):
        logger.error("✗ Missing credentials in .env file")
        logger.error("  Set: BIRTH_DHIS_URL, BIRTH_DHIS_USERNAME, BIRTH_DHIS_PASSWORD")
        return
    
    # Load program ID from central dhis_programs.json
    programs_file = root_dir / 'dhis_programs.json'
    if not programs_file.exists():
        logger.error(f"✗ {programs_file} not found!")
        logger.error("  Central programs file is required")
        return
    
    with open(programs_file, 'r') as f:
        programs = json.load(f)
    
    birth_program = programs.get('birth_notification', {})
    program_id = birth_program.get('program_id')
    
    if not program_id or program_id == 'TBD':
        logger.error("✗ Birth notification program_id not found in dhis_programs.json")
        return
    
    # Load org unit ID from central dhis_org_units.json
    org_units_file = root_dir / 'dhis_org_units.json'
    if not org_units_file.exists():
        logger.error(f"✗ {org_units_file} not found!")
        logger.error("  Central org units file is required")
        return
    
    with open(org_units_file, 'r') as f:
        org_units_data = json.load(f)
    
    org_units = org_units_data.get('org_units', {})
    
    # Use Ghatere as default for discovery (can be changed)
    facility = org_units.get('Ghatere', {})
    org_unit_id = facility.get('id')
    
    if not org_unit_id:
        logger.error("✗ Ghatere org_unit_id not found in dhis_org_units.json")
        return
    
    logger.info("=" * 70)
    logger.info("BIRTH NOTIFICATION FIELD DISCOVERY")
    logger.info("=" * 70)
    logger.info(f"Server: {base_url}")
    logger.info(f"Program: birth_notification → {program_id}")
    logger.info(f"Org Unit: Ghatere → {org_unit_id}")
    logger.info(f"Loaded from: {programs_file.name} + {org_units_file.name}")
    logger.info("=" * 70)
    
    discovery = BirthFieldDiscovery()
    
    try:
        await discovery.initialize()
        
        if not await discovery.login(base_url, username, password):
            logger.error("✗ Login failed. Exiting.")
            return
        
        await discovery.discover_event_fields(program_id, org_unit_id, base_url)
        
        # Compare with existing
        discovery.compare_with_existing("field_mappings.json")
        
        # Save discovered fields
        discovery.save_discovered_fields()
        
        logger.info("\n" + "="*70)
        logger.info("✓ DISCOVERY COMPLETE")
        logger.info("="*70)
        logger.info("\nNext steps:")
        logger.info("1. Review discovered_fields_*.json")
        logger.info("2. Update field_mappings.json if needed")
        logger.info("3. Run birth_report_cli.py to test automation")
        
    except Exception as e:
        logger.error(f"✗ Discovery failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await discovery.close()


if __name__ == "__main__":
    asyncio.run(main())
