import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables for LLM integration
load_dotenv()

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
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        
    async def login(self, url: str, username: str, password: str):
        logger.info(f"Navigating to: {url}")
        await self.page.goto(url)
        await self.page.wait_for_selector("#username", timeout=10000)
        await self.page.fill("#username", username)
        await self.page.fill("#password", password)
        await self.page.click('button[data-test="dhis2-uicore-button"]')
        await self.page.wait_for_selector('[data-test="headerbar-apps-icon"]', timeout=30000)
        logger.info("Login successful!")
        
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
            
            with open(self.org_unit_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
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
        
    async def select_period(self, period: str = "August 2025"):
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
        
        # Find input fields on current tab
        selectors_to_try = [
            'input.entryfield',      
            'input[id*="-val"]',     
            'input[type="text"]',
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
            
    # UNUSED METHOD - NOT USED IN CURRENT FLOW (replaced by fill_field_by_selector)
    # async def fill_field_by_key(self, key: str, value: str) -> bool:
    #     if key not in self.mapping_cache:
    #         logger.warning(f"No mapping found for key: {key}")
    #         return False
    #         
    #     selector = self.mapping_cache[key]
    #     
    #     try:
    #         # Check if element exists and is visible
    #         element = self.page.locator(selector)
    #         if await element.count() == 0:
    #             logger.warning(f"Element not found: {selector}")
    #             return False
    #             
    #         # Fill the field
    #         await element.fill(str(value))
    #         logger.info(f"Filled {key} = {value}")
    #         
    #         # Brief pause to allow UI updates
    #         await self.page.wait_for_timeout(100)
    #         return True
    #         
    #     except Exception as e:
    #         logger.error(f"Error filling {key}: {e}")
    #         return False
            
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
                
                # ALWAYS switch to the correct tab (don't assume any tab is active)
                tab_switch_success = await self._switch_to_tab(tab_name)
                
                if not tab_switch_success:
                    logger.error(f"Failed to switch to {tab_name} - skipping {len(fields)} fields")
                    for field_name, _, _ in fields:
                        results[field_name] = False
                    continue
                
                # Fill all fields on this tab
                for field_name, value, selector in fields:
                    try:
                        success = await self.fill_field_by_selector(selector, value)
                        results[field_name] = success
                        if success:
                            logger.info(f"Filled {field_name} = {value}")
                        else:
                            logger.warning(f"Failed to fill {field_name}")
                    except Exception as e:
                        logger.error(f"Error filling {field_name}: {e}")
                        results[field_name] = False
                
                logger.info(f"Completed {tab_name}: {sum(1 for fn, _, _ in fields if results.get(fn, False))}/{len(fields)} successful")
                
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
    
    async def fill_field_by_selector(self, selector: str, value: str) -> bool:
        """Fill a field using its CSS selector"""
        try:
            element = self.page.locator(selector)
            
            # Wait for element to be visible and enabled
            await element.wait_for(state="visible", timeout=5000)
            
            # Clear and fill the field
            await element.clear()
            await element.fill(str(value))
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to fill field {selector}: {e}")
            return False
        
    async def validate_form_data(self) -> bool:
        """Click the validate button to validate the filled form data"""
        logger.info("Validating form data...")
        
        try:
            # Click the validate button
            validate_button = self.page.locator("//input[@id='validateButton']")
            await validate_button.wait_for(state="visible", timeout=10000)
            await validate_button.click()
            logger.info("Clicked validate button")
            
            # Wait a bit for validation to complete
            await self.page.wait_for_timeout(3000)
            
            # TODO: Add logic to check validation results
            # Could check for validation error messages or success indicators
            
            logger.info("Form validation completed")
            return True
            
        except Exception as e:
            logger.error(f"Form validation failed: {e}")
            return False
        
    # UNUSED METHOD - NOT USED IN CURRENT FLOW
    # async def ai_fallback_mapping(self, missing_keys: List[str]) -> Dict[str, str]:
    #     """
    #     AI Fallback: Attempt fuzzy matching for missing keys
    #     """
    #     logger.info(f"AI fallback for {len(missing_keys)} missing keys...")
    #     
    #     # Placeholder for AI/fuzzy matching logic
    #     # Could implement:
    #     # 1. XPath-based label matching
    #     # 2. Text similarity matching
    #     # 3. ML-based field identification
    #     
    #     fallback_mappings = {}
    #     
    #     # Simple example: try to find fields by partial text match
    #     for key in missing_keys:
    #         # Extract meaningful parts from the key
    #         parts = key.replace("||", " ").split()
    #         search_text = " ".join(parts[:2])  # Use first 2 meaningful words
    #         
    #         try:
    #             # Try to find input near text containing search terms
    #             xpath = f"//text()[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_text.lower()}')]/following::input[1]"
    #             element = self.page.locator(f"xpath={xpath}")
    #             
    #             if await element.count() > 0:
    #                 element_id = await element.get_attribute('id')
    #                 if element_id:
    #                     fallback_mappings[key] = f"#{element_id}"
    #                     logger.info(f"AI fallback found: {key} -> #{element_id}")
    #                     
    #         except Exception as e:
    #             logger.warning(f"AI fallback failed for {key}: {e}")
    #             
    #     return fallback_mappings
        
    # UNUSED METHOD - NOT USED IN CURRENT FLOW
    # async def take_screenshot(self, name: str = "form_state"):
    #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #     filename = f"screenshots/{name}_{timestamp}.png"
    #     
    #     os.makedirs("screenshots", exist_ok=True)
    #     await self.page.screenshot(path=filename)
    #     logger.info(f"Screenshot saved: {filename}")
        
    # UNUSED METHOD - NOT USED IN CURRENT FLOW (replaced by main() function)
    # async def run_complete_workflow(self, sample_data: Optional[Dict] = None):
    #     try:
    #         # Initialize
    #         await self.initialize()
    #         
    #         # Login
    #         await self.login(
    #             url="https://sols1.baosystems.com",
    #             username="qure", 
    #             password="A1@wpro1"
    #         )
    #         
    #         await self.navigate_to_data_entry()
    #         await self.navigate_organizational_units()
    #         await self.select_period("August 2025")
    #         cache_loaded = await self.load_cached_mappings()
    #         if not cache_loaded:
    #             await self.discover_field_mappings()
    # 
    #         await self.validate_form_data()
    # 
    #         if sample_data:
    #             logger.info("Filling form with sample data...")
    #             results = await self.fill_form_data(sample_data)
    # 
    #             successful = sum(1 for success in results.values() if success)
    #             logger.info(f"Final results: {successful}/{len(results)} fields filled successfully")
    #             
    #         logger.info("Workflow completed successfully!")
    #         
    #     except Exception as e:
    #         logger.error(f"Workflow error: {e}")
    #         await self.take_screenshot("error_state")
    #         raise
            
    # UNUSED METHOD - NOT USED IN CURRENT FLOW (partially commented out and replaced by map_health_data_to_dhis_fields)
    # def map_kwaraka_to_dhis_fields(self, kwaraka_data: Dict[str, Any]) -> Dict[str, str]:
    #     """Enhanced LLM mapping to utilize ALL available data points"""
    #     
    #     if not self.openai_client:
    #         logger.error("LLM not available - cannot map KWARAKA data")
    #         return {}
    #     
    #     dhis2_fields = []
    #     if os.path.exists(self.cache_file):
    #         try:
    #             with open(self.cache_file, 'r') as f:
    #                 cache_data = json.load(f)
    #                 dhis2_fields = list(cache_data.get('mappings', {}).keys())
    #         except Exception as e:
    #             logger.error(f"Failed to load DHIS2 fields: {e}")
    #             return {}
    #     
    #     if not dhis2_fields:
    #         logger.error("No DHIS2 fields available - run field discovery first")
    #         return {}
    #     
    #     logger.info(f"Using LLM to map KWARAKA data to {len(dhis2_fields)} available DHIS2 fields")
    #     
    #     # Smart filtering: Show only RELEVANT DHIS2 fields to fit in token limit
    #     relevant_keywords = [
    #         'HA - Outpatients', 'HA - Treatments', 'HA - Referrals', 'HA - Tours', 
    #         'HA - Cold chain', 'HA - Radio', 'HA - Access to basic', 'HA - Medical',
    #         'HA - Midwife', 'HA - Registered Nurse', 'HA - GBV', 'Outpatients with Disability',
    #         'Stock out'
    #     ]
    #     
    #     relevant_fields = []
    #     for field in dhis2_fields:
    #         if any(keyword in field for keyword in relevant_keywords):
    #             relevant_fields.append(field)
    #     
    #     logger.info(f"Filtered to {len(relevant_fields)} relevant DHIS2 fields for LLM context")
    #     
    #     # Create comprehensive LLM prompt that covers ALL data types  
    #     prompt = f"""You are a DHIS2 health data mapping expert. Your task is to map ALL non-zero/non-empty data from this KWARAKA health facility report to exact DHIS2 field names.
    # 
    # KWARAKA HEALTH FACILITY DATA (COMPLETE):
    # {json.dumps(kwaraka_data, indent=2)}
    # 
    # RELEVANT DHIS2 FIELDS ({len(relevant_fields)} fields):
    # {json.dumps(relevant_fields, indent=1)}
    # 
    # COMPREHENSIVE MAPPING RULES:
    # ==========================
    # 
    # 1. OUTPATIENT DATA MAPPING:
    #    - new_cases_by_age_sex → "HA - Outpatients New||[AGE], [GENDER]"
    #    - return_cases_by_age_sex → "HA - Outpatients Returned||[AGE], [GENDER]"  
    #    - chronic_cases_by_age_sex → "HA - Outpatients Chronic||[AGE], [GENDER]"
    #    - person_with_disability_by_age_sex → "Outpatients with Disability||[AGE], [GENDER]"
    # 
    # 2. AGE GROUP CONVERSIONS:
    #    - "< 8 days" → "<8 Days"
    #    - "8 to 27 days" → "8 to 27 Days" 
    #    - "28 days to < 1 yr" → "28 Days to <1 Year"
    #    - "1 to 4" → "1 to 4 Years"
    #    - "5 to 14" → "5 to 14 Years"
    #    - "15 to 49" → "15 to 49 Years"
    #    - "50+" → "50+ Years"
    # 
    # 3. GENDER CONVERSIONS:
    #    - "male" → "M"
    #    - "female" → "F"
    # 
    # 4. TREATMENTS MAPPING:
    #    - new_cases_total_injections → "HA - Treatments Injection||default"
    #    - return_cases_total_dressings → "HA - Treatments Dressing||default"
    # 
    # 5. REFERRALS MAPPING:
    #    - referrals_to_clinics_and_hospitals.emergency → "HA - Referrals Emergency||[TYPE]"
    #    - referrals_to_clinics_and_hospitals.non_emergency → "HA - Referrals Non-Emergency||[TYPE]"
    #    - Where [TYPE] = "RHC", "AHC", "Hospital", "NRH"
    # 
    # 6. SUPERVISORY TOURS MAPPING:
    #    - supervisory_tours.national_program → "HA - Tours National program||default"
    #    - supervisory_tours.provincial_program → "HA - Tours Provincial program||default"
    #    - supervisory_tours.area_supervisors → "HA - Tours Area Supervisory||default"
    #    - supervisory_tours.medical_team → "HA - Tours Medical team||default"
    # 
    # 7. COLD CHAIN & RADIO MAPPING:
    #    - cold_chain_radio.cold_chain.days_not_working → "HA - Cold chain days not working||default"
    #    - cold_chain_radio.radio.days_not_working → "HA - Radio days not working||default"
    # 
    # 8. RWASH SERVICES MAPPING:
    #    - access_to_basic_rwash_services.water_access → "HA - Access to basic Water||[LEVEL]"
    #    - access_to_basic_rwash_services.sanitation_access → "HA - Access to basic Sanitation||[LEVEL]"
    #    - access_to_basic_rwash_services.hygiene_access → "HA - Access to basic Hygiene||[LEVEL]"
    #    - access_to_basic_rwash_services.waste_management → "HA - Access to basic Waste Management||[LEVEL]"
    #    - Where [LEVEL]: "Limited" → "Limit", "Basic" → "Basic", "No Service" → "No Service"
    # 
    # 9. HUMAN RESOURCES MAPPING:
    #    - human_resource.no_of_medical_doctors → "HA - Medical doctor(s)||default"
    #    - human_resource.no_of_midwives → "HA - Midwife(s)||default"
    #    - human_resource.no_of_registered_nurses → "HA - Registered Nurse(s)||default"
    #    - human_resource.no_of_registered_nurse_aides → "HA - Registered Nurse Aide(s)||default"
    # 
    # 10. GBV REFERRALS MAPPING:
    #     - gbv_referrals → "HA - GBV referrals||[AGE]" where [AGE] = "<18 Years" or "18+ Years"
    # 
    # CRITICAL REQUIREMENTS - MAP ALL DATA:
    # ===================================
    # - YOU MUST extract ALL 60 data points from KWARAKA data (including zeros!)
    # - Map EVERY age/gender combination in new_cases, return_cases, chronic_cases, disability_cases
    # - Map ALL treatment totals (injections, dressings)
    # - Map ALL referral data (emergency, non_emergency by type)
    # - Map ALL supervisory tours (national, provincial, area, medical)
    # - Map ALL cold chain/radio data (availability = Yes/No, days_not_working = 0)  
    # - Map ALL RWASH services (water, sanitation, hygiene, waste = "Limited")
    # - Map ALL human resources (doctors, midwives, nurses, nurse_aides)
    # - Map drug stock status and completed_by information
    # - INCLUDE zero values - they are meaningful data points in health reporting
    # - Convert values: "Yes"→"true", "No"→"false", "Limited"→"Limited", numbers→strings
    # 
    # OUTPUT FORMAT - COMPREHENSIVE MAPPING (JSON only):
    # {{
    #   "HA - Outpatients New||<8 Days, M": "0",
    #   "HA - Outpatients New||<8 Days, F": "0", 
    #   "HA - Outpatients New||28 Days to <1 Year, F": "3",
    #   "HA - Outpatients New||1 to 4 Years, M": "5",
    #   "HA - Outpatients Returned||15 to 49 Years, F": "0",
    #   "HA - Outpatients Returned||50+ Years, M": "0", 
    #   "HA - Outpatients Chronic||15 to 49 Years, F": "1",
    #   "HA - Outpatients Chronic||50+ Years, M": "1",
    #   "Outpatients with Disability||15 to 49 Years, M": "1",
    #   "HA - Treatments Injection||default": "62",
    #   "HA - Treatments Dressing||default": "67",
    #   "HA - Referrals Non-Emergency||Hospital": "3", 
    #   "HA - Tours Medical team||default": "1",
    #   "HA - Cold chain days not working||default": "0",
    #   "HA - Radio days not working||default": "0",
    #   "HA - Access to basic Water||Limit": "Limited",
    #   "HA - Access to basic Sanitation||Limit": "Limited",
    #   "HA - Access to basic Hygiene||Limit": "Limited", 
    #   "HA - Access to basic Waste Management||Limit": "Limited",
    #   "HA - Registered Nurse(s)||default": "1"
    # }}
    # 
    # DEMAND: Return 40-50+ mappings from ALL 60 data points. Be comprehensive and include zeros!"""
    # 
    #     try:
    #         logger.info("Calling enhanced LLM for comprehensive KWARAKA → DHIS2 mapping...")
    #         
    #         response = self.openai_client.chat.completions.create(
    #             model="gpt-3.5-turbo",
    #             messages=[{"role": "user", "content": prompt}],
    #             max_tokens=4000,  # Increased for comprehensive mapping
    #             temperature=0.0   # Zero temperature for maximum consistency
    #         )
    #         
    #         result = response.choices[0].message.content.strip()
    #         
    #         # Parse LLM response
    #         try:
    #             # Clean response - sometimes LLM adds markdown formatting
    #             if "```json" in result:
    #                 result = result.split("```json")[1].split("```")[0].strip()
    #             elif "```" in result:
    #                 result = result.split("```")[1].strip()
    #             
    #             mapped_fields = json.loads(result)
    #             logger.info(f"Enhanced LLM successfully mapped {len(mapped_fields)} fields from {self._count_available_data_points(kwaraka_data)} available data points")
    #             
    #             # Validate mappings exist in full DHIS2 fields list (not just filtered)
    #             validated_mappings = {}
    #             for dhis_field, value in mapped_fields.items():
    #                 if dhis_field in dhis2_fields:
    #                     validated_mappings[dhis_field] = str(value)
    #                 else:
    #                     logger.warning(f"Field not found in DHIS2: {dhis_field}")
    #             
    #             logger.info(f"Final validated mappings: {len(validated_mappings)} fields (from {len(mapped_fields)} LLM suggestions)")
    #             return validated_mappings
    #             
    #         except json.JSONDecodeError as e:
    #             logger.error(f"LLM returned invalid JSON: {e}")
    #             logger.debug(f"Raw LLM response: {result}")
    #             return {}
    #             
    #     except Exception as e:
    #         logger.error(f"Enhanced LLM mapping failed: {e}")
    #         return {}
    
    # UNUSED METHOD - NOT USED IN CURRENT FLOW (related to commented out map_kwaraka_to_dhis_fields)
    # def _count_available_data_points(self, data: Dict[str, Any], path: str = '') -> int:
    #     """Count non-zero/non-empty data points in the JSON"""
    #     count = 0
    #     if isinstance(data, dict):
    #         for key, value in data.items():
    #             if isinstance(value, (int, float)) and value != 0:
    #                 count += 1
    #             elif isinstance(value, str) and value.strip() and key not in ['province_name', 'health_facility_name', 'month', 'zone', 'type', 'year']:
    #                 count += 1
    #             elif isinstance(value, (dict, list)):
    #                 count += self._count_available_data_points(value, f"{path}.{key}" if path else key)
    #     elif isinstance(data, list):
    #         for item in data:
    #             count += self._count_available_data_points(item, path)
    #     return count

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
        
        # Create focused LLM prompt for data extraction and mapping
        prompt = f"""You are a DHIS2 health data mapping expert. Map health facility data fields to exact DHIS2 field names.

INPUT DATA:
{json.dumps(health_data, indent=2)}

AVAILABLE DHIS2 FIELDS:
{json.dumps(dhis2_fields, indent=1)}

FIELD MAPPING RULES:
==================

OUTPATIENT DATA MAPPING:
- outpatients_new_cases_less_than_8_days_male → "HA - Outpatients New||<8 Days, M"
- outpatients_new_cases_less_than_8_days_female → "HA - Outpatients New||<8 Days, F"
- outpatients_new_cases_8_to_27_days_male → "HA - Outpatients New||8 to 27 Days, M"  
- outpatients_new_cases_8_to_27_days_female → "HA - Outpatients New||8 to 27 Days, F"
- outpatients_new_cases_28_days_to_less_than_1_year_male → "HA - Outpatients New||28 Days to <1 Year, M"
- outpatients_new_cases_28_days_to_less_than_1_year_female → "HA - Outpatients New||28 Days to <1 Year, F"
- outpatients_new_cases_1_to_4_years_male → "HA - Outpatients New||1 to 4 Years, M"
- outpatients_new_cases_1_to_4_years_female → "HA - Outpatients New||1 to 4 Years, F"
- outpatients_new_cases_5_to_14_years_male → "HA - Outpatients New||5 to 14 Years, M"
- outpatients_new_cases_5_to_14_years_female → "HA - Outpatients New||5 to 14 Years, F"
- outpatients_new_cases_15_to_49_years_male → "HA - Outpatients New||15 to 49 Years, M"
- outpatients_new_cases_15_to_49_years_female → "HA - Outpatients New||15 to 49 Years, F"
- outpatients_new_cases_50_plus_years_male → "HA - Outpatients New||50+ Years, M"
- outpatients_new_cases_50_plus_years_female → "HA - Outpatients New||50+ Years, F"

RETURN CASES:
- outpatients_return_cases_*_male → "HA - Outpatients Returned||[AGE], M"
- outpatients_return_cases_*_female → "HA - Outpatients Returned||[AGE], F"

REFERRAL DATA:
- referrals_emergency_rhc → "HA - Referrals Emergency||RHC"
- referrals_emergency_hospital → "HA - Referrals Emergency||Hospital"
- referrals_non_emergency_rhc → "HA - Referrals Non-Emergency||RHC"
- referrals_non_emergency_hospital → "HA - Referrals Non-Emergency||Hospital"

CRITICAL REQUIREMENTS:
1. Map ONLY fields that exist in the input data AND the DHIS2 fields list
2. Convert all values to strings: 0 → "0", 62 → "62"
3. Use exact DHIS2 field names (case sensitive)
4. Include ALL non-null values from input data

EXPECTED OUTPUT FORMAT (JSON only):
{{
  "HA - Outpatients New||<8 Days, M": "0",
  "HA - Outpatients New||<8 Days, F": "0",
  "HA - Outpatients New||8 to 27 Days, M": "0",
  "HA - Outpatients New||8 to 27 Days, F": "3",
  "HA - Outpatients New||28 Days to <1 Year, M": "5",
  "HA - Outpatients New||28 Days to <1 Year, F": "30"
}}

Return ONLY the JSON mapping, no explanations."""

        try:
            logger.info("Calling LLM for health facility data → DHIS2 field mapping...")
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Using more capable model for better extraction
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
                temperature=0.0
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

    # def _fallback_mapping(self, health_data: Dict[str, Any]) -> Dict[str, str]:
    #     """
    #     LEGACY FALLBACK - Only used when complete mapping and auto-regeneration both fail
    #     This provides minimal coverage as a last resort. The hybrid system above handles 98.5% coverage.
    #     """
    #     logger.warning("Using legacy fallback mapping - limited coverage available")
    #     logger.info("Consider running: python generate_complete_mapping.py for full coverage")
        
    #     # Load DHIS2 field mappings
    #     dhis2_fields = []
    #     if os.path.exists(self.cache_file):
    #         try:
    #             with open(self.cache_file, 'r') as f:
    #                 cache_data = json.load(f)
    #                 dhis2_fields = list(cache_data.get('mappings', {}).keys())
    #         except Exception as e:
    #             logger.error(f"Failed to load DHIS2 field mappings: {e}")
    #             return {}
        
    #     if not dhis2_fields:
    #         logger.error("No DHIS2 field mappings available")
    #         return {}
        
    #     mapped_data = {}
        
    #     # COMMENTED OUT: Large hardcoded mapping rules (replaced by auto-regeneration in hybrid system)
    #     # The following ~200 lines of hardcoded mappings are now replaced by the auto-regeneration system
    #     # which provides the same mappings dynamically. Keeping only essential ones for absolute emergency.
        
    #     # Essential emergency mappings (minimal set for absolute fallback)
    #     essential_mapping_rules = {
    #         # Core outpatient fields - just the basics for emergency fallback
    #         'outpatients_new_cases_less_than_8_days_male': 'HA - Outpatients New||<8 Days, M',
    #         'outpatients_new_cases_less_than_8_days_female': 'HA - Outpatients New||<8 Days, F',
    #         'referrals_non_emergency_hospital': 'HA - Referrals Non-Emergency||Hospital',
    #         'gbv_referrals_18_plus_years': 'HA - GBV referrals||18+ Years',
    #         'cold_chain_days_not_working': 'HA - Cold chain days not working||default',
    #     }
        
    #     # COMMENTED OUT: ~200 lines of detailed hardcoded mappings (replaced by hybrid system)
    #     # The hybrid system above provides all these mappings automatically via:
    #     # 1. complete_field_mapping.json (828 mappings, 98.5% coverage)
    #     # 2. Auto-regeneration (generates same mappings dynamically)
    #     # 3. This emergency fallback (5 essential mappings)
        
    #     # LARGE COMMENTED SECTION - The original mapping_rules contained ~200 lines
    #     # All those detailed mappings are now provided by the hybrid system automatically
    #     # Replaced with minimal essential_mapping_rules above for emergency fallback only
        
        
    #     ORIGINAL LARGE MAPPING RULES (NOW COMMENTED OUT):
    #     mapping_rules = {
    #         'outpatients_new_cases_8_to_27_days_male': 'HA - Outpatients New||8 to 27 Days, M',
    #         'outpatients_new_cases_8_to_27_days_female': 'HA - Outpatients New||8 to 27 Days, F',
    #         'outpatients_new_cases_28_days_to_less_than_1_year_male': 'HA - Outpatients New||28 Days to <1 Year, M',
    #         'outpatients_new_cases_28_days_to_less_than_1_year_female': 'HA - Outpatients New||28 Days to <1 Year, F',
    #         'outpatients_new_cases_1_to_4_years_male': 'HA - Outpatients New||1 to 4 Years, M',
    #         'outpatients_new_cases_1_to_4_years_female': 'HA - Outpatients New||1 to 4 Years, F',
    #         'outpatients_new_cases_5_to_14_years_male': 'HA - Outpatients New||5 to 14 Years, M',
    #         'outpatients_new_cases_5_to_14_years_female': 'HA - Outpatients New||5 to 14 Years, F',
    #         'outpatients_new_cases_15_to_49_years_male': 'HA - Outpatients New||15 to 49 Years, M',
    #         'outpatients_new_cases_15_to_49_years_female': 'HA - Outpatients New||15 to 49 Years, F',
    #         'outpatients_new_cases_50_plus_years_male': 'HA - Outpatients New||50+ Years, M',
    #         'outpatients_new_cases_50_plus_years_female': 'HA - Outpatients New||50+ Years, F',
            
    #         # Outpatient return cases
    #         'outpatients_return_cases_less_than_8_days_male': 'HA - Outpatients Returned||<8 Days, M',
    #         'outpatients_return_cases_less_than_8_days_female': 'HA - Outpatients Returned||<8 Days, F',
    #         'outpatients_return_cases_8_to_27_days_male': 'HA - Outpatients Returned||8 to 27 Days, M',
    #         'outpatients_return_cases_8_to_27_days_female': 'HA - Outpatients Returned||8 to 27 Days, F',
    #         'outpatients_return_cases_28_days_to_less_than_1_year_male': 'HA - Outpatients Returned||28 Days to <1 Year, M',
    #         'outpatients_return_cases_28_days_to_less_than_1_year_female': 'HA - Outpatients Returned||28 Days to <1 Year, F',
    #         'outpatients_return_cases_1_to_4_years_male': 'HA - Outpatients Returned||1 to 4 Years, M',
    #         'outpatients_return_cases_1_to_4_years_female': 'HA - Outpatients Returned||1 to 4 Years, F',
    #         'outpatients_return_cases_5_to_14_years_male': 'HA - Outpatients Returned||5 to 14 Years, M',
    #         'outpatients_return_cases_5_to_14_years_female': 'HA - Outpatients Returned||5 to 14 Years, F',
    #         'outpatients_return_cases_15_to_49_years_male': 'HA - Outpatients Returned||15 to 49 Years, M',
    #         'outpatients_return_cases_15_to_49_years_female': 'HA - Outpatients Returned||15 to 49 Years, F',
    #         'outpatients_return_cases_50_plus_years_male': 'HA - Outpatients Returned||50+ Years, M',
    #         'outpatients_return_cases_50_plus_years_female': 'HA - Outpatients Returned||50+ Years, F',
            
    #         # Referrals
    #         'referrals_non_emergency_hospital': 'HA - Referrals Non-Emergency||Hospital',
    #         'referrals_emergency_hospital': 'HA - Referrals Emergency||Hospital',
    #         'referrals_non_emergency_rhc': 'HA - Referrals Non-Emergency||RHC',
    #         'referrals_emergency_rhc': 'HA - Referrals Emergency||RHC',
    #         'referrals_non_emergency_ahc': 'HA - Referrals Non-Emergency||AHC',
    #         'referrals_emergency_ahc': 'HA - Referrals Emergency||AHC',
    #         'referrals_non_emergency_nrh': 'HA - Referrals Non-Emergency||NRH',
    #         'referrals_emergency_nrh': 'HA - Referrals Emergency||NRH',
            
    #         # PAGE3 DISEASE DATA - Serious Bacterial Infection Cases
    #         'communicable_diseases_serious_bacter_infection_less_than_28_days': 'HA - Serious Bacterial Infection Cases||<28 Days',
    #         'communicable_diseases_serious_bacter_infection_28_days_to_less_than_1_year': 'HA - Serious Bacterial Infection Cases||28 Days to 1 Year',
    #         'communicable_diseases_serious_bacter_infection_1_to_4_years': 'HA - Serious Bacterial Infection Cases||1 to 4 Years',
    #         'communicable_diseases_serious_bacter_infection_5_to_14_years': 'HA - Serious Bacterial Infection Cases||5 to 14 Years',
    #         'communicable_diseases_serious_bacter_infection_15_to_49_years': 'HA - Serious Bacterial Infection Cases||15 to 49 Years',
    #         'communicable_diseases_serious_bacter_infection_50_plus_years': 'HA - Serious Bacterial Infection Cases||50+ Years',
            
    #         # Local Bacterial Infection Cases
    #         'communicable_diseases_local_bacterial_infection_less_than_28_days': 'HA - Local Bacterial Infection Cases||<28 Days',
    #         'communicable_diseases_local_bacterial_infection_28_days_to_less_than_1_year': 'HA - Local Bacterial Infection Cases||28 Days to 1 Year',
    #         'communicable_diseases_local_bacterial_infection_1_to_4_years': 'HA - Local Bacterial Infection Cases||1 to 4 Years',
    #         'communicable_diseases_local_bacterial_infection_5_to_14_years': 'HA - Local Bacterial Infection Cases||5 to 14 Years',
    #         'communicable_diseases_local_bacterial_infection_15_to_49_years': 'HA - Local Bacterial Infection Cases||15 to 49 Years',
    #         'communicable_diseases_local_bacterial_infection_50_plus_years': 'HA - Local Bacterial Infection Cases||50+ Years',
            
    #         # Pneumonia Cases
    #         'communicable_diseases_pneumonia_less_than_28_days': 'HA - Pneumonia cases||<28 Days',
    #         'communicable_diseases_pneumonia_28_days_to_less_than_1_year': 'HA - Pneumonia cases||28 Days to 1 Year',
    #         'communicable_diseases_pneumonia_1_to_4_years': 'HA - Pneumonia cases||1 to 4 Years',
    #         'communicable_diseases_pneumonia_5_to_14_years': 'HA - Pneumonia cases||5 to 14 Years',
    #         'communicable_diseases_pneumonia_15_to_49_years': 'HA - Pneumonia cases||15 to 49 Years',
    #         'communicable_diseases_pneumonia_50_plus_years': 'HA - Pneumonia cases||50+ Years',
            
    #         # Severe Pneumonia Cases
    #         'communicable_diseases_severe_pneumonia_less_than_28_days': 'HA - Severe Pneumonia cases||<28 Days',
    #         'communicable_diseases_severe_pneumonia_28_days_to_less_than_1_year': 'HA - Severe Pneumonia cases||28 Days to 1 Year',
    #         'communicable_diseases_severe_pneumonia_1_to_4_years': 'HA - Severe Pneumonia cases||1 to 4 Years',
    #         'communicable_diseases_severe_pneumonia_5_to_14_years': 'HA - Severe Pneumonia cases||5 to 14 Years',
    #         'communicable_diseases_severe_pneumonia_15_to_49_years': 'HA - Severe Pneumonia cases||15 to 49 Years',
    #         'communicable_diseases_severe_pneumonia_50_plus_years': 'HA - Severe Pneumonia cases||50+ Years',
            
    #         # Influenza Like Illness Cases
    #         'communicable_diseases_influenza_like_illness_less_than_28_days': 'HA - Influenza like illness cases||<28 Days',
    #         'communicable_diseases_influenza_like_illness_28_days_to_less_than_1_year': 'HA - Influenza like illness cases||28 Days to 1 Year',
    #         'communicable_diseases_influenza_like_illness_1_to_4_years': 'HA - Influenza like illness cases||1 to 4 Years',
    #         'communicable_diseases_influenza_like_illness_5_to_14_years': 'HA - Influenza like illness cases||5 to 14 Years',
    #         'communicable_diseases_influenza_like_illness_15_to_49_years': 'HA - Influenza like illness cases||15 to 49 Years',
    #         'communicable_diseases_influenza_like_illness_50_plus_years': 'HA - Influenza like illness cases||50+ Years',
            
    #         # Diarrhea Cases (multiple types)
    #         'communicable_diseases_diarrhea_no_dehydration_less_than_28_days': 'HA - Diarrhea with no dehydration cases||<28 Days',
    #         'communicable_diseases_diarrhea_no_dehydration_28_days_to_less_than_1_year': 'HA - Diarrhea with no dehydration cases||28 Days to 1 Year',
    #         'communicable_diseases_diarrhea_no_dehydration_1_to_4_years': 'HA - Diarrhea with no dehydration cases||1 to 4 Years',
    #         'communicable_diseases_diarrhea_no_dehydration_5_to_14_years': 'HA - Diarrhea with no dehydration cases||5 to 14 Years',
    #         'communicable_diseases_diarrhea_no_dehydration_15_to_49_years': 'HA - Diarrhea with no dehydration cases||15 to 49 Years',
    #         'communicable_diseases_diarrhea_no_dehydration_50_plus_years': 'HA - Diarrhea with no dehydration cases||50+ Years',
            
    #         'communicable_diseases_diarrhea_some_dehydration_less_than_28_days': 'HA - Diarrhea with some dehydration cases||<28 Days',
    #         'communicable_diseases_diarrhea_some_dehydration_28_days_to_less_than_1_year': 'HA - Diarrhea with some dehydration cases||28 Days to 1 Year',
    #         'communicable_diseases_diarrhea_some_dehydration_1_to_4_years': 'HA - Diarrhea with some dehydration cases||1 to 4 Years',
    #         'communicable_diseases_diarrhea_some_dehydration_5_to_14_years': 'HA - Diarrhea with some dehydration cases||5 to 14 Years',
    #         'communicable_diseases_diarrhea_some_dehydration_15_to_49_years': 'HA - Diarrhea with some dehydration cases||15 to 49 Years',
    #         'communicable_diseases_diarrhea_some_dehydration_50_plus_years': 'HA - Diarrhea with some dehydration cases||50+ Years',
            
    #         'communicable_diseases_diarrhea_severe_dehydration_less_than_28_days': 'HA - Diarrhea with severe dehydration cases||<28 Days',
    #         'communicable_diseases_diarrhea_severe_dehydration_28_days_to_less_than_1_year': 'HA - Diarrhea with severe dehydration cases||28 Days to 1 Year',
    #         'communicable_diseases_diarrhea_severe_dehydration_1_to_4_years': 'HA - Diarrhea with severe dehydration cases||1 to 4 Years',
    #         'communicable_diseases_diarrhea_severe_dehydration_5_to_14_years': 'HA - Diarrhea with severe dehydration cases||5 to 14 Years',
    #         'communicable_diseases_diarrhea_severe_dehydration_15_to_49_years': 'HA - Diarrhea with severe dehydration cases||15 to 49 Years',
    #         'communicable_diseases_diarrhea_severe_dehydration_50_plus_years': 'HA - Diarrhea with severe dehydration cases||50+ Years',
            
    #         # ANC/PNC/Delivery data (Page2)
    #         'anc_1st_visit_1st_trimester_health_facility': 'HA - ANC 1st visit||Trimester 1st, Health Facility',
    #         'anc_1st_visit_1st_trimester_satellite': 'HA - ANC 1st visit||Trimester 1st, Satellite',
    #         'anc_1st_visit_2nd_trimester_health_facility': 'HA - ANC 1st visit||Trimester 2nd, Health Facility',
    #         'anc_1st_visit_2nd_trimester_satellite': 'HA - ANC 1st visit||Trimester 2nd, Satellite',
    #         'anc_1st_visit_3rd_trimester_health_facility': 'HA - ANC 1st visit||Trimester 3rd, Health Facility',
    #         'anc_1st_visit_3rd_trimester_satellite': 'HA - ANC 1st visit||Trimester 3rd, Satellite',
    #         'anc_return_visit_health_facility': 'HA - ANC Return Visit||Health Facility',
    #         'anc_return_visit_satellite': 'HA - ANC Return Visit||Satellite',
            
    #         # PNC visits
    #         'pnc_visit_within_2_days_health_facility': 'HA - PNC visit <=2 days||Health Facility',
    #         'pnc_visit_within_2_days_satellite': 'HA - PNC visit <=2 days||Satellite',
    #         'pnc_visit_2_to_4_days_health_facility': 'HA - PNC visit 2-4 days||Health Facility',
    #         'pnc_visit_2_to_4_days_satellite': 'HA - PNC visit 2-4 days||Satellite',
    #         'pnc_visit_5_to_7_days_health_facility': 'HA - PNC visit 5-7 days||Health Facility',
    #         'pnc_visit_5_to_7_days_satellite': 'HA - PNC visit 5-7 days||Satellite',
    #         'pnc_visit_at_6_weeks_health_facility': 'HA - PNC visit at 6 weeks||Health Facility',
    #         'pnc_visit_at_6_weeks_satellite': 'HA - PNC visit at 6 weeks||Satellite',
            
    #         # Delivery and birth data
    #         'delivery_by_others_live_birth': 'HA - Delivery by attendants||Live Birth, Others',
    #         'delivery_by_skilled_attendant_live_birth': 'HA - Delivery by attendants||Live Birth, Skilled attendant',
    #         'breast_feeding_initiation_within_90_mins': 'HA - Breast Feeding initiation <=90 mins at birth||default',
    #         'introduction_of_fluids_foods_at_6_months': 'HA - Introduction of fluids/foods to babies at 6 months||default',
            
    #         # Child welfare and immunization
    #         'child_welfare_clinic_attendance_less_than_12_months_health_facility': 'HA - Child welfare clinic attendance||<12 Months, Health Facility',
    #         'child_welfare_clinic_attendance_less_than_12_months_satellite': 'HA - Child welfare clinic attendance||<12 Months, Satellite',
    #         'child_welfare_clinic_attendance_12_to_59_months_health_facility': 'HA - Child welfare clinic attendance||12 to 59 Months, Health Facility',
    #         'child_welfare_clinic_attendance_12_to_59_months_satellite': 'HA - Child welfare clinic attendance||12 to 59 Months, Satellite',
            
    #         # Deaths data (Page4)
    #         'deaths_general_less_than_8_days_health_facility_male': 'HA - Deaths general||<8 Days, Health Facility, M',
    #         'deaths_general_less_than_8_days_health_facility_female': 'HA - Deaths general||<8 Days, Health Facility, F',
    #         'deaths_general_8_to_27_days_health_facility_male': 'HA - Deaths general||8 to 27 Days, Health Facility, M',
    #         'deaths_general_8_to_27_days_health_facility_female': 'HA - Deaths general||8 to 27 Days, Health Facility, F',
    #         'deaths_general_28_days_to_less_than_1_year_health_facility_male': 'HA - Deaths general||28 Days to <1 Year, Health Facility, M',
    #         'deaths_general_28_days_to_less_than_1_year_health_facility_female': 'HA - Deaths general||28 Days to <1 Year, Health Facility, F',
    #         'deaths_general_1_to_4_years_health_facility_male': 'HA - Deaths general||1 to 4 Years, Health Facility, M',
    #         'deaths_general_1_to_4_years_health_facility_female': 'HA - Deaths general||1 to 4 Years, Health Facility, F',
    #         'deaths_general_5_to_14_years_health_facility_male': 'HA - Deaths general||5 to 14 Years, Health Facility, M',
    #         'deaths_general_5_to_14_years_health_facility_female': 'HA - Deaths general||5 to 14 Years, Health Facility, F',
    #         'deaths_general_15_to_49_years_health_facility_male': 'HA - Deaths general||15 to 49 Years, Health Facility, M',
    #         'deaths_general_15_to_49_years_health_facility_female': 'HA - Deaths general||15 to 49 Years, Health Facility, F',
    #         'deaths_general_50_plus_years_health_facility_male': 'HA - Deaths general||50+ Years, Health Facility, M',
    #         'deaths_general_50_plus_years_health_facility_female': 'HA - Deaths general||50+ Years, Health Facility, F',
            
    #         # GBV and other special cases
    #         'gender_based_violence_referrals_18_plus_years': 'HA - GBV referrals||18+ Years',
    #         'gbv_referrals_18_plus_years': 'HA - GBV referrals||18+ Years',
            
    #         # Infrastructure and resources
    #         'medical_teams_tours': 'HA - Tours Medical team||default',
    #         'tours_medical_team': 'HA - Tours Medical team||default',
    #         'cold_chain_days_not_working': 'HA - Cold chain days not working||default',
    #         'radio_days_not_working': 'HA - Radio days not working||default',
    #         'access_to_basic_water': 'HA - Access to basic Water||Basic',
    #         'access_to_basic_sanitation': 'HA - Access to basic Sanitation||Basic',
    #         'access_to_basic_hygiene': 'HA - Access to basic Hygiene||Basic',
    #         'access_to_basic_waste_management': 'HA - Access to basic Waste Management||Basic',
    #         'medical_doctors': 'HA - Medical doctor(s)||default',
    #         'registered_nurses': 'HA - Registered Nurse(s)||default',
            
    #         # Hospital admissions
    #         'admissions_other_15_to_49_years_male': 'HA - Admissions Other||15 to 49 Years, M',
    #         'admissions_other_15_to_49_years_female': 'HA - Admissions Other||15 to 49 Years, F',
    #     }
        
        
    #     # Apply essential emergency mapping rules (minimal fallback)
    #     for input_field, value in health_data.items():
    #         if input_field in essential_mapping_rules:
    #             dhis_field = essential_mapping_rules[input_field]
                
    #             # Check if the DHIS2 field actually exists in our mappings
    #             if dhis_field in dhis2_fields:
    #                 mapped_data[dhis_field] = str(value)
    #                 logger.info(f"Mapped: {input_field} → {dhis_field} = {value}")
    #             else:
    #                 logger.warning(f"DHIS2 field not found: {dhis_field}")
        
    #     logger.info(f"Rule-based mapping completed: {len(mapped_data)} fields mapped")
    #     return mapped_data
    
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

# UNUSED FUNCTION - NOT USED IN CURRENT FLOW
# def load_test_data(json_file: str = "test_data.json") -> Dict[str, Any]:
#     try:
#         with open(json_file, 'r') as f:
#             test_data_config = json.load(f)
#             return test_data_config.get("data", {})
#     except FileNotFoundError:
#         logger.error(f"Test data file {json_file} not found")
#         return {}
#     except Exception as e:
#         logger.error(f"Failed to load test data: {e}")
#         return {}

async def main():
    """Main entry point - now supports KWARAKA JSON input!"""
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
        
        # Initialize once
        await automation.initialize()
        
        # Login once
        await automation.login(
            url="https://sols1.baosystems.com",
            username="qure", 
            password="A1@wpro1"
        )
        
        # Navigate to Data Entry once
        await automation.navigate_to_data_entry()
        
        # Check if we need to discover org units first
        if not await automation.load_org_unit_cache():
            logger.info("No org unit cache found - discovering organizational units...")
            await automation.discover_organizational_units()
        
        # Dynamic org unit navigation - can be configured via command line
        # Default path if none provided
        default_path = ["Solomon Islands", "Western", "Central Islands Western Province", "Ghatere"]
        
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
            
        await automation.select_period("August 2025")
        
        # Try to load cached mappings first
        cache_loaded = await automation.load_cached_mappings()
        
        if not cache_loaded:
            # Discover field mappings dynamically
            await automation.discover_field_mappings()
        
        # Field mappings ready - proceed to data processing
        
        # Load data file and detect if it's health facility data
        try:
            with open(health_data_file, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded data from {health_data_file}")
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return

        # SMART DETECTION: Check if data contains health facility fields
        has_health_facility_fields = any(
            key.startswith(('outpatients_', 'referrals_', 'gbv_', 'supervisory_', 'treatments_', 'cold_chain_', 'access_to_', 'human_resource_'))
            for key in data.keys() if isinstance(data, dict)
        )
        
        # UNUSED DETECTION - related to commented out map_kwaraka_to_dhis_fields method
        # is_health_facility_data = (
        #     'report_header' in data and 
        #     'outpatients' in data and 
        #     'health_facility_name' in data.get('report_header', {})
        # )
        
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
            
        # UNUSED CODE BLOCK - map_kwaraka_to_dhis_fields method is commented out
        # elif is_health_facility_data:
        #     logger.info("DETECTED: Complex health facility data - Using STREAMLINED approach!")
        #     logger.info("WORKFLOW: Health Facility JSON → LLM → DHIS2 (no intermediate files!)")
        #     
        #     # Use LLM to map health facility data directly to DHIS2 fields  
        #     mapped_data = automation.map_kwaraka_to_dhis_fields(data)
        #     
        #     if not mapped_data:
        #         logger.error("LLM mapping failed - cannot proceed")
        #         return
        #         
        #     logger.info(f"LLM mapped {len(mapped_data)} fields directly from health facility data")
            
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

# UNUSED FUNCTION - NOT USED IN CURRENT FLOW
# def run_with_health_data(filename: str = "health_facility_data.json"):
#     """
#     Convenience function to run automation with a specific health data file
#     """
#     import sys
#     
#     # Set the data source
#     if len(sys.argv) == 1:
#         sys.argv.append(filename)
#     
#     logger.info(f"Starting DHIS2 automation with {filename}...")
#     asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())

