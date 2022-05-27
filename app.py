import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # extract all the purchase records from database
    portfolio = db.execute(
        "SELECT Ticker, sum(Qty) AS Qty FROM purchases WHERE user_id = ? GROUP BY Ticker HAVING sum(Qty) >= 1", session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    Total = 0
    # for each row in the portfolio, look up the current price
    for i in range(len(portfolio)):
        Cprice = int(lookup(portfolio[i]["Ticker"])["price"])
        CValue = portfolio[i]["Qty"]*Cprice
        Name = lookup(portfolio[i]["Ticker"])["name"]
        # add the currentprice ("Cprice") in to each row of the portfolio with key = "currentprice"
        portfolio[i].update({"currentprice": Cprice})

        # add the value ("CValue"), thats current price of stock * qty hold in to each row of the portfolio with key = "currentvalue"
        portfolio[i].update({"currentvalue": CValue})

        # add the company name of the stock in to each row of the portfolio with key = "companyname"
        portfolio[i].update({"companyname": Name})
        # Sum up all the values of each stock
        Total += portfolio[i]["currentvalue"]
    return render_template("index.html", portfolio=portfolio, cash=cash[0]["cash"], Total=Total+cash[0]["cash"])


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Ensure stock symbol was submitted
        symbol = request.form.get("symbol").upper()
        if not request.form.get("symbol") or not lookup(symbol):
            # return to samepage. show warning via HTML.
            return apology("must provide stock ticker", 400)
        if not request.form.get("shares").isdigit():
            return apology("No. of shares buy need to be a whole number", 400)
        if not request.form.get("shares") or int(request.form.get("shares")) < 0:
            # return to samepage. show warning via HTML.
            return apology("Have to buy at least 1 stock", 400)
        symbol = request.form.get("symbol")
        price = int(lookup(symbol)["price"])
        qty = int(request.form.get("shares"))
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        if price * int(qty) > balance[0]["cash"]:
            return apology("Insufficient Fund", 403)
        # insert a record into the database
        db.execute("INSERT INTO purchases(user_id, Price, Qty, Ticker, direction) VALUES(?,?,?,?,?)",
                   session["user_id"], price, qty, symbol.upper(), 'buy')
        Nbalance = balance[0]["cash"] - (price * qty)
        print(f"Type: {type(Nbalance)}, Amount: {Nbalance}")
        db.execute("UPDATE users SET cash = ? WHERE id = ?", Nbalance, session["user_id"])
        return redirect("/")
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # extract all the purchase records from database
    portfolio = db.execute("SELECT * FROM purchases WHERE user_id = ?", session["user_id"])
    return render_template("history.html", portfolio=portfolio)


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

    if request.method == "POST":

        # Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            # return to samepage. show warning via HTML.
            return apology("Please provide a stock symbol", 400)

        symbol = request.form.get("symbol")
        if not lookup(symbol):
            return apology("No Such stock ticker", 400)

        return render_template("quote.html",  name=lookup(symbol)["name"], price=lookup(symbol)["price"], symbol=lookup(symbol)["symbol"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username to check if username been used.
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) == 1:
            return apology("User name taken sorry", 400)

        # Check confirmation on password
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("password not match", 400)

        # insert username and hash of password to the username database.
        username = request.form.get("username")
        hashPassword = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashPassword)
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Get the list of ticker sybmols from the users portfolio that have stocks can sell.
    ticker = db.execute(
        "SELECT Ticker, sum(Qty) FROM purchases WHERE user_id = ? GROUP BY Ticker HAVING sum(Qty) >= 1", session["user_id"])
    if request.method == "POST":
        if not request.form.get("shares") or int(request.form.get("shares")) < 1:
            # return to samepage. show warning via HTML.
            return apology("Have to sell at least 1 stock", 400)
        # get symbol from form
        symbol = request.form.get("symbol")
        # get no. of shares from form, convert to integer
        qty = int(request.form.get("shares"))
        price = int(lookup(symbol)["price"])
        # it needs to look up the nummber of stocks available for sell.
        # Got to do a loop here to go thru every rows in the 'ticker' and look for the sum(qty)
        for i in range(len(ticker)):
            if (ticker[i]["Ticker"] == symbol):
                held_qty = ticker[i]["sum(Qty)"]
        if held_qty < qty:
            return apology("Don't have that many stocks to sell", 400)
        db.execute("INSERT INTO purchases(user_id, Price, Qty, Ticker, direction) VALUES(?,?,?,?,?)",
                   session["user_id"], price, qty*-1, symbol.upper(), 'sell')
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        Nbalance = balance[0]["cash"] + (price * int(qty))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", Nbalance, session["user_id"])
        return redirect("/")
    return render_template("sell.html", ticker=ticker)
