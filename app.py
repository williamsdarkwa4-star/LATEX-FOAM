from flask import Flask, render_template, request, redirect, url_for, session, flash,jsonify
import sqlite3
import os
import psycopg2
from datetime import datetime

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
        
    import psycopg2
    from psycopg2.extras import DictCursor
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(database_url, cursor_factory=DictCursor)

def init_db():
    """Initialises all user, deposit, withdrawal, and purchasing ledger tables with history tracking."""
    conn = get_db_connection()
    if conn is None:
        return
        
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            withdraw_password TEXT NOT NULL,
            invite_code TEXT,
            balance NUMERIC DEFAULT 30.0
        )
    ''')
    
    # 2. Deposits Table (Kept as is, records status modifications automatically)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            amount NUMERIC NOT NULL,
            reference TEXT,
            screenshot_path TEXT,
            status TEXT DEFAULT 'Pending',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. Withdrawals Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            amount NUMERIC NOT NULL,
            fee NUMERIC NOT NULL,
            network TEXT NOT NULL,
            wallet_number TEXT NOT NULL,
            status TEXT DEFAULT 'Bank Processing',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_date TEXT
        )
    ''')
    
    # 4. User Purchased Plans Table (Added 'last_claimed_date' column)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_plans (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            plan_id TEXT NOT NULL,
            price NUMERIC NOT NULL,
            daily_profit NUMERIC NOT NULL,
            date_purchased TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_claimed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()
    print("All PostgreSQL tracking schemas initialised successfully.")
from werkzeug.security import generate_password_hash, check_password_hash

from werkzeug.security import generate_password_hash, check_password_hash

