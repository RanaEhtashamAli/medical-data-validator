#!/usr/bin/env python3
"""
Launcher script for the Medical Data Validator API Server.
This script ensures proper imports and launches the API server.
"""

import sys
import os
from flask import redirect

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    """Launch the API server."""
    try:
        from medical_data_validator.dashboard.app import create_dashboard_app
        import argparse
        
        parser = argparse.ArgumentParser(description='Medical Data Validator API Server')
        parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
        parser.add_argument('--port', type=int, default=8000, help='Port to bind to (default: 8000)')
        parser.add_argument('--debug', action='store_true', help='Enable debug mode')
        
        args = parser.parse_args()
        
        app = create_dashboard_app()
        
        # Add redirect for Swagger UI compatibility
        @app.route('/swagger.json')
        def root_swagger_json():
            return redirect('/docs/swagger.json')
        
        if args.debug:
            app.config['DEBUG'] = True
            print("🐛 Starting API server in debug mode...")
        else:
            print("🚀 Starting Medical Data Validator API Server...")
        
        print(f"🔌 API will be available at: http://{args.host}:{args.port}")
        print(f"📊 Dashboard will be available at: http://{args.host}:{args.port}")
        print(f"🏥 Health check: http://{args.host}:{args.port}/api/health")
        print("⏹️  Press Ctrl+C to stop the server")
        print("-" * 60)
        
        app.run(host=args.host, port=args.port, debug=args.debug)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all dependencies are installed:")
        print("   pip install -r requirements.txt")
        print("   pip install -r requirements-api.txt")
        return 1
    except KeyboardInterrupt:
        print("\n👋 API server stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Error starting API server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 