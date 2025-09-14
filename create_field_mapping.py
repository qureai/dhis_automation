#!/usr/bin/env python3

import json
import re
from datetime import datetime
from difflib import SequenceMatcher
import sys

def normalize_age_group(age_text):
    """Normalize age groups to a standard format"""
    age_mappings = {
        'less_than_8_days': '<8 Days',
        '8_to_27_days': '8 to 27 Days',
        '28_days_to_less_than_1_year': '28 Days to <1 Year',
        '1_to_4_years': '1 to 4 Years',
        '5_to_14_years': '5 to 14 Years',
        '15_to_49_years': '15 to 49 Years',
        '50_plus_years': '50+ Years',
        'less_than_1_year': '<1 Year',
        '0_to_5_months': '0 to 5 Months',
        '6_to_11_months': '6 to 11 Months',
        '12_to_23_months': '12 to 23 Months',
        '24_to_59_months': '24 to 59 Months',
        'less_than_12_months': '<12 Months',
        '0_to_11_months': '0 to 11 Months',
        '10_to_19_years': '10 to 19 Years',
        '20_to_24_years': '20 to 24 Years',
        '25_to_49_years': '25 to 49 Years',
        'less_than_18_years': '<18 Years',
        '18_plus_years': '18+ Years',
        'less_than_20_years': '<20 Years',
        'greater_than_or_equal_to_20_years': '20+ Years',
        'less_than_10_years': '<10 Years',
        '18_to_19': '18 to 19 Years',
        '20_to_24': '20 to 24 Years',
        'less_than_5_years': '<5 Years',
        '5_to_9_years': '5 to 9 Years',
        '15_years': '15 Years',
        'less_than_28_days': '<28 Days'
    }
    
    for key, value in age_mappings.items():
        if key in age_text:
            return value
    return age_text

def normalize_gender(gender_text):
    """Normalize gender codes"""
    if 'male' in gender_text and 'female' not in gender_text:
        return 'M'
    elif 'female' in gender_text:
        return 'F'
    return gender_text

