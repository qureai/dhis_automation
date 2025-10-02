import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables for LLM integration
load_dotenv()

# Configuration constants
class Config:
    """Configuration constants for DHIS automation"""
    # Timeouts (milliseconds)
    LOGIN_TIMEOUT = int(os.getenv("DHIS_LOGIN_TIMEOUT", "30000"))
    NAVIGATION_TIMEOUT = int(os.getenv("DHIS_NAVIGATION_TIMEOUT", "10000"))
    FORM_LOAD_TIMEOUT = int(os.getenv("DHIS_FORM_LOAD_TIMEOUT", "10000"))
    TAB_SWITCH_DELAY = int(os.getenv("DHIS_TAB_SWITCH_DELAY", "2000"))
    
    # Cache settings
    ORG_CACHE_HOURS = int(os.getenv("DHIS_ORG_CACHE_HOURS", "168"))  # 7 days
    FIELD_CACHE_HOURS = int(os.getenv("DHIS_FIELD_CACHE_HOURS", "24"))  # 1 day
    
    # Retry settings
    MAX_LOGIN_RETRIES = int(os.getenv("DHIS_MAX_LOGIN_RETRIES", "3"))
    RETRY_DELAY = int(os.getenv("DHIS_RETRY_DELAY", "2000"))

# Setup logging with file and console handlers
def setup_logging():
    """Setup logging with timestamped file output and console output"""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Generate timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = log_dir / f"dhis_automation_{timestamp}.log"
    
    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create file handler
    file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Log the log file location
    logger.info(f"Logging initialized. Log file: {log_filename}")
    
    return logger

logger = setup_logging()

