"""
Death Report Automation CLI
Main entry point for running death notification automation
Uses dynamic program and org unit resolution from central JSON files
"""

import asyncio
import json
import argparse
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from death_report_automation import CompleteDeathAutomation

# Load environment variables from root .env
root_dir = Path(__file__).parent.parent
env_path = root_dir / '.env'
load_dotenv(env_path)

# Central JSON file paths
PROGRAMS_FILE = root_dir / 'dhis_programs.json'
ORG_UNITS_FILE = root_dir / 'dhis_org_units.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_programs():
    """Load program IDs from central dhis_programs.json"""
    if not PROGRAMS_FILE.exists():
        logger.error(f"✗ {PROGRAMS_FILE} not found!")
        logger.error("  Run validation script to create this file.")
        return None
    
    with open(PROGRAMS_FILE, 'r') as f:
        return json.load(f)


def load_org_units():
    """Load org unit IDs from central dhis_org_units.json"""
    if not ORG_UNITS_FILE.exists():
        logger.error(f"✗ {ORG_UNITS_FILE} not found!")
        return None
    
    with open(ORG_UNITS_FILE, 'r') as f:
        data = json.load(f)
        return data.get('org_units', {})


def resolve_program_id(program_key: str, programs: dict) -> str:
    """Resolve program key to program ID"""
    program = programs.get(program_key)
    if not program:
        logger.error(f"✗ Program '{program_key}' not found in dhis_programs.json")
        logger.error(f"  Available programs: {', '.join(programs.keys())}")
        return None
    
    program_id = program.get('program_id')
    if not program_id or program_id == 'TBD':
        logger.error(f"✗ Program '{program_key}' has no valid program_id (TBD)")
        return None
    
    return program_id


def resolve_org_unit_id(facility_name: str, org_units: dict) -> str:
    """Resolve facility name to org unit ID"""
    org_unit = org_units.get(facility_name)
    if not org_unit:
        logger.error(f"✗ Facility '{facility_name}' not found in dhis_org_units.json")
        logger.error(f"  Available facilities: {len(org_units)} total")
        logger.error(f"  Search example: Yandina, Tulagi, Honiara")
        return None
    
    org_unit_id = org_unit.get('id')
    if not org_unit_id:
        logger.error(f"✗ Facility '{facility_name}' has no valid org_unit_id")
        return None
    
    return org_unit_id


