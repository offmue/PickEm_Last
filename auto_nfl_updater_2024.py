#!/usr/bin/env python3
"""
Automatic NFL Data Updater for PickEm 2024 Season
Automatically detects and adds new NFL weeks as they become available
Runs without manual intervention throughout the season
"""

import requests
import json
import sqlite3
from datetime import datetime, timezone, timedelta
import pytz
import time
import logging
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Vienna timezone
VIENNA_TZ = pytz.timezone('Europe/Vienna')

class NFLAutoUpdater:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.season = 2024  # Current NFL season
        
    def get_available_weeks_from_espn(self) -> List[int]:
        """
        Query ESPN API to find which weeks are currently available
        """
        try:
            # Get current season calendar from ESPN
            url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            
            # Try to get a broad date range to see what's available
            season_start = datetime(self.season, 9, 1)  # NFL season starts in September
            season_end = datetime(self.season + 1, 2, 15)  # Season ends in February
            
            params = {
                'dates': f"{season_start.strftime('%Y%m%d')}-{season_end.strftime('%Y%m%d')}",
                'seasontype': 2,  # Regular season
                'limit': 1000
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            available_weeks = set()
            
            if 'events' in data:
                for event in data['events']:
                    week_info = event.get('week', {})
                    if 'number' in week_info:
                        week_num = week_info['number']
                        if 1 <= week_num <= 18:  # Regular season weeks
                            available_weeks.add(week_num)
            
            # If no events found, try week-by-week approach
            if not available_weeks:
                logger.info("No events found in broad query, trying week-by-week...")
                available_weeks = self._check_weeks_individually()
            
            available_weeks = sorted(list(available_weeks))
            logger.info(f"Available weeks from ESPN: {available_weeks}")
            return available_weeks
            
        except Exception as e:
            logger.error(f"Error getting available weeks from ESPN: {e}")
            # Fallback: assume current weeks based on date
            return self._estimate_available_weeks()
    
    def _check_weeks_individually(self) -> set:
        """
        Check each week individually to see if it's available
        """
        available_weeks = set()
        
        # Check weeks 1-18
        for week in range(1, 19):
            try:
                # Calculate week dates based on NFL 2024 schedule
                # NFL 2024 season started September 5, 2024 (Thursday)
                season_start = datetime(2024, 9, 5)  # First Thursday of September 2024
                week_start = season_start + timedelta(days=(week-1)*7)
                week_end = week_start + timedelta(days=6)
                
                url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
                params = {
                    'dates': f"{week_start.strftime('%Y%m%d')}-{week_end.strftime('%Y%m%d')}",
                    'seasontype': 2,
                    'week': week
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'events' in data and len(data['events']) > 0:
                        available_weeks.add(week)
                        logger.info(f"Week {week}: Available ({len(data['events'])} games)")
                    else:
                        logger.info(f"Week {week}: No games found")
                else:
                    logger.info(f"Week {week}: API error {response.status_code}")
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"Error checking week {week}: {e}")
                continue
        
        return available_weeks
    
    def _estimate_available_weeks(self) -> List[int]:
        """
        Estimate which weeks should be available based on current date
        """
        current_date = datetime.now()
        season_start = datetime(2024, 9, 5)  # NFL 2024 season start
        
        if current_date < season_start:
            # Pre-season: no weeks available yet
            return []
        
        # Calculate weeks since season start
        days_since_start = (current_date - season_start).days
        weeks_since_start = min(days_since_start // 7 + 1, 18)
        
        # Add buffer for schedule release (usually 2-3 weeks ahead)
        available_weeks = list(range(1, min(weeks_since_start + 3, 19)))
        
        logger.info(f"Estimated available weeks: {available_weeks}")
        return available_weeks
    
    def get_weeks_in_database(self) -> List[int]:
        """
        Get which weeks are already in the database
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT DISTINCT week FROM matches ORDER BY week')
            db_weeks = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            logger.info(f"Weeks in database: {db_weeks}")
            return db_weeks
            
        except Exception as e:
            logger.error(f"Error getting weeks from database: {e}")
            return []
    
    def fetch_week_games(self, week: int) -> List[Dict]:
        """
        Fetch all games for a specific week from ESPN API
        """
        try:
            # Calculate date range for the week based on NFL 2024 schedule
            season_start = datetime(2024, 9, 5)  # NFL 2024 season start
            week_start = season_start + timedelta(days=(week-1)*7)
            week_end = week_start + timedelta(days=6)
            
            url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            params = {
                'dates': f"{week_start.strftime('%Y%m%d')}-{week_end.strftime('%Y%m%d')}",
                'seasontype': 2,
                'week': week
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            games = []
            
            if 'events' in data:
                for event in data['events']:
                    try:
                        game_id = event['id']
                        week_num = event.get('week', {}).get('number', week)
                        
                        # Get teams
                        competitors = event['competitions'][0]['competitors']
                        away_team = next(c for c in competitors if c['homeAway'] == 'away')
                        home_team = next(c for c in competitors if c['homeAway'] == 'home')
                        
                        # Get game time
                        game_date = event['date']
                        game_time = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
                        vienna_time = game_time.astimezone(VIENNA_TZ)
                        
                        # Check if game is completed
                        status = event['status']
                        is_completed = status['type']['completed']
                        
                        # Get scores if available
                        away_score = None
                        home_score = None
                        if is_completed:
                            away_score = int(away_team.get('score', 0))
                            home_score = int(home_team.get('score', 0))
                        
                        game_info = {
                            'id': int(game_id),
                            'week': week_num,
                            'away_team_id': int(away_team['team']['id']),
                            'home_team_id': int(home_team['team']['id']),
                            'game_time': vienna_time.isoformat(),
                            'is_completed': is_completed,
                            'away_score': away_score,
                            'home_score': home_score
                        }
                        
                        games.append(game_info)
                        
                    except Exception as e:
                        logger.warning(f"Error processing game {event.get('id', 'unknown')}: {e}")
                        continue
            
            logger.info(f"Week {week}: Fetched {len(games)} games")
            return games
            
        except Exception as e:
            logger.error(f"Error fetching Week {week}: {e}")
            return []
    
    def update_teams_in_database(self) -> bool:
        """
        Update teams table with latest data from ESPN
        """
        try:
            url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            teams = []
            
            if 'sports' in data and len(data['sports']) > 0:
                leagues = data['sports'][0]['leagues']
                if len(leagues) > 0 and 'teams' in leagues[0]:
                    for team_data in leagues[0]['teams']:
                        team = team_data['team']
                        
                        # Get team logo URL
                        logo_url = ''
                        if 'logos' in team and len(team['logos']) > 0:
                            logo_url = team['logos'][0]['href']
                        
                        teams.append({
                            'id': int(team['id']),
                            'name': team['displayName'],
                            'abbreviation': team['abbreviation'],
                            'logo_url': logo_url
                        })
            
            # Update database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for team in teams:
                cursor.execute('''
                    INSERT OR REPLACE INTO teams (id, name, abbreviation, logo_url)
                    VALUES (?, ?, ?, ?)
                ''', (team['id'], team['name'], team['abbreviation'], team['logo_url']))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated {len(teams)} teams in database")
            return True
            
        except Exception as e:
            logger.error(f"Error updating teams: {e}")
            return False
    
    def add_week_to_database(self, week: int) -> bool:
        """
        Add a specific week's games to the database
        """
        try:
            games = self.fetch_week_games(week)
            if not games:
                logger.warning(f"No games found for Week {week}")
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Remove existing games for this week (in case of updates)
            cursor.execute('DELETE FROM matches WHERE week = ?', (week,))
            
            # Insert new games
            for game in games:
                cursor.execute('''
                    INSERT OR REPLACE INTO matches 
                    (id, week, away_team_id, home_team_id, game_time, is_completed, away_score, home_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    game['id'], game['week'], game['away_team_id'], game['home_team_id'],
                    game['game_time'], game['is_completed'], game['away_score'], game['home_score']
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Added Week {week} to database ({len(games)} games)")
            return True
            
        except Exception as e:
            logger.error(f"Error adding Week {week} to database: {e}")
            return False
    
    def update_game_results(self) -> bool:
        """
        Update results for completed games
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get weeks with incomplete games
            cursor.execute('SELECT DISTINCT week FROM matches WHERE is_completed = 0')
            weeks_to_check = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            updated_games = 0
            for week in weeks_to_check:
                games = self.fetch_week_games(week)
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for game in games:
                    if game['is_completed']:
                        cursor.execute('''
                            UPDATE matches 
                            SET is_completed = ?, away_score = ?, home_score = ?
                            WHERE id = ?
                        ''', (game['is_completed'], game['away_score'], game['home_score'], game['id']))
                        updated_games += 1
                
                conn.commit()
                conn.close()
                time.sleep(0.5)  # Rate limiting
            
            if updated_games > 0:
                logger.info(f"✅ Updated results for {updated_games} completed games")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating game results: {e}")
            return False
    
    def run_auto_update(self) -> Dict[str, any]:
        """
        Main auto-update function - checks for new weeks and updates results
        """
        logger.info("🏈 Starting automatic NFL data update...")
        
        results = {
            'success': True,
            'teams_updated': False,
            'new_weeks_added': [],
            'results_updated': False,
            'errors': []
        }
        
        try:
            # 1. Update teams (occasionally)
            try:
                results['teams_updated'] = self.update_teams_in_database()
            except Exception as e:
                results['errors'].append(f"Teams update failed: {e}")
            
            # 2. Check for new weeks
            available_weeks = self.get_available_weeks_from_espn()
            db_weeks = self.get_weeks_in_database()
            
            new_weeks = [w for w in available_weeks if w not in db_weeks]
            
            # 3. Add new weeks
            for week in new_weeks:
                try:
                    if self.add_week_to_database(week):
                        results['new_weeks_added'].append(week)
                    time.sleep(1)  # Rate limiting
                except Exception as e:
                    results['errors'].append(f"Failed to add Week {week}: {e}")
            
            # 4. Update game results
            try:
                results['results_updated'] = self.update_game_results()
            except Exception as e:
                results['errors'].append(f"Results update failed: {e}")
            
            # Summary
            if results['new_weeks_added']:
                logger.info(f"✅ Added new weeks: {results['new_weeks_added']}")
            else:
                logger.info("ℹ️ No new weeks to add")
            
            if results['errors']:
                logger.warning(f"⚠️ Errors occurred: {results['errors']}")
                results['success'] = False
            
            logger.info("🎉 Automatic NFL data update completed")
            
        except Exception as e:
            logger.error(f"❌ Auto-update failed: {e}")
            results['success'] = False
            results['errors'].append(str(e))
        
        return results

def main():
    """
    Command line interface for the auto updater
    """
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python auto_nfl_updater_2024.py <database_path> [weeks]")
        print("Examples:")
        print("  python auto_nfl_updater_2024.py nfl_pickem.db")
        print("  python auto_nfl_updater_2024.py nfl_pickem.db 3")
        print("  python auto_nfl_updater_2024.py nfl_pickem.db 1-5")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    # Parse weeks argument
    weeks_to_fetch = None
    if len(sys.argv) > 2:
        weeks_arg = sys.argv[2]
        if '-' in weeks_arg:
            start, end = map(int, weeks_arg.split('-'))
            weeks_to_fetch = list(range(start, end + 1))
        else:
            weeks_to_fetch = [int(weeks_arg)]
    
    print(f"🏈 NFL API Integration for PickEm 2024 Season")
    print(f"Database: {db_path}")
    print(f"Weeks: {weeks_to_fetch or 'All available'}")
    print("-" * 50)
    
    updater = NFLAutoUpdater(db_path)
    results = updater.run_auto_update()
    
    if results['success']:
        print("\n🎉 NFL data integration completed successfully!")
        if results['new_weeks_added']:
            print(f"📅 New weeks added: {results['new_weeks_added']}")
    else:
        print("\n❌ NFL data integration completed with errors!")
        for error in results['errors']:
            print(f"   • {error}")

if __name__ == '__main__':
    main()