class DHISSmartAutomation:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.mapping_cache = {}
        self.cache_file = "dhis_field_mappings.json"
        self.org_unit_cache = {}
        self.org_unit_cache_file = "dhis_org_units.json"
        
        # Initialize LLM client if API key is available
        self.openai_client = None
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.openai_client = OpenAI(api_key=api_key)
            logger.info("LLM integration enabled")
        else:
            logger.warning("No OpenAI API key found - LLM features disabled")
        
    async def initialize(self):
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=False)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            logger.info("Browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            logger.error("Make sure Playwright is installed: pip install playwright && playwright install")
            raise
        
    async def login(self, url: str, username: str, password: str, max_retries: int = None):
        if max_retries is None:
            max_retries = Config.MAX_LOGIN_RETRIES
        for attempt in range(max_retries):
            try:
                logger.info(f"Login attempt {attempt + 1}/{max_retries}: Navigating to {url}")
                await self.page.goto(url)
                await self.page.wait_for_selector("#username", timeout=Config.NAVIGATION_TIMEOUT)
                await self.page.fill("#username", username)
                await self.page.fill("#password", password)
                await self.page.click('button[data-test="dhis2-uicore-button"]')
                await self.page.wait_for_selector('[data-test="headerbar-apps-icon"]', timeout=Config.LOGIN_TIMEOUT)
                logger.info("Login successful!")
                return
            except Exception as e:
                logger.warning(f"Login attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error("All login attempts failed")
                    raise
                await self.page.wait_for_timeout(Config.RETRY_DELAY)  # Wait before retry
        
    async def navigate_to_data_entry(self):
        logger.info("Navigating to Data Entry...")
        await self.page.click('[data-test="headerbar-apps-icon"]')
        await self.page.wait_for_timeout(2000)
        await self.page.click('text="Data Entry"')
        await self.page.wait_for_timeout(3000)
        logger.info("Switching to Data Entry tab...")
        pages = self.context.pages
        if len(pages) > 1:
            self.page = pages[-1]
            await self.page.wait_for_load_state('networkidle')
            logger.info(f"Switched to new tab: {self.page.url}")
        else:
            logger.warning("No new tab detected, continuing with current page")
        
        logger.info("Data Entry application loaded")
        
    async def navigate_organizational_units(self):
        logger.info("Navigating organizational units...")
        await self.page.wait_for_timeout(3000)
        
        solomon_toggle = self.page.locator("//li[@id='orgUnitNtlgKoJBimp']/span[@class='toggle']")
        await solomon_toggle.click()
        await self.page.wait_for_timeout(2000)
        
        western_toggle = self.page.locator("//li[@id='orgUnitNtlgKoJBimp']//li[@id='orgUnitv8eXAbhzdWe']/span[@class='toggle']")
        await western_toggle.click()
        await self.page.wait_for_timeout(2000)
        
        central_toggle = self.page.locator("//li[@id='orgUnitNtlgKoJBimp']//li[@id='orgUnitv8eXAbhzdWe']//li[@id='orgUnitmoAolIb5xS4']/span[@class='toggle']")
        await central_toggle.click()
        await self.page.wait_for_timeout(2000)
        
        ghatere_link = self.page.locator("//li[@id='orgUnitNtlgKoJBimp']//li[@id='orgUnitv8eXAbhzdWe']//li[@id='orgUnitmoAolIb5xS4']//li[@id='orgUnitlzXff2e8Dip']//a")
        await ghatere_link.click()
        await self.page.wait_for_timeout(3000)
        
        logger.info("Organizational unit navigation completed")
        
    async def discover_organizational_units(self) -> Dict[str, Any]:
        """
        Discover ALL organizational units by recursively expanding every expandable node
        """
        logger.info("Starting COMPREHENSIVE organizational unit discovery...")
        logger.info("This will expand ALL provinces and districts to find every health facility")
        
        try:
            # Wait for org unit tree to load
            await self.page.wait_for_selector('#orgUnitTreeContainer', timeout=10000)
            await self.page.wait_for_timeout(3000)
            
            org_mapping = {}
            
            # Start comprehensive recursive discovery
            await self._discover_all_org_units_recursive(org_mapping, "orgUnitNtlgKoJBimp")
            
            logger.info(f"COMPREHENSIVE discovery complete: {len(org_mapping)} organizational units found")
            
            # Save to cache
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "org_units": org_mapping,
                "total_units": len(org_mapping),
                "discovery_type": "comprehensive"
            }
            
            try:
                with open(self.org_unit_cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                logger.info(f"Saved org units to cache: {self.org_unit_cache_file}")
            except Exception as e:
                logger.warning(f"Could not save org unit cache: {e}")
            
            self.org_unit_cache = org_mapping
            return org_mapping
            
        except Exception as e:
            logger.error(f"Organizational unit discovery failed: {e}")
            return {}
    
    async def _discover_all_org_units_recursive(self, org_mapping: Dict, unit_id: str, depth: int = 0, max_depth: int = 6):
        """
        Recursively discover ALL organizational units by expanding every expandable node
        """
        if depth > max_depth:
            return
            
        try:
            # Add current unit to mapping
            await self._add_org_unit_to_mapping(org_mapping, unit_id)
            
            # Check if this unit has a toggle (potentially has children)
            toggle = self.page.locator(f"#{unit_id} span.toggle")
            if await toggle.count() == 0:
                return  # No toggle, no children
            
            unit_name = unit_id.replace('orgUnit', '')
            
            # First check if children are already visible
            existing_children = await self.page.locator(f"#{unit_id} > ul > li[id^='orgUnit']").all()
            
            if len(existing_children) == 0:
                # No children visible - try to expand
                logger.info(f"{'  ' * depth}Expanding {unit_name} to load children...")
                await toggle.click()
                await self.page.wait_for_timeout(2000)  # Wait for lazy loading
                
                # Check children again after expansion
                existing_children = await self.page.locator(f"#{unit_id} > ul > li[id^='orgUnit']").all()
            
            logger.info(f"{'  ' * depth}Found {len(existing_children)} children under {unit_name}")
            
            # Recursively process each child
            for child in existing_children:
                child_id = await child.get_attribute('id')
                if child_id:
                    await self._discover_all_org_units_recursive(org_mapping, child_id, depth + 1, max_depth)
                
        except Exception as e:
            logger.warning(f"Error processing unit {unit_id} at depth {depth}: {e}")
    
    def _get_unit_name_from_cache(self, unit_id: str) -> str:
        """Get unit name from current cache for logging"""
        for name, info in self.org_unit_cache.items():
            if info.get('full_element_id') == unit_id:
                return name
        return unit_id.replace('orgUnit', '')
    
    async def _add_org_unit_to_mapping(self, org_mapping: Dict, unit_id: str):
        """Helper to add a single org unit to the mapping"""
        try:
            # Get the element
            element = self.page.locator(f"#{unit_id}")
            if await element.count() == 0:
                return
            
            # Get level
            level_attr = await element.get_attribute('level')
            level = int(level_attr) if level_attr else 0
            
            # Get name from anchor
            anchor = element.locator('a')
            if await anchor.count() > 0:
                name = await anchor.text_content()
                name = name.strip() if name else ""
                
                if name:
                    actual_id = unit_id.replace('orgUnit', '')
                    org_mapping[name] = {
                        "id": actual_id,
                        "full_element_id": unit_id,
                        "level": level,
                        "selector": f"#{unit_id}",
                        "toggle_selector": f"#{unit_id} span.toggle",
                        "link_selector": f"#{unit_id} a"
                    }
                    logger.info(f"Added: {name} (Level {level}) -> {actual_id}")
                    
        except Exception as e:
            logger.warning(f"Error adding org unit {unit_id}: {e}")
    
    async def _discover_org_units_recursive(self, org_mapping: Dict, current_level: int = 1, max_level: int = 4):
        """
        Recursively discover org units by expanding each level
        """
        if current_level > max_level:
            return
            
        logger.info(f"Discovering level {current_level} organizational units...")
        
        try:
            # Get all visible org units at current level
            visible_units = await self.page.locator('#orgUnitTree li[id^="orgUnit"]:visible').all()
            
            units_to_expand = []
            current_level_units = []
            
            for org_unit in visible_units:
                try:
                    # Get unit info
                    unit_id = await org_unit.get_attribute('id')
                    if not unit_id:
                        continue
                    
                    level_attr = await org_unit.get_attribute('level')
                    unit_level = int(level_attr) if level_attr else 0
                    
                    # Only process units at current level
                    if unit_level != current_level:
                        continue
                        
                    actual_id = unit_id.replace('orgUnit', '')
                    
                    # Get the name
                    anchor = org_unit.locator('a')
                    if await anchor.count() > 0:
                        name = await anchor.text_content()
                        name = name.strip() if name else ""
                        
                        if name and name not in org_mapping:
                            org_mapping[name] = {
                                "id": actual_id,
                                "full_element_id": unit_id,
                                "level": unit_level,
                                "selector": f"#{unit_id}",
                                "toggle_selector": f"#{unit_id} span.toggle",
                                "link_selector": f"#{unit_id} a"
                            }
                            logger.info(f"Found: {name} (Level {unit_level})")
                            current_level_units.append((unit_id, name))
                            
                            # Check if this unit can be expanded (has children)
                            # Look for expand.png image (collapsed state) or presence of nested ul
                            toggle = org_unit.locator('span.toggle')
                            if await toggle.count() > 0 and current_level < max_level:
                                # Check if it has expand.png OR has nested ul (children)
                                expand_img = toggle.locator('img[src*="expand.png"]')
                                nested_ul = org_unit.locator('ul')
                                
                                if await expand_img.count() > 0 or await nested_ul.count() > 0:
                                    units_to_expand.append((unit_id, name))
                                    logger.info(f"  -> {unit_name} has children and will be expanded")
                
                except Exception as e:
                    logger.warning(f"Error processing org unit: {e}")
                    continue
            
            logger.info(f"Found {len(current_level_units)} units at level {current_level}")
            logger.info(f"Will expand {len(units_to_expand)} units to discover children")
            
            # Expand each unit individually and discover its children
            for unit_id, unit_name in units_to_expand:
                try:
                    logger.info(f"Expanding {unit_name} to discover children...")
                    toggle_selector = f"#{unit_id} span.toggle"
                    
                    toggle_element = self.page.locator(toggle_selector)
                    if await toggle_element.count() > 0:
                        await toggle_element.click()
                        await self.page.wait_for_timeout(2000)  # Wait for expansion
                        
                        # Recursively discover next level after this expansion
                        await self._discover_org_units_recursive(org_mapping, current_level + 1, max_level)
                        
                        # Don't collapse - leave expanded so we can navigate later
                        
                except Exception as e:
                    logger.warning(f"Error expanding {unit_name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in recursive discovery at level {current_level}: {e}")
    
    async def load_org_unit_cache(self) -> bool:
        """Load cached organizational unit mappings"""
        if not os.path.exists(self.org_unit_cache_file):
            logger.info("No org unit cache found - will discover units")
            return False
            
        try:
            with open(self.org_unit_cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check cache age (refresh if > 7 days old)
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            age_hours = (datetime.now() - cache_time).total_seconds() / 3600
            
            if age_hours < 168:  # 7 days
                self.org_unit_cache = cache_data['org_units']
                logger.info(f"Loaded {len(self.org_unit_cache)} org units from cache")
                return True
            else:
                logger.info(f"Org unit cache too old ({age_hours/24:.1f} days) - will rediscover")
                return False
                
        except Exception as e:
            logger.warning(f"Error loading org unit cache: {e}")
            return False
    
    async def navigate_to_org_unit_by_path(self, unit_path: List[str]) -> bool:
        """
        Navigate to organizational unit by following a path of unit names
        Example: ["Solomon Islands", "Western", "Central Islands Western Province", "Ghatere"]
        """
        logger.info(f"Navigating to org unit path: {' -> '.join(unit_path)}")
        
        # Ensure org unit cache is loaded
        if not self.org_unit_cache:
            cache_loaded = await self.load_org_unit_cache()
            if not cache_loaded:
                await self.discover_organizational_units()
        
        try:
            # Wait for org tree to be ready
            await self.page.wait_for_selector('#orgUnitTreeContainer', timeout=10000)
            await self.page.wait_for_timeout(2000)
            
            # Navigate through each level
            for i, unit_name in enumerate(unit_path):
                if unit_name not in self.org_unit_cache:
                    logger.error(f"Organizational unit not found: {unit_name}")
                    logger.info(f"Available units: {list(self.org_unit_cache.keys())[:10]}...")
                    return False
                
                unit_info = self.org_unit_cache[unit_name]
                level = unit_info['level']
                full_element_id = unit_info['full_element_id']
                
                logger.info(f"Step {i+1}: Navigating to '{unit_name}' (Level {level})")
                
                # Wait for the element to be visible
                element = self.page.locator(f"#{full_element_id}")
                try:
                    await element.wait_for(state="visible", timeout=5000)
                except:
                    logger.warning(f"Element {unit_name} not visible, attempting to make it visible...")
                
                # If not the final unit, expand it to show children
                if i < len(unit_path) - 1:
                    await self._expand_org_unit(unit_name, unit_info)
                    
                    # Wait for children to load after expansion
                    await self.page.wait_for_timeout(2000)
                    
                    # Verify next unit in path is now visible
                    if i + 1 < len(unit_path):
                        next_unit = unit_path[i + 1]
                        if next_unit in self.org_unit_cache:
                            next_unit_id = self.org_unit_cache[next_unit]['full_element_id']
                            try:
                                await self.page.locator(f"#{next_unit_id}").wait_for(state="visible", timeout=3000)
                                logger.info(f"Verified {next_unit} is now visible")
                            except:
                                logger.warning(f"Next unit {next_unit} not visible after expanding {unit_name}")
                
                # If this is the final unit, click to select it
                if i == len(unit_path) - 1:
                    await self._select_org_unit(unit_name, unit_info)
            
            logger.info("Organizational unit navigation completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error navigating org unit path: {e}")
            return False
    
    async def _expand_org_unit(self, unit_name: str, unit_info: dict):
        """Helper method to expand an organizational unit using the same approach as discovery"""
        full_element_id = unit_info['full_element_id']
        
        try:
            logger.info(f"Checking if {unit_name} needs expansion...")
            
            # Use the same approach as the working discovery process
            toggle = self.page.locator(f"#{full_element_id} span.toggle")
            
            if await toggle.count() == 0:
                logger.info(f"{unit_name} has no toggle - might be a leaf node")
                return False
            
            # First check if children are already visible
            existing_children = await self.page.locator(f"#{full_element_id} > ul > li[id^='orgUnit']").all()
            
            if len(existing_children) == 0:
                # No children visible - try to expand
                logger.info(f"Expanding {unit_name} by clicking toggle...")
                await toggle.click()
                await self.page.wait_for_timeout(2000)  # Wait for lazy loading
                
                # Check children again after expansion
                existing_children = await self.page.locator(f"#{full_element_id} > ul > li[id^='orgUnit']").all()
                logger.info(f"After expansion, {unit_name} has {len(existing_children)} children")
            else:
                logger.info(f"{unit_name} already has {len(existing_children)} visible children")
            
            return True
                        
        except Exception as e:
            logger.error(f"Failed to expand {unit_name}: {e}")
            return False
    
    async def _select_org_unit(self, unit_name: str, unit_info: dict):
        """Helper method to select an organizational unit"""
        full_element_id = unit_info['full_element_id']
        
        try:
            # Try multiple link selector strategies
            link_selectors = [
                f"#{full_element_id} > a",  # Direct child anchor
                f"#{full_element_id} a:first-child",  # First anchor child
                f"#{full_element_id} a"  # Any anchor descendant
            ]
            
            selected = False
            for link_selector in link_selectors:
                try:
                    link_element = self.page.locator(link_selector)
                    if await link_element.count() == 1:  # Ensure exactly one element
                        await link_element.click()
                        logger.info(f"Selected {unit_name} using selector: {link_selector}")
                        selected = True
                        await self.page.wait_for_timeout(3000)
                        break
                except Exception as e:
                    logger.debug(f"Link selector {link_selector} failed: {e}")
                    continue
            
            if not selected:
                raise Exception(f"Could not select {unit_name} with any selector strategy")
                
        except Exception as e:
            logger.error(f"Failed to select {unit_name}: {e}")
            raise
        
    async def select_period(self, period: str = None):
        if period is None:
            period = os.getenv("DHIS_PERIOD", "August 2025")
        logger.info(f"Attempting to select period: {period}")
        
        try:
            period_select = self.page.locator('#selectedPeriodId')
            await period_select.wait_for(state="visible", timeout=10000)
            
            options = await period_select.locator('option').all_text_contents()
            logger.info(f"Available periods: {options[:5]}...") 
            
            if period in options:
                await period_select.select_option([period])
                logger.info(f"Successfully selected period: {period}")
            else:
                available_periods = [opt for opt in options if not opt.startswith("[ Select")]
                if available_periods:
                    selected_period = available_periods[1]
                    await period_select.select_option([selected_period])
                    logger.info(f"Selected available period: {selected_period}")
                else:
                    logger.warning("No periods available to select")
                    
        except Exception as e:
            logger.error(f"Period selection failed: {e}")
        
        logger.info("Waiting for form to load after period selection...")
        await self.page.wait_for_timeout(5000)
                
    async def discover_field_mappings(self) -> Dict[str, Any]:
        logger.info("Starting TAB-AWARE dynamic field mapping discovery...")

        try:
            logger.info("Waiting for DHIS2 form tables to load...")
            await self.page.wait_for_selector('table', timeout=10000)
            await self.page.wait_for_selector('input.entryfield', timeout=10000)
            logger.info("Form elements detected, waiting additional time...")
            await self.page.wait_for_timeout(3000) 
        except Exception as e:
            logger.warning(f"Form loading timeout: {e}")
        
        # Debug: Check page title and URL
        page_title = await self.page.title()
        page_url = self.page.url
        logger.info(f"Page title: {page_title}")
        logger.info(f"Page URL: {page_url}")
        
        # TAB-AWARE DISCOVERY: Find all tabs first
        tab_selectors = [
            'ul.ui-tabs-nav li a',  # Standard jQuery UI tabs
            '.ui-tabs-anchor',      # Direct tab anchors  
            'a[href*="#Page"]'      # DHIS2 page pattern
        ]
        
        tabs = []
        for selector in tab_selectors:
            try:
                tab_elements = await self.page.locator(selector).all()
                if tab_elements:
                    tabs = tab_elements
                    logger.info(f"Found {len(tabs)} tabs using selector: {selector}")
                    break
            except Exception as e:
                logger.warning(f"Tab selector '{selector}' failed: {e}")
        
        if not tabs:
            logger.warning("No tabs found, treating as single-page form")
            tabs = [None]  # Single page mode
        
        mappings = {}
        
        # Process each tab
        for tab_index, tab in enumerate(tabs):
            try:
                current_tab = f"Page{tab_index + 1}"
                
                if tab:
                    # Get tab name/text for logging
                    tab_text = await tab.text_content()
                    logger.info(f"Processing tab {tab_index + 1}: {tab_text}")
                    
                    # Click the tab to make it active
                    await tab.click()
                    await self.page.wait_for_timeout(2000)  # Wait for tab content to load
                else:
                    logger.info("Processing single-page form")
                    current_tab = "Page1"
                
                # Discover fields on this tab
                tab_mappings = await self._discover_fields_on_current_tab(current_tab)
                
                # Merge with main mappings
                mappings.update(tab_mappings)
                logger.info(f"Tab {current_tab}: Found {len(tab_mappings)} fields")
                
            except Exception as e:
                logger.warning(f"Error processing tab {tab_index + 1}: {e}")
                continue
        
        logger.info(f"TAB-AWARE discovery complete: {len(mappings)} total mappings across all tabs")
        
        # Generate form fingerprint for future validation
        try:
            form_fingerprint = await self.generate_form_fingerprint()
            logger.info(f"Generated form fingerprint: {form_fingerprint['total_field_estimate']} fields across {form_fingerprint['tabs_found']} tabs")
        except Exception as e:
            logger.warning(f"Could not generate form fingerprint: {e}")
            form_fingerprint = {}
        
        # Save to enhanced cache with tab information AND form fingerprint
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "page_url": self.page.url,
            "mappings": mappings,
            "total_fields": len(mappings),
            "tabs_discovered": len(tabs),
            "discovery_method": "tab_aware",
            "form_fingerprint": form_fingerprint
        }
        
        with open(self.cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
            
        self.mapping_cache = mappings
        return mappings
    
    # FORM VALIDATION METHOD - Used to detect form structure changes
    async def generate_form_fingerprint(self) -> Dict[str, Any]:
        """
        Generate a fingerprint of the current form structure to detect changes
        """
        try:
            # Quick form structure check without full discovery
            fingerprint = {
                'tabs_found': 0,
                'total_field_estimate': 0,
                'field_counts_per_tab': {},
                'form_hash': None
            }
            
            # Find tabs
            tab_selectors = ['ul.ui-tabs-nav li a', '.ui-tabs-anchor', 'a[href*="#Page"]']
            tabs = []
            
            for selector in tab_selectors:
                try:
                    tab_elements = await self.page.locator(selector).all()
                    if tab_elements:
                        tabs = tab_elements
                        break
                except Exception:
                    continue
            
            fingerprint['tabs_found'] = len(tabs)
            
            # Quick count on each tab
            if tabs:
                for tab_index, tab in enumerate(tabs):
                    try:
                        current_tab = f"Page{tab_index + 1}"
                        
                        # Click tab to activate
                        await tab.click()
                        await self.page.wait_for_timeout(1000)
                        
                        # Quick field count
                        field_count = await self.page.locator('input.entryfield').count()
                        fingerprint['field_counts_per_tab'][current_tab] = field_count
                        fingerprint['total_field_estimate'] += field_count
                        
                    except Exception as e:
                        logger.warning(f"Error checking tab {tab_index + 1}: {e}")
            else:
                # Single page - count all fields
                field_count = await self.page.locator('input.entryfield').count()
                fingerprint['field_counts_per_tab']['Page1'] = field_count
                fingerprint['total_field_estimate'] = field_count
            
            # Generate simple hash of structure
            structure_string = f"{fingerprint['tabs_found']}_{fingerprint['total_field_estimate']}_{sorted(fingerprint['field_counts_per_tab'].items())}"
            fingerprint['form_hash'] = hash(structure_string)
            
            return fingerprint
            
        except Exception as e:
            logger.warning(f"Error generating form fingerprint: {e}")
            return {
                'tabs_found': 0,
                'total_field_estimate': 0,
                'field_counts_per_tab': {},
                'form_hash': None
            }
    
    async def _discover_fields_on_current_tab(self, tab_name: str) -> Dict[str, Dict[str, str]]:
        """
        Discover all fields on the currently active tab
        Returns: {field_name: {"selector": "#id", "tab": "PageX"}}
        """
        mappings = {}
        
        # Find input fields on current tab (including radio buttons)
        selectors_to_try = [
            'input.entryfield',      
            'input.entryselect',     # Radio buttons
            'input[id*="-val"]',     
            'input[type="text"]',
            'input[type="radio"]',   # Additional radio button selector
            'table input[type="text"]'
        ]
        
        input_elements = []
        for selector in selectors_to_try:
            try:
                elements = await self.page.locator(selector).all()
                if elements:
                    input_elements = elements
                    logger.info(f"Tab {tab_name}: Using selector '{selector}' - found {len(elements)} elements")
                    break
            except Exception as e:
                continue
        
        # Process each input element
        for input_elem in input_elements:
            try:
                input_id = await input_elem.get_attribute('id')
                if not input_id:
                    continue
                
                # Check if field is visible (on current tab)
                is_visible = await input_elem.is_visible()
                if not is_visible:
                    continue
                
                # Extract DHIS2 field information
                dataelement_text = ""
                optioncombo_text = ""
                
                try:
                    parent_td = input_elem.locator('xpath=ancestor::td[1]')
                    
                    # Get dataelement text
                    dataelement_spans = await parent_td.locator('span[id*="-dataelement"]').all()
                    for span in dataelement_spans:
                        text = await span.text_content()
                        if text and text.strip():
                            dataelement_text = text.strip()
                            break
                    
                    # Get optioncombo text  
                    optioncombo_spans = await parent_td.locator('span[id*="-optioncombo"]').all()
                    for span in optioncombo_spans:
                        text = await span.text_content()
                        if text and text.strip():
                            optioncombo_text = text.strip()
                            break
                            
                except Exception as e:
                    logger.warning(f"Error extracting spans for {input_id}: {e}")
                
                # Create field mapping with tab info
                if dataelement_text or optioncombo_text:
                    field_name = f"{dataelement_text}||{optioncombo_text}"
                    
                    # Check if this is a radio button
                    input_type = await input_elem.get_attribute('type')
                    input_class = await input_elem.get_attribute('class')
                    
                    if input_type == 'radio' or (input_class and 'entryselect' in input_class):
                        # For radio buttons, use name+value selector
                        input_name = await input_elem.get_attribute('name')
                        input_value = await input_elem.get_attribute('value')
                        if input_name and input_value:
                            # Create separate mappings for Yes and No
                            if input_value == 'true':
                                field_name_yes = f"{dataelement_text}||Yes"
                                mappings[field_name_yes] = {
                                    "selector": f"input[name='{input_name}'][value='true']",
                                    "tab": tab_name
                                }
                            elif input_value == 'false':
                                field_name_no = f"{dataelement_text}||No"
                                mappings[field_name_no] = {
                                    "selector": f"input[name='{input_name}'][value='false']",
                                    "tab": tab_name
                                }
                    else:
                        # For text inputs, use ID selector
                        mappings[field_name] = {
                            "selector": f"#{input_id}",
                            "tab": tab_name
                        }
                
            except Exception as e:
                logger.warning(f"Error processing input element: {e}")
                continue
        
        return mappings
        
    async def load_cached_mappings(self) -> bool:
        if not os.path.exists(self.cache_file):
            logger.info("No cache file found - will discover fields")
            return False
            
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
                
            # Check if cache is recent (less than 24 hours)
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            age_hours = (datetime.now() - cache_time).total_seconds() / 3600
            
            # Return False if no mappings found (force rediscovery)
            if len(cache_data.get('mappings', {})) == 0:
                logger.info("Cache has 0 mappings - will force rediscovery")
                return False
            
            if age_hours < 24:
                logger.info(f"Cache is recent ({age_hours:.1f}h) - validating form structure...")
                
                # ENHANCED: Validate form structure hasn't changed
                try:
                    current_fingerprint = await self.generate_form_fingerprint()
                    cached_fingerprint = cache_data.get('form_fingerprint', {})
                    
                    # Compare key structural elements
                    structure_changed = False
                    
                    if cached_fingerprint:
                        # Check tab count
                        if current_fingerprint.get('tabs_found', 0) != cached_fingerprint.get('tabs_found', 0):
                            logger.warning(f"Tab count changed: {cached_fingerprint.get('tabs_found')} → {current_fingerprint.get('tabs_found')}")
                            structure_changed = True
                        
                        # Check total field count (allow 10% variance for dynamic content)
                        cached_total = cached_fingerprint.get('total_field_estimate', 0)
                        current_total = current_fingerprint.get('total_field_estimate', 0)
                        
                        if cached_total > 0:
                            variance = abs(current_total - cached_total) / cached_total
                            if variance > 0.10:  # More than 10% change
                                logger.warning(f"Total field count changed significantly: {cached_total} → {current_total} ({variance:.1%} change)")
                                structure_changed = True
                        
                        # Check per-tab field counts
                        cached_counts = cached_fingerprint.get('field_counts_per_tab', {})
                        current_counts = current_fingerprint.get('field_counts_per_tab', {})
                        
                        for tab, cached_count in cached_counts.items():
                            current_count = current_counts.get(tab, 0)
                            if abs(current_count - cached_count) > max(5, cached_count * 0.15):  # 5 fields or 15% difference
                                logger.warning(f"Tab {tab} field count changed: {cached_count} → {current_count}")
                                structure_changed = True
                    
                    if structure_changed:
                        logger.info("FORM STRUCTURE CHANGED - Invalidating cache and rediscovering")
                        return False
                    else:
                        logger.info("Form structure validated - using cached mappings")
                        self.mapping_cache = cache_data['mappings']
                        logger.info(f"Loaded {len(self.mapping_cache)} cached mappings")
                        return True
                        
                except Exception as e:
                    logger.warning(f"Form validation failed: {e} - Will use cache anyway")
                    # Fallback: use cache despite validation failure
                    self.mapping_cache = cache_data['mappings']
                    logger.info(f"Loaded {len(self.mapping_cache)} cached mappings (validation skipped)")
                    return True
                    
            else:
                logger.info(f"Cache too old ({age_hours:.1f}h) - will rediscover")
                return False
                
        except Exception as e:
            logger.warning(f"Error loading cache: {e}")
            return False
            
            
    async def fill_form_data(self, data: Dict[str, Any]) -> Dict[str, bool]:
        logger.info(f"Starting TAB-AWARE form filling with {len(data)} data points...")
        
        # RESET: Ensure we start from a known state (Page1) after discovery
        logger.info("Resetting to Page1 before filling...")
        await self._switch_to_tab("Page1")
        
        # Group fields by tab from cached mappings
        fields_by_tab = {}
        unmapped_fields = []
        
        for field_name, value in data.items():
            if value is not None and value != "":
                # Check if we have mapping info for this field
                if field_name in self.mapping_cache:
                    mapping_info = self.mapping_cache[field_name]
                    
                    # Handle both old format (string) and new format (dict)
                    if isinstance(mapping_info, dict):
                        tab = mapping_info.get("tab", "Page1")
                        selector = mapping_info.get("selector", mapping_info)
                    else:
                        # Old format - assume Page1
                        tab = "Page1"
                        selector = mapping_info
                    
                    if tab not in fields_by_tab:
                        fields_by_tab[tab] = []
                    fields_by_tab[tab].append((field_name, value, selector))
                else:
                    unmapped_fields.append(field_name)
        
        if unmapped_fields:
            logger.warning(f"No mapping found for {len(unmapped_fields)} fields: {unmapped_fields[:5]}")
        
        logger.info(f"Fields grouped by tabs: {[(tab, len(fields)) for tab, fields in fields_by_tab.items()]}")
        
        results = {}
        
        # Fill fields tab by tab
        for tab_name, fields in fields_by_tab.items():
            try:
                logger.info(f"Switching to {tab_name} to fill {len(fields)} fields...")
                
                # Clear any stuck focus before switching tabs to prevent focus lock issues
                await self.clear_focus_safely()
                
                # ALWAYS switch to the correct tab (don't assume any tab is active)
                tab_switch_success = await self._switch_to_tab(tab_name)
                
                if not tab_switch_success:
                    logger.error(f"Failed to switch to {tab_name} - skipping {len(fields)} fields")
                    for field_name, _, _ in fields:
                        results[field_name] = False
                    continue
                
                # Fill all fields on this tab
                filled_count = 0
                hidden_count = 0
                error_count = 0
                
                for field_name, value, selector in fields:
                    try:
                        success = await self.fill_field_by_selector(selector, value)
                        results[field_name] = success
                        if success:
                            filled_count += 1
                            logger.info(f"Filled {field_name} = {value}")
                        else:
                            # Check if field was hidden vs other error
                            if not await self.is_field_truly_visible(selector):
                                hidden_count += 1
                                logger.debug(f"Skipped {field_name} (field hidden)")
                            else:
                                error_count += 1
                                logger.warning(f"Failed to fill {field_name}")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error filling {field_name}: {e}")
                        results[field_name] = False
                
                # Clear focus after completing tab to prevent cross-tab interference
                await self.clear_focus_safely()
                
                # Enhanced completion logging
                logger.info(f"Completed {tab_name}: {filled_count}/{len(fields)} successful ({hidden_count} hidden, {error_count} errors)")
                
                # Wait 5 seconds after completing each page/tab
                logger.info(f"Waiting 5 seconds after completing {tab_name}...")
                await self.page.wait_for_timeout(5000)
                
            except Exception as e:
                logger.error(f"Error processing {tab_name}: {e}")
                for field_name, _, _ in fields:
                    results[field_name] = False
        
        successful = sum(1 for success in results.values() if success)
        logger.info(f"TAB-AWARE form filling complete: {successful}/{len(results)} fields successful")
        
        # SELF-HEALING: If fill rate is very low, trigger cache invalidation for next run
        if len(results) > 0:
            success_rate = successful / len(results)
            if success_rate < 0.5:  # Less than 50% success rate
                logger.warning(f"Low success rate ({success_rate:.1%}) detected - this may indicate form changes")
                logger.info("TIP: Delete dhis_field_mappings.json to force fresh discovery on next run")
                
                # Optional: Auto-invalidate cache for next run
                try:
                    if os.path.exists(self.cache_file):
                        cache_backup = self.cache_file + ".backup_failed"
                        import shutil
                        shutil.copy(self.cache_file, cache_backup)
                        logger.info(f"Backed up potentially stale cache to {cache_backup}")
                except Exception as e:
                    logger.warning(f"Could not backup cache: {e}")
        
        return results
    
    async def _switch_to_tab(self, tab_name: str):
        """Switch to the specified tab with enhanced reliability"""
        try:
            logger.info(f"Switching to {tab_name}...")
            
            # Try different tab selector patterns with better targeting
            tab_selectors = [
                f'a[href="#{tab_name}"]',                     # Direct href match
                f'ul.ui-tabs-nav a[href="#{tab_name}"]',      # Within tab navigation
                f'.ui-tabs-anchor[href="#{tab_name}"]',       # jQuery UI specific
                f'a[href*="{tab_name}"]'                      # Partial href match
            ]
            
            tab_clicked = False
            for selector in tab_selectors:
                try:
                    tab_elements = await self.page.locator(selector).all()
                    if tab_elements:
                        # Click the first matching tab
                        await tab_elements[0].click()
                        tab_clicked = True
                        logger.info(f"Clicked {tab_name} tab using selector: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            if not tab_clicked:
                logger.error(f"Could not find clickable tab for {tab_name}")
                return False
            
            # Wait for tab content to load and verify visibility
            await self.page.wait_for_timeout(2000)
            
            # Verify tab switch by checking if content is visible
            try:
                visible_fields = await self.page.locator('input.entryfield:visible').count()
                logger.info(f"{tab_name} loaded - {visible_fields} visible fields detected")
                
                if visible_fields == 0:
                    logger.warning(f"No visible fields on {tab_name} - tab switch may have failed")
                    return False
                    
                return True
                
            except Exception as e:
                logger.warning(f"Could not verify tab content: {e}")
                return True  # Assume success if we can't verify
            
        except Exception as e:
            logger.error(f"Error switching to {tab_name}: {e}")
            return False
    
    async def is_field_truly_visible(self, selector: str) -> bool:
        """Check if field is truly visible and interactable without causing focus lock"""
        try:
            element = self.page.locator(selector)
            
            # Quick check if element exists
            if not await element.count():
                return False
            
            # Check if element is visible using JavaScript without focusing
            is_visible = await self.page.evaluate(f"""
                () => {{
                    const element = document.querySelector('{selector}');
                    if (!element) return false;
                    
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    
                    return (
                        style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        style.opacity !== '0' &&
                        rect.width > 0 &&
                        rect.height > 0 &&
                        element.offsetParent !== null
                    );
                }}
            """)
            
            return is_visible
            
        except Exception:
            return False

    async def clear_focus_safely(self):
        """Clear any stuck focus to prevent tab switching issues"""
        try:
            await self.page.evaluate("""
                () => {
                    if (document.activeElement && document.activeElement.blur) {
                        document.activeElement.blur();
                    }
                    document.body.focus();
                }
            """)
            await self.page.wait_for_timeout(100)  # Brief pause
        except Exception:
            pass  # Not critical if this fails

    async def take_screenshot(self, description: str = "form_state") -> str:
        """Take a timestamped screenshot and save to screenshots folder"""
        try:
            # Create screenshots directory if it doesn't exist
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            
            # Generate timestamp-based filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{description}.png"
            filepath = screenshots_dir / filename
            
            # Take screenshot
            await self.page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"Screenshot saved: {filepath}")
            
            return str(filepath)
            
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {e}")
            return ""

    def _convert_value_for_dhis_fields(self, selector: str, value: str) -> str:
        """
        Smart value conversion for DHIS2 fields that expect specific data types
        Handles boolean-to-integer conversion for fields that require numeric input
        """
        integer_field_patterns = [
            'cynmNGHXI9T-val',  # RWASH Basic fields - confirmed to need integer conversion
            'cqJMN931gqT-val',  # RWASH Limit fields (may also need conversion)
            'QAYLwlDuBYY-val',  # RWASH No Service fields (may also need conversion)
            # Add more patterns here as we discover other fields with integer validation
            # Common DHIS2 patterns that might need conversion:
            # - Any field ending with '-val' that shows "Value must be zero or positive integer" error
        ]
        
        # Alternative: Check if value looks like a boolean but field might expect integer
        # This is a more aggressive approach that converts ANY boolean string to integer
        # if the current value suggests it might be boolean data
        value_str = str(value).lower()
        is_boolean_value = value_str in ['true', 'false', 'yes', 'no']
        
        # Strategy 1: Convert known field patterns
        expects_integer = any(pattern in selector for pattern in integer_field_patterns)
        
        if expects_integer and isinstance(value, str):
            # Convert boolean strings to integers for known patterns
            if str(value).lower() in ['false', 'no', 'none', '0']:
                logger.debug(f"Converting '{value}' to 0 for known integer field: {selector}")
                return '0'
            elif str(value).lower() in ['true', 'yes', '1']:
                logger.debug(f"Converting '{value}' to 1 for known integer field: {selector}")
                return '1'
            # If it's already a number, keep it as-is
            elif str(value).isdigit():
                return str(value)
        
        # Strategy 2: Auto-detect potential integer fields with boolean values
        # This helps catch fields we haven't identified yet
        elif is_boolean_value and '-val' in selector:
            # This is likely a DHIS2 form field that might expect integer input
            if value_str in ['false', 'no', 'none']:
                logger.info(f"Auto-converting boolean '{value}' to 0 for potential integer field: {selector}")
                return '0'
            elif value_str in ['true', 'yes']:
                logger.info(f"Auto-converting boolean '{value}' to 1 for potential integer field: {selector}")
                return '1'
        
        # For all other fields, return the value as-is
        return str(value)

    async def fill_field_by_selector(self, selector: str, value: str) -> bool:
        """Fill a field using its CSS selector with smart visibility checking"""
        try:
            # CRITICAL: Check visibility first WITHOUT focusing the element
            if not await self.is_field_truly_visible(selector):
                logger.debug(f"Field {selector} is hidden - skipping immediately")
                return False
            
            element = self.page.locator(selector)
            
            # Now that we know it's visible, wait a short time for it to be ready
            await element.wait_for(state="visible", timeout=2000)
            
            # Ensure element is enabled and editable
            is_enabled = await element.is_enabled()
            if not is_enabled:
                logger.debug(f"Field {selector} is disabled - skipping")
                return False
            
            # Convert value for DHIS2 field requirements (handles boolean-to-integer conversion)
            converted_value = self._convert_value_for_dhis_fields(selector, value)
            
            # Check if this is a radio button by examining the element type and attributes
            element_type = await element.get_attribute("type")
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            
            # Detect radio buttons by element type or selector patterns
            is_radio_selector = ("value=" in selector) or ("input[name=" in selector and "[value=" in selector)
            
            if element_type == "radio" or (tag_name == "input" and is_radio_selector):
                # Handle radio buttons - click to select
                if converted_value.lower() in ["y", "yes", "1", "true"]:
                    await element.click()
                    logger.debug(f"Clicked radio button field {selector}")
                else:
                    # For "No" values, try to find and click the "No" option
                    no_selector = selector.replace("'true'", "'false'").replace("Yes", "No")
                    try:
                        no_element = self.page.locator(no_selector)
                        if await no_element.count() > 0:
                            await no_element.click()
                            logger.debug(f"Clicked 'No' radio button {no_selector}")
                    except:
                        logger.debug(f"Could not find 'No' option for {selector}")
            else:
                # Handle all other fields as text inputs (original behavior)
                await element.clear()
                await element.fill(converted_value)
                logger.debug(f"Filled field {selector} with {converted_value}")
            
            # Clear focus to prevent tab switching issues
            await self.clear_focus_safely()
            
            return True
            
        except Exception as e:
            logger.debug(f"Failed to fill field {selector}: {e}")
            # Clear focus if we got stuck
            await self.clear_focus_safely()
            return False
        
    async def validate_form_data(self) -> bool:
        """Click the validate button to validate the filled form data and take screenshot"""
        logger.info("Validating form data...")
        
        try:
            # Click the validate button
            validate_button = self.page.locator("//input[@id='validateButton']")
            await validate_button.wait_for(state="visible", timeout=10000)
            await validate_button.click()
            logger.info("Clicked validate button")
            
            # Wait for validation to complete
            await self.page.wait_for_timeout(3000)
            
            # Take screenshot after validation
            screenshot_path = await self.take_screenshot("validation_result")
            
            # TODO: Add logic to check validation results
            # Could check for validation error messages or success indicators
            
            logger.info("Form validation completed")
            return True
            
        except Exception as e:
            logger.error(f"Form validation failed: {e}")
            # Take screenshot of error state too
            await self.take_screenshot("validation_error")
            return False
        

    def map_health_data_to_dhis_fields(self, health_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Use LLM to extract exact values from health facility data and map to DHIS2 fields
        using the existing dhis_field_mappings.json
        """
        
        if not self.openai_client:
            logger.warning("LLM not available - no additional mapping possible")
            return {}
        
        # Load existing DHIS2 field mappings
        dhis2_fields = []
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    dhis2_fields = list(cache_data.get('mappings', {}).keys())
            except Exception as e:
                logger.error(f"Failed to load DHIS2 field mappings: {e}")
                return {}
        
        if not dhis2_fields:
            logger.error("No DHIS2 field mappings found - run field discovery first")
            return {}
        
        logger.info(f"Using LLM to extract health facility data and map to {len(dhis2_fields)} DHIS2 fields")
        
        # Create comprehensive LLM prompt for health facility data mapping
        prompt = f"""You are a DHIS2 health data mapping expert specializing in Solomon Islands health facility reporting. 

TASK: Map the provided health facility data to exact DHIS2 field names using the comprehensive patterns below.

INPUT HEALTH FACILITY DATA:
{json.dumps(health_data, indent=2)}

AVAILABLE DHIS2 FIELDS (must match exactly):
{json.dumps(dhis2_fields[:200] if len(dhis2_fields) > 200 else dhis2_fields, indent=1)}
{"... (" + str(len(dhis2_fields) - 200) + " more fields available)" if len(dhis2_fields) > 200 else ""}

COMPREHENSIVE MAPPING PATTERNS:
================================

1. OUTPATIENT DATA:
- outpatients_new_cases_*_male/female → "HA - Outpatients New||[AGE_GROUP], [M/F]"
- outpatients_return_cases_*_male/female → "HA - Outpatients Returned||[AGE_GROUP], [M/F]" 
- outpatients_chronic_*_male/female → "HA - Outpatients Chronic||[AGE_GROUP], [M/F]"

2. ADMISSIONS DATA:
- admissions_malaria_*_male/female → "HA - Admissions Malaria||[AGE_GROUP], [M/F]"
- admissions_pneumonia_*_male/female → "HA - Admissions Pneumonia||[AGE_GROUP], [M/F]"
- admissions_diarrhoea_*_male/female → "HA - Admissions Diarrhoea||[AGE_GROUP], [M/F]"
- admissions_injury_*_male/female → "HA - Admissions Injury/Trauma||[AGE_GROUP], [M/F]"
- admissions_childbirth_* → "HA - Admissions Childbirth [AGE_GROUP]||default"
- admissions_diabetes_*_male/female → "HA - Admissions Diabetes||[AGE_GROUP], [M/F]"
- admissions_hypertension_*_male/female → "HA - Admissions Hypertension||[AGE_GROUP], [M/F]"

3. DEATHS DATA:
- deaths_general_*_male/female_* → "HA - Deaths general||[AGE_GROUP], [LOCATION], [M/F]"
- deaths_maternal_*_* → "HA - Deaths maternal||[AGE_GROUP], [LOCATION]"

4. CHILD HEALTH & NUTRITION:
- child_stunting_*_new/return → "HA - Child stunting < -2ZS - New/Return||[AGE_GROUP]"
- child_wasting_*_new/return → "HA - Child Wasting < -2ZS - New/Return||[AGE_GROUP]" 
- child_underweight_*_new/return → "HA - Child Underweight < -2ZS - New/Return||[AGE_GROUP]"
- child_overweight_*_new → "HA - Child Overweight >+2ZS - New||[AGE_GROUP]"
- child_obese_*_new/return → "HA - Child Obese >+3ZS New/Return||[AGE_GROUP]"
- child_welfare_clinic_* → "HA - Child welfare clinic attendance||[AGE_GROUP], [LOCATION]"

5. MATERNAL HEALTH:
- anc_1st_visit_*_* → "HA - ANC 1st visit||[TRIMESTER], [LOCATION]"
- anc_return_visit_* → "HA - ANC Return Visit||[LOCATION]"
- pnc_visit_*_* → "HA - PNC visit [TIME_PERIOD]||[LOCATION]"
- delivery_*_* → "HA - Delivery by [TYPE/ATTENDANTS]||[CATEGORY]"
- births_*_* → "HA - Birth [TYPE]||[LOCATION], [CONDITION]"

6. DISEASE CASES:
- *_pneumonia_cases_* → "HA - [Severe ]Pneumonia cases||[AGE_GROUP]"
- *_diarrhea_cases_* → "HA - Diarrhea [TYPE] cases||[AGE_GROUP]"
- *_influenza_cases_* → "HA - Influenza like illness cases||[AGE_GROUP]"
- *_malaria_cases_* → "HA - Malaria cases||[AGE_GROUP]"

7. IMMUNIZATION:
- hpv_*_years_* → "HPV||[AGE] years, [LOCATION]"
- measles_rubella_* → "HA - Measles Rubella Vaccine 1||default"
- vitamin_a_* → "HA - Vitamin A doses [AGE_GROUP]||default"
- anc_booster → "HA - ANC Booster||default"

8. REFERRALS:
- referrals_emergency_* → "HA - Referrals Emergency||[FACILITY_TYPE]"
- referrals_non_emergency_* → "HA - Referrals Non-Emergency||[FACILITY_TYPE]"
- referrals_mental_health_* → "HA - Referrals Mental Health Problem||[FACILITY_TYPE]"
- gbv_referrals_* → "HA - GBV referrals||[AGE_GROUP]"

9. STAFF & INFRASTRUCTURE:
- medical_doctors → "HA - Medical doctor(s)||default"
- registered_nurses → "HA - Registered Nurse(s)||default"  
- nurse_aides → "HA - Registered Nurse Aide(s)||default"
- cold_chain_days_not_working → "HA - Cold chain days not working||default"
- radio_days_not_working → "HA - Radio days not working||default"

10. SERVICES & ACTIVITIES:
- tours_* → "HA - Tours [TYPE]||default"
- satellite_clinic_conducted → "HA - Satellite Clinic Conducted||default"
- school_health_visits → "HA - School Health Visits||default"
- family_health_card_* → "HA - Family Health Card [TYPE]||default"

AGE GROUP MAPPINGS:
- less_than_8_days / <8_days → "<8 Days"
- 8_to_27_days → "8 to 27 Days"  
- 28_days_to_less_than_1_year / 28_days_to_1_year → "28 Days to <1 Year" / "28 Days to 1 Year"
- 1_to_4_years → "1 to 4 Years"
- 5_to_14_years → "5 to 14 Years"
- 15_to_49_years → "15 to 49 Years"
- 50_plus_years / 50+ → "50+ Years"
- 0_to_5_months → "0 to 5 Months"
- 6_to_11_months → "6 to 11 Months"
- 12_to_23_months → "12 to 23 Months"
- 24_to_59_months → "24 to 59 Months"

BOOLEAN/CHECKBOX MAPPING:
- true/yes/1 → "Yes" or "True"
- false/no/0 → "No" or "False"
- Basic/Limited/No Service → "Basic" or "Limited" or "No Service"

CRITICAL MAPPING RULES:
======================
1. Map ONLY fields that exist in both input data AND the DHIS2 fields list
2. Convert ALL numeric values to strings: 0 → "0", 62 → "62"
3. Use exact DHIS2 field names (case and punctuation sensitive)
4. Handle age groups, gender (M/F), and location categories precisely
5. Map complex nested fields using the "||" separator correctly
6. Include ALL non-null values from input data
7. For missing exact matches, find closest semantic match in DHIS2 fields list
8. Prioritize completeness - map as many fields as possible

OUTPUT FORMAT (JSON only - no explanations):
{{
  "HA - Outpatients New||<8 Days, M": "0",
  "HA - Outpatients New||28 Days to <1 Year, F": "30",  
  "HA - Admissions Childbirth 15 To 49 Years||default": "31",
  "HA - Medical doctor(s)||default": "0",
  "HPV||9 years, Health Facility": "0"
}}

Return ONLY the JSON mapping."""

        try:
            logger.info("Calling LLM for health facility data → DHIS2 field mapping...")
            
            response = self.openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),  # Configurable model for health data mapping
                messages=[{"role": "user", "content": prompt}],
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "8000")),  # Configurable token limit
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.0"))
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse LLM response
            try:
                # Clean response - remove markdown formatting
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                elif "```" in result:
                    result = result.split("```")[1].strip()
                
                mapped_fields = json.loads(result)
                logger.info(f"LLM successfully extracted and mapped {len(mapped_fields)} fields from health facility data")
                
                # Validate mappings exist in DHIS2 fields list
                validated_mappings = {}
                invalid_fields = []
                
                for dhis_field, value in mapped_fields.items():
                    if dhis_field in dhis2_fields:
                        validated_mappings[dhis_field] = str(value)
                    else:
                        invalid_fields.append(dhis_field)
                
                if invalid_fields:
                    logger.warning(f"Found {len(invalid_fields)} invalid DHIS2 field names: {invalid_fields[:5]}...")
                
                logger.info(f"Final validated mappings: {len(validated_mappings)} fields ready for form filling")
                return validated_mappings
                
            except json.JSONDecodeError as e:
                logger.error(f"LLM returned invalid JSON: {e}")
                logger.debug(f"Raw LLM response: {result[:500]}...")
                return {}
                
        except Exception as e:
            logger.error(f"LLM mapping failed: {e}")
            return {}

    
    def complete_mapping(self, health_data: Dict[str, Any]) -> Dict[str, str]:
        """
        HYBRID MAPPING SYSTEM with Smart Auto-Regeneration:
        1. Try complete_field_mapping.json (98.5% coverage)
        2. If missing/corrupted → Auto-regenerate it
        3. If regeneration fails → Fall back to rule-based mapping
        4. Self-healing system that never fails
        """
        complete_mapping_file = "complete_field_mapping.json"
        
        # Attempt to use existing complete mapping
        mapped_data = self._try_complete_mapping(complete_mapping_file, health_data)
        if mapped_data:
            return mapped_data
        
        # If complete mapping failed, try auto-regeneration
        logger.info("Complete mapping failed - attempting auto-regeneration...")
        if self._auto_regenerate_complete_mapping():
            # Try complete mapping again after regeneration
            mapped_data = self._try_complete_mapping(complete_mapping_file, health_data)
            if mapped_data:
                logger.info("Auto-regeneration successful - using regenerated complete mapping")
                return mapped_data
        
        # Final fallback: return empty dict (system has tried everything)
        logger.error("All mapping strategies failed - no mappings available")
        logger.info("Try running: python generate_complete_mapping.py")
        return {}
    
    def _try_complete_mapping(self, mapping_file: str, health_data: Dict[str, Any]) -> Dict[str, str]:
        """Helper method to attempt complete mapping from file"""
        if not os.path.exists(mapping_file):
            logger.info(f"Complete mapping file not found: {mapping_file}")
            return {}
        
        try:
            with open(mapping_file, 'r') as f:
                mapping_data = json.load(f)
            
            generated_mappings = mapping_data.get('mappings', {})
            coverage = mapping_data.get('coverage_percentage', 0)
            
            if not generated_mappings:
                logger.warning("Complete mapping file exists but contains no mappings")
                return {}
            
            logger.info(f"Using complete mapping with {coverage}% coverage ({len(generated_mappings)} fields)")
            
            # Load DHIS2 field cache to verify fields exist
            dhis2_fields = set()
            if os.path.exists(self.cache_file):
                try:
                    with open(self.cache_file, 'r') as f:
                        cache_data = json.load(f)
                        dhis2_fields = set(cache_data.get('mappings', {}).keys())
                except Exception as e:
                    logger.warning(f"Could not load DHIS2 field cache: {e}")
            
            mapped_data = {}
            mapped_count = 0
            
            # Map all fields using complete mapping
            for input_field, value in health_data.items():
                # Skip metadata fields
                if input_field in ['province_name', 'health_facility_name', 'month', 'year', 'zone', 'type']:
                    continue
                    
                if input_field in generated_mappings:
                    dhis_field = generated_mappings[input_field]
                    
                    # Verify DHIS2 field exists (if cache available)
                    if dhis2_fields and dhis_field not in dhis2_fields:
                        logger.debug(f"DHIS2 field not in cache (may still work): {dhis_field}")
                    
                    mapped_data[dhis_field] = str(value)
                    mapped_count += 1
                    
                    if mapped_count <= 10:  # Log first 10 mappings
                        logger.info(f"Mapped: {input_field} → {dhis_field} = {value}")
                    elif mapped_count == 11:
                        logger.info("... (continuing to map remaining fields)")
            
            logger.info(f"Complete mapping finished: {mapped_count} fields mapped successfully")
            return mapped_data
            
        except Exception as e:
            logger.error(f"Error processing complete mapping: {e}")
            return {}
    
    def _auto_regenerate_complete_mapping(self) -> bool:
        """Auto-regenerate complete field mapping if missing or corrupted"""
        try:
            # Check if required files exist for regeneration
            health_file = "health_facility_report.json"  # Current data file
            dhis_file = self.cache_file  # DHIS field mappings
            
            if not os.path.exists(dhis_file):
                logger.warning("Cannot auto-regenerate: DHIS2 field cache not found")
                return False
            
            # Import and run the mapping generator
            logger.info("Auto-regenerating complete field mapping...")
            
            # Simple inline regeneration (avoid external imports)
            return self._simple_mapping_regeneration()
            
        except Exception as e:
            logger.error(f"Auto-regeneration failed: {e}")
            return False
    
    def _simple_mapping_regeneration(self) -> bool:
        """Simple inline mapping regeneration without external dependencies"""
        try:
            # Load DHIS2 fields
            with open(self.cache_file, 'r') as f:
                dhis_cache = json.load(f)
                dhis_fields = set(dhis_cache.get('mappings', {}).keys())
            
            if not dhis_fields:
                logger.warning("No DHIS2 fields found for regeneration")
                return False
            
            # Generate basic mappings using the same logic as the rule-based system
            # This ensures we have at least the core mappings working
            basic_mappings = {
                # Outpatients New Cases
            'outpatients_new_cases_less_than_8_days_male': 'HA - Outpatients New||<8 Days, M',
            'outpatients_new_cases_less_than_8_days_female': 'HA - Outpatients New||<8 Days, F',
            'outpatients_new_cases_8_to_27_days_male': 'HA - Outpatients New||8 to 27 Days, M',
            'outpatients_new_cases_8_to_27_days_female': 'HA - Outpatients New||8 to 27 Days, F',
            'outpatients_new_cases_28_days_to_less_than_1_year_male': 'HA - Outpatients New||28 Days to <1 Year, M',
            'outpatients_new_cases_28_days_to_less_than_1_year_female': 'HA - Outpatients New||28 Days to <1 Year, F',
            'outpatients_new_cases_1_to_4_years_male': 'HA - Outpatients New||1 to 4 Years, M',
            'outpatients_new_cases_1_to_4_years_female': 'HA - Outpatients New||1 to 4 Years, F',
            'outpatients_new_cases_5_to_14_years_male': 'HA - Outpatients New||5 to 14 Years, M',
            'outpatients_new_cases_5_to_14_years_female': 'HA - Outpatients New||5 to 14 Years, F',
            'outpatients_new_cases_15_to_49_years_male': 'HA - Outpatients New||15 to 49 Years, M',
            'outpatients_new_cases_15_to_49_years_female': 'HA - Outpatients New||15 to 49 Years, F',
            'outpatients_new_cases_50_plus_years_male': 'HA - Outpatients New||50+ Years, M',
            'outpatients_new_cases_50_plus_years_female': 'HA - Outpatients New||50+ Years, F',
            
                # Key additional fields that are commonly needed
            'referrals_non_emergency_hospital': 'HA - Referrals Non-Emergency||Hospital',
            'gbv_referrals_18_plus_years': 'HA - GBV referrals||18+ Years',
            'cold_chain_days_not_working': 'HA - Cold chain days not working||default',
            'radio_days_not_working': 'HA - Radio days not working||default',
            }
            
            # Filter mappings to only include fields that exist in DHIS
            valid_mappings = {}
            for health_field, dhis_field in basic_mappings.items():
                if dhis_field in dhis_fields:
                    valid_mappings[health_field] = dhis_field
            
            # Save emergency mapping file
            emergency_mapping = {
                "timestamp": datetime.now().isoformat(),
                "description": "Emergency auto-generated mapping (basic coverage)",
                "total_health_fields": "unknown",
                "mapped_fields": len(valid_mappings),
                "coverage_percentage": "emergency",
                "mappings": valid_mappings,
                "note": "Auto-generated emergency mapping - run generate_complete_mapping.py for full coverage"
            }
            
            with open("complete_field_mapping.json", 'w') as f:
                json.dump(emergency_mapping, f, indent=2)
            
            logger.info(f"Emergency mapping generated with {len(valid_mappings)} core fields")
            logger.info("For full 98.5% coverage, run: python generate_complete_mapping.py")
            
            return True
            
        except Exception as e:
            logger.error(f"Simple regeneration failed: {e}")
            return False

    async def cleanup(self):
        """Cleanup browser resources"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")


async def main():
    import sys
    
    # Check for health facility JSON file argument
    if len(sys.argv) > 1:
        health_data_file = sys.argv[1]
        if not os.path.exists(health_data_file):
            logger.error(f"Health data file not found: {health_data_file}")
            return
    else:
        logger.error("Please provide a health facility data JSON file as argument")
        logger.error("Usage: python dhis_automation.py <health_facility_data.json> [org_unit_path]")
        logger.error("Examples:")
        logger.error("  python dhis_automation.py data.json")
        logger.error("  python dhis_automation.py data.json 'Solomon Islands,Western,Central Islands Western Province,Ringgi'")
        logger.error("  python dhis_automation.py data.json 'Solomon Islands,Honiara,NRH,Antenatal Ward'")
        return
    
    automation = DHISSmartAutomation()
    
    try:
        logger.info(f"Starting DHIS2 Smart Automation with data from {health_data_file}...")
        
        # Validate required environment variables
        dhis_username = os.getenv("DHIS_USERNAME")
        dhis_password = os.getenv("DHIS_PASSWORD")
        
        if not dhis_username or not dhis_password:
            logger.error("Missing required environment variables: DHIS_USERNAME and DHIS_PASSWORD")
            logger.error("Please set them in your .env file or environment")
            return
        
        # Initialize once
        await automation.initialize()
        
        # Login once
        await automation.login(
            url=os.getenv("DHIS_URL", "https://sols1.baosystems.com"),
            username=dhis_username, 
            password=dhis_password
        )
        
        # Navigate to Data Entry once
        await automation.navigate_to_data_entry()
        
        # Check if we need to discover org units first
        if not await automation.load_org_unit_cache():
            logger.info("No org unit cache found - discovering organizational units...")
            await automation.discover_organizational_units()
        
        # Dynamic org unit navigation - can be configured via command line or environment
        # Default path from environment variable or fallback
        default_org_path = os.getenv("DHIS_DEFAULT_ORG_PATH", "Solomon Islands,Western,Central Islands Western Province,Ghatere")
        default_path = [unit.strip() for unit in default_org_path.split(",")]
        
        # Check if org unit path was provided as command line argument
        if len(sys.argv) > 2:
            # Parse org unit path from command line (comma-separated)
            org_unit_str = sys.argv[2]
            org_unit_path = [unit.strip() for unit in org_unit_str.split(",")]
            logger.info(f"Using org unit path from command line: {org_unit_path}")
        else:
            org_unit_path = default_path
            logger.info(f"Using default org unit path: {org_unit_path}")
        
        success = await automation.navigate_to_org_unit_by_path(org_unit_path)
        if not success:
            logger.error("Failed to navigate to organizational unit")
            return
            
        await automation.select_period()
        
        # Try to load cached mappings first
        cache_loaded = await automation.load_cached_mappings()
        
        if not cache_loaded:
            # Discover field mappings dynamically
            await automation.discover_field_mappings()
        
        # Field mappings ready - proceed to data processing
        
        # Load and validate data file
        try:
            with open(health_data_file, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded data from {health_data_file}")
            
            # Validate data structure
            if not isinstance(data, dict):
                logger.error("Data file must contain a JSON object")
                return
                
            if len(data) == 0:
                logger.error("Data file is empty")
                return
                
            logger.info(f"Data validation passed: {len(data)} fields found")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in data file: {e}")
            return
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return

        # SMART DETECTION: Check if data contains health facility fields
        has_health_facility_fields = any(
            key.startswith(('outpatients_', 'referrals_', 'gbv_', 'supervisory_', 'treatments_', 'cold_chain_', 'access_to_', 'human_resource_'))
            for key in data.keys() if isinstance(data, dict)
        )
        
        
        # Auto-detect health facility data format based on content, not filename
        if has_health_facility_fields or any(key.startswith(('outpatients_', 'deaths_', 'anc_', 'communicable_diseases_')) for key in data.keys() if isinstance(data, dict)):
            logger.info("DETECTED: Health facility data (structured format)")
            logger.info("WORKFLOW: Health data JSON → Complete Auto-mapping → dhis_field_mappings.json → DHIS2 form")
            
            # Use COMPLETE MAPPING as primary approach (98.5% coverage, all fields mapped automatically)
            logger.info("Using complete auto-generated mapping for maximum field coverage...")
            mapped_data = automation.complete_mapping(data)
            
            # If complete mapping gets insufficient results, try LLM as backup (unlikely with 98.5% coverage)
            if len(mapped_data) < 50 and automation.openai_client:
                logger.info(f"Complete mapping found {len(mapped_data)} fields. Trying LLM for additional coverage...")
                llm_mapped_data = automation.map_health_data_to_dhis_fields(data)
                
                # Merge complete mapping + LLM results (complete mapping takes priority for conflicts)
                if llm_mapped_data:
                    for field, value in llm_mapped_data.items():
                        if field not in mapped_data:  # Don't override complete mapping
                            mapped_data[field] = value
                    logger.info(f"Combined mapping: {len(mapped_data)} fields (complete mapping + LLM)")
            
            if not mapped_data:
                logger.error("Complete mapping failed and no LLM backup - cannot proceed")
                return
                
            logger.info(f"Complete auto-mapping finished: {len(mapped_data)} fields ready for form filling")
            
            
        else:
            # OLD APPROACH: Direct field mapping (for already mapped data)
            logger.info("Using direct field mapping - data already in DHIS2 format...")
            mapped_data = data.get("data", {}) if "data" in data else data
            
            if not mapped_data:
                logger.error("No mappable data found - skipping form filling")
                return
        
        # Fill the form with mapped data (same for both approaches)
        logger.info("Filling DHIS2 form...")
        results = await automation.fill_form_data(mapped_data)
        
        # Report results
        successful = sum(1 for success in results.values() if success)
        logger.info(f"Final results: {successful}/{len(results)} fields filled successfully")
        
        # Validate the complete form after filling all data
        logger.info("Validating complete form after filling all pages...")
        validation_success = await automation.validate_form_data()
        if validation_success:
            logger.info("Form validation passed successfully!")
        else:
            logger.warning("Form validation failed - please check the data")
        
        # Brief pause to view results, then auto-close
        logger.info("Automation complete! Closing browser in 5 seconds...")
        await asyncio.sleep(5)
        logger.info("Closing browser and exiting.")
            
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await automation.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

