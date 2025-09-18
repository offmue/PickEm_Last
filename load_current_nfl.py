#!/usr/bin/env python3
"""
Load current NFL games from ESPN API
Simple script to populate database with real NFL data
"""

import requests
import json
import sqlite3
from datetime import datetime
import pytz

# Vienna timezone
VIENNA_TZ = pytz.timezone('Europe/Vienna')

def load_current_nfl_games(db_path='nfl_pickem.db'):
    """
    Load current NFL games from ESPN API
    """
    print("🏈 Loading current NFL games from ESPN...")
    
    try:
        # Get current NFL games
        url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        params = {'seasontype': 2}  # Regular season
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if 'events' not in data:
            print("❌ No events found in ESPN response")
            return False
        
        games = []
        teams = {}
        
        for event in data['events']:
            try:
                game_id = int(event['id'])
                week_num = event.get('week', {}).get('number', 3)
                
                # Get teams
                competitors = event['competitions'][0]['competitors']
                away_team = next(c for c in competitors if c['homeAway'] == 'away')
                home_team = next(c for c in competitors if c['homeAway'] == 'home')
                
                # Store team info
                for team_data in [away_team, home_team]:
                    team = team_data['team']
                    team_id = int(team['id'])
                    
                    # Get logo URL
                    logo_url = ''
                    if 'logos' in team and len(team['logos']) > 0:
                        logo_url = team['logos'][0]['href']
                    
                    teams[team_id] = {
                        'id': team_id,
                        'name': team['displayName'],
                        'abbreviation': team['abbreviation'],
                        'logo_url': logo_url
                    }
                
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
                    'id': game_id,
                    'week': week_num,
                    'away_team_id': int(away_team['team']['id']),
                    'home_team_id': int(home_team['team']['id']),
                    'game_time': vienna_time.strftime('%a., %d.%m, %H:%M'),
                    'is_completed': is_completed,
                    'away_score': away_score,
                    'home_score': home_score
                }
                
                games.append(game_info)
                
            except Exception as e:
                print(f"⚠️ Error processing game {event.get('id', 'unknown')}: {e}")
                continue
        
        print(f"📊 Found {len(games)} games and {len(teams)} teams")
        
        # Update database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                abbreviation TEXT NOT NULL,
                logo_url TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY,
                week INTEGER NOT NULL,
                away_team_id INTEGER NOT NULL,
                home_team_id INTEGER NOT NULL,
                game_time TEXT NOT NULL,
                is_completed BOOLEAN DEFAULT 0,
                away_score INTEGER,
                home_score INTEGER,
                FOREIGN KEY (away_team_id) REFERENCES teams (id),
                FOREIGN KEY (home_team_id) REFERENCES teams (id)
            )
        ''')
        
        # Insert teams
        for team in teams.values():
            cursor.execute('''
                INSERT OR REPLACE INTO teams (id, name, abbreviation, logo_url)
                VALUES (?, ?, ?, ?)
            ''', (team['id'], team['name'], team['abbreviation'], team['logo_url']))
        
        # Insert games
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
        
        print(f"✅ Successfully loaded {len(games)} NFL games into database!")
        
        # Show sample games
        print("\n📋 Sample games:")
        for game in games[:5]:
            away_team = teams[game['away_team_id']]['abbreviation']
            home_team = teams[game['home_team_id']]['abbreviation']
            print(f"   Week {game['week']}: {away_team} @ {home_team} - {game['game_time']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading NFL games: {e}")
        return False

if __name__ == '__main__':
    import sys
    
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'nfl_pickem.db'
    
    print(f"Database: {db_path}")
    print("-" * 50)
    
    success = load_current_nfl_games(db_path)
    
    if success:
        print("\n🎉 NFL data loading completed successfully!")
    else:
        print("\n❌ NFL data loading failed!")

