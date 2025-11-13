# API Response Capture Implementation

## Overview
Both Birth and Death report automations now capture HTTP status codes and full API responses from DHIS2 for reliable success/failure detection and detailed reporting.

---

## 📡 API Endpoints Captured

### Birth Report (Event Program)
- **Endpoint:** `POST /api/{version}/tracker`
- **Description:** Creates a single event in the birth notification program
- **Request Body:** JSON with event data including all form fields

### Death Report (Tracker Program)
- **Endpoint:** `POST /api/{version}/tracker`
- **Description:** Creates enrollment (person) + event (death details) in tracker program
- **Request Body:** JSON with enrollment data and event data

---

## 📋 API Response Structure

### Success Response (HTTP 200)
```json
{
  "status": "OK",
  "stats": {
    "created": 1,
    "updated": 0,
    "ignored": 0,
    "deleted": 0
  },
  "validationReport": {
    "errorReports": []
  },
  "bundleReport": {
    "typeReportMap": {
      "ENROLLMENT": {...},
      "EVENT": {...}
    }
  }
}
```

### Duplicate/Conflict Response (HTTP 409)
```json
{
  "status": "ERROR",
  "stats": {
    "created": 0,
    "updated": 0,
    "ignored": 1,
    "deleted": 0
  },
  "validationReport": {
    "errorReports": []
  }
}
```

### Validation Error Response (HTTP 200 with errors)
```json
{
  "status": "ERROR",
  "stats": {
    "created": 0,
    "updated": 0,
    "ignored": 1,
    "deleted": 0
  },
  "validationReport": {
    "errorReports": [
      {
        "message": "Value `true` is not a valid option code in option set `xyz`",
        "errorCode": "E1125",
        "trackerType": "EVENT",
        "uid": "event-uid",
        "args": ["true", "xyz"]
      }
    ]
  }
}
```

---

## 🎯 Status Code-Based Logic

### Success Detection
- **HTTP 200** → Record created successfully
- **HTTP 409** → Conflict/Duplicate (serial number already exists)
- **Other codes** → Failed

### Log Messages

#### HTTP 200 (Success)
```
============================================================
✅ RECORD CREATED SUCCESSFULLY!
============================================================

📡 HTTP Status Code: 200
   ✓ Success - Record created

📋 API RESPONSE DETAILS:
   Status: OK
   Created: 1
   Updated: 0
   Ignored: 0
```

#### HTTP 409 (Duplicate)
```
============================================================
⚠️  RECORD NOT CREATED - DUPLICATE/CONFLICT!
============================================================

📡 HTTP Status Code: 409
   ⚠️  Conflict - Duplicate serial number or data

📋 API RESPONSE DETAILS:
   Status: ERROR
   Created: 0
   Updated: 0
   Ignored: 1
```

#### Validation Errors
```
📋 API RESPONSE DETAILS:
   Status: ERROR
   Created: 0
   Updated: 0
   Ignored: 1
   ⚠️  Validation Errors: 2
      - Value `true` is not a valid option code in option set `xyz`
      - Required field is missing
```

---

## 🔧 Implementation Details

### 1. **Capturing API Response**
```python
async def submit_form(self):
    api_response = None
    status_code = None
    
    async def handle_response(response):
        nonlocal api_response, status_code
        if (response.request.method == 'POST' and 
            '/api/' in response.url and 
            'tracker' in response.url):
            status_code = response.status
            api_response = await response.json()
            
            # Log based on status code
            if status_code == 200:
                logger.info(f"📡 API Response: {status_code} - ✓ Created successfully")
            elif status_code == 409:
                logger.warning(f"📡 API Response: {status_code} - ⚠️  Conflict/Duplicate")
    
    self.page.on("response", handle_response)
    await self.page.click('button:has-text("Save")')
    await asyncio.sleep(2)  # Wait for API response
    self.page.remove_listener("response", handle_response)
    
    return success, enrollment_id, api_response, status_code
```

### 2. **Return Dictionary Structure**
```python
{
    "success": True/False,           # Based on HTTP status code (200 = True)
    "status_code": 200,              # HTTP status code
    "enrollment_id": "xyz123",       # From URL redirect (tracker programs only)
    "fields_filled": 36,             # Number of fields successfully filled
    "total_fields": 38,              # Total fields in form
    "api_response": {                # Full DHIS2 API response
        "status": "OK",
        "stats": {...},
        "validationReport": {...}
    },
    "error": "Optional error message"  # Only present on failure
}
```

---

## 💡 For Developers

### Using the Return Data Programmatically

```python
# Birth Report
result = await automation.automate(program_id, org_unit_id, data)

# Check HTTP status code
if result["status_code"] == 200:
    print("✅ Record created!")
    print(f"Fields filled: {result['fields_filled']}/{result['total_fields']}")
elif result["status_code"] == 409:
    print("⚠️  Duplicate record detected")
    print(f"Ignored: {result['api_response']['stats']['ignored']}")
else:
    print("❌ Failed")
    errors = result['api_response']['validationReport']['errorReports']
    for err in errors:
        print(f"  - {err['message']}")
```

### Accessing Full API Response
```python
api_resp = result["api_response"]

# Get statistics
stats = api_resp["stats"]
print(f"Created: {stats['created']}")
print(f"Updated: {stats['updated']}")
print(f"Ignored: {stats['ignored']}")

# Get validation errors
validation = api_resp["validationReport"]
errors = validation["errorReports"]
for err in errors:
    print(f"Error: {err['message']}")
    print(f"Code: {err['errorCode']}")
```

---

## 📝 Known Issues

### Birth Report
1. **"Child Named at Birth" field** causes validation error:
   - DHIS2 frontend converts "Yes"/"No" → `true`/`false`
   - Backend rejects boolean values for this option set
   - **Workaround:** Field is disabled in mapping until DHIS2 bug is fixed

### Death Report
- No known issues (all 36 fields working correctly)

---

## ✅ Testing

Both automations have been tested with:
- ✓ Successful creation (HTTP 200)
- ✓ Duplicate detection (HTTP 409) 
- ✓ Validation error handling
- ✓ API response capture and display
- ✓ Full field filling with real data
- ✓ Status code-based success determination

**Last Updated:** November 13, 2025