def extract_components(field_name):
    """Extract components from health facility field name"""
    components = {
        'category': '',
        'subcategory': '',
        'age_group': '',
        'gender': '',
        'type': '',
        'location': '',
        'condition': ''
    }
    
    # Initialize remaining variable
    remaining = field_name
    
    # Extract main categories
    if field_name.startswith('outpatients_'):
        components['category'] = 'outpatients'
        remaining = field_name[12:]  # Remove 'outpatients_'
        
        if remaining.startswith('new_cases_'):
            components['subcategory'] = 'new'
            remaining = remaining[10:]
        elif remaining.startswith('return_cases_'):
            components['subcategory'] = 'return'
            remaining = remaining[13:]
        elif remaining.startswith('chronic_cases_'):
            components['subcategory'] = 'chronic'
            remaining = remaining[14:]
        elif remaining.startswith('person_with_disability_'):
            components['subcategory'] = 'disability'
            remaining = remaining[23:]
    
    elif field_name.startswith('admissions_'):
        components['category'] = 'admissions'
        remaining = field_name[11:]  # Remove 'admissions_'
        
        # Extract condition
        conditions = ['malaria', 'ari', 'pneumonia', 'diarrhoea', 'injury_trauma', 
                     'malnutrition', 'diabetes', 'hypertension', 'skin_infections', 
                     'child_birth', 'others']
        for condition in conditions:
            if remaining.startswith(condition + '_'):
                components['condition'] = condition
                remaining = remaining[len(condition) + 1:]
                break
    
    elif field_name.startswith('general_deaths_') or field_name.startswith('maternal_deaths_'):
        components['category'] = 'deaths'
        if field_name.startswith('maternal_deaths_'):
            components['subcategory'] = 'maternal'
            remaining = field_name[16:]
        else:
            components['subcategory'] = 'general'
            remaining = field_name[14:]
            
        # Extract location
        locations = ['health_facility', 'village_home', 'other_dba']
        for location in locations:
            if remaining.startswith(location + '_'):
                components['location'] = location
                remaining = remaining[len(location) + 1:]
                break
    
    elif field_name.startswith('non_communicable_diseases_'):
        components['category'] = 'non_communicable_diseases'
        remaining = field_name[26:]
        
        # Extract condition and type
        if remaining.startswith('new_case_of_'):
            components['type'] = 'new'
            remaining = remaining[12:]
        
        conditions = ['diabetes', 'hypertension', 'asthma_chest', 'heart_disease', 
                     'rheumatic_heart_disease', 'mental_health_problem', 'substance_abuse']
        for condition in conditions:
            if remaining.startswith(condition + '_'):
                components['condition'] = condition
                remaining = remaining[len(condition) + 1:]
                break
    
    elif field_name.startswith('family_planning_'):
        components['category'] = 'family_planning'
        remaining = field_name[16:]
        
        # Extract method
        methods = ['pills', 'depo_provera', 'condom_male', 'condom_female', 'iucd', 
                  'jadelle', 'tubal_ligation', 'vasectomy']
        for method in methods:
            if remaining.startswith(method + '_'):
                components['subcategory'] = method
                remaining = remaining[len(method) + 1:]
                break
    
    elif field_name.startswith('referrals_'):
        components['category'] = 'referrals'
        remaining = field_name[10:]  # Remove 'referrals_'
        
        if remaining.startswith('emergency_'):
            components['subcategory'] = 'emergency'
            remaining = remaining[10:]
        elif remaining.startswith('non_emergency_'):
            components['subcategory'] = 'non_emergency'
            remaining = remaining[14:]
        elif remaining.startswith('mental_health_'):
            components['subcategory'] = 'mental_health'
            remaining = remaining[14:]
    
    elif field_name.startswith('gbv_referrals_'):
        components['category'] = 'gbv_referrals'
        remaining = field_name[14:]
    
    elif field_name.startswith('supervisory_tours_'):
        components['category'] = 'supervisory_tours'
        remaining = field_name[18:]
        
        if 'national_program' in remaining:
            components['subcategory'] = 'national_program'
        elif 'provincial_program' in remaining:
            components['subcategory'] = 'provincial_program'
        elif 'area_supervisors' in remaining:
            components['subcategory'] = 'area_supervisors'
        elif 'medical_team' in remaining:
            components['subcategory'] = 'medical_team'
    
    elif field_name.startswith('outreach_'):
        components['category'] = 'outreach'
        remaining = field_name[9:]
    
    elif field_name.startswith('communicable_diseases_'):
        components['category'] = 'communicable_diseases'
        remaining = field_name[22:]
    
    elif field_name.startswith('epi_') or field_name.startswith('hpv_'):
        components['category'] = 'immunization'
        remaining = field_name
    
    elif field_name.startswith('antenatal_care_') or field_name.startswith('postnatal_care_'):
        components['category'] = 'maternal_care'
        remaining = field_name
    
    elif field_name.startswith('child_'):
        components['category'] = 'child_care'
        remaining = field_name
    
    # Extract age group and gender from remaining part
    age_patterns = [
        r'less_than_8_days', r'8_to_27_days', r'28_days_to_less_than_1_year',
        r'1_to_4_years', r'5_to_14_years', r'15_to_49_years', r'50_plus_years',
        r'0_to_5_months', r'6_to_11_months', r'12_to_23_months', r'24_to_59_months',
        r'less_than_12_months', r'0_to_11_months', r'10_to_19_years', r'20_to_24_years',
        r'25_to_49_years', r'less_than_18_years', r'18_plus_years', r'less_than_20_years',
        r'greater_than_or_equal_to_20_years', r'less_than_10_years', r'18_to_19',
        r'20_to_24', r'less_than_5_years', r'5_to_9_years', r'15_years',
        r'less_than_28_days', r'less_than_1_year'
    ]
    
    # Extract gender first before processing age patterns
    original_remaining = remaining
    if remaining.endswith('_male'):
        components['gender'] = 'M'
        remaining = remaining[:-5]
    elif remaining.endswith('_female'):
        components['gender'] = 'F'
        remaining = remaining[:-7]
    elif remaining.endswith('_total'):
        components['gender'] = 'Total'
        remaining = remaining[:-6]
    
    # Also check in the original field name if not found
    if not components['gender']:
        if original_remaining.endswith('_male'):
            components['gender'] = 'M'
        elif original_remaining.endswith('_female'):
            components['gender'] = 'F'
        elif original_remaining.endswith('_total'):
            components['gender'] = 'Total'
    
    for pattern in age_patterns:
        if re.search(pattern, remaining):
            components['age_group'] = normalize_age_group(pattern)
            remaining = re.sub(pattern + r'_?', '', remaining)
            break
    
    return components

