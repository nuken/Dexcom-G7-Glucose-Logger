import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from pydexcom import Dexcom

app = Flask(__name__)

# CONFIGURATION
DEXCOM_USER = os.environ.get('DEXCOM_USER')
DEXCOM_PASS = os.environ.get('DEXCOM_PASS')
IS_OUS = os.environ.get('DEXCOM_OUS', 'False').lower() == 'true'
DEXCOM_REGION = "ous" if IS_OUS else "us"
DB_FILE = "/app/glucose.db"

# --- DATABASE FUNCTIONS ---
def init_db():
    """Creates the table if it doesn't exist."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS readings (
                time_str TEXT PRIMARY KEY,
                timestamp DATETIME,
                mg_dl INTEGER,
                trend TEXT,
                trend_arrow TEXT
            )
        ''')

def save_readings_to_db(readings):
    """Saves a list of readings to SQLite, ignoring duplicates."""
    if not readings:
        return
    
    with sqlite3.connect(DB_FILE) as conn:
        for r in readings:
            t_str = r.datetime.strftime('%Y-%m-%d %H:%M:%S')
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO readings (time_str, timestamp, mg_dl, trend, trend_arrow) VALUES (?, ?, ?, ?, ?)",
                    (t_str, r.datetime, r.value, r.trend_description, r.trend_arrow)
                )
            except Exception as e:
                print(f"DB Error: {e}")
    print(f"Synced {len(readings)} readings to database.")

# --- BACKGROUND SYNC ---
def background_sync():
    """Runs every 30 minutes to fetch data from Dexcom."""
    while True:
        try:
            print("Starting background sync...")
            dexcom = Dexcom(
                username=DEXCOM_USER, 
                password=DEXCOM_PASS, 
                region=DEXCOM_REGION
            )
            readings = dexcom.get_glucose_readings(minutes=1440)
            save_readings_to_db(readings)
        except Exception as e:
            print(f"Background Sync Failed: {e}")
        
        time.sleep(1800)

try:
    init_db()
    threading.Thread(target=background_sync, daemon=True).start()
except Exception as e:
    print(f"Startup Error: {e}")

# --- WEB ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/readings')
def get_readings():
    # 1. Trigger Quick Live Sync
    try:
        dexcom = Dexcom(
            username=DEXCOM_USER, 
            password=DEXCOM_PASS, 
            region=DEXCOM_REGION
        )
        latest = dexcom.get_glucose_readings(minutes=40)
        save_readings_to_db(latest)
    except:
        pass

    # 2. Query & Filter Data
    try:
        step = int(request.args.get('step', 1))       # 1=All, 3=15m, 6=30m, 12=1h
        minutes_back = int(request.args.get('minutes', 1440))
        
        # Calculate the Target Interval in Minutes
        # If step is 1, interval is 0 (show all). If step is 3, interval is 15.
        target_interval = 0 if step == 1 else (step * 5)
        
        cutoff = datetime.now() - timedelta(minutes=minutes_back)
        
        data = []
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT time_str, mg_dl, trend, trend_arrow FROM readings WHERE timestamp > ? ORDER BY timestamp DESC", (cutoff,))
            rows = cursor.fetchall()
            
            last_kept_time = None
            
            for row in rows:
                # Parse the time
                dt = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                
                keep_row = False
                
                if step == 1:
                    # If "All Readings", keep everything
                    keep_row = True
                elif last_kept_time is None:
                    # Always keep the very first (newest) reading
                    keep_row = True
                else:
                    # TIME CALCULATION:
                    # Check difference between the last one we showed and this one
                    # Since we are going DESC (Newest -> Oldest), last_kept_time is larger
                    diff_mins = (last_kept_time - dt).total_seconds() / 60
                    
                    # If the gap is big enough (e.g. >= 15 mins), keep it
                    if diff_mins >= target_interval:
                        keep_row = True
                
                if keep_row:
                    last_kept_time = dt
                    
                    # Format Pretty Time
                    friendly_time = dt.strftime('%b %d, %Y %-I:%M %p').replace('AM', 'am').replace('PM', 'pm')
                    
                    data.append({
                        'timestamp': row[0],
                        'time': friendly_time,
                        'mg_dl': row[1],
                        'trend': row[2],
                        'trend_arrow': row[3]
                    })
                
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)