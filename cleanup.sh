#!/bin/bash
# DHIS Repository Cleanup Script

echo "🧹 Cleaning DHIS repository..."

# Remove log files
echo "Removing log files..."
find . -name "*.log" -not -path "./logs/*" -delete
find logs/ -name "*.log" -mtime +7 -delete 2>/dev/null || true

# Remove temporary files
echo "Removing temporary files..."
rm -f *.pdf output.json lol.ipynb monthly_report.zip

# Remove database files
echo "Removing database files..."
find . -name "db.sqlite3" -delete
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Clean backend screenshots
echo "Cleaning screenshots..."
find backend/screenshots -name "*.png" -mtime +7 -delete 2>/dev/null || true

# Clean node_modules if present
if [ -d "frontend/node_modules" ]; then
    echo "Cleaning frontend node_modules..."
    rm -rf frontend/node_modules
fi

# Create necessary directories
mkdir -p logs docs configs

echo "✅ Repository cleaned!"