import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    transactions = db.execute("SELECT symbol,SUM(shares) AS shares,price FROM transactions WHERE user_id = ? GROUP BY symbol",user_id)
    result_db = db.execute("SELECT cash FROM users WHERE id = ?",user_id)
    result = result_db[0]["cash"]

    return render_template("index.html",transactions = transactions, result = "%.2f" % result)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        shares = int(request.form.get("shares"))
        symbol = request.form.get("symbol")

        #symbol checks
        if not symbol:
            return apology("Missing Symbol")
        stock = lookup(symbol.upper())
        if stock == None:
            return apology("Symbol Does Not Exist")

        #Share checks
        if not shares:
            return apology("Missing shares")
        if shares < 0:
            return apology("Shares Not Allowed")

        #SQL checks
        #symbol per shares price
        symbol_price = shares * stock["price"]

        #check user money
        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]

        if user_cash < symbol_price:
            return apology("Not Enough Money")

        #Make the transaction
        uptd_cash = user_cash - symbol_price
        db.execute("UPDATE users SET cash = ? WHERE id = ?", uptd_cash, user_id)
        date = datetime.datetime.now()

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)",
                    user_id, stock["name"], shares ,stock["price"], date)

        flash("Bought!")

        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions = db.execute("SELECT symbol,shares,price,date FROM transactions WHERE user_id = ? ORDER BY date DESC",user_id)
    result_db = db.execute("SELECT cash FROM users WHERE id = ?",user_id)
    result = result_db[0]["cash"]

    return render_template("history.html",transactions = transactions, result = "%.2f" % result)



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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        #Receive quote
        quote = request.form.get("quote")
        if not quote:
            return apology("Missing Quote")

        stock = lookup(quote.upper())
        if stock == None:
            return apology("Quote don't exist")
        return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        #Check record
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Missing Username")
        if not password:
            return apology("Missing Password")
        if not confirmation:
            return apology("Missing Confirmation")
        if password != confirmation:
            return apology("Confirmation is incorrect")

        #Save registener
        hash = generate_password_hash(password)
        try:
            new_user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        except:
            return apology("Username already exists")

        session["user_id"] = new_user
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user_id = session["user_id"]
        symbols_db = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", user_id)
        return render_template("sell.html", symbols = [row["symbol"] for row in symbols_db])

    else:
        shares = int(request.form.get("shares"))
        symbol = request.form.get("symbol")

        #symbol checks
        if not symbol:
            return apology("Missing Symbol")
        stock = lookup(symbol.upper())
        if stock == None:
            return apology("Symbol Does Not Exist")

        #Share checks
        if not shares:
            return apology("Missing shares")
        if shares < 0:
            return apology("Shares Not Allowed")

        #SQL checks
        #symbol per shares price
        symbol_price = shares * stock["price"]

        #check user money
        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]

        user_shares_db = db.execute("SELECT SUM(shares) AS shares FROM transactions WHERE user_id = ? AND symbol = ?",user_id , symbol)
        user_shares = user_shares_db[0]["shares"]

        if shares > user_shares:
            return apology("Not Enough Shares!")

        #Make the transaction
        uptd_cash = user_cash + symbol_price
        db.execute("UPDATE users SET cash = ? WHERE id = ?", uptd_cash, user_id)
        date = datetime.datetime.now()

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)",
                    user_id, stock["name"], (-1)*shares ,stock["price"], date)

        flash("Sold!")
        return redirect("/")

@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    if request.method == "GET":
        return render_template("addcash.html")
    else:
        user_id = session["user_id"]
        #Check cash
        cash = int(request.form.get("addcash"))
        if not cash:
            return apology("Missing Cash")
        if cash < 0:
            return apology("Entry is not greater than zero")

        #See user cash
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]

        #Add cash
        upt_cash = user_cash + cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?",upt_cash,user_id)

        flash("Cash Added!")
        return redirect("/")