# 1. MATCHING YOUR ORIGINAL REGISTRATION FORM SUBMISSION PATH
@app.route('/process_registration', methods=['POST'])
def process_registration():
    phone = request.form.get('phone', '').strip()
    login_pass = request.form.get('password', '').strip()
    withdraw_pass = request.form.get('withdrawal_password', '').strip()
    ref_code = request.form.get('ref_code', '').strip()

    if not phone or not login_pass:
        return render_template('register.html', error="All fields are required!")

    try:
        cursor = connection.cursor()
        
        # Check if phone number already exists
        cursor.execute("SELECT id FROM users WHERE phone = %s", (phone,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            return render_template('register.html', error="This phone number is already registered!")

        # Hash passwords securely before database entry
        hashed_login = generate_password_hash(login_pass)
        hashed_withdraw = generate_password_hash(withdraw_pass) if withdraw_pass else None

        # Insert fresh user record into database
        cursor.execute(
            "INSERT INTO users (phone, password, withdrawal_password, referral_code, balance) VALUES (%s, %s, %s, %s, 0.00)",
            (phone, hashed_login, hashed_withdraw, ref_code)
        )
        connection.commit()

        # Log user into active session memory instantly
        cursor.execute("SELECT id FROM users WHERE phone = %s", (phone,))
        new_user = cursor.fetchone()
        
        # Safely extract user ID whether database returns dict or tuple
        if isinstance(new_user, dict):
            session['user_id'] = new_user['id']
        else:
            session['user_id'] = new_user[0]
            
        session['user_phone'] = phone
        return redirect('/dashboard')

    except Exception as e:
        print(f"Registration Error: {e}")
        return render_template('register.html', error="Registration failed. Please try again.")


# 2. MATCHING YOUR ORIGINAL LOGIN FORM SUBMISSION PATH
@app.route('/process_login', methods=['POST'])
def process_login():
    phone = request.form.get('phone', '').strip()
    login_pass = request.form.get('password', '').strip()

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, password FROM users WHERE phone = %s", (phone,))
        user_record = cursor.fetchone()

        if user_record:
            # Safely extract details whether database returns dict or tuple
            if isinstance(user_record, dict):
                db_id = user_record['id']
                db_password = user_record['password']
            else:
                db_id = user_record[0]
                db_password = user_record[1]

            if check_password_hash(db_password, login_pass):
                session['user_id'] = db_id
                session['user_phone'] = phone
                return redirect('/dashboard')
        
        return render_template('login.html', error="Invalid phone number or password!")

    except Exception as e:
        print(f"Login Error: {e}")
        return render_template('login.html', error="Server error during login.")

def team_page_view():
    user_id = session.get('user_id')
    if not user_id:
        return "Unauthorized. Please log in first.", 401
        
    # Automatically generate the individual's UNIQUE invitation link
    base_url = "https://latex-foam-site.onrender.com"  # ← Change this to your live Render URL
    unique_referral_link = f"{base_url}/register?ref={user_id}"
    
    return render_template('team_dashboard.html', invite_link=unique_referral_link)

@app.route('/api/team/dashboard-data', methods=['GET'])
def get_team_dashboard_data():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    user_phone = session.get('user_phone', '0204216188') 
    
    # Return your dashboard data as JSON here
    return jsonify({"user_phone": user_phone})

    # 1. Fetch logged-in user identifier metadata safely from active sessions
    user_phone = session.get('user_phone', '0204216188') 

    # 2. Automatically generate the individual's UNIQUE invitation link using your live URL
    unique_referral_link = f"https://onrender.com{user_id}"

    # Line 185 onwards (Ensure this matches the 4-space indentation above)
    # If this is inside a try block or another structure, indent it by an additional 4 spaces.
    cursor.execute(
        "SELECT * FROM users WHERE id = %s", 
        (user_id,)
    )


    # 3. Pull level downlines directly from the Render database core
    downline = ReferralNetwork.query.filter_by(referrer_id=user_id).all()
    
    levels_data = {
        1: {"count": 0, "commission_rate": "30%", "members": []},
        2: {"count": 0, "commission_rate": "2%", "members": []},
        3: {"count": 0, "commission_rate": "1%", "members": []}
    }
    
    for member in downline:
        lvl = member.level
        if lvl in levels_data:
            levels_data[lvl]["count"] += 1
            levels_data[lvl]["members"].append({
                "id": member.referred_id,
                "date": member.joined_at.strftime('%Y-%m-%d %H:%M')
            })

    return jsonify({
        "username": user_phone,
        "referral_link": unique_referral_link,
        "total_team": len(downline),
        "levels": levels_data
    })

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


@app.route('/api/admin/users-list', methods=['GET'])
def admin_get_all_users():
    if not session.get('user_id') or not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403

    cursor = connection.cursor()
    # 2. Fetch all user records so the admin can monitor balances and accounts
    cursor.execute("SELECT id, phone, account_number, balance FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    
    user_list = []
    for u in users:
        user_list.append({
            "id": u[0],
            "phone": u[1],
            "account_number": u[2] if u[2] else f"ACC-{u[0]:05d}",
            "balance": float(u[3]) if u[3] else 0.00
        })
        
    return jsonify({"users": user_list})

@app.route('/api/admin/update-user-credentials', methods=['POST'])
def admin_modify_user_security():
    if not session.get('user_id') or not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
        
    data = request.get_json()
    target_user_id = data.get('user_id')
    change_type = data.get('type')  # 'login' or 'withdrawal'
    new_credential = data.get('value')
    
    if not target_user_id or not new_credential or len(new_credential) < 6:
        return jsonify({"error": "Invalid inputs. Minimum 6 characters required."}), 400
        
    from werkzeug.security import generate_password_hash
    hashed_value = generate_password_hash(new_credential)
    cursor = connection.cursor()
    
    # 3. Apply password overrides directly to the targeted user ID
    if change_type == 'login':
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_value, target_user_id))
    elif change_type == 'withdrawal':
        cursor.execute("UPDATE users SET withdrawal_password = %s WHERE id = %s", (hashed_value, target_user_id))
    else:
        return jsonify({"error": "Unknown operational flag type"}), 400
        
    connection.commit()
    return jsonify({"success": f"User {target_user_id}'s {change_type} password updated successfully."})


@app.route('/details')
def details():
    return render_template('details.html')
@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('login'))
    return redirect(url_for('admin'))
    

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    
init_db()
