#!/usr/bin/env python3
"""
Test script to verify DHIS2 PDF Automation setup
"""

import os
import sys
from pathlib import Path

def test_conda_environment():
    """Test if we're in the dhis conda environment"""
    print("🧪 Testing Conda Environment...")
    
    conda_env = os.environ.get('CONDA_DEFAULT_ENV')
    if conda_env == 'dhis':
        print("✅ Running in 'dhis' conda environment")
        return True
    else:
        print(f"❌ Not in 'dhis' environment. Current: {conda_env}")
        return False

def test_python_version():
    """Test Python version"""
    print("🧪 Testing Python Version...")
    
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Requires 3.8+")
        return False

def test_required_files():
    """Test if required files exist"""
    print("🧪 Testing Required Files...")
    
    files_to_check = [
        'dhis_automation.py',
        'llm.py', 
        'backend/.env',
        'backend/manage.py',
        'frontend/package.json'
    ]
    
    all_exist = True
    for file_path in files_to_check:
        path = Path(file_path)
        if path.exists():
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            all_exist = False
    
    return all_exist

def test_django_imports():
    """Test Django and required imports"""
    print("🧪 Testing Django Imports...")
    
    try:
        import django
        print(f"✅ Django {django.get_version()} imported successfully")
        
        import rest_framework
        print("✅ Django REST Framework available")
        
        import corsheaders
        print("✅ Django CORS headers available")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_ai_dependencies():
    """Test AI processing dependencies"""
    print("🧪 Testing AI Dependencies...")
    
    try:
        from portkey_ai import Portkey
        print("✅ Portkey AI imported successfully")
        
        import base64
        print("✅ Base64 encoding available")
        
        return True
    except ImportError as e:
        print(f"❌ AI dependency error: {e}")
        return False

def test_automation_dependencies():
    """Test automation dependencies"""
    print("🧪 Testing Automation Dependencies...")
    
    try:
        from playwright.async_api import async_playwright
        print("✅ Playwright imported successfully")
        
        import asyncio
        print("✅ Asyncio available")
        
        return True
    except ImportError as e:
        print(f"❌ Automation dependency error: {e}")
        return False

def test_dhis_automation_import():
    """Test if we can import the DHIS automation class"""
    print("🧪 Testing DHIS Automation Import...")
    
    try:
        # Add current directory to path
        sys.path.insert(0, str(Path.cwd()))
        
        from dhis_automation import DHISSmartAutomation
        print("✅ DHISSmartAutomation imported successfully")
        
        # Test instantiation
        automation = DHISSmartAutomation()
        print("✅ DHISSmartAutomation instantiated successfully")
        
        return True
    except ImportError as e:
        print(f"❌ DHIS automation import error: {e}")
        return False
    except Exception as e:
        print(f"❌ DHIS automation instantiation error: {e}")
        return False

def test_environment_variables():
    """Test environment variables"""
    print("🧪 Testing Environment Variables...")
    
    required_vars = [
        'DHIS_USERNAME',
        'DHIS_PASSWORD',
        'DHIS_URL',
        'PORTKEY_API_KEY'
    ]
    
    all_present = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Don't print sensitive values, just confirm they exist
            if 'PASSWORD' in var or 'KEY' in var:
                print(f"✅ {var} is set (value hidden)")
            else:
                print(f"✅ {var} = {value}")
        else:
            print(f"❌ {var} not set")
            all_present = False
    
    return all_present

def main():
    """Run all tests"""
    print("🚀 DHIS2 PDF Automation Setup Test")
    print("=" * 50)
    
    tests = [
        test_python_version,
        test_conda_environment,
        test_required_files,
        test_environment_variables,
        test_django_imports,
        test_ai_dependencies,
        test_automation_dependencies,
        test_dhis_automation_import
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        print()
        if test():
            passed += 1
        else:
            failed += 1
    
    print()
    print("=" * 50)
    print(f"🎯 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! System is ready.")
        print()
        print("Next steps:")
        print("1. Run: ./start.sh")
        print("2. Open: http://localhost:3000")
        return True
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)