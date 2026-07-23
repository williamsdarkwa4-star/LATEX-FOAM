import os
import sqlite3
import psycopg2
from datetime import datetime
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# Global Environment Database Properties Configuration
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

app = Flask(__name__)
app.secret_key = 'latex_foam_secure_key_2026'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PLANS_DATA = {
    '1': {'name': 'Plan one', 'price': 50.0, 'daily': 6.0, 'days': 50},
    '2': {'name': 'Plan two', 'price': 150.0, 'daily': 30.0, 'days': 50},
    '3': {'name': 'Plan three', 'price': 300.0, 'daily': 50.0, 'days': 50},
    '4': {'name': 'Plan four', 'price': 600.0, 'daily': 155.0, 'days': 50},
    '5': {'name': 'Plan five', 'price': 1000.0, 'daily': 450.0, 'days': 50}
}

def get_db_connection():
    """Establishes connection to Render PostgreSQL when online, handles locally safely."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("Running locally without a database engine. Skipping connection.")
        return None

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    return psycopg2.connect(database_url, cursor_factory=DictCursor)

def init_db():
    """Initialises all user, deposit, withdrawal, and purchasing ledger tables with history tracking."""
    conn = get_db_connection()
    if conn is None:
        return
        
    cursor = conn.cursor()
    try:
        # 1. Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                phone TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                withdraw_password TEXT NOT NULL,
                invite_code TEXT,
                balance NUMERIC DEFAULT 30.0
            );
        ''')
        
        # 2. User Plan Table (Resolves dashboard engine relationship errors)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_plan (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                plan_name VARCHAR(100) NOT NULL DEFAULT 'Basic',
                amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # 3. User plan Table (Resolves ledger relationship errors)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_investments (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        conn.commit()
        print("DATABASE PIPELINES STANDARDIZED SUCCESSFULLY.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"DATABASE AUTO-INIT ERROR: {e}")
    finally:
        cursor.close()
        conn.close()

# Call the function right away when app launches
init_db()

    
# 2. Deposits Table
# Stores all user deposit records and payment status
cursor.execute("""
    CREATE TABLE IF NOT EXISTS deposits (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        amount NUMERIC(10,2) NOT NULL,
        reference TEXT,
        screenshot_path TEXT,
        status TEXT DEFAULT 'Pending',
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")


# 3. Withdrawals Table
# Stores user withdrawal requests
cursor.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        amount NUMERIC(10,2) NOT NULL,
        fee NUMERIC(10,2) NOT NULL,
        network TEXT NOT NULL,
        wallet_number TEXT NOT NULL,
        status TEXT DEFAULT 'Bank Processing',
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved_date TIMESTAMP
    );