async def run_automation(
    data_file: str = "sample_data.json",
    complete_event: bool = True,
    headless: bool = False,
    slow_mo: int = 100
):
    """Run death notification automation with dynamic resolution"""
    
    try:
        # Load central registries
        programs = load_programs()
        org_units = load_org_units()
        
        if not programs or not org_units:
            return False
        
        logger.info(f"✓ Loaded {len(programs)} programs from {PROGRAMS_FILE.name}")
        logger.info(f"✓ Loaded {len(org_units)} org units from {ORG_UNITS_FILE.name}")
        
        # Load sample data
        with open(data_file, 'r') as f:
            death_data = json.load(f)
        
        # Extract metadata from sample data
        meta = death_data.get('_meta', {})
        program_key = meta.get('program')
        facility_name = meta.get('facility')
        
        if not program_key:
            logger.error("✗ Missing '_meta.program' in sample data")
            logger.error("  Example: {\"_meta\": {\"program\": \"death_notification\", \"facility\": \"Yandina\"}}")
            return False
        
        if not facility_name:
            logger.error("✗ Missing '_meta.facility' in sample data")
            logger.error("  Example: {\"_meta\": {\"program\": \"death_notification\", \"facility\": \"Yandina\"}}")
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info("DHIS2 Death Notification Automation")
        logger.info("=" * 60)
        
        # Resolve program_id
        program_id = resolve_program_id(program_key, programs)
        if not program_id:
            return False
        
        # Resolve org_unit_id
        org_unit_id = resolve_org_unit_id(facility_name, org_units)
        if not org_unit_id:
            return False
        
        # Get credentials from environment variables
        base_url = os.getenv('DEATH_DHIS_URL') or os.getenv('DHIS_URL')
        username = os.getenv('DEATH_DHIS_USERNAME') or os.getenv('DHIS_USERNAME')
        password = os.getenv('DEATH_DHIS_PASSWORD') or os.getenv('DHIS_PASSWORD')
        
        if not all([base_url, username, password]):
            logger.error("✗ Missing required environment variables")
            logger.error("  Set: DEATH_DHIS_URL, DEATH_DHIS_USERNAME, DEATH_DHIS_PASSWORD")
            return False
        
        # Log resolved configuration
        logger.info(f"Server: {base_url}")
        logger.info(f"Program: {program_key} → {program_id}")
        logger.info(f"Facility: {facility_name} → {org_unit_id}")
        logger.info(f"Browser: {'Headless' if headless else 'Visible'} (slow_mo: {slow_mo}ms)")
        logger.info("=" * 60)
        
        # Create automation instance
        async with CompleteDeathAutomation(
            base_url=base_url,
            username=username,
            password=password,
            headless=headless,
            slow_mo=slow_mo
        ) as automation:
            
            # Run automation
            result = await automation.automate(
                program_id=program_id,
                org_unit_id=org_unit_id,
                data=death_data
            )
            
            # Display result based on HTTP status code
            status_code = result.get("status_code")
            api_resp = result.get("api_response")
            
            if result.get("success"):
                logger.info("=" * 60)
                
                # Log message based on status code
                if status_code == 200:
                    logger.info("✅ RECORD CREATED SUCCESSFULLY!")
                else:
                    logger.info("✓ Automation completed")
                    
                logger.info("=" * 60)
                
                # Display HTTP status code
                if status_code:
                    logger.info("")
                    logger.info(f"📡 HTTP Status Code: {status_code}")
                    if status_code == 200:
                        logger.info("   ✓ Success - Record created")
                    elif status_code == 409:
                        logger.warning("   ⚠️  Conflict - Possible duplicate")
                
                if result.get("enrollment_id"):
                    logger.info("")
                    logger.info("📋 ENROLLMENT ID FOR VERIFICATION:")
                    logger.info(f"   {result['enrollment_id']}")
                    logger.info("")
                    logger.info(f"🔗 Direct link:")
                    logger.info(f"   {base_url}/dhis-web-capture/index.html#/enrollment?enrollmentId={result['enrollment_id']}")
                
                # Display API response body
                if api_resp:
                    logger.info("")
                    logger.info("📋 API RESPONSE DETAILS:")
                    logger.info(f"   Status: {api_resp.get('status', 'UNKNOWN')}")
                    
                    stats = api_resp.get('stats', {})
                    if stats:
                        logger.info(f"   Created: {stats.get('created', 0)}")
                        logger.info(f"   Updated: {stats.get('updated', 0)}")
                        logger.info(f"   Ignored: {stats.get('ignored', 0)}")
                    
                    # Show validation errors if any
                    validation = api_resp.get('validationReport', {})
                    errors = validation.get('errorReports', [])
                    if errors:
                        logger.warning(f"   ⚠️  Validation Errors: {len(errors)}")
                        for err in errors[:3]:  # Show first 3 errors
                            logger.warning(f"      - {err.get('message', 'Unknown error')}")
                
                logger.info("=" * 60)
                return result
            else:
                logger.error("=" * 60)
                
                # Log message based on status code
                if status_code == 409:
                    logger.error("⚠️  RECORD NOT CREATED - DUPLICATE/CONFLICT!")
                elif status_code:
                    logger.error(f"❌ RECORD NOT CREATED - HTTP {status_code}")
                else:
                    logger.error("✗ Automation failed!")
                    
                logger.error("=" * 60)
                
                # Display HTTP status code
                if status_code:
                    logger.error("")
                    logger.error(f"📡 HTTP Status Code: {status_code}")
                    if status_code == 409:
                        logger.error("   ⚠️  Conflict - Duplicate serial number or data")
                    else:
                        logger.error(f"   ❌ Failed - HTTP {status_code}")
                
                if result.get("error"):
                    logger.error("")
                    logger.error(f"Error: {result['error']}")
                
                # Display API response even on failure
                if api_resp:
                    logger.error("")
                    logger.error("📋 API RESPONSE DETAILS:")
                    logger.error(f"   Status: {api_resp.get('status', 'UNKNOWN')}")
                    
                    stats = api_resp.get('stats', {})
                    if stats:
                        logger.error(f"   Created: {stats.get('created', 0)}")
                        logger.error(f"   Updated: {stats.get('updated', 0)}")
                        logger.error(f"   Ignored: {stats.get('ignored', 0)}")
                    
                    # Show validation errors
                    validation = api_resp.get('validationReport', {})
                    errors = validation.get('errorReports', [])
                    if errors:
                        logger.error(f"   ❌ Validation Errors:")
                        for err in errors:
                            logger.error(f"      - {err.get('message', 'Unknown error')}")
                            if err.get('args'):
                                logger.error(f"        Args: {err['args']}")
                
                logger.error("=" * 60)
                return result
                
    except FileNotFoundError as e:
        logger.error(f"✗ File not found: {e}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"✗ Invalid JSON: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='DHIS2 Death Notification Automation (Dynamic Program & Org Unit Resolution)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (uses _meta from sample_data.json)
  python death_report_cli.py
  
  # Run with custom data file (must include _meta section)
  python death_report_cli.py --data my_death_data.json
  
  # Run in headless mode (no browser window)
  python death_report_cli.py --headless
  
  # Run faster (no slow motion)
  python death_report_cli.py --slow-mo 0
  
  # Save as draft (don't complete event)
  python death_report_cli.py --no-complete

Data File Format:
  {
    "_meta": {
      "program": "death_notification",
      "facility": "Yandina"
    },
    "enrollment": { ... },
    "person_profile": { ... },
    "event": { ... }
  }
        """
    )
    
    parser.add_argument(
        '--data',
        default='sample_data.json',
        help='Path to death data file with _meta section (default: sample_data.json)'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (no window)'
    )
    
    parser.add_argument(
        '--slow-mo',
        type=int,
        default=100,
        help='Slow down Playwright operations by N milliseconds (default: 100, use 0 for fast)'
    )
    
    parser.add_argument(
        '--no-complete',
        action='store_true',
        help='Save as draft without completing event'
    )
    
    args = parser.parse_args()
    
    # Run automation
    success = asyncio.run(run_automation(
        data_file=args.data,
        complete_event=not args.no_complete,
        headless=args.headless,
        slow_mo=args.slow_mo
    ))
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

