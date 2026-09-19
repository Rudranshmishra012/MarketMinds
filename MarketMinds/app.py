"""
MarketMinds - AI-Powered Agricultural Market Intelligence Platform
======================================================================
Main Flask application. Wires together farmer authentication, profiles,
search history, the recommendation engine, sell-now-vs-wait algorithm,
buyer matching, and FPO aggregation logic into a multi-user platform.

Run:  python app.py
"""

import os
import re
import csv
from flask import render_template, request, session
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from utils.data_processor import load_mandi_prices, load_farmers, load_buyers, predict_price
from utils.recommendation_engine import rank_markets, get_best_market_with_reasons
from utils.sell_decision import sell_now_vs_wait
from utils.buyer_matching import match_buyers
from utils.grade_predictor import predict_grade_from_image

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

db = SQLAlchemy(app)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MOBILE_REGEX = re.compile(r"^[6-9]\d{9}$")  # 10-digit Indian mobile number pattern


# ---------------------------------------------------------------------------
# Database Models
# ---------------------------------------------------------------------------

class Farmer(db.Model):
    """A registered farmer account. Passwords are never stored in plain text."""
    __tablename__ = "farmer"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    state = db.Column(db.String(80), nullable=False)
    district = db.Column(db.String(80), nullable=False)
    village = db.Column(db.String(120), nullable=False)
    language = db.Column(db.String(40), nullable=False, default="Hindi")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    searches = db.relationship("FarmerSearch", backref="farmer", lazy=True,
                                cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", backref="farmer", lazy=True,
                                    cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def location_display(self):
        return f"{self.village}, {self.district}, {self.state}"


class FarmerSearch(db.Model):
    """Every crop search a farmer runs, plus a snapshot of the resulting
    recommendation so search history can be displayed without recomputation
    (prices/predictions can legitimately change over time)."""
    __tablename__ = "farmer_search"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmer.id"), nullable=False)
    crop = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    quality = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    waiting_days = db.Column(db.Integer, default=Config.DEFAULT_WAIT_DAYS)

    # Snapshot of the recommendation generated for this search (nullable --
    # populated once the farmer views /recommendation for this search)
    recommended_market = db.Column(db.String(120), nullable=True)
    expected_net_profit = db.Column(db.Float, nullable=True)
    decision = db.Column(db.String(20), nullable=True)  # SELL NOW / WAIT

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Transaction(db.Model):
    """A lightweight, prototype transaction/sale record. No real payment
    processing is implemented -- payment_status is a manual demo field."""
    __tablename__ = "transaction"

    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmer.id"), nullable=False)
    buyer_id = db.Column(db.String(20), nullable=False)      # Buyer_ID from buyers.csv
    buyer_name = db.Column(db.String(120), nullable=False)
    crop = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    market = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), default="Pending")          # Pending/Confirmed/Completed/Cancelled
    payment_status = db.Column(db.String(20), default="Pending")  # Pending/Processing/Paid
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

DUMMY_BEST_BUYER = {
    "buyer_name": "Ramesh Traders",
    "price_offered": 24500,      # in INR
    "quantity_required": 12,     # in quintals
    "upi_id": "marketminds@upi",
}

# ---------------------------------------------------------------------------
# Startup checks: ensure demo data + model exist so the app never crashes
# ---------------------------------------------------------------------------

def ensure_demo_data():
    missing = [p for p in [Config.MANDI_PRICES_CSV, Config.BUYERS_CSV, Config.FARMERS_CSV]
               if not os.path.exists(p)]
    if missing:
        print(f"[MarketMinds] Demo data missing ({missing}); generating now...")
        from utils.generate_data import main as generate_main
        generate_main()


def ensure_model():
    if not os.path.exists(Config.PRICE_MODEL_PATH):
        print("[MarketMinds] Price forecasting model not found; training now...")
        try:
            from utils.train_model import train
            train()
        except Exception as exc:  # noqa: BLE001
            print(f"[MarketMinds] Warning: model training failed ({exc}). "
                  f"The app will use the historical-trend fallback instead.")


