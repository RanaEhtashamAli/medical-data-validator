#!/usr/bin/env python3
"""
Launcher script for the Medical Data Validator Dashboard.
This script ensures proper imports and launches the dashboard.
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    """Launch the dashboard."""
    try:
        from medical_data_validator.dashboard.app import run_dashboard
        print("🚀 Starting Medical Data Validator Dashboard...")
        print("📊 Dashboard will be available at: http://localhost:5000")
        print("🔌 API will be available at: http://localhost:5000/api")
        print("📱 Dash interface will be available at: http://localhost:5000/dash")
        print("⏹️  Press Ctrl+C to stop the server")
        print("-" * 60)
        run_dashboard()
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all dependencies are installed:")
        print("   pip install -r requirements.txt")
        print("   pip install -r requirements-api.txt")
        return 1
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 