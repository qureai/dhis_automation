"""
Automated Field Discovery Tool
Automatically detects ALL fields (person + event) and compares with existing mappings
"""

import json
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import logging
from typing import Dict, List, Any, Set
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


class AutoFieldDiscovery:
    """Automatically discover ALL fields in DHIS2 forms"""
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.discovered_fields = {
            "person_profile": {},
            "enrollment": {},
            "event": {}
        }
        
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
            await self.page.goto(f"{base_url}/dhis-web-login/#/")
            await self.page.wait_for_selector('input[type="text"]', timeout=10000)
            await self.page.fill('input[type="text"]', username)
            await self.page.fill('input[type="password"]', password)
            await self.page.click('button[type="submit"]')
            await asyncio.sleep(3)
            logger.info("✓ Logged in")
            return True
        except Exception as e:
            logger.error(f"✗ Login failed: {e}")
            return False
            
    async def discover_person_fields(self, program_id: str, org_unit_id: str):
        """Discover all person registration fields"""
        try:
            url = f"{os.getenv('DEATH_DHIS_URL')}/dhis-web-capture/index.html#/new?orgUnitId={org_unit_id}&programId={program_id}"
            await self.page.goto(url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            logger.info("\n" + "="*70)
            logger.info("DISCOVERING PERSON FIELDS")
            logger.info("="*70)
            
            # Discover ALL data-test fields
            person_fields = await self.page.query_selector_all('[data-test^="form-field-"]')
            
            for field_elem in person_fields:
                field_id = await field_elem.get_attribute('data-test')
                field_id = field_id.replace('form-field-', '')
                
                # Get label
                try:
                    label_elem = await field_elem.query_selector('.label_labelContainer__xTbRt')
                    label = await label_elem.inner_text() if label_elem else field_id
                    label = label.replace('You must enter a value for this field', '').strip()
                except:
                    label = field_id
                
                # Detect field type
                input_elem = await field_elem.query_selector('input')
                select_elem = await field_elem.query_selector('[role="combobox"]')
                radio_elem = await field_elem.query_selector('input[type="radio"]')
                
                field_info = {
                    "label": label,
                    "id": field_id
                }
                
                if radio_elem:
                    # Get radio button name attribute for specific targeting
                    radio_name = await radio_elem.get_attribute('name')
                    field_info["type"] = "radio"
                    field_info["name"] = radio_name if radio_name else field_id
                    field_info["selector"] = f'input[name="{radio_name}"]' if radio_name else f'[data-test="form-field-{field_id}"] input[type="radio"]'
                elif select_elem:
                    # Check if it has an ID on the input
                    input_with_id = await field_elem.query_selector(f'input#{field_id}')
                    if input_with_id:
                        field_info["type"] = "select"
                        field_info["selector"] = f'input#{field_id}'
                    else:
                        field_info["type"] = "select"
                        field_info["selector"] = f'[data-test="form-field-{field_id}"] [role="combobox"]'
                        
                    # Try to get options
                    try:
                        await select_elem.click()
                        await asyncio.sleep(0.5)
                        options = await self.page.query_selector_all('.Select-option')
                        field_info["options"] = [await opt.inner_text() for opt in options[:10]]  # Limit to 10
                        await self.page.keyboard.press('Escape')
                    except:
                        pass
                        
                elif input_elem:
                    input_type = await input_elem.get_attribute('type')
                    placeholder = await input_elem.get_attribute('placeholder')
                    
                    if placeholder and 'yyyy-mm-dd' in placeholder:
                        field_info["type"] = "date"
                    else:
                        field_info["type"] = "text"
                    
                    field_info["selector"] = f'[data-test="form-field-{field_id}"] input'
                
                self.discovered_fields["person_profile"][field_id] = field_info
                logger.info(f"  ✓ Found: {label} ({field_info.get('type', 'unknown')})")
            
            logger.info(f"\n✓ Discovered {len(self.discovered_fields['person_profile'])} person fields")
            return True
            
        except Exception as e:
            logger.error(f"✗ Person field discovery failed: {e}")
            return False
            
    async def discover_event_fields(self, program_id: str, org_unit_id: str):
        """Discover all event fields by creating a minimal person first"""
        try:
            # Fill minimal person data to proceed to event form
            logger.info("\nFilling minimal person data to access event form...")
            
            timestamp = int(asyncio.get_event_loop().time())
            await self.page.fill('[data-test="form-field-k1jH5QP4TeN"] input', f'DISCOVER{timestamp}')
            await self.page.fill('[data-test="form-field-JqNKVDmsTBD"] input', 'TEST')
            await self.page.fill('[data-test="form-field-ZrUoLrUGgGB"] input', 'Discovery')
            
            # Fill sex dropdown
            sex_input = await self.page.query_selector('input#i2npNEAnH7D')
            if sex_input:
                await sex_input.fill('Male')
                await asyncio.sleep(0.2)
                await self.page.keyboard.press('Enter')
            
            # Save person
            await self.page.click('button:has-text("Save person")')
            await asyncio.sleep(2)
            
            # Handle duplicate dialog
            try:
                save_as_new = await self.page.wait_for_selector('button:has-text("Save as new")', timeout=3000)
                if save_as_new:
                    await save_as_new.click()
                    logger.info("  ✓ Handled duplicate dialog")
            except:
                pass
            
            # Wait for event form
            await asyncio.sleep(3)
            
            logger.info("\n" + "="*70)
            logger.info("DISCOVERING EVENT FIELDS")
            logger.info("="*70)
            
            # Discover event fields with data-test
            event_fields = await self.page.query_selector_all('[data-test^="form-field-"], [data-test^="dataentry-field-"]')
            
            for field_elem in event_fields:
                field_id = await field_elem.get_attribute('data-test')
                
                # Get label
                try:
                    label_elem = await field_elem.query_selector('.label_labelContainer__xTbRt, label')
                    label = await label_elem.inner_text() if label_elem else field_id
                    label = label.split('\n')[0].strip()  # Get first line only
                except:
                    label = field_id
                
                # Detect field type
                input_elem = await field_elem.query_selector('input')
                radio_elem = await field_elem.query_selector('input[type="radio"]')
                
                field_info = {
                    "label": label,
                    "id": field_id
                }
                
                if radio_elem:
                    # Get radio button name attribute for specific targeting
                    radio_name = await radio_elem.get_attribute('name')
                    field_info["type"] = "radio"
                    field_info["name"] = radio_name if radio_name else field_id
                    field_info["selector"] = f'input[name="{radio_name}"]' if radio_name else f'[data-test="{field_id}"] input[type="radio"]'
                elif input_elem:
                    input_id = await input_elem.get_attribute('id')
                    input_type = await input_elem.get_attribute('type')
                    placeholder = await input_elem.get_attribute('placeholder')
                    role = await input_elem.get_attribute('role')
                    
                    if role == 'combobox' and input_id:
                        field_info["type"] = "select"
                        field_info["selector"] = f'input#{input_id}'
                        
                        # Try to get options
                        try:
                            await input_elem.click()
                            await asyncio.sleep(0.5)
                            options = await self.page.query_selector_all('.Select-option')
                            field_info["options"] = [await opt.inner_text() for opt in options[:10]]
                            await self.page.keyboard.press('Escape')
                        except:
                            pass
                            
                    elif placeholder and 'yyyy-mm-dd' in placeholder:
                        field_info["type"] = "date"
                        field_info["selector"] = f'[data-test="{field_id}"] input'
                    else:
                        field_info["type"] = "text"
                        field_info["selector"] = f'[data-test="{field_id}"] input'
                
                self.discovered_fields["event"][field_id] = field_info
                logger.info(f"  ✓ Found: {label} ({field_info.get('type', 'unknown')})")
            
            logger.info(f"\n✓ Discovered {len(self.discovered_fields['event'])} event fields")
            return True
            
        except Exception as e:
            logger.error(f"✗ Event field discovery failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def compare_with_existing(self, existing_file: str = "field_mappings.json") -> Dict:
        """Compare discovered fields with existing mappings"""
        try:
            with open(existing_file, 'r') as f:
                existing = json.load(f)
        except FileNotFoundError:
            logger.warning(f"⚠ No existing mappings file found: {existing_file}")
            return {"new_fields": self.discovered_fields, "missing_fields": {}, "changed_fields": {}}
        
        # Extract field IDs from existing mappings
        existing_person_ids = set(existing.get("person_profile", {}).keys())
        existing_event_ids = set()
        
        for section in existing.get("event", {}).values():
            if isinstance(section, dict):
                existing_event_ids.update(section.keys())
        
        # Extract discovered IDs
        discovered_person_ids = set(self.discovered_fields["person_profile"].keys())
        discovered_event_ids = set(self.discovered_fields["event"].keys())
        
        # Find new and missing fields
        new_person = discovered_person_ids - existing_person_ids
        new_event = discovered_event_ids - existing_event_ids
        missing_person = existing_person_ids - discovered_person_ids
        missing_event = existing_event_ids - discovered_event_ids
        
        return {
            "new_fields": {
                "person": {fid: self.discovered_fields["person_profile"][fid] for fid in new_person},
                "event": {fid: self.discovered_fields["event"][fid] for fid in new_event}
            },
            "missing_fields": {
                "person": list(missing_person),
                "event": list(missing_event)
            },
            "total_discovered": {
                "person": len(discovered_person_ids),
                "event": len(discovered_event_ids)
            },
            "total_existing": {
                "person": len(existing_person_ids),
                "event": len(existing_event_ids)
            }
        }
    
    async def run_discovery(self):
        """Run complete discovery process"""
        try:
            # Get credentials
            base_url = os.getenv('DEATH_DHIS_URL')
            username = os.getenv('DEATH_DHIS_USERNAME')
            password = os.getenv('DEATH_DHIS_PASSWORD')
            
            # Load config
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            program_config = config['programs']['death_notification']
            
            await self.initialize()
            
            if not await self.login(base_url, username, password):
                return False
            
            # Discover person fields
            if not await self.discover_person_fields(program_config['program_id'], program_config['org_unit_id']):
                return False
            
            # Discover event fields
            if not await self.discover_event_fields(program_config['program_id'], program_config['org_unit_id']):
                return False
            
            # Compare with existing mappings
            comparison = self.compare_with_existing()
            
            # Generate report
            self.generate_report(comparison)
            
            # Save discovered fields
            output_file = f"discovered_fields_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(self.discovered_fields, f, indent=2)
            
            logger.info(f"\n✓ Discovered fields saved to: {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Discovery failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self.close()
    
    def generate_report(self, comparison: Dict):
        """Generate comparison report"""
        logger.info("\n" + "="*70)
        logger.info("FIELD DISCOVERY REPORT")
        logger.info("="*70)
        
        logger.info(f"\n📊 TOTAL FIELDS:")
        logger.info(f"  Person: {comparison['total_discovered']['person']} discovered | {comparison['total_existing']['person']} existing")
        logger.info(f"  Event:  {comparison['total_discovered']['event']} discovered | {comparison['total_existing']['event']} existing")
        
        new_person = comparison['new_fields']['person']
        new_event = comparison['new_fields']['event']
        
        if new_person or new_event:
            logger.info(f"\n🆕 NEW FIELDS DETECTED:")
            if new_person:
                logger.info(f"\n  Person Profile ({len(new_person)} new):")
                for fid, info in new_person.items():
                    logger.info(f"    ✨ {info['label']} ({info.get('type', 'unknown')})")
            if new_event:
                logger.info(f"\n  Event ({len(new_event)} new):")
                for fid, info in new_event.items():
                    logger.info(f"    ✨ {info['label']} ({info.get('type', 'unknown')})")
        else:
            logger.info("\n✓ No new fields detected - mappings are up to date!")
        
        missing_person = comparison['missing_fields']['person']
        missing_event = comparison['missing_fields']['event']
        
        if missing_person or missing_event:
            logger.info(f"\n⚠ MISSING FIELDS (in mappings but not found):")
            if missing_person:
                logger.info(f"  Person: {', '.join(missing_person)}")
            if missing_event:
                logger.info(f"  Event: {', '.join(missing_event)}")
        
        logger.info("\n" + "="*70)


async def main():
    """Main entry point"""
    discovery = AutoFieldDiscovery()
    success = await discovery.run_discovery()
    
    if success:
        print("\n✅ Discovery completed successfully!")
        print("Review the discovered_fields_*.json file for details")
    else:
        print("\n❌ Discovery failed!")


if __name__ == "__main__":
    asyncio.run(main())

