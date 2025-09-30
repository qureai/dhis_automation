import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class DHISAutomationService:
    """Django service that directly imports and uses functions from root dhis_automation.py"""
    
    def __init__(self):
        # Add root directory to Python path to import dhis_automation
        self.root_dir = Path(settings.BASE_DIR).parent
        if str(self.root_dir) not in sys.path:
            sys.path.insert(0, str(self.root_dir))
        
        # Import the DHISSmartAutomation class from root folder
        try:
            from dhis_automation import DHISSmartAutomation
            self.DHISSmartAutomation = DHISSmartAutomation
            logger.info("Successfully imported DHISSmartAutomation from root dhis_automation.py")
        except ImportError as e:
            logger.error(f"Failed to import DHISSmartAutomation from root folder: {e}")
            self.DHISSmartAutomation = None
        
        self.temp_data_dir = Path(settings.MEDIA_ROOT) / 'temp_data'
        self.temp_data_dir.mkdir(exist_ok=True)
        
    def fill_dhis_form(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fill DHIS2 form using extracted data - uses the exact DHISSmartAutomation class from root folder
        """
        if not self.DHISSmartAutomation:
            raise Exception("DHISSmartAutomation class not available - check import from root folder")
        
        try:
            logger.info(f"Starting DHIS2 form filling with {len(extracted_data)} fields using root automation class")
            
            # Save extracted data to temporary JSON file
            temp_file_path = self._save_temp_data(extracted_data)
            
            # Run the DHIS automation using the imported class
            result = self._run_dhis_automation(temp_file_path)
            
            # Clean up temporary file
            self._cleanup_temp_file(temp_file_path)
            
            return result
            
        except Exception as e:
            logger.error(f"DHIS2 form filling failed: {e}")
            raise Exception(f"DHIS2 automation error: {str(e)}")
    
    def _save_temp_data(self, extracted_data: Dict[str, Any]) -> str:
        """Save extracted data to temporary JSON file"""
        try:
            import uuid
            temp_filename = f"temp_health_data_{uuid.uuid4().hex[:8]}.json"
            temp_file_path = self.temp_data_dir / temp_filename
            
            # Format data for DHIS automation
            formatted_data = self._format_for_dhis(extracted_data)
            
            with open(temp_file_path, 'w') as f:
                json.dump(formatted_data, f, indent=2)
            
            logger.info(f"Saved temporary data file: {temp_file_path}")
            return str(temp_file_path)
            
        except Exception as e:
            logger.error(f"Failed to save temporary data: {e}")
            raise
    
    def _format_for_dhis(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format extracted data for DHIS2 automation"""
        dhis_data = {}
        
        for key, value in extracted_data.items():
            # Skip metadata fields
            if key in ['raw_text', 'extraction_method', 'note', 'error']:
                continue
                
            # Ensure numeric values are properly formatted
            if isinstance(value, (int, float)):
                dhis_data[key] = value
            elif isinstance(value, str):
                try:
                    if value.isdigit():
                        dhis_data[key] = int(value)
                    else:
                        dhis_data[key] = value
                except:
                    dhis_data[key] = value
            else:
                dhis_data[key] = value
        
        logger.info(f"Formatted {len(dhis_data)} fields for DHIS2")
        return dhis_data
    
    def _run_dhis_automation(self, temp_file_path: str) -> Dict[str, Any]:
        """Run DHIS automation using the imported DHISSmartAutomation class"""
        
        try:
            # Check required environment variables
            required_env_vars = ['DHIS_USERNAME', 'DHIS_PASSWORD']
            missing_vars = [var for var in required_env_vars if not os.getenv(var)]
            
            if missing_vars:
                raise Exception(f"Missing required environment variables: {', '.join(missing_vars)}")
            
            # Use asyncio to run the automation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(self._run_automation_async(temp_file_path))
                return result
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"DHIS automation execution failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "fields_filled": 0,
                "success_rate": "0%"
            }
    
    async def _run_automation_async(self, temp_file_path: str) -> Dict[str, Any]:
        """Run automation using the exact imported DHISSmartAutomation class"""
        
        try:
            # Create instance of the imported class (uses ALL original logic)
            automation = self.DHISSmartAutomation()
            
            # Load data from temp file
            with open(temp_file_path, 'r') as f:
                health_data = json.load(f)
            
            logger.info("Using DHISSmartAutomation class directly from root dhis_automation.py")
            
            # All methods below are the EXACT ORIGINAL methods from root folder
            
            # Initialize browser using original method
            await automation.initialize()
            
            # Login with original retry logic
            await automation.login(
                url=os.getenv("DHIS_URL", "https://sols1.baosystems.com"),
                username=os.getenv("DHIS_USERNAME"),
                password=os.getenv("DHIS_PASSWORD")
            )
            
            # Navigate to Data Entry (original method)
            await automation.navigate_to_data_entry()
            
            # Load or discover org units using original caching logic
            if not await automation.load_org_unit_cache():
                logger.info("No org unit cache - using original discovery method")
                await automation.discover_organizational_units()
            
            # Navigate using original path navigation
            default_org_path = os.getenv("DHIS_DEFAULT_ORG_PATH", "Solomon Islands,Western,Central Islands Western Province,Ghatere")
            org_unit_path = [unit.strip() for unit in default_org_path.split(",")]
            
            success = await automation.navigate_to_org_unit_by_path(org_unit_path)
            if not success:
                raise Exception("Failed to navigate to organizational unit using original logic")
            
            # Select period using original method
            await automation.select_period()
            
            # Load or discover field mappings using original caching and discovery
            cache_loaded = await automation.load_cached_mappings()
            if not cache_loaded:
                logger.info("No field mappings cache - using original discovery method")
                await automation.discover_field_mappings()
            
            # Use original complete mapping system (98.5% coverage)
            mapped_data = automation.complete_mapping(health_data)
            
            if not mapped_data:
                raise Exception("No data could be mapped using original mapping logic")
            
            logger.info(f"Original mapping system mapped {len(mapped_data)} fields")
            
            # Fill form using original tab-aware filling logic
            results = await automation.fill_form_data(mapped_data)
            
            # Validate using original validation logic
            validation_success = await automation.validate_form_data()
            
            # Calculate results
            successful = sum(1 for success in results.values() if success)
            total_fields = len(results)
            success_rate = (successful / total_fields * 100) if total_fields > 0 else 0
            
            logger.info(f"Original automation completed: {successful}/{total_fields} fields filled")
            
            # Cleanup using original method with proper error handling
            try:
                logger.info("Performing browser cleanup after successful automation")
                await automation.cleanup()
                logger.info("Browser cleanup completed successfully")
            except Exception as cleanup_error:
                logger.warning(f"Browser cleanup failed (this is usually safe to ignore): {cleanup_error}")
            
            return {
                "status": "completed" if validation_success else "completed_with_warnings",
                "fields_filled": successful,
                "total_fields": total_fields,
                "success_rate": f"{success_rate:.1f}%",
                "validation_passed": validation_success,
                "details": {
                    "mapped_fields": len(mapped_data),
                    "org_unit_path": org_unit_path,
                    "period": os.getenv("DHIS_PERIOD", "August 2025"),
                    "processing_method": "original_root_dhis_automation_py"
                }
            }
            
        except Exception as e:
            logger.error(f"Original DHIS automation failed: {e}")
            
            # Ensure cleanup using original cleanup method with better error handling
            try:
                if 'automation' in locals() and hasattr(automation, 'browser') and automation.browser:
                    logger.info("Attempting to cleanup browser resources")
                    await automation.cleanup()
                    logger.info("Browser cleanup completed")
            except Exception as cleanup_error:
                logger.warning(f"Browser cleanup failed (this is usually safe to ignore): {cleanup_error}")
            
            raise Exception(f"Original DHIS automation failed: {str(e)}")
    
    def _cleanup_temp_file(self, temp_file_path: str):
        """Clean up temporary data file"""
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary file: {e}")
    
    def get_automation_status(self) -> Dict[str, Any]:
        """Get status of DHIS automation setup"""
        
        status = {
            "dhis_automation_imported": self.DHISSmartAutomation is not None,
            "root_folder_accessible": self.root_dir.exists(),
            "original_file_exists": (self.root_dir / 'dhis_automation.py').exists(),
            "environment_configured": True,
            "missing_env_vars": [],
            "ready": True
        }
        
        # Check required environment variables
        required_vars = ['DHIS_USERNAME', 'DHIS_PASSWORD', 'DHIS_URL']
        
        for var in required_vars:
            if not os.getenv(var):
                status["missing_env_vars"].append(var)
                status["environment_configured"] = False
        
        status["ready"] = (
            status["dhis_automation_imported"] and 
            status["root_folder_accessible"] and
            status["original_file_exists"] and
            status["environment_configured"]
        )
        
        return status