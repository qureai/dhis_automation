#!/usr/bin/env python3
"""
Automated DHIS2 Field Mapping Generator

This script analyzes your health facility data and automatically generates
complete mapping rules by matching field patterns with discovered DHIS2 fields.
"""

import json
import re
from typing import Dict, List, Tuple
from pathlib import Path
import difflib

class DHISMappingGenerator:
    def __init__(self):
        self.health_data = {}
        self.dhis_fields = {}
        self.generated_mappings = {}
        self.unmapped_fields = []
        
    def load_data(self, health_file: str, dhis_file: str):
        """Load health facility data and DHIS2 field mappings"""
        print(f"Loading health facility data from {health_file}...")
        with open(health_file, 'r') as f:
            self.health_data = json.load(f)
        print(f"Loaded {len(self.health_data)} health data fields")
        
        print(f"Loading DHIS2 field mappings from {dhis_file}...")
        with open(dhis_file, 'r') as f:
            dhis_cache = json.load(f)
            self.dhis_fields = dhis_cache.get('mappings', {})
        print(f"Loaded {len(self.dhis_fields)} DHIS2 fields")
    
    def normalize_field_name(self, field_name: str) -> str:
        """Normalize field names for better matching"""
        # Convert to lowercase and replace underscores with spaces
        normalized = field_name.lower().replace('_', ' ').replace('-', ' ')
        # Remove extra spaces
        normalized = ' '.join(normalized.split())
        return normalized
    
    def extract_age_groups(self, field_name: str) -> Tuple[str, str]:
        """Extract age group and gender information"""
        age_patterns = {
            'less_than_8_days': '<8 Days',
            '8_to_27_days': '8 to 27 Days', 
            '28_days_to_less_than_1_year': '28 Days to <1 Year',
            '28_days_to_1_year': '28 Days to 1 Year',
            '1_to_4_years': '1 to 4 Years',
            '5_to_14_years': '5 to 14 Years',
            '15_to_49_years': '15 to 49 Years',
            '50_plus_years': '50+ Years',
            'less_than_28_days': '<28 Days',
            'less_than_12_months': '<12 Months',
            '18_plus_years': '18+ Years'
        }
        
        gender_patterns = {
            '_male': ', M',
            '_female': ', F'
        }
        
        age_group = ''
        gender = ''
        
        # Find age group
        for pattern, replacement in age_patterns.items():
            if pattern in field_name:
                age_group = replacement
                break
                
        # Find gender
        for pattern, replacement in gender_patterns.items():
            if field_name.endswith(pattern):
                gender = replacement
                break
        
        return age_group, gender
    
    def find_best_dhis_match(self, health_field: str) -> str:
        """Find best matching DHIS2 field for a health data field"""
        
        # Extract components from health field name
        age_group, gender = self.extract_age_groups(health_field)
        
        # Define field category mappings
        category_mappings = {
            'outpatients_new_cases': 'HA - Outpatients New||',
            'outpatients_return_cases': 'HA - Outpatients Returned||',
            'referrals_emergency': 'HA - Referrals Emergency||',
            'referrals_non_emergency': 'HA - Referrals Non-Emergency||',
            'gbv_referrals': 'HA - GBV referrals||',
            'cold_chain_days_not_working': 'HA - Cold chain days not working||',
            'radio_days_not_working': 'HA - Radio days not working||',
            'child_welfare_clinic_attendance': 'HA - Child welfare clinic attendance||',
            'communicable_diseases_serious_bacter_infection': 'HA - Serious Bacterial Infection Cases||',
            'communicable_diseases_local_bacterial_infection': 'HA - Local Bacterial Infection Cases||',
            'communicable_diseases_influenza_like_illness': 'HA - Influenza like illness cases||',
            'communicable_diseases_pneumonia': 'HA - Pneumonia cases||',
            'communicable_diseases_severe_pneumonia': 'HA - Severe Pneumonia cases||',
        }
        
        # Find category match
        dhis_prefix = ''
        for pattern, dhis_pattern in category_mappings.items():
            if health_field.startswith(pattern):
                dhis_prefix = dhis_pattern
                break
        
        if not dhis_prefix:
            # Try fuzzy matching for unmapped categories
            return self.fuzzy_match_dhis_field(health_field)
        
        # Handle special cases
        if 'health_facility' in health_field:
            facility_suffix = 'Health Facility'
        elif 'satellite' in health_field:
            facility_suffix = 'Satellite'
        elif 'rhc' in health_field:
            facility_suffix = 'RHC'
        elif 'ahc' in health_field:
            facility_suffix = 'AHC'
        elif 'hospital' in health_field:
            facility_suffix = 'Hospital'
        elif 'nrh' in health_field:
            facility_suffix = 'NRH'
        elif 'default' in health_field:
            facility_suffix = 'default'
        else:
            facility_suffix = age_group + gender
        
        # Construct expected DHIS field name
        expected_dhis = dhis_prefix + facility_suffix
        
        # Look for exact match
        if expected_dhis in self.dhis_fields:
            return expected_dhis
        
        # Try variations
        variations = [
            expected_dhis.replace(', M', ' M').replace(', F', ' F'),
            expected_dhis.replace('||', ' '),
            expected_dhis.replace('HA - ', ''),
        ]
        
        for variation in variations:
            if variation in self.dhis_fields:
                return variation
        
        # Fuzzy matching as fallback
        return self.fuzzy_match_dhis_field(health_field)
    
    def fuzzy_match_dhis_field(self, health_field: str) -> str:
        """Use fuzzy matching to find similar DHIS2 fields"""
        normalized_health = self.normalize_field_name(health_field)
        
        best_match = ''
        best_ratio = 0
        
        for dhis_field in self.dhis_fields.keys():
            normalized_dhis = self.normalize_field_name(dhis_field)
            ratio = difflib.SequenceMatcher(None, normalized_health, normalized_dhis).ratio()
            
            if ratio > best_ratio and ratio > 0.4:  # Minimum similarity threshold
                best_ratio = ratio
                best_match = dhis_field
        
        return best_match if best_ratio > 0.4 else ''
    
    def generate_mappings(self):
        """Generate complete field mappings"""
        print("Generating complete field mappings...")
        
        mapped_count = 0
        for health_field in self.health_data.keys():
            # Skip metadata fields
            if health_field in ['province_name', 'health_facility_name', 'month', 'year', 'zone', 'type']:
                continue
                
            dhis_match = self.find_best_dhis_match(health_field)
            
            if dhis_match:
                self.generated_mappings[health_field] = dhis_match
                mapped_count += 1
            else:
                self.unmapped_fields.append(health_field)
        
        print(f"Successfully mapped {mapped_count} fields")
        print(f"Failed to map {len(self.unmapped_fields)} fields")
        
        if self.unmapped_fields:
            print("Unmapped fields:")
            for field in self.unmapped_fields[:10]:  # Show first 10
                print(f"  - {field}")
            if len(self.unmapped_fields) > 10:
                print(f"  ... and {len(self.unmapped_fields) - 10} more")
    
    def save_complete_mapping(self, output_file: str):
        """Save complete mapping rules to file"""
        complete_mapping = {
            "timestamp": "auto-generated",
            "description": "Complete field mapping generated automatically",
            "total_health_fields": len(self.health_data),
            "mapped_fields": len(self.generated_mappings),
            "unmapped_fields": len(self.unmapped_fields),
            "coverage_percentage": round((len(self.generated_mappings) / (len(self.health_data) - 6)) * 100, 1),  # -6 for metadata fields
            "mappings": self.generated_mappings,
            "unmapped": self.unmapped_fields
        }
        
        with open(output_file, 'w') as f:
            json.dump(complete_mapping, f, indent=2)
        
        print(f"Complete mapping saved to {output_file}")
        print(f"Coverage: {complete_mapping['coverage_percentage']}% ({complete_mapping['mapped_fields']}/{len(self.health_data)-6} fields)")

def main():
    generator = DHISMappingGenerator()
    
    # Load data files
    health_file = "health_facility_report.json"
    dhis_file = "dhis_field_mappings.json"
    output_file = "complete_field_mapping.json"
    
    if not Path(health_file).exists():
        print(f"Error: {health_file} not found")
        return
    
    if not Path(dhis_file).exists():
        print(f"Error: {dhis_file} not found")
        print("Please run the main automation first to discover DHIS2 fields")
        return
    
    generator.load_data(health_file, dhis_file)
    generator.generate_mappings()
    generator.save_complete_mapping(output_file)
    
    print(f"\nNext steps:")
    print(f"1. Review {output_file} for accuracy")
    print(f"2. Run: python dhis_automation.py {health_file}")
    print(f"   The automation will automatically use the complete mapping")

if __name__ == "__main__":
    main()