""")


# 4. User Purchased Plan Table
# Tracks purchased plans and profit claim dates
cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_plans (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        plan_id TEXT NOT NULL,
        price NUMERIC(10,2) NOT NULL,
        daily_profit NUMERIC(10,2) NOT NULL,
        date_purchased TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_claimed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")


# Save database changes
conn.commit()

# Close database connection
cursor.close()
conn.close()

print("PostgreSQL database tables initialized successfully.")    
 
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        withdraw_password = request.form.get('withdraw_password', '').strip()
        invite_code = request.form.get('invite_code', '').strip()
        
if not phone or not password or not withdraw_password:
            flash('Please fill in all required fields!', 'error')
            return redirect(url_for('register'))
            
conn = get_db_connection()
if conn is None:
            flash('Database engine offline locally. Test registration on live host.', 'error')
            return redirect(url_for('register'))
            
try:
            cursor = conn.cursor()
            
            # FIX 1: Explicitly verify if phone number already exists to prevent duplicate failures
            cursor.execute('SELECT id FROM users WHERE phone = %s', (phone,))
            existing_user = cursor.fetchone()
if existing_user:
                cursor.close()
                conn.close()
                flash('This phone number is already registered!', 'error')
               return redirect(url_for('register'))
            
            # FIX 2: Securely hash raw plain-text passwords before saving them to the database
            hashed_login_pass = generate_password_hash(password)
            hashed_withdraw_pass = generate_password_hash(withdraw_password)
 
# Run the database verification setup right at application execution startup phase
#init_db()

# Run the initialization check right away when app launches
#init_db()
            # 1. Execute insertion statement with generated password hashes
            cursor.execute(
                'INSERT INTO users (phone, password, withdraw_password, invite_code, balance) VALUES (%s, %s, %s, %s, 30.0) RETURNING id', 
                (phone, hashed_login_pass, hashed_withdraw_pass, invite_code)
            )
            
            inserted_row = cursor.fetchone()
            
            if not inserted_row:
                raise Exception("Database failed to return inserted user ID.")
                
            # Safe extraction handling dictionary cursors or standard list tuples
            new_user_id = inserted_row['id'] if isinstance(inserted_row, dict) else inserted_row[0]
            
            # ====================================================================
            # FIXED REGISTER COMMISSION ROUTER (STOPS SELF-PAYING BUG)
            # ====================================================================

                                    # ====================================================================
               # ====================================================================
            # FIXED REGISTER COMMISSION ROUTER (STOPS SELF-PAYING BUG)
            # ====================================================================
            # Extract the hidden field value passed from the link
invite_code = request.form.get('invite_code', '').strip() 

# Inside your register function's database block, append this downline verification logger:
if invite_code and new_user_id:
    cursor.execute('SELECT id FROM users WHERE id = %s', (invite_code,))
    referrer = cursor.fetchone()
    if referrer:
        parent_id = referrer['id'] if isinstance(referrer, dict) else referrer[0]
        # Log them into your network hierarchy instantly
        cursor.execute('INSERT INTO referral_network (referrer_id, referred_id, level) VALUES (%s, %s, 1)', (parent_id, new_user_id))

                referrer_record = cursor.fetchone()
                
                if referrer_record:
                    # Unpack the direct parent ID safely from the psycopg2 tuple
                    lvl1_parent_id = int(referrer_record[0]) if isinstance(referrer_record, (tuple, list)) else int(referrer_record)
                    
                    if lvl1_parent_id:
                        # ─── LEVEL 1 Payout: 30% of GH₵30.00 = GH₵9.00 ───
                        cursor.execute(
                            'INSERT INTO referral_network (referrer_id, referred_id, level) VALUES (%s, %s, 1)',
                            (lvl1_parent_id, int(new_user_id))
                        )
                        # FIXED: Updates lvl1_parent_id (Sponsor) balance, NOT new_user_id
                        cursor.execute(
                            'UPDATE users SET balance = balance + 9.00 WHERE id = %s', 
                            # NEW CORRECT LINE:
                             (lvl1_parent_id,)
                        )
                            

                        
                        # ─── LEVEL 2 Payout: 2% of GH₵30.00 = GH₵0.60 ───
                        # Find who invited the Level 1 parent
                        cursor.execute('SELECT referrer_id FROM referral_network WHERE referred_id = %s AND level = 1', (lvl1_parent_id,))
                        level_2_record = cursor.fetchone()
                        
                        if level_2_record:
                            lvl2_parent_id = int(level_2_record[0]) if isinstance(level_2_record, (tuple, list)) else int(level_2_record)
                            
                            if lvl2_parent_id:
                                cursor.execute(
                                    'INSERT INTO referral_network (referrer_id, referred_id, level) VALUES (%s, %s, 2)',
                                    (lvl2_parent_id, int(new_user_id))
                                )
                                # FIXED: Updates lvl2_parent_id (Grandparent) balance
                                cursor.execute(
                                    'UPDATE users SET balance = balance + 0.60 WHERE id = %s', 
                                    (lvl2_parent_id,)
                                )
                                
                                # ─── LEVEL 3 Payout: 1% of GH₵30.00 = GH₵0.30 ───
                                # Find who invited the Level 2 parent
                                cursor.execute('SELECT referrer_id FROM referral_network WHERE referred_id = %s AND level = 1', (lvl2_parent_id,))
                                level_3_record = cursor.fetchone()
                                
                                if level_3_record:
                                    lvl3_parent_id = int(level_3_record[0]) if isinstance(level_3_record, (tuple, list)) else int(level_3_record)
                                    
                                    if lvl3_parent_id:
                                        cursor.execute(
                                            'INSERT INTO referral_network (referrer_id, referred_id, level) VALUES (%s, %s, 3)',
                                            (lvl3_parent_id, int(new_user_id))
                                        )
                                        # FIXED: Updates lvl3_parent_id (Great-Grandparent) balance
                                        cursor.execute(
                                            'UPDATE users SET balance = balance + 0.30 WHERE id = %s', 
                                            (lvl3_parent_id,)
                                        )
         

            
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            if conn:
                conn.rollback()
                cursor.close()
                conn.close()
            
            # Print the actual error statement down to your live web service console
            print(f"CRITICAL REGISTRATION ERROR: {e}")
            flash(f'Registration system error: {str(e)}', 'error')
            return redirect(url_for('register'))
            
    # GET Processing Phase: Automatically look for incoming link tags (?ref=XYZ)
    url_invite_code = request.args.get('ref', '')
    return render_template('register.html', url_invite_code=url_invite_code)

            
    # GET Processing Phase: Automatically look for incoming link tags (?ref=XYZ)
    url_invite_code = request.args.get('ref', '')
    return render_template('register.html', url_invite_code=url_invite_code)
@app.route('/team')
def team_page_view():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
        
    # Generate the link directly in Python so it shows up even if database query fails
    base_url = "https://latex-foam-site.onrender.com"
    unique_referral_link = f"{base_url}/register?ref={user_id}"
    
    return render_template('team_dashboard.html',)
    
@app.route('/api/team/dashboard-data', methods=['GET'])
def get_team_dashboard_data():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database offline"}), 500

    cursor = None
    try:
        cursor = conn.cursor()
        
        # 1. Fetch user counts grouped cleanly by referral level
        cursor.execute('''
            SELECT level, COUNT(id) 
            FROM referral_network 
            WHERE referrer_id = %s 
            GROUP BY level
        ''', (user_id,))
        count_rows = cursor.fetchall()
        
        # 2. Fetch investment sums checking table relations safely
        cursor.execute('''
            SELECT rn.level, COALESCE(SUM(p.amount), 0)
            FROM referral_network rn
            LEFT JOIN user_plan p ON rn.referred_id = p.user_id
            WHERE rn.referrer_id = %s
            GROUP BY rn.level
        ''', (user_id,))
        plan_rows = cursor.fetchall()

        # Initialize baseline fallback storage dictionaries
        counts = {1: 0, 2: 0, 3: 0}
        plans = {1: 0.00, 2: 0.00, 3: 0.00}

        # Safely extract values explicitly mapping positional row index components
        for row in count_rows:
            lvl = int(row['level'] if isinstance(row, dict) else row[0])
            val = int(row['count'] if isinstance(row, dict) else row[1])
            if lvl in counts:
                counts[lvl] = val

        for row in plan_rows:
            lvl = int(row['level'] if isinstance(row, dict) else row[0])
            val = float(row['coalesce'] if isinstance(row, dict) else row[1])
            if lvl in plans:
                plans[lvl] = val

        # Calculate combined network dimensions
        total_members = counts[1] + counts[2] + counts[3]
        total_team_plan = plans[1] + plans[2] + plans[3]

        return jsonify({
            "total_members": total_members,
            "total_plan": round(total_team_plan, 2),
            "lvl1_count": counts[1],
            "lvl1_plan": round(plans[1], 2),
            "lvl2_count": counts[2],
            "lvl2_plan": round(plans[2], 2),
            "lvl3_count": counts[3],
            "lvl3_plan": round(plans[3], 2)
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        
        # Print the exact log format throwing in your Render logs
        print(f"PSYCOPG2 TEAM ANALYTICS ENGINE ERROR: {e}")
        
        # OPTION A: Return zeros so frontend doesn't crash (Your current setup)
        return jsonify({
            "total_members": 0,
            "total_plan": 0.00,
            "lvl1_count": 0,
            "lvl1_plan": 0.00,
            "lvl2_count": 0,
            "lvl2_plan": 0.00,
            "lvl3_count": 0,
            "lvl3_plan": 0.00
        }), 200

        # OPTION B: Use this instead if you want front-end monitoring tools to catch it:
        # return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()





@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()

        if not phone or not password:
            flash('Please fill in all fields!', 'error')
            return redirect(url_for('login'))

        conn = get_db_connection()
        if conn is None:
            flash('Database engine offline.', 'error')
            return redirect(url_for('login'))

        try:
            cursor = conn.cursor()
            # Uses a dynamic check to find the user row by phone string safely
            cursor.execute('SELECT * FROM users WHERE phone = %s', (phone,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user:
                # CRASH PROTECTION: Read dictionary keys or traditional column positions automatically
                if isinstance(user, dict):
                    db_id = user.get('id')
                    db_phone = user.get('phone')
                    db_password = user.get('password')
                else:
                    # In a typical 'SELECT *' tuple layout, id is index 0, phone is index 1, password is index 2
                    db_id = user[0]
                    db_phone = user[1]
                    db_password = user[2]

                # Secure cryptographic verification hash execution check
                if db_password and check_password_hash(db_password, password):
                    session['user_id'] = db_id
                    session['phone'] = db_phone
                    return redirect(url_for('dashboard'))

            flash('Invalid phone number or password!', 'error')
            return redirect(url_for('login'))

        except Exception as e:
            # This logs the specific error right into your terminal panel console
            print(f"MASTER LOGIN CODE CRASH LOG: {e}")
            flash('An error occurred during login. Please try again.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if conn is None:
        return render_template('dashboard.html', user_phone=session['phone'], user_balance=30.0)
        
    cursor = conn.cursor()
    # Changed placeholder from '?' to '%s' to match PostgreSQL
    cursor.execute('SELECT balance FROM users WHERE id = %s', (session['user_id'],))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    current_balance = float(result['balance']) if result else 0.0
    return render_template('dashboard.html', user_phone=session['phone'], user_balance=current_balance)

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    if request.method == 'POST':
        amount_raw = request.form.get('amount')
        reference = request.form.get('reference')
        file = request.files.get('screenshot')
        amount = float(amount_raw) if amount_raw else 0
        
        # New minimum deposit constraint verification set to 100 GHS
        if amount < 50:
            if conn: conn.close()
            flash('Minimum deposit requirement is 50 GHS!', 'error')
            return redirect(url_for('deposit'))
            
        if file and reference:
            filename = f"user_{session['user_id']}_{int(datetime.now().timestamp())}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            if conn:
                cursor = conn.cursor()
                # Changed query parameters from '?' to '%s' to match PostgreSQL
                cursor.execute(
                    'INSERT INTO deposits (user_id, amount, reference, screenshot_path, status) VALUES (%s, %s, %s, %s, %s)', 
                    (session['user_id'], amount, reference, filepath, "Pending")
                )
                conn.commit()
                cursor.close()
                conn.close()
                flash('Deposit order submitted!', 'success')
                return redirect(url_for('deposit'))
                
    user_balance = 0.0
    if conn:
        cursor = conn.cursor()
        # Changed query parameter from '?' to '%s' to match PostgreSQL
        cursor.execute('SELECT balance FROM users WHERE id = %s', (session['user_id'],))
        result = cursor.fetchone()
        user_balance = float(result['balance']) if result else 0.0
        cursor.close()
        conn.close()
        
    return render_template('deposit.html', user_balance=user_balance)
@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash("Database connection unavailable.", "error")
        return render_template('withdraw.html', user_balance=0.0)

    cursor = conn.cursor()

    if request.method == 'POST':
        amount_raw = request.form.get('amount')
        network = request.form.get('network')
        wallet_number = request.form.get('wallet_number')
        withdraw_password = request.form.get('withdraw_password')

        amount = float(amount_raw) if amount_raw else 0

        if amount < 60:
            flash('Minimum withdrawal amount is 60 GHS!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('withdraw'))

        # Changed placeholder from '?' to '%s' to match PostgreSQL
        cursor.execute(
            "SELECT id FROM user_plans WHERE user_id = %s",
            (session['user_id'],)
        )
        active_plan = cursor.fetchone()

        if not active_plan:
            flash('You must purchase a plan before you can withdraw!', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('withdraw'))

        # Changed placeholder from '?' to '%s' to match PostgreSQL
        cursor.execute(
            "SELECT balance, withdraw_password FROM users WHERE id = %s",
            (session['user_id'],)
        )
        user_data = cursor.fetchone()

        if user_data:
            current_balance = float(user_data['balance'])
            db_withdraw_password = user_data['withdraw_password']

            if amount > current_balance:
                flash('Insufficient account balance!', 'error')

            elif withdraw_password != db_withdraw_password:
                flash('Incorrect withdrawal password!', 'error')

            else:
                fee = amount * 0.19
                actual_payout = amount - fee
                new_balance = current_balance - amount

                # Changed placeholders from '?' to '%s' to match PostgreSQL
                cursor.execute(
                    "UPDATE users SET balance=%s WHERE id=%s",
                    (new_balance, session['user_id'])
                )

                # Changed placeholders from '?' to '%s' to match PostgreSQL
                cursor.execute(
                    """
                    INSERT INTO withdrawals
                    (user_id, amount, fee, network, wallet_number, status)
                    VALUES (%s, %s, %s, %s, %s, 'Bank Processing')
                    """,
                    (
                        session['user_id'],
                        actual_payout,
                        fee,
                        network,
                        wallet_number
                    )
                )

                conn.commit()
                flash('Withdrawal request sent to admin.', 'success')

    # Changed placeholder from '?' to '%s' to match PostgreSQL
    cursor.execute(
        "SELECT balance FROM users WHERE id=%s",
        (session['user_id'],)
    )

    result = cursor.fetchone()
    user_balance = float(result['balance']) if result else 0.0

    cursor.close()
    conn.close()

    return render_template(
        'withdraw.html',
        user_balance=user_balance
    )
''
@app.route('/history')
def history():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if conn is None:
        flash("History logging engine currently offline.", "error")
        return redirect(url_for('dashboard'))
        
    cursor = conn.cursor()
    
    # Fetch all deposit history records
    cursor.execute("""
        SELECT amount, reference, status, date 
        FROM deposits 
        WHERE user_id = %s 
        ORDER BY date DESC
    """, (session['user_id'],))
    deposit_history = cursor.fetchall()
    
    # Fetch all withdrawal history records
    cursor.execute("""
        SELECT amount, fee, status, date, approved_date 
        FROM withdrawals 
        WHERE user_id = %s 
        ORDER BY date DESC
    """, (session['user_id'],))
    withdrawal_history = cursor.fetchall()
    
    # Fetch active plan listings to generate timers on the frontend interface
    cursor.execute("""
        SELECT id, plan_id, price, daily_profit, date_purchased, last_claimed_date 
        FROM user_plans 
        WHERE user_id = %s 
        ORDER BY date_purchased DESC
    """, (session['user_id'],))
    active_plans = cursor.fetchall()
    
    # Calculate countdown metrics for each plan
    processed_plans = []
    now = datetime.now()
    for plan in active_plans:
        # Time difference calculation since last extraction claim
        time_elapsed = now - plan['last_claimed_date']
        seconds_elapsed = time_elapsed.total_seconds()
        
        # 24 hours equals 86400 seconds
        time_left = max(0, 86400 - seconds_elapsed)
        can_claim = seconds_elapsed >= 86400
        
        processed_plans.append({
            'id': plan['id'],
            'plan_id': plan['plan_id'],
            'price': float(plan['price']),
            'daily_profit': float(plan['daily_profit']),
            'date_purchased': plan['date_purchased'],
            'time_left_seconds': int(time_left),
            'can_claim': can_claim
        })
        
    cursor.close()
    conn.close()
    
    return render_template(
        'history.html', 
        deposits=deposit_history, 
        withdrawals=withdrawal_history, 
        plans=processed_plans
    )
@app.route('/claim_profit/<int:user_plan_id>', methods=['POST'])
def claim_profit(user_plan_id):
    if 'user_id' not in session: 
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if conn is None:
        flash("Earnings validator server unreachable.", "error")
        return redirect(url_for('history'))
        
    cursor = conn.cursor()
    
    # Fetch specific targeted plan to double check verification timestamps
    cursor.execute("""
        SELECT last_claimed_date, daily_profit 
        FROM user_plans 
        WHERE id = %s AND user_id = %s
    """, (user_plan_id, session['user_id']))
    plan = cursor.fetchone()
    
    if not plan:
        cursor.close()
        conn.close()
        flash("Target asset ledger signature mismatch.", "error")
        return redirect(url_for('history'))
        
    now = datetime.now()
    time_elapsed = now - plan['last_claimed_date']
    
    # Verify the 24-hour interval safety floor limit
    if time_elapsed.total_seconds() < 86400:
        cursor.close()
        conn.close()
        flash("24-hour cycle timer countdown is still running!", "error")
        return redirect(url_for('history'))
        
    profit = float(plan['daily_profit'])
    
    try:
        # 1. Award balance to user wallet profile
        cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (profit, session['user_id']))
        # 2. Reset the last_claimed_date timestamp to the current moment
        cursor.execute("UPDATE user_plans SET last_claimed_date = %s WHERE id = %s", (now, user_plan_id))
        
        conn.commit()
        flash(f"Successfully claimed your daily profit of {profit} GHS!", "success")
    except Exception as e:
        conn.rollback()
        flash("Transaction execution exception loop occurred.", "error")
        
    cursor.close()
    conn.close()
    return redirect(url_for('history'))

@app.route('/service')
def service():
    return render_template('service.html')
@app.route('/plan', methods=['GET', 'POST'])
def plan():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash("Database connection unavailable.", "error")
        return render_template('plan.html', plans=PLANS_DATA)

    cursor = conn.cursor()

    if request.method == 'POST':
        plan_id = request.form.get('plan_id')

        if plan_id in PLANS_DATA:
            selected_plan = PLANS_DATA[plan_id]

            # Changed placeholders from '?' to '%s' to match PostgreSQL
            cursor.execute(
                'SELECT id FROM user_plans WHERE user_id=%s AND plan_id=%s',
                (session['user_id'], plan_id)
            )

            if cursor.fetchone():
                flash(f"{selected_plan['name']} is already running.", 'error')

            else:
                # Changed placeholder from '?' to '%s' to match PostgreSQL
                cursor.execute('SELECT balance FROM users WHERE id=%s', (session['user_id'],))
                user = cursor.fetchone()
                balance = float(user['balance']) if user else 0.0

                if balance < selected_plan['price']:
                    flash('Insufficient balance!', 'error')

                else:
                    new_balance = balance - selected_plan['price']

                    # Changed placeholders from '?' to '%s' to match PostgreSQL
                    cursor.execute(
                        'UPDATE users SET balance=%s WHERE id=%s',
                        (new_balance, session['user_id'])
                    )

                    # Changed placeholders from '?' to '%s' to match PostgreSQL
                    cursor.execute(
                        'INSERT INTO user_plans (user_id, plan_id, price, daily_profit) VALUES (%s, %s, %s, %s)',
                        (
                            session['user_id'],
                            plan_id,
                            selected_plan['price'],
                            selected_plan['daily']
                        )
                    )

                    conn.commit()
                    flash('Plan purchased successfully!', 'success')

        cursor.close()
        conn.close()
        return redirect(url_for('plan'))

    cursor.close()
    conn.close()
    return render_template('plan.html', plans=PLANS_DATA)

@app.route('/my_plan')
def my_plan():
    return render_template('my_plan.html')
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_phone = session.get('phone', 'No phone number')
    user_balance = session.get('balance', 30)

    return render_template(
        'profile.html',
        user_phone=user_phone,
        account_number=user_phone,
        user_balance=user_balance)
 

    user_phone = session.get('phone', 'No phone number')
    user_balance = session.get('balance', 0)

    return render_template(
        'profile.html',
        user_phone=user_phone,
        account_number=user_phone,
        user_balance=user_balance
    )
@app.route('/api/invest/activate-plan', methods=['POST'])
def activate_investment_plan():
    buyer_id = session.get('user_id')
    if not buyer_id:
        return jsonify({"error": "Please log in first"}), 401

    payload = request.get_json()
    plan_cost = float(payload.get('amount', 0)) # Example: GH₵ 50.00 or GH₵ 200.00

    if plan_cost <= 0:
        return jsonify({"error": "Invalid plan selection"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Verify the buyer has enough money in their account wallet
        cursor.execute("SELECT balance FROM users WHERE id = %s", (int(buyer_id),))
        buyer_balance = float(cursor.fetchone()[0])

        if buyer_balance < plan_cost:
            cursor.close()
            conn.close()
            return jsonify({"error": "Insufficient account balance! Please deposit funds."}), 400

        # 2. Deduct the package cost from the buyer's balance
        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (plan_cost, int(buyer_id)))

        # 3. Log this asset purchase into the active user_investments table
        cursor.execute(
            "INSERT INTO user_investments (user_id, amount) VALUES (%s, %s) RETURNING id",
            (int(buyer_id), plan_cost)
        )
        conn.commit() # Save investment records immediately

        # 4. COMMISSION ROUTER: Climb the network tree to reward ancestors
        # Calculate exactly 30% for Level 1, 2% for Level 2, and 1% for Level 3 based on the PLAN COST
        l1_commission = plan_cost * 0.30
        l2_commission = plan_cost * 0.02
        l3_commission = plan_cost * 0.01

        # Look up who invited this buyer (Level 1 Parent)
        cursor.execute("SELECT referrer_id FROM referral_network WHERE referred_id = %s AND level = 1", (int(buyer_id),))
        l1_row = cursor.fetchone()

        if l1_row:
            l1_parent_id = int(l1_row[0])
            # Credit the owner of the referral code with 30% commission
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (l1_commission, l1_parent_id))

            # Look up who invited the Level 1 parent (Level 2 Grandparent)
            cursor.execute("SELECT referrer_id FROM referral_network WHERE referred_id = %s AND level = 1", (l1_parent_id,))
            l2_row = cursor.fetchone()
            
            if l2_row:
                l2_parent_id = int(l2_row[0])
                # Credit Level 2 ancestor with 2% commission
                cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (l2_commission, l2_parent_id))

                # Look up who invited the Level 2 parent (Level 3 Great-Grandparent)
                cursor.execute("SELECT referrer_id FROM referral_network WHERE referred_id = %s AND level = 1", (l2_parent_id,))
                l3_row = cursor.fetchone()
                
                if l3_row:
                    l3_parent_id = int(l3_row[0])
                    # Credit Level 3 ancestor with 1% commission
                    cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (l3_commission, l3_parent_id))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": "Investment active! Commissions distributed successfully."}), 200

    except Exception as e:
        print(f"CRITICAL COMMISSION ROUTING SYSTEM CRASH: {e}")
        return jsonify({"error": "Internal network processing failure"}), 500


@app.route('/api/team/investment-ledger', methods=['GET'])
def get_investment_ledger():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database offline"}), 500

    try:
        cursor = conn.cursor()
        # Query matching the newly established database scheme parameters
        cursor.execute('''
            SELECT rn.level, p.amount, p.created_at
            FROM referral_network rn
            JOIN user_investments p ON rn.referred_id = p.user_id
            WHERE rn.referrer_id = %s
            ORDER BY p.created_at DESC
        ''', (user_id,))
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({"ledger": records}), 200
    except Exception as e:
        print(f"LEDGER PIPELINE ERROR: {e}")
        return jsonify({"ledger": []}), 200

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == "Williams" and password == "Williams12":
            session["admin"] = True
            return redirect(url_for('admin'))
        else:
            flash("Invalid admin username or password!", "error")

    return render_template("admin_login.html")
@app.route('/admin/adjust_balance', methods=['POST'])
def admin_adjust_balance():
    if not session.get("admin"):
        return redirect(url_for('admin_login'))

    phone = request.form.get('phone')
    amount = float(request.form.get('amount'))
    action_type = request.form.get('action_type')

    conn = get_db_connection()
    if conn is None:
        flash("Database connection unavailable.", "error")
        return redirect(url_for('admin'))

    cursor = conn.cursor()
    # Changed placeholder from '?' to '%s' to match PostgreSQL
    cursor.execute("SELECT balance FROM users WHERE phone=%s", (phone,))
    user = cursor.fetchone()

    if user is None:
        cursor.close()
        conn.close()
        flash("User not found!", "error")
        return redirect(url_for('admin'))

    # Accesses data by column name 'balance' thanks to DictCursor mapping rules
    balance = float(user['balance'])

    if action_type == "add":
        balance += amount
    elif action_type == "deduct":
        balance -= amount
        if balance < 0:
            balance = 0

    # Changed placeholders from '?' to '%s' to match PostgreSQL
    cursor.execute("UPDATE users SET balance=%s WHERE phone=%s", (balance, phone))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Balance updated successfully!", "success")
    return redirect(url_for('admin'))  
@app.route('/admin')
def admin():
    if not session.get("admin"):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    if conn is None:
        # Graceful fallback data structures to prevent dashboard crashes when editing offline
        return render_template(
            "admin.html",
            users=[],
            pending_deposits=[],
            pending_withdrawals=[]
        )

    cursor = conn.cursor()

    # Get all registered website users
    cursor.execute("""
        SELECT id, phone, balance
        FROM users
        ORDER BY id DESC
    """)
    users = cursor.fetchall()

    # Get pending user invoice receipts
    cursor.execute("""
        SELECT 
            d.id,
            d.amount,
            d.reference,
            d.screenshot_path,
            u.phone
        FROM deposits d
        JOIN users u ON d.user_id = u.id
        WHERE d.status = 'Pending'
    """)
    pending_deposits = cursor.fetchall()

    # Get pending bank processing payouts 
    cursor.execute("""
        SELECT 
            w.id,
            w.amount,
            w.fee,
            w.network,
            w.wallet_number,
            u.phone
        FROM withdrawals w
        JOIN users u ON w.user_id = u.id
        WHERE w.status = 'Bank Processing'
    """)
    pending_withdrawals = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin.html",
        users=users,
        pending_deposits=pending_deposits,
        pending_withdrawals=pending_withdrawals
    )
@app.route('/admin/deposit/<int:id>/<action>')
def admin_handle_deposit(id, action):
    if not session.get("admin"):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    if conn is None:
        flash("Database connection unavailable.", "error")
        return redirect(url_for('admin'))

    cursor = conn.cursor()
    # Changed placeholder from '?' to '%s' to match PostgreSQL
    cursor.execute("SELECT user_id, amount FROM deposits WHERE id=%s", (id,))
    deposit = cursor.fetchone()

    if not deposit:
        cursor.close()
        conn.close()
        flash("Deposit not found!", "error")
        return redirect(url_for('admin'))

    # Access data fields by explicit dictionary key strings via DictCursor mapping
    user_id = deposit['user_id']
    amount = float(deposit['amount'])

    if action == "accept":
        # Changed placeholders from '?' to '%s' to match PostgreSQL
        cursor.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, user_id))
        cursor.execute("UPDATE deposits SET status='Approved' WHERE id=%s", (id,))
        flash("Deposit approved. User balance updated.", "success")

    elif action == "reject":
        # Changed placeholder from '?' to '%s' to match PostgreSQL
        cursor.execute("UPDATE deposits SET status='Rejected' WHERE id=%s", (id,))
        flash("Deposit rejected.", "error")

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin'))

@app.route('/admin/withdrawal/<int:id>/<action>')
def admin_handle_withdrawal(id, action):
    if not session.get("admin"):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    if conn is None:
        flash("Database connection unavailable.", "error")
        return redirect(url_for('admin'))

    cursor = conn.cursor()
    # Changed placeholder from '?' to '%s' to match PostgreSQL
    cursor.execute("SELECT user_id, amount, fee FROM withdrawals WHERE id=%s", (id,))
    withdrawal = cursor.fetchone()

    if withdrawal is None:
        cursor.close()
        conn.close()
        flash("Withdrawal not found!", "error")
        return redirect(url_for('admin'))

    # Access data fields by explicit dictionary key strings via DictCursor mapping configurations
    user_id = withdrawal['user_id']
    amount = float(withdrawal['amount'])
    fee = float(withdrawal['fee'])

    if action == "accept":
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Changed placeholders from '?' to '%s' to match PostgreSQL
        cursor.execute("UPDATE withdrawals SET status='Completed', approved_date=%s WHERE id=%s", (current_time, id))
        flash("Withdrawal approved successfully!", "success")

    elif action == "reject":
        refund = amount + fee
        # Changed placeholders from '?' to '%s' to match PostgreSQL
        cursor.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (refund, user_id))
        cursor.execute("UPDATE withdrawals SET status='Rejected' WHERE id=%s", (id,))
        flash("Withdrawal rejected. Funds returned to user.", "success")

    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/recharge')
def recharge():
    return render_template('recharge.html')

@app.route('/admin/withdraw')
def admin_withdraw():
    return render_template('admin_withdraw.html')

# Run the database verification setup right at application startup
init_db()


@app.route('/api/user/account-details', methods=['GET'])
def account_details():
    # Fetch your user details from the database here
    # return jsonify({"status": "success", "data": {...}})
    pass

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('login'))
    return redirect(url_for('admin'))
    

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    
def init_db():
    """Ensures all required tables exist in PostgreSQL before handling traffic."""
    # Replace with your actual connection configuration or environment variable
    import psycopg2
    import os
    
    db_url = os.environ.get('DATABASE_URL', 'your_connection_string_here')
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    try:
        # Create user_plan table if missing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_plan (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                plan_name VARCHAR(100) NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create user_investments table if missing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_investments (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        print("DATABASE INIT: Tables verified and created successfully.")
    except Exception as e:
        conn.rollback()
        print(f"DATABASE INIT ERROR: {e}")
    finally:
        cursor.close()
        conn.close()

# Call this right under your if __name__ == '__main__': block
# init_db()

#================================================================
# AUTO-SCHEMA INITIALIZER (PASTED SAFELY AT THE BOTTOM OF APP.PY)
# ====================================================================
def init_db():
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Create the missing referral network table automatically
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referral_network (
                    id SERIAL PRIMARY KEY,
                    referrer_id INTEGER NOT NULL,
                    referred_id INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (referred_id) REFERENCES users(id) ON DELETE CASCADE
                );
            ''')
            conn.commit()
            cursor.close()
            conn.close()
            print("All PostgreSQL tracking schemas initialised successfully.")
    except Exception as e:
        print(f"Error initializing database table: {e}")
init_db()
# ... your old code ends here ...

def init_all_tables():
    """Executes schema generation to resolve relation does not exist errors."""
    import psycopg2
    import os

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("DATABASE INIT ERROR: DATABASE_URL environment variable is missing!")
        return

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # 1. Resolve 'relation user_plan does not exist'
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_plan (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                plan_name VARCHAR(100) NOT NULL DEFAULT 'Basic',
                amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        from flask import request, session, jsonify

@app.route('/api/plan/purchase', methods=['POST'])
def purchase_plan():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    plan_name = data.get('plan_name', '').strip()
    
    try:
        amount = float(data.get('amount', 0))
        if amount <= 0 or not plan_name:
            return jsonify({"error": "Invalid plan name or purchase amount."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a valid decimal number."}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database service offline"}), 500

    cursor = None
    try:
        cursor = conn.cursor()
        
        # Check if the user already has an assigned plan record
        cursor.execute('SELECT id FROM user_plan WHERE user_id = %s;', (user_id,))
        existing_plan = cursor.fetchone()
        
        if existing_plan:
            # Update their active plan parameters cleanly
            cursor.execute('''
                UPDATE user_plan 
                SET plan_name = %s, amount = %s, status = 'active', created_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                RETURNING id;
            ''', (plan_name, amount, user_id))
        else:
            # Create a brand new plan assignment row
            cursor.execute('''
                INSERT INTO user_plan (user_id, plan_name, amount, status)
                VALUES (%s, %s, %s, 'active')
                RETURNING id;
            ''', (user_id, plan_name, amount))
            
        record = cursor.fetchone()
        conn.commit()
        
        rec_id = record['id'] if isinstance(record, dict) else record[0]
        return jsonify({
            "status": "success",
            "message": f"Successfully activated plan: {plan_name}",
            "plan_id": rec_id
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"PLAN ACTIVATION SEVERE ERROR: {str(e)}")
        return jsonify({"error": "Internal database error processing plan change."}), 500
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
@app.route('/api/plan/current', methods=['GET'])
def get_current_plan():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database offline"}), 500

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT plan_name, amount, status, created_at 
            FROM user_plan 
            WHERE user_id = %s LIMIT 1;
        ''', (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({
                "has_plan": False,
                "plan_name": "No Active Plan",
                "amount": 0.00,
                "status": "inactive"
            }), 200

        if isinstance(row, dict):
            return jsonify({
                "has_plan": True,
                "plan_name": row['plan_name'],
                "amount": float(row['amount']),
                "status": row['status'],
                "activated_at": str(row['created_at'])
            }), 200
        else:
            return jsonify({
                "has_plan": True,
                "plan_name": row[0],
                "amount": float(row[1]),
                "status": row[2],
                "activated_at": str(row[3])
            }), 200

    except Exception as e:
        print(f"DATABASE FETCH PLAN FAILURE: {str(e)}")
        return jsonify({"error": "Could not recover active subscription data."}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
  ALTER TABLE user_plan ADD COLUMN IF NOT EXISTS plan_name VARCHAR(100) DEFAULT 'Basic';
ALTER TABLE user_plan ADD COLUMN IF NOT EXISTS amount NUMERIC(15, 2) DEFAULT 0.00;
          conn.close()

        # 2. Resolve 'relation user_investments does not exist'
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_investments (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 3. Add explicit indexes to optimize performance for the ledger joins
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_plan_uid ON user_plan(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_inv_uid ON user_investments(user_id);")
        
        conn.commit()
        print("DATABASE INITIALIZATION SUCCESS: Tables and indices verified.")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"CRITICAL DATABASE INITIALIZATION FAILURE: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

init_db()
if __name__ == '__main__':
    init_all_tables() # Runs every time the web service spins up or redeploys
    app.run()