ensure_demo_data()
ensure_model()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def get_current_farmer():
    farmer_id = session.get("farmer_id")
    if not farmer_id:
        return None
    try:
        return db.session.get(Farmer, farmer_id)
    except Exception:  # noqa: BLE001 - never let a DB hiccup crash rendering
        return None


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("farmer_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        # session has a farmer_id, but that account may no longer exist
        # (e.g. the database was reset/recreated while an old browser
        # cookie was still around) -- verify it actually resolves before
        # letting the route run, so templates never see a None farmer.
        if get_current_farmer() is None:
            session.clear()
            flash("Your session could not be verified. Please log in again.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_globals():
    farmer = get_current_farmer()

    # Logged-in farmer ki language use karo
    if farmer:
        language = farmer.language or "English"
    else:
        language = session.get("language", "English")

    return {
        "current_farmer": farmer,
        "language": language
    }


# ---------------------------------------------------------------------------
# Helpers - farmer input / search
# ---------------------------------------------------------------------------

def get_farmer_input():
    """Read the current farmer's latest crop search from the session."""
    return session.get("farmer_input")


def require_farmer_input():
    """Redirect to /dashboard if no active search exists yet."""
    if not get_farmer_input():
        flash("Please enter your crop details first.", "warning")
        return redirect(url_for("dashboard"))
    return None


def get_active_search():
    """Return the FarmerSearch DB row for the current session's search, if any."""
    search_id = session.get("search_id")
    if not search_id:
        return None
    return db.session.get(FarmerSearch, search_id)


# ---------------------------------------------------------------------------
# SCREEN - HOME
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ---------------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("farmer_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        state = request.form.get("state", "").strip()
        district = request.form.get("district", "").strip()
        village = request.form.get("village", "").strip()
        language = request.form.get("language", "Hindi").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not MOBILE_REGEX.match(mobile):
            errors.append("Please enter a valid 10-digit mobile number.")
        if not EMAIL_REGEX.match(email):
            errors.append("Please enter a valid email address.")
        if len(password) < Config.MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {Config.MIN_PASSWORD_LENGTH} characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if not state or not district or not village:
            errors.append("State, district, and village are required.")

        if not errors:
            if Farmer.query.filter_by(email=email).first():
                errors.append("An account with this email already exists.")
            if Farmer.query.filter_by(mobile=mobile).first():
                errors.append("An account with this mobile number already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", states=Config.STATES, languages=Config.LANGUAGES,
                                    form_data=request.form)

        farmer = Farmer(
            full_name=full_name, mobile=mobile, email=email,
            state=state, district=district, village=village, language=language,
        )
        farmer.set_password(password)

        try:
            db.session.add(farmer)
            db.session.commit()
        except Exception:  # noqa: BLE001
            db.session.rollback()
            flash("Something went wrong while creating your account. Please try again.", "danger")
            return render_template("register.html", states=Config.STATES, languages=Config.LANGUAGES,
                                    form_data=request.form)
        session["farmer_id"] = farmer.id
        session["language"] = farmer.language
        flash(f"Welcome to MarketMinds, {farmer.full_name}! Your account has been created.", "success")
        return redirect(url_for("dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("register.html", states=Config.STATES, languages=Config.LANGUAGES, form_data={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("farmer_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")

        if not identifier or not password:
            flash("Please enter both your email/mobile and password.", "danger")
            return render_template("login.html", form_data=request.form)

        farmer = Farmer.query.filter(
            (Farmer.email == identifier) | (Farmer.mobile == identifier)
        ).first()

        if not farmer or not farmer.check_password(password):
            flash("Invalid email/mobile or password.", "danger")
            return render_template("login.html", form_data=request.form)

        session["farmer_id"] = farmer.id
        session["language"] = farmer.language
        flash(f"Welcome back, {farmer.full_name}!", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("dashboard"))
        next_url = request.args.get("next")
        return redirect(next_url or url_for("dashboard"))

    return render_template("login.html", form_data={})


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    farmer = get_current_farmer()
    if not farmer:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        village = request.form.get("village", "").strip()
        district = request.form.get("district", "").strip()
        state = request.form.get("state", "").strip()
        language = request.form.get("language", "").strip()

        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not village or not district or not state:
            errors.append("Village, district, and state are required.")

        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            farmer.full_name = full_name
            farmer.village = village
            farmer.district = district
            farmer.state = state
            farmer.language = language
            db.session.commit()
            flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", farmer=farmer, states=Config.STATES, languages=Config.LANGUAGES)


# ---------------------------------------------------------------------------
# SCREEN - FARMER DASHBOARD
# ---------------------------------------------------------------------------

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    farmer = get_current_farmer()

    if request.method == "POST":
        crop = request.form.get("crop", "").strip()
        quantity_raw = request.form.get("quantity", "").strip()
        quality = request.form.get("quality", "").strip()
        location = request.form.get("location", "").strip() or farmer.location_display
        waiting_days_raw = request.form.get("waiting_days", str(Config.DEFAULT_WAIT_DAYS)).strip()

        errors = []
        if crop not in Config.CROPS:
            errors.append("Please select a valid crop.")
        if quality not in Config.QUALITY_GRADES:
            errors.append("Please select a valid quality grade.")
        if not location:
            errors.append("Please enter your location.")

        try:
            quantity = float(quantity_raw)
            if quantity <= 0:
                errors.append("Quantity must be greater than zero.")
        except ValueError:
            quantity = None
            errors.append("Quantity must be a valid number.")

        try:
            waiting_days = int(waiting_days_raw)
            if waiting_days < 0:
                errors.append("Waiting days cannot be negative.")
        except ValueError:
            waiting_days = Config.DEFAULT_WAIT_DAYS
            errors.append("Waiting days must be a valid whole number.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("dashboard.html", crops=Config.CROPS, qualities=Config.QUALITY_GRADES,
                                    farmer=farmer, form_data=request.form,
                                    latest_search=get_active_search())

        session["farmer_input"] = {
            "crop": crop, "quantity": quantity, "quality": quality,
            "location": location, "waiting_days": waiting_days,
        }

        record = FarmerSearch(
            farmer_id=farmer.id, crop=crop, quantity=quantity,
            quality=quality, location=location, waiting_days=waiting_days,
        )
        db.session.add(record)
        db.session.commit()
        session["search_id"] = record.id

        flash(f"Found market options for {quantity} quintals of {crop}.", "success")
        return redirect(url_for("market"))

    latest_search = get_active_search()
    default_form = get_farmer_input() or {"location": farmer.location_display,
                                           "waiting_days": Config.DEFAULT_WAIT_DAYS}

    return render_template("dashboard.html", crops=Config.CROPS, qualities=Config.QUALITY_GRADES,
                            farmer=farmer, form_data=default_form, latest_search=latest_search)


# ---------------------------------------------------------------------------
# AJAX - PREDICT QUALITY GRADE FROM AN UPLOADED PHOTO
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB


def _has_allowed_image_extension(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@app.route("/predict-grade", methods=["POST"])
@login_required
def predict_grade():
    """
    Farmer uploads a photo of their produce; we run a lightweight image
    analysis (see utils/grade_predictor.py) and suggest a quality grade.
    The farmer can still accept or override the suggestion before submitting
    the main crop-details form.
    """
    farmer = get_current_farmer()
    language = farmer.language if farmer else "English"

    image_file = request.files.get("crop_image")
    if image_file is None or image_file.filename == "":
        return jsonify({"error": "Please choose a photo to upload."}), 400

    if not _has_allowed_image_extension(image_file.filename):
        return jsonify({"error": "Please upload a JPG, PNG, or WEBP image."}), 400

    image_file.seek(0, os.SEEK_END)
    size_bytes = image_file.tell()
    image_file.seek(0)
    if size_bytes > MAX_IMAGE_BYTES:
        return jsonify({"error": "Image is too large. Please upload a photo under 8 MB."}), 400

    try:
        result = predict_grade_from_image(image_file, language=language)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result)


# ---------------------------------------------------------------------------
# SCREEN - MARKET INTELLIGENCE
# ---------------------------------------------------------------------------

@app.route("/market")
@login_required
def market():
    redirect_resp = require_farmer_input()
    if redirect_resp:
        return redirect_resp

    farmer_input = get_farmer_input()
    waiting_days = farmer_input.get("waiting_days", Config.DEFAULT_WAIT_DAYS)
    ranked = rank_markets(farmer_input["crop"], farmer_input["quantity"], waiting_days=waiting_days)

    chart_labels = [m["market"] for m in ranked]
    chart_profits = [m["expected_net_profit"] for m in ranked]
    chart_prices = [m["current_price"] for m in ranked]
    chart_predicted = [m["predicted_price"] for m in ranked]

    price_history = ranked[0]["price_history"] if ranked else []

    return render_template(
        "market.html",
        farmer_input=farmer_input,
        markets=ranked,
        chart_labels=chart_labels,
        chart_profits=chart_profits,
        chart_prices=chart_prices,
        chart_predicted=chart_predicted,
        price_history=price_history,
    )


# ---------------------------------------------------------------------------
# SCREEN - AI RECOMMENDATION
# ---------------------------------------------------------------------------

@app.route("/recommendation")
@login_required
def recommendation():
    redirect_resp = require_farmer_input()
    if redirect_resp:
        return redirect_resp

    farmer_input = get_farmer_input()
    waiting_days = farmer_input.get("waiting_days", Config.DEFAULT_WAIT_DAYS)
    best = get_best_market_with_reasons(farmer_input["crop"], farmer_input["quantity"], waiting_days=waiting_days)

    if not best:
        flash("No market data available for this crop yet.", "warning")
        return redirect(url_for("dashboard"))

    decision = sell_now_vs_wait(
        commodity=farmer_input["crop"],
        current_price=best["current_price"],
        predicted_price=best["predicted_price"],
        quantity=farmer_input["quantity"],
        waiting_days=waiting_days,
    )

    # Add a buyer-demand-aware reason if a strong buyer match exists (ties
    # the recommendation to real buyer data, not a canned phrase).
    top_buyers = match_buyers(farmer_input["crop"], farmer_input["quantity"], farmer_input["quality"])
    if top_buyers and top_buyers[0]["match_score"] >= 70:
        best["reasons"].append(
            f"Strong buyer demand nearby: {top_buyers[0]['buyer_name']} scores "
            f"{top_buyers[0]['match_score']}/100 for this crop and quality."
        )

    # Snapshot the recommendation onto the active search record, if one exists
    active_search = get_active_search()
    if active_search:
        active_search.recommended_market = best["market"]
        active_search.expected_net_profit = best["expected_net_profit"]
        active_search.decision = decision["decision"]
        db.session.commit()

    return render_template(
        "recommendation.html",
        farmer_input=farmer_input,
        best=best,
        decision=decision,
    )


# ---------------------------------------------------------------------------
# SCREEN - BUYER MATCHING
# ---------------------------------------------------------------------------

@app.route("/buyers")
@login_required
def buyers():
    redirect_resp = require_farmer_input()
    if redirect_resp:
        return redirect_resp

    farmer_input = get_farmer_input()

    mandi_df = load_mandi_prices()
    subset = mandi_df[mandi_df["Commodity"] == farmer_input["crop"]]
    reference_price = float(subset["Modal_Price"].tail(20).mean()) if not subset.empty else None

    ranked_buyers = match_buyers(
        commodity=farmer_input["crop"],
        quantity=farmer_input["quantity"],
        quality=farmer_input["quality"],
        market_reference_price=reference_price,
    )

    if not ranked_buyers:
        flash("No buyers currently listed for this crop.", "warning")
        return render_template("buyers.html", farmer_input=farmer_input, best_buyer=None, other_buyers=[])

    best_buyer = ranked_buyers[0]
    other_buyers = ranked_buyers[1:]

    return render_template("buyers.html", farmer_input=farmer_input,
                            best_buyer=best_buyer, other_buyers=other_buyers)


@app.route("/buyers/<buyer_id>")
@login_required
def buyer_details(buyer_id):
    """Full profile page for a single buyer -- this is what 'Continue with
    this Buyer' opens now, replacing the old broken /buyer_details.html
    link. Buyers are NOT registered platform users in this prototype; this
    is a read-only detail view built from the buyers.csv demo dataset."""
    buyers_df = load_buyers()
    match = buyers_df[buyers_df["Buyer_ID"] == buyer_id]

    if match.empty:
        flash("That buyer could not be found.", "danger")
        return redirect(url_for("buyers"))

    # Blank/missing cells come through pandas as NaN (which is truthy in
    # Jinja), so normalise them to None before they reach the template.
    buyer_row = {k: (None if isinstance(v, float) and v != v else v)
                 for k, v in match.iloc[0].to_dict().items()}

    # If the farmer has an active search that matches this buyer's crop,
    # show their personal match score + breakdown for this specific buyer.
    match_info = None
    farmer_input = get_farmer_input()
    if farmer_input and farmer_input.get("crop") == buyer_row["Crop"]:
        mandi_df = load_mandi_prices()
        subset = mandi_df[mandi_df["Commodity"] == farmer_input["crop"]]
        reference_price = float(subset["Modal_Price"].tail(20).mean()) if not subset.empty else None
        ranked = match_buyers(farmer_input["crop"], farmer_input["quantity"], farmer_input["quality"],
                               market_reference_price=reference_price)
        match_info = next((b for b in ranked if b["buyer_id"] == buyer_id), None)

    return render_template("buyer_details.html", buyer=buyer_row, match_info=match_info)


@app.route("/buyers/contact/<buyer_id>", methods=["POST"])
@login_required
def contact_buyer(buyer_id):
    """Create a prototype (demo-only) transaction record when a farmer
    chooses to proceed with a matched buyer. No real payment is processed."""
    redirect_resp = require_farmer_input()
    if redirect_resp:
        return redirect_resp

    farmer = get_current_farmer()
    farmer_input = get_farmer_input()

    buyers_df = load_buyers()
    match = buyers_df[buyers_df["Buyer_ID"] == buyer_id]

    if match.empty:
        flash("That buyer could not be found.", "danger")
        return redirect(url_for("buyers"))

    buyer_row = match.iloc[0]
    txn = Transaction(
        farmer_id=farmer.id,
        buyer_id=str(buyer_row["Buyer_ID"]),
        buyer_name=str(buyer_row["Buyer_Name"]),
        crop=farmer_input["crop"],
        quantity=farmer_input["quantity"],
        price=float(buyer_row["Price_Offered"]),
        market=None,
        status="Pending",
        payment_status="Pending",
    )
    db.session.add(txn)
    db.session.commit()

    flash(f"Demo transaction created with {txn.buyer_name} (status: Pending). "
          f"This is a prototype record only -- no real payment has been made.", "success")
    return redirect(url_for("buyer_details", buyer_id=buyer_id))


# ---------------------------------------------------------------------------
# SCREEN - FPO AGGREGATION
# ---------------------------------------------------------------------------

@app.route("/fpo", methods=["GET", "POST"])
@login_required
def fpo():
    farmer = get_current_farmer()
    farmers_df = load_farmers()

    farmer_input = get_farmer_input() or {}
    crop_filter = request.values.get("crop") or farmer_input.get("crop") or Config.CROPS[0]
    buyer_demand_raw = request.values.get("buyer_demand", "500")
    try:
        buyer_demand = float(buyer_demand_raw)
    except ValueError:
        buyer_demand = 500.0

    join_fpo = request.method == "POST" and request.form.get("join_fpo") == "yes"

    matching_farmers = farmers_df[farmers_df["Crop"] == crop_filter].to_dict(orient="records")

    # If the logged-in farmer opts in and has an active search for this crop,
    # their own quantity is added to the aggregation pool (clearly labeled).
    own_contribution = 0.0
    if join_fpo and farmer_input.get("crop") == crop_filter:
        own_contribution = float(farmer_input.get("quantity", 0))
        matching_farmers = [{
            "Farmer_ID": f"YOU-{farmer.id}",
            "Farmer_Name": f"{farmer.full_name} (You)",
            "Crop": crop_filter,
            "Quantity": own_contribution,
            "Quality": farmer_input.get("quality", "-"),
            "Location": farmer_input.get("location", farmer.location_display),
        }] + matching_farmers
        flash(f"Added your {own_contribution} quintals of {crop_filter} to the FPO group.", "success")

    total_quantity = sum(float(f["Quantity"]) for f in matching_farmers)

    if total_quantity >= buyer_demand:
        fpo_message = "Demand can be fulfilled through the current farmer group."
        fulfilled = True
    else:
        shortfall = round(buyer_demand - total_quantity, 2)
        fpo_message = (f"Add more farmers through the FPO to fulfill the buyer's demand "
                        f"(shortfall of {shortfall} quintals).")
        fulfilled = False

    return render_template(
        "fpo.html",
        crops=Config.CROPS,
        selected_crop=crop_filter,
        buyer_demand=buyer_demand,
        farmers=matching_farmers,
        total_quantity=round(total_quantity, 2),
        fulfilled=fulfilled,
        fpo_message=fpo_message,
        can_join=bool(farmer_input.get("crop") == crop_filter),
        already_joined=join_fpo,
    )


# ---------------------------------------------------------------------------
# SCREEN - SEARCH HISTORY
# ---------------------------------------------------------------------------

@app.route("/history")
@login_required
def history():
    farmer = get_current_farmer()
    # Every query is scoped to the logged-in farmer's own ID only.
    searches = (FarmerSearch.query
                .filter_by(farmer_id=farmer.id)
                .order_by(FarmerSearch.created_at.desc())
                .all())
    return render_template("history.html", searches=searches)


# ---------------------------------------------------------------------------
# JSON API — MarketMinds' own buyer-directory API
# ---------------------------------------------------------------------------
# Read-only endpoints over the same buyers.csv demo dataset the rest of the
# app uses. No login required (it's the same public directory data the
# Buyer Matching page already shows) -- these exist so buyer data can be
# consumed by something other than the HTML pages (e.g. a mobile client,
# a script, curl/Postman for testing, or a future partner integration).

def _clean_text(value):
    """Return a stripped string, or None for missing/NaN cells."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    text = str(value).strip()
    return text or None


def _buyer_row_to_dict(row) -> dict:
    """Convert one buyers.csv row into a plain JSON-safe dict with
    consistent field names (never leak raw pandas/numpy types into JSON)."""
    return {
        "buyer_id": str(row["Buyer_ID"]),
        "buyer_name": str(row["Buyer_Name"]),
        "crop": str(row["Crop"]),
        "quantity_required_quintals": float(row["Quantity_Required"]),
        "quality_required": str(row["Quality"]),
        "price_offered_per_quintal": float(row["Price_Offered"]),
        "location": str(row["Location"]),
        "distance_km": float(row["Distance_KM"]),
        "payment_score": float(row["Payment_Score"]),
        "dispute_score": float(row["Dispute_Score"]),
        "verified": bool(row["Verified"]),
        "contact_phone": _clean_text(row.get("Contact_Phone")),
        "contact_email": _clean_text(row.get("Contact_Email")),
    }


@app.route("/api/buyers", methods=["GET"])
def api_list_buyers():
    """GET /api/buyers
    GET /api/buyers?crop=Tomato

    Returns every buyer in the demo directory as JSON, optionally filtered
    to one crop. Example:
        curl "http://127.0.0.1:5000/api/buyers?crop=Tomato"
    """
    buyers_df = load_buyers()
    crop_filter = request.args.get("crop")

    if crop_filter:
        buyers_df = buyers_df[buyers_df["Crop"].str.lower() == crop_filter.strip().lower()]

    results = [_buyer_row_to_dict(row) for _, row in buyers_df.iterrows()]
    return jsonify({
        "ok": True,
        "count": len(results),
        "crop_filter": crop_filter,
        "buyers": results,
    })


@app.route("/api/buyers/<buyer_id>", methods=["GET"])
def api_get_buyer(buyer_id):
    """GET /api/buyers/<buyer_id>

    Returns one buyer's full profile as JSON, plus this farmer's live match
    score for that buyer if they're logged in with an active crop search.
    Example:
        curl "http://127.0.0.1:5000/api/buyers/B001"
    """
    buyers_df = load_buyers()
    match = buyers_df[buyers_df["Buyer_ID"] == buyer_id]

    if match.empty:
        return jsonify({"ok": False, "error": f"No buyer found with id '{buyer_id}'."}), 404

    buyer_data = _buyer_row_to_dict(match.iloc[0])

    match_info = None
    farmer_input = get_farmer_input()
    if session.get("farmer_id") and farmer_input and farmer_input.get("crop") == buyer_data["crop"]:
        mandi_df = load_mandi_prices()
        subset = mandi_df[mandi_df["Commodity"] == farmer_input["crop"]]
        reference_price = float(subset["Modal_Price"].tail(20).mean()) if not subset.empty else None
        ranked = match_buyers(farmer_input["crop"], farmer_input["quantity"], farmer_input["quality"],
                               market_reference_price=reference_price)
        found = next((b for b in ranked if b["buyer_id"] == buyer_id), None)
        if found:
            match_info = {
                "match_score": found["match_score"],
                "reliability_score": found["reliability_score"],
                "score_breakdown": found["score_breakdown"],
            }

    return jsonify({"ok": True, "buyer": buyer_data, "your_match": match_info})


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("base.html", error_message="Page not found."), 404


@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return render_template("base.html", error_message="Something went wrong on our end. Please try again."), 500


@app.route("/payment")
def scan_to_pay():
    # Later: fetch the actual matched buyer for the logged-in farmer/FPO
    # e.g. best_buyer = get_best_buyer_for_user(current_user.id)
    best_buyer = DUMMY_BEST_BUYER
    return render_template("payment.html", best_buyer=best_buyer)




# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
