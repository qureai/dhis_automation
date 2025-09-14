#!/usr/bin/env python3
"""
Setup script for DHIS2 PDF Automation project
This script sets up both frontend and backend components
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(command, cwd=None, shell=True):
    """Run a command and handle errors"""
    print(f"Running: {command}")
    result = subprocess.run(command, cwd=cwd, shell=shell, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(f"Error output: {result.stderr}")
        return False
    
    print(f"Success: {result.stdout}")
    return True


def setup_backend():
    """Set up Django backend"""
    print("\n=== Setting up Django Backend ===")
    
    backend_dir = Path(__file__).parent / "backend"
    
    # Install Python dependencies
    if not run_command("pip install -r requirements.txt", cwd=backend_dir):
        print("Failed to install backend dependencies")
        return False
    
    # Run Django migrations
    if not run_command("python manage.py makemigrations", cwd=backend_dir):
        print("Failed to create migrations")
        return False
        
    if not run_command("python manage.py migrate", cwd=backend_dir):
        print("Failed to run migrations")
        return False
    
    # Create superuser (optional)
    print("\nCreating Django superuser (optional):")
    print("Press Ctrl+C to skip")
    try:
        subprocess.run("python manage.py createsuperuser", cwd=backend_dir, shell=True)
    except KeyboardInterrupt:
        print("\nSkipping superuser creation")
    
    # Install Playwright browsers
    print("\nInstalling Playwright browsers for DHIS2 automation...")
    if not run_command("playwright install", cwd=backend_dir):
        print("Warning: Failed to install Playwright browsers")
        print("You may need to install them manually: playwright install")
    
    return True


def setup_frontend():
    """Set up React frontend"""
    print("\n=== Setting up React Frontend ===")
    
    frontend_dir = Path(__file__).parent / "frontend"
    
    # Check if Node.js is installed
    result = subprocess.run("node --version", shell=True, capture_output=True)
    if result.returncode != 0:
        print("Error: Node.js is not installed. Please install Node.js first.")
        return False
    
    # Install npm dependencies
    if not run_command("npm install", cwd=frontend_dir):
        print("Failed to install frontend dependencies")
        return False
    
    return True


def check_environment():
    """Check environment configuration"""
    print("\n=== Checking Environment Configuration ===")
    
    env_file = Path(__file__).parent / ".env"
    env_example = Path(__file__).parent / ".env.example"
    
    if not env_file.exists():
        if env_example.exists():
            print("Creating .env file from .env.example...")
            with open(env_example, 'r') as src, open(env_file, 'w') as dst:
                dst.write(src.read())
            print("✓ Created .env file")
            print("⚠️  Please edit .env file with your actual API keys and DHIS2 credentials")
        else:
            print("⚠️  No .env.example found. Please create .env file manually")
    else:
        print("✓ .env file already exists")
    
    # Check for reference PDF
    reference_pdf = Path(__file__).parent / "report_digital.pdf"
    if reference_pdf.exists():
        print("✓ Reference PDF (report_digital.pdf) found")
    else:
        print("⚠️  Reference PDF (report_digital.pdf) not found")
        print("   This file is used for PDF comparison")


def main():
    """Main setup function"""
    print("🚀 DHIS2 PDF Automation Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        sys.exit(1)
    
    # Setup backend
    if not setup_backend():
        print("❌ Backend setup failed")
        sys.exit(1)
    
    # Setup frontend
    if not setup_frontend():
        print("❌ Frontend setup failed")
        sys.exit(1)
    
    # Check environment
    check_environment()
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your DHIS2 credentials and API keys")
    print("2. Place your reference PDF as 'report_digital.pdf' in the project root")
    print("3. Start the backend: cd backend && python manage.py runserver")
    print("4. Start the frontend: cd frontend && npm start")
    print("5. Open http://localhost:3000 in your browser")
    
    print("\n🔧 Optional: Install browser automation dependencies:")
    print("   playwright install")


if __name__ == "__main__":
    main()