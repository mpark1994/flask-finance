import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
# from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# for ubuntu: export API_KEY=pk_416c7da607bc412a93acb94a75ea2c08
# for powershell: $Env:API_KEY = "pk_416c7da607bc412a93acb94a75ea2c08"

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, username TEXT NOT NULL, hash TEXT NOT NULL, cash NUMERIC NOT NULL DEFAULT 10000.00);")

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    db.execute("CREATE TABLE IF NOT EXISTS stocks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, shares INTEGER NOT NULL, price NUMERIC NOT NULL, symbol TEXT NOT NULL, time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));")

    # Set data values
    user_id = session["user_id"]
    stocks = db.execute(
        "SELECT symbol, name, price, SUM(shares) as total_shares FROM stocks WHERE user_id = ? GROUP BY symbol;", user_id)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    # Set amount of cash
    total = cash
    
    # Get rid of display if total shares = 0
    for i in range(len(stocks) - 1, -1, -1):
        stock = stocks[i]
        if stock["total_shares"] == 0:
            stocks.pop(i)

    return render_template("index.html", stocks=stocks, cash=cash, total=total, usd=usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get input & set data
        symbol = request.form.get("symbol").upper()
        symbol_data = lookup(symbol)
        user_id = session["user_id"]
        cash = db.execute(
            "SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        # Check for correct inputs
        if not symbol:
            return apology("symbol not entered", 400)
        if not symbol_data:
            return apology("invalid symbol", 400)

        # Check for correct input for shares
        try:
            shares = int(request.form.get("shares"))
            if shares <= 0:
                return apology("shares must be positive", 400)
        except:
            return apology("shares must be int", 400)

        # Set more data
        symbol_name = symbol_data["name"]
        symbol_price = symbol_data["price"]
        symbol_symbol = symbol_data["symbol"]

        # Get total price and check if user can afford
        total_price = symbol_price * shares
        updated_cash = cash - total_price

        if updated_cash < 0:
            return apology("can't afford!", 400)

        # Insert data into SQL
        db.execute("UPDATE users SET cash = ? WHERE id = ?;", updated_cash, user_id)
        db.execute("INSERT INTO stocks (user_id, name, shares, price, symbol) VALUES (?, ?, ?, ?, ?);",
                   user_id, symbol_name, shares, symbol_price, symbol_symbol)

        # Flash message
        flash("Bought!")

        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Set data
    user_id = session["user_id"]
    stocks = db.execute("SELECT * FROM stocks WHERE user_id = ?", user_id)

    return render_template("history.html", stocks=stocks, usd=usd)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get symbol input
        symbol = request.form.get("symbol")

        # # If user enters nothing
        if not symbol:
            return apology("missing symbol", 400)

        # # If symbol is not in API database
        if not lookup(symbol):
            return apology("invalid symbol", 400)

        return render_template("quoted.html", value=lookup(symbol))

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("missing password", 400)

        # Ensure passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 400)

        # No duplicate IDs
        name_list = db.execute("SELECT username FROM users")
        for users in name_list:
            if request.form.get('username') in users:
                return apology("account already exists", 400)

        # Create data
        username = request.form.get("username")
        password = request.form.get("password")

        # Password requires letters/numbers/symbols
        special_characters = """'"`~!@#$%^&*()-+?_=,<>/"""
        alpha = 0
        number = 0
        symbol = 0
        for char in password:

            # Check for letter
            if char.isalpha():
                alpha += 1

            # Check for number
            try:
                if int(char):
                    number += 1
            except:
                pass

            # Check for symbol
            if char in special_characters:
                symbol += 1

        if alpha == 0 or number == 0 or symbol == 0:
            return apology("password requires a letter, number, and a symbol", 400)

        # Create hash for user's password
        hash = generate_password_hash(password)

        try:
            # Insert data into database
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?);", username, hash)

            # direct user to index
            return redirect("/")

        except:
            # if username has a duplicate
            return apology("account already exists", 400)

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Set data values
    user_id = session["user_id"]
    stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM stocks WHERE user_id = ? GROUP BY symbol;", user_id)

    # Get rid of display if total shares = 0
    for i in range(len(stocks) - 1, -1, -1):
        stock = stocks[i]
        if stock["total_shares"] == 0:
            stocks.pop(i)

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get input data and set data values
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        stock_price = lookup(symbol)["price"]
        stock_name = lookup(symbol)["name"]
        current_shares = db.execute(
            "SELECT SUM(shares) as shares FROM stocks WHERE user_id = ? AND symbol = ? GROUP BY symbol;", user_id, symbol)[0]["shares"]
        current_cash = db.execute("SELECT cash FROM users WHERE id = ?;", user_id)[0]["cash"]

        # Check valid share inputs
        if shares <= 0:
            return apology("shares must be positive", 400)

        if current_shares < shares:
            return apology("not enough shares", 400)

        # Upate data to SQL
        db.execute("UPDATE users SET cash = ? WHERE id = ?;", current_cash + (shares * stock_price), user_id)
        db.execute("INSERT INTO stocks (user_id, name, shares, price, symbol) VALUES (?, ?, ?, ?, ?);",
                   user_id, stock_name, (shares * -1), stock_price, symbol)

        # Flash message
        flash("Sold!")

        return redirect("/")

    return render_template("sell.html", stocks=stocks)