def similarity_score(str1, str2):
    """Calculate similarity score between two strings"""
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def find_best_match(health_field, dhis_fields):
    """Find the best matching DHIS field for a health facility field"""
    health_components = extract_components(health_field)
    best_match = None
    best_score = 0
    matching_factors = []
    
    for dhis_field in dhis_fields:
        score = 0
        factors = []
        
        # Parse DHIS field format: "Category||Age Group, Gender" or "Category||Location"
        dhis_parts = dhis_field.split('||')
        if len(dhis_parts) == 2:
            dhis_category = dhis_parts[0].strip()
            dhis_details = dhis_parts[1].strip()
            
            # Match category patterns
            if health_components['category'] == 'outpatients':
                if 'Outpatients' in dhis_category:
                    score += 0.4
                    factors.append('category')
                    
                    # Match subcategory
                    if health_components['subcategory'] == 'new' and 'New' in dhis_category:
                        score += 0.3
                        factors.append('subcategory')
                    elif health_components['subcategory'] == 'return' and 'Returned' in dhis_category:
                        score += 0.3
                        factors.append('subcategory')
                    elif health_components['subcategory'] == 'chronic' and 'Chronic' in dhis_category:
                        score += 0.3
                        factors.append('subcategory')
                    elif health_components['subcategory'] == 'disability' and 'Disability' in dhis_category:
                        score += 0.3
                        factors.append('subcategory')
            
            # Handle referrals
            elif 'referrals_' in health_field:
                if 'Referrals' in dhis_category:
                    score += 0.4
                    factors.append('category')
                    
                    if 'emergency' in health_field and 'Emergency' in dhis_category:
                        score += 0.3
                        factors.append('type')
                    elif 'non_emergency' in health_field and 'Non-Emergency' in dhis_category:
                        score += 0.3
                        factors.append('type')
                    elif 'mental_health' in health_field and 'Mental Health' in dhis_category:
                        score += 0.3
                        factors.append('condition')
                    
                    # Match destination
                    destinations = {'rhc': 'RHC', 'ahc': 'AHC', 'hospital': 'Hospital', 'nrh': 'NRH'}
                    for key, value in destinations.items():
                        if key in health_field and value in dhis_details:
                            score += 0.2
                            factors.append('location')
                            break
            
            # Handle GBV referrals
            elif 'gbv_referrals_' in health_field:
                if 'GBV referrals' in dhis_category:
                    score += 0.4
                    factors.append('category')
                    
                    if 'less_than_18_years' in health_field and '<18 Years' in dhis_details:
                        score += 0.3
                        factors.append('age_group')
                    elif '18_plus_years' in health_field and '18+ Years' in dhis_details:
                        score += 0.3
                        factors.append('age_group')
            
            # Handle supervisory tours
            elif 'supervisory_tours_' in health_field:
                if 'Tours' in dhis_category:
                    score += 0.4
                    factors.append('category')
                    
                    if 'national_program' in health_field and 'National program' in dhis_category:
                        score += 0.3
                        factors.append('type')
                    elif 'provincial_program' in health_field and 'Provincial program' in dhis_category:
                        score += 0.3
                        factors.append('type')
            
            elif health_components['category'] == 'admissions':
                if 'Admissions' in dhis_category or 'Inpatient' in dhis_category:
                    score += 0.4
                    factors.append('category')
                    
                    # Match condition
                    condition_map = {
                        'malaria': 'Malaria',
                        'ari': 'ARI',
                        'pneumonia': 'Pneumonia',
                        'diarrhoea': 'Diarrhoe',
                        'diabetes': 'Diabetes',
                        'hypertension': 'Hypertension',
                        'injury_trauma': 'Injury',
                        'malnutrition': 'Malnutrition',
                        'skin_infections': 'Skin',
                        'child_birth': 'Birth',
                        'others': 'Others'
                    }
                    for condition, dhis_term in condition_map.items():
                        if health_components['condition'] == condition and dhis_term in dhis_category:
                            score += 0.3
                            factors.append('condition')
                            break
            
            elif health_components['category'] == 'deaths':
                if 'Deaths' in dhis_category or 'Death' in dhis_category:
                    score += 0.4
                    factors.append('category')
                    
                    if health_components['subcategory'] == 'maternal' and 'Maternal' in dhis_category:
                        score += 0.3
                        factors.append('subcategory')
            
            # Handle family planning
            elif health_components['category'] == 'family_planning':
                if 'Family Planning' in dhis_category or 'FP ' in dhis_category:
                    score += 0.4
                    factors.append('category')
                    
                    # Match method
                    method_map = {
                        'pills': 'Pills',
                        'depo_provera': 'Depo',
                        'condom_male': 'Condom Male',
                        'condom_female': 'Condom Female',
                        'iucd': 'IUCD',
                        'jadelle': 'Jadelle',
                        'tubal_ligation': 'Tubal',
                        'vasectomy': 'Vasectomy'
                    }
                    for method, dhis_term in method_map.items():
                        if health_components['subcategory'] == method and dhis_term in dhis_category:
                            score += 0.3
                            factors.append('method')
                            break
            
            # Handle communicable diseases
            elif health_components['category'] == 'communicable_diseases':
                if 'Communicable' in dhis_category or any(term in dhis_category for term in 
                    ['Malaria', 'Pneumonia', 'Diarrhea', 'ARI', 'TB', 'STI']):
                    score += 0.4
                    factors.append('category')
            
            # Handle immunization
            elif health_components['category'] == 'immunization':
                if any(term in dhis_category for term in 
                    ['EPI', 'Vaccination', 'Vaccine', 'Immunization', 'HPV']):
                    score += 0.4
                    factors.append('category')
            
            # Handle maternal care
            elif health_components['category'] == 'maternal_care':
                if any(term in dhis_category for term in 
                    ['ANC', 'PNC', 'Antenatal', 'Postnatal', 'Maternal']):
                    score += 0.4
                    factors.append('category')
            
            # Handle child care
            elif health_components['category'] == 'child_care':
                if any(term in dhis_category for term in 
                    ['Child', 'Nutrition', 'Growth', 'Infant']):
                    score += 0.4
                    factors.append('category')
            
            # Handle outreach
            elif health_components['category'] == 'outreach':
                if 'Outreach' in dhis_category or 'Community' in dhis_category:
                    score += 0.4
                    factors.append('category')
            
            # Match age group and gender from details
            if ', ' in dhis_details:
                age_part, gender_part = dhis_details.rsplit(', ', 1)
                
                # Match age group (exact match required)
                if health_components['age_group'] and health_components['age_group'] == age_part:
                    score += 0.25
                    factors.append('age_group')
                
                # Match gender (exact match required for high confidence)
                if health_components['gender'] and health_components['gender'] == gender_part:
                    score += 0.3
                    factors.append('gender')
                elif health_components['gender'] and health_components['gender'] != gender_part:
                    # Penalize gender mismatch heavily to prevent wrong mappings
                    score -= 0.8
            else:
                # Single detail (like location or default)
                if dhis_details == 'default':
                    if not health_components['age_group'] and not health_components['gender']:
                        score += 0.1
                        factors.append('default')
            
            # Use fuzzy matching as fallback
            fuzzy_score = similarity_score(health_field, dhis_field)
            score += fuzzy_score * 0.1
            
            if score > best_score:
                best_score = score
                best_match = dhis_field
                matching_factors = factors
    
    return best_match, best_score, matching_factors

