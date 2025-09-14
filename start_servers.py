#!/usr/bin/env python3
"""
Script to start both frontend and backend servers for DHIS2 automation
"""

import os
import subprocess
import sys
import time
import threading
from pathlib import Path


def run_backend():
    """Run Django backend server"""
    backend_dir = Path(__file__).parent / "backend"
    
    print("🔧 Starting Django backend server...")
    print("   URL: http://localhost:8000")
    
    os.chdir(backend_dir)
    subprocess.run([sys.executable, "manage.py", "runserver", "8000"])


def run_frontend():
    """Run React frontend server"""
    frontend_dir = Path(__file__).parent / "frontend"
    
    print("⚛️  Starting React frontend server...")
    print("   URL: http://localhost:3000")
    
    # Wait a bit for backend to start
    time.sleep(3)
    
    os.chdir(frontend_dir)
    subprocess.run(["npm", "start"])


def main():
    """Start both servers"""
    print("🚀 Starting DHIS2 PDF Automation Servers")
    print("=" * 50)
    
    # Check if setup was run
    backend_dir = Path(__file__).parent / "backend"
    frontend_dir = Path(__file__).parent / "frontend"
    
    if not (backend_dir / "db.sqlite3").exists():
        print("❌ Backend not set up. Please run: python setup_project.py")
        sys.exit(1)
    
    if not (frontend_dir / "node_modules").exists():
        print("❌ Frontend not set up. Please run: python setup_project.py")
        sys.exit(1)
    
    # Start backend in a separate thread
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    
    # Start frontend (this will block)
    try:
        run_frontend()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down servers...")
        sys.exit(0)


if __name__ == "__main__":
    main()