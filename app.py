#!/usr/bin/env python3
"""
NFL PickEm 2025/2026 - Enhanced Version with Historical Week View
Complete production version with auto-updates and week selection
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

# Database configuration - works for both local SQLite and production PostgreSQL
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    # Local development - create SQLite database
    database_url = f'sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), "nfl_pickem.db")}'
else:
    # Production - handle PostgreSQL URL format
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Vienna timezone
VIENNA_TZ = pytz.timezone('Europe/Vienna')

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().isoformat())
    last_login = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)

class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    abbreviation = db.Column(db.String(10), nullable=False)
    logo_url = db.Column(db.String(200))

class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    game_time = db.Column(db.String(50), nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    away_score = db.Column(db.Integer)
    home_score = db.Column(db.Integer)
    
    away_team = db.relationship('Team', foreign_keys=[away_team_id])
    home_team = db.relationship('Team', foreign_keys=[home_team_id])

class Pick(db.Model):
    __tablename__ = 'picks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    week = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().isoformat())
    is_correct = db.Column(db.Boolean)
    
    user = db.relationship('User')
    match = db.relationship('Match')
    team = db.relationship('Team')

class HistoricalPick(db.Model):
    __tablename__ = 'historical_picks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    week = db.Column(db.Integer, nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    is_correct = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().isoformat())
    
    user = db.relationship('User')
    team = db.relationship('Team')

class TeamUsage(db.Model):
    __tablename__ = 'team_usage'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    usage_type = db.Column(db.String(20), nullable=False)  # 'winner' or 'loser'
    week = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().isoformat())
    
    user = db.relationship('User')
    team = db.relationship('Team')

# Initialize database tables
def init_database():
    """Initialize database with tables and sample data"""
    with app.app_context():
        db.create_all()
        
        # Add users if they don't exist
        if User.query.count() == 0:
            users = [
                User(username='Manuel', password_hash='Manuel1', display_name='Manuel'),
                User(username='Daniel', password_hash='Daniel1', display_name='Daniel'),
                User(username='Raff', password_hash='Raff1', display_name='Raff'),
                User(username='Haunschi', password_hash='Haunschi1', display_name='Haunschi')
            ]
            for user in users:
                db.session.add(user)
            
            # Add sample teams (will be updated by auto-updater)
            teams_data = [
                (1, 'Arizona Cardinals', 'ARI', 'https://a.espncdn.com/i/teamlogos/nfl/500/ari.png'),
                (2, 'Atlanta Falcons', 'ATL', 'https://a.espncdn.com/i/teamlogos/nfl/500/atl.png'),
                (3, 'Baltimore Ravens', 'BAL', 'https://a.espncdn.com/i/teamlogos/nfl/500/bal.png'),
                (4, 'Buffalo Bills', 'BUF', 'https://a.espncdn.com/i/teamlogos/nfl/500/buf.png'),
                (5, 'Carolina Panthers', 'CAR', 'https://a.espncdn.com/i/teamlogos/nfl/500/car.png'),
                (6, 'Chicago Bears', 'CHI', 'https://a.espncdn.com/i/teamlogos/nfl/500/chi.png'),
                (7, 'Cincinnati Bengals', 'CIN', 'https://a.espncdn.com/i/teamlogos/nfl/500/cin.png'),
                (8, 'Cleveland Browns', 'CLE', 'https://a.espncdn.com/i/teamlogos/nfl/500/cle.png'),
                (9, 'Dallas Cowboys', 'DAL', 'https://a.espncdn.com/i/teamlogos/nfl/500/dal.png'),
                (10, 'Denver Broncos', 'DEN', 'https://a.espncdn.com/i/teamlogos/nfl/500/den.png'),
                (11, 'Detroit Lions', 'DET', 'https://a.espncdn.com/i/teamlogos/nfl/500/det.png'),
                (12, 'Green Bay Packers', 'GB', 'https://a.espncdn.com/i/teamlogos/nfl/500/gb.png'),
                (13, 'Houston Texans', 'HOU', 'https://a.espncdn.com/i/teamlogos/nfl/500/hou.png'),
                (14, 'Indianapolis Colts', 'IND', 'https://a.espncdn.com/i/teamlogos/nfl/500/ind.png'),
                (15, 'Jacksonville Jaguars', 'JAX', 'https://a.espncdn.com/i/teamlogos/nfl/500/jax.png'),
                (16, 'Kansas City Chiefs', 'KC', 'https://a.espncdn.com/i/teamlogos/nfl/500/kc.png'),
                (17, 'Las Vegas Raiders', 'LV', 'https://a.espncdn.com/i/teamlogos/nfl/500/lv.png'),
                (18, 'Los Angeles Chargers', 'LAC', 'https://a.espncdn.com/i/teamlogos/nfl/500/lac.png'),
                (19, 'Los Angeles Rams', 'LAR', 'https://a.espncdn.com/i/teamlogos/nfl/500/lar.png'),
                (20, 'Miami Dolphins', 'MIA', 'https://a.espncdn.com/i/teamlogos/nfl/500/mia.png'),
                (21, 'Minnesota Vikings', 'MIN', 'https://a.espncdn.com/i/teamlogos/nfl/500/min.png'),
                (22, 'New England Patriots', 'NE', 'https://a.espncdn.com/i/teamlogos/nfl/500/ne.png'),
                (23, 'New Orleans Saints', 'NO', 'https://a.espncdn.com/i/teamlogos/nfl/500/no.png'),
                (24, 'New York Giants', 'NYG', 'https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png'),
                (25, 'New York Jets', 'NYJ', 'https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png'),
                (26, 'Philadelphia Eagles', 'PHI', 'https://a.espncdn.com/i/teamlogos/nfl/500/phi.png'),
                (27, 'Pittsburgh Steelers', 'PIT', 'https://a.espncdn.com/i/teamlogos/nfl/500/pit.png'),
                (28, 'San Francisco 49ers', 'SF', 'https://a.espncdn.com/i/teamlogos/nfl/500/sf.png'),
                (29, 'Seattle Seahawks', 'SEA', 'https://a.espncdn.com/i/teamlogos/nfl/500/sea.png'),
                (30, 'Tampa Bay Buccaneers', 'TB', 'https://a.espncdn.com/i/teamlogos/nfl/500/tb.png'),
                (31, 'Tennessee Titans', 'TEN', 'https://a.espncdn.com/i/teamlogos/nfl/500/ten.png'),
                (32, 'Washington Commanders', 'WAS', 'https://a.espncdn.com/i/teamlogos/nfl/500/was.png')
            ]
            
            # Add teams with merge logic to avoid UNIQUE constraint errors
            for team_id, name, abbr, logo in teams_data:
                existing_team = Team.query.filter_by(id=team_id).first()
                if not existing_team:
                    team = Team(id=team_id, name=name, abbreviation=abbr, logo_url=logo)
                    db.session.add(team)
                else:
                    # Update existing team data
                    existing_team.name = name
                    existing_team.abbreviation = abbr
                    existing_team.logo_url = logo
            
            # Add historical picks (W1+W2 results) - avoid duplicates
            historical_data = [
                (1, 1, 'Atlanta Falcons', 2, False),    # Manuel W1 Falcons (lost)
                (1, 2, 'Dallas Cowboys', 9, True),      # Manuel W2 Cowboys (won)
                (2, 1, 'Denver Broncos', 10, True),     # Daniel W1 Broncos (won)
                (2, 2, 'Philadelphia Eagles', 26, True), # Daniel W2 Eagles (won)
                (3, 1, 'Cincinnati Bengals', 7, True),  # Raff W1 Bengals (won)
                (3, 2, 'Dallas Cowboys', 9, True),      # Raff W2 Cowboys (won)
                (4, 1, 'Washington Commanders', 32, True), # Haunschi W1 Commanders (won)
                (4, 2, 'Buffalo Bills', 4, True)        # Haunschi W2 Bills (won)
            ]
            
            for user_id, week, team_name, team_id, is_correct in historical_data:
                existing_pick = HistoricalPick.query.filter_by(user_id=user_id, week=week).first()
                if not existing_pick:
                    pick = HistoricalPick(user_id=user_id, week=week, team_name=team_name, team_id=team_id, is_correct=is_correct)
                    db.session.add(pick)
            
            # Add team usage based on historical picks - avoid duplicates
            team_usage_data = [
                (1, 9, 'winner', 2),   # Manuel: Cowboys as winner W2
                (2, 10, 'winner', 1),  # Daniel: Broncos as winner W1
                (2, 26, 'winner', 2),  # Daniel: Eagles as winner W2
                (3, 7, 'winner', 1),   # Raff: Bengals as winner W1
                (3, 9, 'winner', 2),   # Raff: Cowboys as winner W2
                (4, 32, 'winner', 1),  # Haunschi: Commanders as winner W1
                (4, 4, 'winner', 2)    # Haunschi: Bills as winner W2
            ]
            
            for user_id, team_id, usage_type, week in team_usage_data:
                existing_usage = TeamUsage.query.filter_by(user_id=user_id, team_id=team_id, usage_type=usage_type, week=week).first()
                if not existing_usage:
                    usage = TeamUsage(user_id=user_id, team_id=team_id, usage_type=usage_type, week=week)
                    db.session.add(usage)
            
            db.session.commit()
            logger.info("✅ Database initialized with sample data")

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Benutzername und Passwort erforderlich'}), 400
        
        user = User.query.filter_by(username=username, password_hash=password).first()
        
        if user and user.is_active:
            session['user_id'] = user.id
            session['username'] = user.username
            session['display_name'] = user.display_name
            
            # Update last login
            user.last_login = datetime.now().isoformat()
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Login erfolgreich',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'display_name': user.display_name
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Ungültige Anmeldedaten'}), 401
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Server-Fehler beim Login'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Erfolgreich abgemeldet'})

@app.route('/api/available-weeks')
def available_weeks():
    """Get all available weeks for dropdown selection"""
    try:
        # Get weeks from matches table
        weeks_query = db.session.query(Match.week).distinct().order_by(Match.week).all()
        match_weeks = [w[0] for w in weeks_query]
        
        # Get weeks from historical picks
        historical_weeks_query = db.session.query(HistoricalPick.week).distinct().order_by(HistoricalPick.week).all()
        historical_weeks = [w[0] for w in historical_weeks_query]
        
        # Combine and sort all available weeks
        all_weeks = sorted(list(set(match_weeks + historical_weeks)))
        
        # Determine current week (highest week with games)
        current_week = max(match_weeks) if match_weeks else 3
        
        weeks_info = []
        for week in all_weeks:
            # Check if week is completed
            completed_matches = Match.query.filter_by(week=week, is_completed=True).count()
            total_matches = Match.query.filter_by(week=week).count()
            historical_picks = HistoricalPick.query.filter_by(week=week).count()
            
            status = 'completed' if (completed_matches == total_matches and total_matches > 0) or historical_picks > 0 else 'active'
            if week > current_week:
                status = 'upcoming'
            
            weeks_info.append({
                'week': week,
                'status': status,
                'games_count': total_matches,
                'completed_games': completed_matches
            })
        
        return jsonify({
            'success': True,
            'weeks': weeks_info,
            'current_week': current_week
        })
        
    except Exception as e:
        logger.error(f"Available weeks error: {e}")
        return jsonify({'success': False, 'message': 'Fehler beim Laden der verfügbaren Wochen'}), 500

@app.route('/api/dashboard')
def dashboard():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Nicht angemeldet'}), 401
        
        user_id = session['user_id']
        current_week = 3  # Current week
        
        # Get user's current week picks
        current_picks = Pick.query.filter_by(user_id=user_id, week=current_week).all()
        picks_count = len(current_picks)
        
        # Calculate total points from historical picks
        historical_picks = HistoricalPick.query.filter_by(user_id=user_id).all()
        total_points = sum(1 for pick in historical_picks if pick.is_correct)
        
        # Calculate correct picks
        correct_picks = sum(1 for pick in historical_picks if pick.is_correct)
        total_historical = len(historical_picks)
        
        # Get team usage
        team_usage = TeamUsage.query.filter_by(user_id=user_id).all()
        winner_teams = [usage.team.name for usage in team_usage if usage.usage_type == 'winner']
        loser_teams = [usage.team.name for usage in team_usage if usage.usage_type == 'loser']
        
        # Get recent picks
        recent_picks = []
        for pick in current_picks:
            recent_picks.append({
                'week': pick.week,
                'team': pick.team.name,
                'status': 'Pending' if pick.is_correct is None else ('Correct' if pick.is_correct else 'Incorrect')
            })
        
        # Calculate rank (simplified)
        all_users = User.query.all()
        user_scores = []
        for user in all_users:
            user_historical = HistoricalPick.query.filter_by(user_id=user.id).all()
            user_points = sum(1 for pick in user_historical if pick.is_correct)
            user_scores.append((user.id, user_points))
        
        user_scores.sort(key=lambda x: x[1], reverse=True)
        rank = next((i + 1 for i, (uid, _) in enumerate(user_scores) if uid == user_id), len(user_scores))
        
        return jsonify({
            'success': True,
            'data': {
                'current_week': current_week,
                'picks_submitted': picks_count,
                'total_points': total_points,
                'correct_picks': correct_picks,
                'total_picks': total_historical,
                'rank': rank,
                'winner_teams': winner_teams,
                'loser_teams': loser_teams,
                'recent_picks': recent_picks
            }
        })
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return jsonify({'success': False, 'message': 'Fehler beim Laden des Dashboards'}), 500

@app.route('/api/matches')
def matches():
    try:
        week = request.args.get('week', 3, type=int)
        
        # Get matches from database
        matches = Match.query.filter_by(week=week).all()
        matches_data = []
        
        # Get historical picks for this week if it's a completed week
        historical_picks = {}
        if week <= 2:  # Historical weeks
            picks = HistoricalPick.query.filter_by(week=week).all()
            for pick in picks:
                if pick.team_id not in historical_picks:
                    historical_picks[pick.team_id] = []
                historical_picks[pick.team_id].append({
                    'user': pick.user.display_name,
                    'correct': pick.is_correct
                })
        
        # Get current picks for this week
        current_picks = {}
        if week >= 3:  # Current/future weeks
            picks = Pick.query.filter_by(week=week).all()
            for pick in picks:
                if pick.team_id not in current_picks:
                    current_picks[pick.team_id] = []
                current_picks[pick.team_id].append({
                    'user': pick.user.display_name,
                    'correct': pick.is_correct
                })
        
        for match in matches:
            # Convert game time to Vienna timezone
            game_time = datetime.fromisoformat(match.game_time.replace('Z', '+00:00'))
            vienna_time = game_time.astimezone(VIENNA_TZ)
            
            # Get picks for both teams
            away_picks = historical_picks.get(match.away_team.id, []) + current_picks.get(match.away_team.id, [])
            home_picks = historical_picks.get(match.home_team.id, []) + current_picks.get(match.home_team.id, [])
            
            match_data = {
                'id': match.id,
                'week': match.week,
                'away_team': {
                    'id': match.away_team.id,
                    'name': match.away_team.name,
                    'abbreviation': match.away_team.abbreviation,
                    'logo_url': match.away_team.logo_url,
                    'picks': away_picks,
                    'score': match.away_score
                },
                'home_team': {
                    'id': match.home_team.id,
                    'name': match.home_team.name,
                    'abbreviation': match.home_team.abbreviation,
                    'logo_url': match.home_team.logo_url,
                    'picks': home_picks,
                    'score': match.home_score
                },
                'game_time': vienna_time.strftime('%a., %d.%m, %H:%M'),
                'is_completed': match.is_completed
            }
            
            matches_data.append(match_data)
        
        return jsonify({'success': True, 'matches': matches_data})
        
    except Exception as e:
        logger.error(f"Matches error: {e}")
        return jsonify({'success': False, 'message': 'Fehler beim Laden der Spiele'}), 500

@app.route('/api/picks', methods=['POST'])
def create_pick():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Nicht angemeldet'}), 401
        
        data = request.get_json()
        user_id = session['user_id']
        match_id = data.get('match_id')
        team_id = data.get('team_id')
        week = data.get('week', 3)
        
        if not match_id or not team_id:
            return jsonify({'success': False, 'message': 'Match ID und Team ID erforderlich'}), 400
        
        # Check if week is still open for picks
        if week <= 2:
            return jsonify({'success': False, 'message': 'Diese Woche ist bereits abgeschlossen'}), 400
        
        # Check team usage limits
        team_usage = TeamUsage.query.filter_by(user_id=user_id, team_id=team_id).all()
        winner_count = sum(1 for usage in team_usage if usage.usage_type == 'winner')
        loser_count = sum(1 for usage in team_usage if usage.usage_type == 'loser')
        
        if loser_count > 0:
            return jsonify({'success': False, 'message': 'Dieses Team wurde bereits als Verlierer verwendet und ist eliminiert'}), 400
        
        if winner_count >= 2:
            return jsonify({'success': False, 'message': 'Dieses Team wurde bereits 2x als Gewinner verwendet'}), 400
        
        # Remove existing pick for this week
        existing_pick = Pick.query.filter_by(user_id=user_id, week=week).first()
        if existing_pick:
            db.session.delete(existing_pick)
        
        # Create new pick
        new_pick = Pick(
            user_id=user_id,
            match_id=match_id,
            team_id=team_id,
            week=week
        )
        
        db.session.add(new_pick)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Pick erfolgreich gespeichert'})
        
    except Exception as e:
        logger.error(f"Create pick error: {e}")
        return jsonify({'success': False, 'message': 'Fehler beim Speichern des Picks'}), 500

@app.route('/api/leaderboard')
def leaderboard():
    try:
        users = User.query.all()
        leaderboard_data = []
        
        for user in users:
            # Calculate points from historical picks
            historical_picks = HistoricalPick.query.filter_by(user_id=user.id).all()
            points = sum(1 for pick in historical_picks if pick.is_correct)
            
            # Count total picks
            current_picks = Pick.query.filter_by(user_id=user.id).count()
            total_picks = len(historical_picks) + current_picks
            
            # Count correct picks
            correct_picks = sum(1 for pick in historical_picks if pick.is_correct)
            
            leaderboard_data.append({
                'user_id': user.id,
                'username': user.display_name,
                'points': points,
                'total_picks': total_picks,
                'correct_picks': correct_picks
            })
        
        # Sort by points (descending)
        leaderboard_data.sort(key=lambda x: x['points'], reverse=True)
        
        # Add ranks (handle ties)
        current_rank = 1
        for i, entry in enumerate(leaderboard_data):
            if i > 0 and entry['points'] != leaderboard_data[i-1]['points']:
                current_rank = i + 1
            entry['rank'] = current_rank
        
        return jsonify({'success': True, 'leaderboard': leaderboard_data})
        
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify({'success': False, 'message': 'Fehler beim Laden des Leaderboards'}), 500

@app.route('/api/all-picks')
def all_picks():
    try:
        all_picks_data = []
        
        # Get historical picks
        historical_picks = HistoricalPick.query.all()
        for pick in historical_picks:
            all_picks_data.append({
                'user': pick.user.display_name,
                'week': pick.week,
                'team': pick.team_name,
                'result': 'Correct' if pick.is_correct else 'Incorrect',
                'created_at': pick.created_at
            })
        
        # Get current picks
        current_picks = Pick.query.all()
        for pick in current_picks:
            result = 'Pending'
            if pick.is_correct is not None:
                result = 'Correct' if pick.is_correct else 'Incorrect'
            
            all_picks_data.append({
                'user': pick.user.display_name,
                'week': pick.week,
                'team': pick.team.name,
                'result': result,
                'created_at': pick.created_at
            })
        
        # Sort by week and user
        all_picks_data.sort(key=lambda x: (x['week'], x['user']))
        
        return jsonify({'success': True, 'picks': all_picks_data})
        
    except Exception as e:
        logger.error(f"All picks error: {e}")
        return jsonify({'success': False, 'message': 'Fehler beim Laden aller Picks'}), 500

# Initialize database on startup
init_database()

# Import and integrate NFL auto-updater
try:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from flask_auto_updater import integrate_nfl_auto_updater
    
    # Set database path for auto-updater
    app.config['DATABASE_PATH'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nfl_pickem.db')
    
    # Integrate auto-updater
    nfl_updater = integrate_nfl_auto_updater(app)
    
    if nfl_updater:
        logger.info("✅ NFL auto-updater integrated successfully")
        
        # Run initial update on startup
        @app.before_first_request
        def initial_nfl_update():
            try:
                logger.info("🔄 Running initial NFL data update...")
                results = nfl_updater.updater.run_auto_update()
                if results['success']:
                    logger.info("✅ Initial NFL update completed")
                else:
                    logger.warning(f"⚠️ Initial NFL update had errors: {results['errors']}")
            except Exception as e:
                logger.warning(f"Initial NFL update failed: {e}")
    else:
        logger.warning("⚠️ NFL auto-updater integration failed")
        
except ImportError as e:
    logger.warning(f"NFL auto-updater not available: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

