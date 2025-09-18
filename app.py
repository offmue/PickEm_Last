#!/usr/bin/env python3
"""
NFL PickEm 2025/2026 - Clean Production Version
Fixed login system and pick functionality for Render deployment
"""

import os
import logging
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'nfl_pickem_2025_secret_key_very_secure')

# Database configuration
database_url = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.abspath("nfl_pickem_robust.db")}')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Vienna timezone
VIENNA_TZ = pytz.timezone('Europe/Vienna')

# Database Models - Angepasst an robuste DB-Struktur
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().isoformat())
    last_login = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)

class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    away_team_id = db.Column(db.Integer, nullable=False)
    away_team_name = db.Column(db.String(100), nullable=False)
    home_team_id = db.Column(db.Integer, nullable=False)
    home_team_name = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.String(50), nullable=False)
    away_score = db.Column(db.Integer)
    home_score = db.Column(db.Integer)
    winner_team_id = db.Column(db.Integer)
    is_completed = db.Column(db.Boolean, default=False)
    source = db.Column(db.String(50), default='nfl_official')
    last_sync = db.Column(db.String(50))
    created_at = db.Column(db.String(50), default=lambda: datetime.now().isoformat())

class HistoricalPick(db.Model):
    __tablename__ = 'historical_picks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    week = db.Column(db.Integer, nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    chosen_team_id = db.Column(db.Integer, nullable=False)
    chosen_team_name = db.Column(db.String(100), nullable=False)
    is_winner = db.Column(db.Boolean)
    points_earned = db.Column(db.Integer, default=0)
    pick_time = db.Column(db.String(50), nullable=False)
    week_completed = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref='historical_picks')
    match = db.relationship('Match', backref='historical_picks')

class TeamUsage(db.Model):
    __tablename__ = 'team_usage'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    team_id = db.Column(db.Integer, nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    usage_type = db.Column(db.String(20), nullable=False)  # 'winner' or 'loser'
    week_used = db.Column(db.Integer, nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().isoformat())
    
    user = db.relationship('User', backref='team_usage')
    match = db.relationship('Match', backref='team_usage')

# Legacy Pick model for current week picks
class Pick(db.Model):
    __tablename__ = 'picks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    chosen_team_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().isoformat())
    is_correct = db.Column(db.Boolean)
    
    user = db.relationship('User', backref='picks')
    match = db.relationship('Match', backref='picks')

# Helper functions
def convert_to_vienna_time(utc_time):
    """Convert UTC time to Vienna timezone"""
    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=timezone.utc)
    return utc_time.astimezone(VIENNA_TZ)

def format_vienna_time(utc_time):
    """Format time for Vienna timezone display"""
    vienna_time = convert_to_vienna_time(utc_time)
    return vienna_time.strftime('%a, %d.%m., %H:%M')

# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """Login API endpoint with simple password check"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        # Simple password check for the 4 users
        valid_users = {
            'Manuel': 'Manuel1',
            'Daniel': 'Daniel1', 
            'Raff': 'Raff1',
            'Haunschi': 'Haunschi1'
        }
        
        if username in valid_users and password == valid_users[username]:
            # Get user from database
            user = User.query.filter_by(username=username).first()
            if user:
                session['user_id'] = user.id
                session['username'] = user.username
                logger.info(f"✅ User {username} logged in successfully")
                return jsonify({
                    'success': True, 
                    'message': 'Login erfolgreich',
                    'user': {
                        'id': user.id,
                        'username': user.username
                    }
                })
        
        logger.warning(f"❌ Failed login attempt for {username}")
        return jsonify({'success': False, 'message': 'Ungültige Anmeldedaten'})
            
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server-Fehler beim Login'})

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Logout API endpoint"""
    try:
        username = session.get('username', 'Unknown')
        session.clear()
        logger.info(f"✅ User {username} logged out")
        return jsonify({'success': True, 'message': 'Logout erfolgreich'})
        
    except Exception as e:
        logger.error(f"❌ Logout error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server-Fehler beim Logout'})

@app.route('/api/matches')
def get_matches():
    """Get matches for specified week"""
    try:
        week = request.args.get('week', 3, type=int)
        matches = Match.query.filter_by(week=week).all()
        
        matches_data = []
        for match in matches:
            # Parse start_time string to datetime for formatting
            try:
                if isinstance(match.start_time, str):
                    start_time_dt = datetime.fromisoformat(match.start_time.replace('Z', '+00:00'))
                else:
                    start_time_dt = match.start_time
                
                # Convert to Vienna time
                vienna_time = convert_to_vienna_time(start_time_dt)
                start_time_display = vienna_time.strftime('%a, %d.%m., %H:%M')
            except:
                start_time_display = match.start_time
            
            match_data = {
                'id': match.id,
                'week': match.week,
                'home_team': {
                    'id': match.home_team_id,
                    'name': match.home_team_name,
                    'abbreviation': match.home_team_name[:3].upper(),  # Simple abbreviation
                    'logo_url': getattr(match, 'home_team_logo', 'https://a.espncdn.com/i/teamlogos/nfl/500/default.png')
                },
                'away_team': {
                    'id': match.away_team_id,
                    'name': match.away_team_name,
                    'abbreviation': match.away_team_name[:3].upper(),  # Simple abbreviation
                    'logo_url': getattr(match, 'away_team_logo', 'https://a.espncdn.com/i/teamlogos/nfl/500/default.png')
                },
                'start_time': match.start_time,
                'start_time_display': start_time_display,
                'is_completed': match.is_completed or False,
                'home_score': match.home_score,
                'away_score': match.away_score,
                'winner_team_id': match.winner_team_id
            }
            matches_data.append(match_data)
        
        logger.info(f"✅ Loaded {len(matches_data)} matches for week {week}")
        return jsonify({
            'success': True,
            'week': week,
            'matches': matches_data
        })
        
    except Exception as e:
        logger.error(f"❌ Matches error: {str(e)}")
        return jsonify({'success': False, 'message': 'Fehler beim Laden der Spiele'})

@app.route('/api/picks/create', methods=['POST'])
def create_pick():
    """Create a new pick"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not logged in'})
        
        data = request.get_json()
        user_id = session['user_id']
        match_id = data.get('match_id')
        chosen_team_id = data.get('chosen_team_id')
        
        if not match_id or not chosen_team_id:
            return jsonify({'success': False, 'message': 'Missing match_id or chosen_team_id'})
        
        # Check if match exists
        match = Match.query.get(match_id)
        if not match:
            return jsonify({'success': False, 'message': 'Match not found'})
        
        # Get team name from match data
        if chosen_team_id == match.home_team_id:
            chosen_team_name = match.home_team_name
        elif chosen_team_id == match.away_team_id:
            chosen_team_name = match.away_team_name
        else:
            return jsonify({'success': False, 'message': 'Invalid team selection'})
        
        # Check if pick already exists for this user and match
        existing_pick = Pick.query.filter_by(user_id=user_id, match_id=match_id).first()
        if existing_pick:
            # Update existing pick
            existing_pick.chosen_team_id = chosen_team_id
            existing_pick.created_at = datetime.now().isoformat()
        else:
            # Create new pick
            new_pick = Pick(
                user_id=user_id,
                match_id=match_id,
                chosen_team_id=chosen_team_id,
                created_at=datetime.now().isoformat()
            )
            db.session.add(new_pick)
        
        db.session.commit()
        
        logger.info(f"✅ Pick saved: User {user_id} picked {chosen_team_name} for match {match_id}")
        
        return jsonify({
            'success': True,
            'message': f'Pick gespeichert: {chosen_team_name}',
            'pick': {
                'match_id': match_id,
                'chosen_team_id': chosen_team_id,
                'chosen_team_name': chosen_team_name
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Pick creation error: {str(e)}")
        return jsonify({'success': False, 'message': 'Fehler beim Speichern des Picks'})

@app.route('/api/dashboard')
def get_dashboard():
    """Get dashboard data for current user"""
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not logged in'})
        
        user_id = session['user_id']
        username = session['username']
        
        # Get user picks
        picks = Pick.query.filter_by(user_id=user_id).all()
        
        # Calculate stats
        total_picks = len(picks)
        correct_picks = len([p for p in picks if p.is_correct])
        points = correct_picks
        
        # Get current week (simplified to 3 for now)
        current_week = 3
        
        # Get recent picks
        recent_picks = []
        for pick in picks[-3:]:  # Last 3 picks
            # Get team name from match data
            match = pick.match
            if pick.chosen_team_id == match.home_team_id:
                team_name = match.home_team_name
            elif pick.chosen_team_id == match.away_team_id:
                team_name = match.away_team_name
            else:
                team_name = "Unknown Team"
            
            result = "✅" if pick.is_correct else "❌" if pick.is_correct is False else "⏳"
            recent_picks.append(f"W{pick.match.week}: {team_name} {result}")
        
        return jsonify({
            'success': True,
            'data': {
                'username': username,
                'current_week': current_week,
                'points': points,
                'total_picks': total_picks,
                'correct_picks': correct_picks,
                'recent_picks': recent_picks,
                'team_usage': {
                    'winners': [],
                    'losers': []
                }
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Dashboard error: {str(e)}")
        return jsonify({'success': False, 'message': 'Fehler beim Laden der Dashboard-Daten'})

@app.route('/api/leaderboard')
def get_leaderboard():
    """Get leaderboard data"""
    try:
        users = User.query.all()
        leaderboard = []
        
        for user in users:
            picks = Pick.query.filter_by(user_id=user.id).all()
            correct_picks = len([p for p in picks if p.is_correct])
            total_picks = len(picks)
            
            leaderboard.append({
                'username': user.username,
                'points': correct_picks,
                'total_picks': total_picks,
                'correct_picks': correct_picks
            })
        
        # Sort by points descending
        leaderboard.sort(key=lambda x: x['points'], reverse=True)
        
        # Add rankings
        for i, player in enumerate(leaderboard):
            player['rank'] = i + 1
        
        return jsonify({
            'success': True,
            'leaderboard': leaderboard
        })
        
    except Exception as e:
        logger.error(f"❌ Leaderboard error: {str(e)}")
        return jsonify({'success': False, 'message': 'Fehler beim Laden des Leaderboards'})

@app.route('/api/all-picks')
def get_all_picks():
    """Get all picks from all users"""
    try:
        picks = Pick.query.join(User).join(Match).all()
        
        picks_data = []
        for pick in picks:
            # Get team name from match data
            match = pick.match
            if pick.chosen_team_id == match.home_team_id:
                team_name = match.home_team_name
            elif pick.chosen_team_id == match.away_team_id:
                team_name = match.away_team_name
            else:
                team_name = "Unknown Team"
            
            result = "✅" if pick.is_correct else "❌" if pick.is_correct is False else "⏳"
            picks_data.append({
                'week': pick.match.week,
                'username': pick.user.username,
                'chosen_team': team_name,
                'result': result,
                'created_at': pick.created_at.strftime('%d.%m.%Y %H:%M')
            })
        
        # Sort by week descending, then by username
        picks_data.sort(key=lambda x: (-x['week'], x['username']))
        
        return jsonify({
            'success': True,
            'picks': picks_data
        })
        
    except Exception as e:
        logger.error(f"❌ All picks error: {str(e)}")
        return jsonify({'success': False, 'message': 'Fehler beim Laden aller Picks'})

# Initialize database
def init_db():
    """Initialize database with tables and sample data"""
    with app.app_context():
        db.create_all()
        
        # Check if users exist
        if User.query.count() == 0:
            users = [
                User(username='Manuel', password='Manuel1'),
                User(username='Daniel', password='Daniel1'),
                User(username='Raff', password='Raff1'),
                User(username='Haunschi', password='Haunschi1')
            ]
            for user in users:
                db.session.add(user)
            db.session.commit()
            logger.info("✅ Users created")

# Alias for Render deployment
initialize_database = init_db

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
