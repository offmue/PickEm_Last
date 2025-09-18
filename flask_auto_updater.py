#!/usr/bin/env python3
"""
Flask Integration for Automatic NFL Updates
Adds auto-update endpoints and background tasks to the main Flask app
"""

import os
import threading
import time
from datetime import datetime, timedelta
from flask import jsonify
import logging

# Import our auto updater
from auto_nfl_updater import NFLAutoUpdater

logger = logging.getLogger(__name__)

class FlaskNFLUpdater:
    def __init__(self, app, db_path):
        self.app = app
        self.db_path = db_path
        self.updater = NFLAutoUpdater(db_path)
        self.last_update = None
        self.update_thread = None
        self.running = False
        
        # Add routes to Flask app
        self._add_routes()
        
        # Start background updater
        self._start_background_updater()
    
    def _add_routes(self):
        """Add auto-update routes to Flask app"""
        
        @self.app.route('/api/nfl-auto-update', methods=['POST'])
        def manual_nfl_update():
            """Manual trigger for NFL data update"""
            try:
                results = self.updater.run_auto_update()
                self.last_update = datetime.now()
                
                return jsonify({
                    'success': results['success'],
                    'message': 'NFL data update completed',
                    'details': {
                        'teams_updated': results['teams_updated'],
                        'new_weeks_added': results['new_weeks_added'],
                        'results_updated': results['results_updated'],
                        'errors': results['errors']
                    },
                    'last_update': self.last_update.isoformat()
                })
                
            except Exception as e:
                logger.error(f"Manual NFL update failed: {e}")
                return jsonify({
                    'success': False,
                    'message': f'NFL update failed: {str(e)}'
                }), 500
        
        @self.app.route('/api/nfl-update-status')
        def nfl_update_status():
            """Get status of NFL auto-updater"""
            try:
                available_weeks = self.updater.get_available_weeks_from_espn()
                db_weeks = self.updater.get_weeks_in_database()
                
                return jsonify({
                    'success': True,
                    'status': {
                        'running': self.running,
                        'last_update': self.last_update.isoformat() if self.last_update else None,
                        'available_weeks': available_weeks,
                        'database_weeks': db_weeks,
                        'missing_weeks': [w for w in available_weeks if w not in db_weeks]
                    }
                })
                
            except Exception as e:
                logger.error(f"NFL status check failed: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Status check failed: {str(e)}'
                }), 500
    
    def _start_background_updater(self):
        """Start background thread for automatic updates"""
        if not self.running:
            self.running = True
            self.update_thread = threading.Thread(target=self._background_update_loop, daemon=True)
            self.update_thread.start()
            logger.info("🔄 NFL auto-updater background thread started")
    
    def _background_update_loop(self):
        """Background loop for automatic NFL updates"""
        while self.running:
            try:
                current_time = datetime.now()
                
                # Check if it's time for an update
                should_update = False
                
                # Update conditions:
                # 1. Never updated before
                if self.last_update is None:
                    should_update = True
                    logger.info("First-time NFL data update")
                
                # 2. Daily update at 6 AM (for new weeks and results)
                elif (current_time.hour == 6 and 
                      self.last_update.date() < current_time.date()):
                    should_update = True
                    logger.info("Daily NFL data update (6 AM)")
                
                # 3. Tuesday update at 10 AM (new week release)
                elif (current_time.weekday() == 1 and  # Tuesday
                      current_time.hour == 10 and
                      self.last_update < current_time.replace(hour=10, minute=0, second=0)):
                    should_update = True
                    logger.info("Weekly NFL data update (Tuesday 10 AM)")
                
                # 4. Post-game updates (Monday nights and Sunday/Monday after games)
                elif (current_time.weekday() in [0, 1] and  # Monday or Tuesday
                      current_time.hour >= 23 and  # After 11 PM
                      self.last_update < current_time.replace(hour=23, minute=0, second=0)):
                    should_update = True
                    logger.info("Post-game NFL results update")
                
                # Perform update if needed
                if should_update:
                    logger.info("🔄 Running automatic NFL data update...")
                    results = self.updater.run_auto_update()
                    self.last_update = current_time
                    
                    if results['success']:
                        if results['new_weeks_added']:
                            logger.info(f"✅ Auto-update: Added weeks {results['new_weeks_added']}")
                        if results['results_updated']:
                            logger.info("✅ Auto-update: Game results updated")
                    else:
                        logger.warning(f"⚠️ Auto-update completed with errors: {results['errors']}")
                
                # Sleep for 1 hour before next check
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"Background NFL update error: {e}")
                time.sleep(3600)  # Wait 1 hour before retrying
    
    def stop(self):
        """Stop the background updater"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        logger.info("🛑 NFL auto-updater stopped")

# Integration function for main Flask app
def integrate_nfl_auto_updater(app):
    """
    Integrate NFL auto-updater into Flask app
    Call this function in your main app.py
    """
    try:
        # Get database path from app config or environment
        db_path = getattr(app, 'config', {}).get('DATABASE_PATH')
        if not db_path:
            # Try to determine database path
            if hasattr(app, 'config') and 'SQLALCHEMY_DATABASE_URI' in app.config:
                db_uri = app.config['SQLALCHEMY_DATABASE_URI']
                if db_uri.startswith('sqlite:///'):
                    db_path = db_uri.replace('sqlite:///', '')
                else:
                    logger.warning("Non-SQLite database detected, NFL auto-updater may not work")
                    return None
            else:
                # Default path
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nfl_pickem.db')
        
        # Create and return the updater
        flask_updater = FlaskNFLUpdater(app, db_path)
        logger.info(f"✅ NFL auto-updater integrated with database: {db_path}")
        return flask_updater
        
    except Exception as e:
        logger.error(f"Failed to integrate NFL auto-updater: {e}")
        return None

# Example usage in main Flask app:
"""
from flask_auto_updater import integrate_nfl_auto_updater

app = Flask(__name__)
# ... your existing Flask setup ...

# Add NFL auto-updater
nfl_updater = integrate_nfl_auto_updater(app)

# Optional: Manual update on startup
if nfl_updater:
    @app.before_first_request
    def update_nfl_on_startup():
        try:
            nfl_updater.updater.run_auto_update()
        except Exception as e:
            logger.warning(f"Startup NFL update failed: {e}")
"""