def create_comprehensive_mapping():
    """Create comprehensive field mapping"""
    
    # Load health facility report
    with open('/Users/bhargav/Documents/codebase/dhis_automation/health_facility_report.json', 'r') as f:
        health_data = json.load(f)
    
    # Load DHIS field mappings  
    with open('/Users/bhargav/Documents/codebase/dhis_automation/dhis_field_mappings.json', 'r') as f:
        dhis_data = json.load(f)
    
    # Get all DHIS field names
    dhis_fields = list(dhis_data['mappings'].keys())
    
    # Metadata fields to exclude
    metadata_fields = {
        'province_name', 'health_facility_name', 'month', 'year', 'zone', 
        'type', 'completed_by_name', 'completed_by_rank', 'completed_by_phone_no',
        'completed_by_signature_present', 'completed_by_date_present',
        'reviewed_by_name', 'reviewed_by_rank', 'reviewed_by_phone_no',
        'reviewed_by_signature_present', 'reviewed_by_date_present'
    }
    
    # Create mappings
    mappings = {}
    unmapped_fields = []
    mapped_count = 0
    
    for health_field, health_value in health_data.items():
        if health_field in metadata_fields:
            continue
            
        best_match, confidence_score, matching_factors = find_best_match(health_field, dhis_fields)
        
        if best_match and confidence_score >= 0.4:  # Minimum confidence threshold
            dhis_info = dhis_data['mappings'][best_match]
            mappings[health_field] = {
                'dhis_field_name': best_match,
                'selector': dhis_info['selector'],
                'tab': dhis_info['tab'],
                'health_value': health_value,
                'mapped': True,
                'confidence_score': round(confidence_score, 3),
                'matching_factors': matching_factors
            }
            mapped_count += 1
        else:
            mappings[health_field] = {
                'dhis_field_name': None,
                'selector': None,
                'tab': None,
                'health_value': health_value,
                'mapped': False,
                'confidence_score': round(confidence_score, 3) if confidence_score else 0.0,
                'matching_factors': matching_factors if confidence_score else []
            }
            unmapped_fields.append(health_field)
    
    total_health_fields = len([f for f in health_data.keys() if f not in metadata_fields])
    coverage_percentage = f"{(mapped_count / total_health_fields * 100):.1f}%"
    
    # Create comprehensive mapping structure
    comprehensive_mapping = {
        'timestamp': datetime.now().isoformat(),
        'source_files': {
            'health_facility_report': 'health_facility_report.json',
            'dhis_field_mappings': 'dhis_field_mappings.json'
        },
        'statistics': {
            'total_health_fields': total_health_fields,
            'mapped_fields': mapped_count,
            'unmapped_fields': len(unmapped_fields),
            'mapping_coverage': coverage_percentage
        },
        'mappings': mappings,
        'unmapped_fields': unmapped_fields
    }
    
    # Save to file
    output_file = '/Users/bhargav/Documents/codebase/dhis_automation/comprehensive_field_mapping.json'
    with open(output_file, 'w') as f:
        json.dump(comprehensive_mapping, f, indent=2)
    
    print(f"Comprehensive field mapping created successfully!")
    print(f"Total health fields: {total_health_fields}")
    print(f"Mapped fields: {mapped_count}")
    print(f"Unmapped fields: {len(unmapped_fields)}")
    print(f"Mapping coverage: {coverage_percentage}")
    print(f"Output saved to: {output_file}")
    
    return comprehensive_mapping

if __name__ == '__main__':
    create_comprehensive_mapping()