# Birth Report Automation

Automates DHIS2 birth notification forms (38+ fields: event-based program).

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Add to root `.env`:
```env
BIRTH_DHIS_URL=http://172.236.165.102/sb_demo
BIRTH_DHIS_USERNAME=qure
BIRTH_DHIS_PASSWORD=Qure@1234
```

## Run

```bash
# Use sample data (default: visible browser, 100ms slow-mo)
python birth_report_cli.py

# Use your data
python birth_report_cli.py --data my_data.json

# Run in headless mode (no browser window)
python birth_report_cli.py --headless

# Run faster (no slow motion)
python birth_report_cli.py --slow-mo 0

# Combine options
python birth_report_cli.py --data my_data.json --headless --slow-mo 0
```

## Files

| File | Purpose |
|------|---------|
| **birth_report_cli.py** | Main entry point with CLI arguments |
| **birth_report_automation.py** | Fills all 38+ fields (event form) |
| **birth_report_discovery.py** | Auto-discovers new fields from DHIS2 |
| **sample_data.json** | Example birth record with `_meta` |
| **schema.json** | Data validation schema |

## Data Format

```json
{
  "_meta": {
    "program": "birth_notification",
    "facility": "Ghatere"
  },
  "metadata": {
    "serial_number": "BN-2025-001",
    "date_of_notification": "2025-01-15"
  },
  "child_details": {
    "first_name": "John",
    "surname": "Doe",
    "sex": "Male",
    "date_of_birth": "2025-01-10"
  },
  "parent_details": {
    "mother_firstname": "Jane",
    "mother_surname": "Doe",
    "father_firstname": "James",
    "father_surname": "Doe"
  }
}
```

**`_meta` section:**
- `program`: Program key from `/dhis_programs.json` (e.g., "birth_notification")
- `facility`: Facility name from `/dhis_org_units.json` (e.g., "Ghatere", "Yandina")

## Maintenance

**DHIS2 form changed?**
```bash
# Auto-discover new fields
python birth_report_discovery.py

# Review discovered_fields_*.json
# Update field_mappings.json if needed
```

## Results

✅ Event fields: 38+/38+ (100%)  
✅ Automated field discovery for scalability
