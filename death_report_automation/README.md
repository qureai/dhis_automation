# Death Report Automation

Automates DHIS2 death notification forms (38 fields: person + event).

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Add to root `.env`:
```env
DEATH_DHIS_URL=http://172.236.165.102/sb_tracker
DEATH_DHIS_USERNAME=Qure
DEATH_DHIS_PASSWORD=Qure@1234
```

## Run

```bash
# Use sample data (default: visible browser, 100ms slow-mo)
python death_report_cli.py

# Use your data
python death_report_cli.py --data my_data.json

# Run in headless mode (no browser window)
python death_report_cli.py --headless

# Run faster (no slow motion)
python death_report_cli.py --slow-mo 0

# Combine options
python death_report_cli.py --data my_data.json --headless --slow-mo 0
```

## Files

| File | Purpose |
|------|---------|
| **death_report_cli.py** | Main entry point with CLI arguments |
| **death_report_automation.py** | Fills all 38 fields (person + event) |
| **death_report_discovery.py** | Auto-discovers new fields from DHIS2 |
| **field_mappings.json** | All field selectors (38 fields) |
| **sample_data.json** | Example death record with `_meta` |
| **schema.json** | Data validation schema |

## Data Format

```json
{
  "_meta": {
    "program": "death_notification",
    "facility": "Yandina"
  },
  "enrollment": {
    "date_of_death": "2025-11-12"
  },
  "person_profile": {
    "serial_no": "DN001",
    "surname": "JOHNSON",
    "first_and_middle_names": "Michael Robert",
    "sex": "Male",
    "date_of_birth": "1965-03-20"
    // ... 19 more person fields
  },
  "event": {
    "basic_info": { "date_of_death": "2025-11-12" },
    "source_of_notification": { "source_of_information": "Registered Nurse/Nurse Aide" },
    "manner_of_death": { "manner_of_death": "Disease" },
    "declaration": { "doctor_nurse_name": "Dr. Wong" }
  }
}
```

**`_meta` section:**
- `program`: Program key from `/dhis_programs.json` (e.g., "death_notification")
- `facility`: Facility name from `/dhis_org_units.json` (e.g., "Yandina", "Tulagi")

## Maintenance

**DHIS2 form changed?**
```bash
# Auto-discover new fields
python death_report_discovery.py

# Review discovered_fields_*.json
# Update field_mappings.json if needed
```

## Results

✅ Person fields: 24/24 (100%)  
✅ Event fields: 13/13 (100%)  
✅ Total: 37/38 (1 auto-filled by DHIS2)
