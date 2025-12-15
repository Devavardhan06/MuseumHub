from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_socketio import SocketIO, emit, join_room, leave_room
import stripe
from flask_cors import CORS
from models import db, User, Ticket, Booking, Escalation
from chatbot import get_chatbot_response
from dotenv import load_dotenv
import os
import re
from datetime import datetime, date, timedelta
from flask_migrate import Migrate
from admin_routes import admin_bp
from api_routes import api_bp
from session_manager import SessionManager
from channels import WebsiteChannel
from utils.analytics import analytics_manager
from functools import wraps

load_dotenv()

app = Flask(__name__)

app.config['BABEL_DEFAULT_LOCALE'] = os.getenv('BABEL_DEFAULT_LOCALE', 'en')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///dev.db')
app.config['STRIPE_PUBLIC_KEY'] = os.getenv('STRIPE_PUBLIC_KEY')
app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY')

db.init_app(app)
migrate = Migrate(app, db)
babel = Babel()
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Register blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# Initialize session manager (channels will be lazy-loaded)
session_manager = SessionManager()

def get_website_channel():
    """Get website channel (lazy initialization)"""
    return session_manager._get_channel('website')

stripe.api_key = app.config.get('STRIPE_SECRET_KEY')

# ------------------------------
# Authentication Decorator
# ------------------------------
def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Store the URL they were trying to access
            session['next_url'] = request.url
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ------------------------------
# Museum booking config
# ------------------------------
TIME_SLOTS = [
    "9AM–10AM",
    "10AM–11AM",
    "11AM–12PM",
    "1PM–2PM",
    "2PM–3PM",
    "3PM–4PM"
]

SLOT_CAPACITY = {
    "9AM–10AM": 20,
    "10AM–11AM": 25,
    "11AM–12PM": 25,
    "1PM–2PM": 30,
    "2PM–3PM": 30,
    "3PM–4PM": 20
}

# ------------------------------
# Locale functions
# ------------------------------
def get_locale():
    return session.get('locale', 'en')

babel.init_app(app, locale_selector=get_locale)

@app.context_processor
def inject_get_locale():
    return dict(get_locale=get_locale)

# ------------------------------
# Basic pages
# ------------------------------
@app.route('/set_locale/<locale>')
def set_locale(locale):
    session['locale'] = locale
    return redirect(request.referrer or url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    return render_template('home.html')

@app.route('/about')
@login_required
def about():
    return render_template('about.html')

@app.route('/services')
@login_required
def services():
    return render_template('services.html')

@app.route('/view')
@login_required
def view():
    return render_template('view.html')

@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    if request.method == 'POST':
        return "Thank you for your message!"
    return render_template('contact.html')

# ------------------------------
# Multi-Channel Features Pages (Main Website UI)
# ------------------------------

@app.route('/admin-portal')
def admin_portal_page():
    """Admin Portal page - accessible from main website"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        user = User.query.get(session['user_id'])
        if not user or (not getattr(user, 'is_admin', False) and getattr(user, 'role', None) != 'admin'):
            return redirect(url_for('home'))
    except:
        return redirect(url_for('home'))
    
    # Redirect to admin dashboard
    return redirect(url_for('admin.dashboard'))

@app.route('/instagram-integration')
@login_required
def instagram_page():
    """Instagram Integration page - accessible from main website"""
    return render_template('instagram_integration.html')

@app.route('/voice-assistant')
@login_required
def voice_page():
    """Voice Assistant page - accessible from main website"""
    return render_template('voice_assistant.html')

@app.route('/chat-api')
@login_required
def chat_api_page():
    """Chat API Management page - accessible from main website"""
    return render_template('chat_api.html')

# ------------------------------
# Registration & Login
# ------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    # If already logged in, redirect to home
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation
        if not username or not password or not email:
            return render_template('register.html', error="All fields are required")
        
        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match")
        
        if len(password) < 6:
            return render_template('register.html', error="Password must be at least 6 characters")
        
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error="Username already exists")
        
        # Create user with email if provided
        user = User(username=username, password=password, email=email if email else None)
        db.session.add(user)
        db.session.commit()
        
        # Auto login after registration
        session['user_id'] = user.id
        session['username'] = user.username
        session['is_admin'] = getattr(user, 'is_admin', False) or (getattr(user, 'role', None) == 'admin')
        
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect to home
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return render_template('login.html', error="Username and password are required")
        
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = getattr(user, 'is_admin', False) or (getattr(user, 'role', None) == 'admin')
            
            # Redirect to the page they were trying to access, or home
            next_url = session.pop('next_url', None)
            if next_url:
                return redirect(next_url)
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid username or password")
    return render_template('login.html')

# ------------------------------
# Booking API
# ------------------------------
@app.route("/api/availability/<date_str>")
def api_availability(date_str):
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        return jsonify({"error": "Date must be YYYY-MM-DD"}), 400

    slots_data = []
    for slot in TIME_SLOTS:
        booked_sum = db.session.query(db.func.coalesce(db.func.sum(Booking.visitors), 0))\
            .filter_by(date=target_date, time_slot=slot).scalar() or 0
        capacity = SLOT_CAPACITY.get(slot, 20)
        slots_data.append({
            "time_slot": slot,
            "capacity": capacity,
            "booked": int(booked_sum),
            "remaining": max(0, int(capacity - booked_sum)),
            "is_full": booked_sum >= capacity
        })
    return jsonify({"date": target_date.isoformat(), "slots": slots_data})

@app.route("/api/book", methods=["POST"])
def api_book():
    if "user_id" not in session:
        return jsonify({"error": "login_required"}), 401

    data = request.get_json() or {}
    date_str = data.get("date")
    time_slot = data.get("time_slot")
    visitors = int(data.get("visitors", 1))

    if not date_str or not time_slot:
        return jsonify({"error": "missing_date_or_slot"}), 400

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        return jsonify({"error": "invalid_date_format"}), 400

    if time_slot not in TIME_SLOTS:
        return jsonify({"error": "invalid_time_slot"}), 400

    booked_sum = db.session.query(db.func.coalesce(db.func.sum(Booking.visitors), 0))\
        .filter_by(date=target_date, time_slot=time_slot).scalar() or 0
    capacity = SLOT_CAPACITY.get(time_slot, 20)

    if booked_sum + visitors > capacity:
        return jsonify({"error": "slot_full_or_not_enough_capacity",
                        "available": max(0, capacity - booked_sum)}), 409

    booking = Booking(user_id=session["user_id"], date=target_date, time_slot=time_slot, visitors=visitors)
    db.session.add(booking)
    db.session.commit()

    return jsonify({"message": "booking_confirmed", "booking": booking.to_dict()}), 201

# ------------------------------
# Booking UI routes
# ------------------------------
@app.route("/calendar")
@login_required
def calendar_page():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)

    first_of_month = date(year, month, 1)
    next_month = date(year + int(month / 12), (month % 12) + 1, 1)
    days_in_month = (next_month - first_of_month).days

    return render_template("booking_calendar.html", year=year, month=month,
                           days_in_month=days_in_month, first_day=first_of_month.weekday(), today=today)

@app.route("/day_view")
@login_required
def day_view():
    date_str = request.args.get("date")
    if not date_str:
        return redirect(url_for('calendar_page'))
    availability = api_availability(date_str).get_json()
    return render_template("day_view.html", date=date_str, slots=availability["slots"])

@app.route('/book_ticket', methods=['GET', 'POST'])
@login_required
def book_ticket():
    if request.method == "POST":
        date_str = request.form.get("date")
        time_slot = request.form.get("time_slot")
        visitors = int(request.form.get("visitors", 1))

        # Validate input
        if not date_str or not time_slot:
            return render_template("booking_form.html",
                                   error="missing_date_or_slot", date=date_str, time_slot=time_slot,
                                   visitors=visitors, slots=TIME_SLOTS)

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            return render_template("booking_form.html",
                                   error="invalid_date_format", date=date_str, time_slot=time_slot,
                                   visitors=visitors, slots=TIME_SLOTS)

        if time_slot not in TIME_SLOTS:
            return render_template("booking_form.html",
                                   error="invalid_time_slot", date=date_str, time_slot=time_slot,
                                   visitors=visitors, slots=TIME_SLOTS)

        # Check availability
        booked_sum = db.session.query(db.func.coalesce(db.func.sum(Booking.visitors), 0))\
            .filter_by(date=target_date, time_slot=time_slot).scalar() or 0
        capacity = SLOT_CAPACITY.get(time_slot, 20)

        if booked_sum + visitors > capacity:
                return render_template("booking_form.html",
                                   error="slot_full_or_not_enough_capacity", date=date_str, time_slot=time_slot,
                                       visitors=visitors, slots=TIME_SLOTS)

        # Create booking
        booking = Booking(user_id=session["user_id"], date=target_date, time_slot=time_slot, visitors=visitors)
        booking.amount = booking.calculate_amount(TICKET_PRICE)
        booking.currency = 'USD'
        booking.payment_status = 'pending'  # Default to pending
        db.session.add(booking)
        db.session.commit()

        # Redirect to payment page (user can choose pay now or pay later)
        return redirect(url_for('payment', booking_id=booking.id))
    else:
        date_str = request.args.get("date", date.today().isoformat())
        time_slot = request.args.get("time_slot", "")
        return render_template("booking_form.html", date=date_str, time_slot=time_slot, visitors=1, slots=TIME_SLOTS)

@app.route("/my_bookings")
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=session["user_id"]).order_by(Booking.date.desc(), Booking.time_slot).all()
    return render_template("my_bookings.html", bookings=bookings)

@app.route("/cancel_booking/<int:booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.filter_by(id=booking_id, user_id=session["user_id"]).first()
    if not booking:
        return "Booking not found", 404
    db.session.delete(booking)
    db.session.commit()
    return redirect(url_for('my_bookings'))

# ------------------------------
# Admin view
# ------------------------------
@app.route("/admin/bookings")
def admin_bookings():
    if not session.get("is_admin"):
        return "Access denied", 403

    date_str = request.args.get("date")
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            bookings = Booking.query.filter_by(date=target_date).order_by(Booking.time_slot).all()
        except:
            bookings = Booking.query.order_by(Booking.date.desc()).limit(100).all()
    else:
        bookings = Booking.query.order_by(Booking.date.desc()).limit(200).all()

    return render_template("admin_bookings.html", bookings=bookings)

# ------------------------------
# Payment Gateway Module
# ------------------------------
# Price per visitor (in cents for Stripe)
TICKET_PRICE = 100  # $1.00 or Rs 100 (adjust based on currency)

@app.route('/payment/<int:booking_id>', methods=['GET', 'POST'])
def payment(booking_id):
    """Payment page for a booking"""
    if "user_id" not in session:
        return redirect(url_for('login'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    # Verify booking belongs to user
    if booking.user_id != session["user_id"]:
        return "Access denied", 403
    
    # Check if already paid
    if booking.payment_status == 'paid':
        return redirect(url_for('payment_success', booking_id=booking_id))
    
    # Handle pay later option
    if request.method == 'POST' and request.form.get('payment_option') == 'pay_later':
        booking.payment_status = 'cash_pending'
        booking.payment_method = 'cash'
        db.session.commit()
        return redirect(url_for('booking_confirmed', booking_id=booking_id))
    
    # Calculate amount
    amount = booking.calculate_amount(TICKET_PRICE)
    amount_cents = int(amount * 100)  # Convert to cents for Stripe
    
    if request.method == 'POST':
        try:
            # Create Payment Intent
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=booking.currency.lower() if booking.currency else 'usd',
                payment_method=request.form.get('payment_method_id'),
                confirmation_method='manual',
                confirm=True,
                metadata={
                    'booking_id': booking.id,
                    'user_id': session['user_id']
                }
            )
            
            # Update booking with payment info
            booking.payment_intent_id = payment_intent.id
            booking.payment_status = 'paid' if payment_intent.status == 'succeeded' else 'pending'
            booking.amount = amount
            booking.currency = booking.currency or 'USD'
            booking.payment_method = 'card'
            booking.transaction_id = payment_intent.id
            booking.paid_at = datetime.utcnow()
            db.session.commit()
            
            if payment_intent.status == 'succeeded':
                return redirect(url_for('payment_success', booking_id=booking_id))
            else:
                return render_template('payment.html', 
                                    booking=booking, 
                                    amount=amount,
                                    stripe_public_key=app.config['STRIPE_PUBLIC_KEY'],
                                    error="Payment processing. Please wait...")
        except stripe.error.CardError as e:
            return render_template('payment.html', 
                                booking=booking, 
                                amount=amount,
                                stripe_public_key=app.config['STRIPE_PUBLIC_KEY'],
                                error=str(e))
        except Exception as e:
            return render_template('payment.html', 
                                booking=booking, 
                                amount=amount,
                                stripe_public_key=app.config['STRIPE_PUBLIC_KEY'],
                                error=f"An error occurred: {str(e)}")
    
    return render_template('payment.html', 
                          booking=booking, 
                          amount=amount,
                          stripe_public_key=app.config['STRIPE_PUBLIC_KEY'])

@app.route('/create-payment-intent/<int:booking_id>', methods=['POST'])
def create_payment_intent(booking_id):
    """Create a Stripe Payment Intent for a booking"""
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.user_id != session["user_id"]:
        return jsonify({"error": "Access denied"}), 403
    
    if booking.payment_status == 'paid':
        return jsonify({"error": "Booking already paid"}), 400
    
    amount = booking.calculate_amount(TICKET_PRICE)
    amount_cents = int(amount * 100)
    
    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=booking.currency.lower() if booking.currency else 'usd',
            metadata={
                'booking_id': booking.id,
                'user_id': session['user_id']
            }
        )
        
        booking.payment_intent_id = payment_intent.id
        db.session.commit()
        
        return jsonify({
            'clientSecret': payment_intent.client_secret,
            'amount': amount
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/payment-success/<int:booking_id>')
def payment_success(booking_id):
    """Payment success page"""
    if "user_id" not in session:
        return redirect(url_for('login'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.user_id != session["user_id"]:
        return "Access denied", 403
    
    return render_template('payment_success.html', booking=booking)

@app.route('/booking-confirmed/<int:booking_id>')
def booking_confirmed(booking_id):
    """Booking confirmed page (for pay later option)"""
    if "user_id" not in session:
        return redirect(url_for('login'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.user_id != session["user_id"]:
        return "Access denied", 403
    
    return render_template('booking_confirmed.html', booking=booking)

@app.route('/payment-webhook', methods=['POST'])
def payment_webhook():
    """Stripe webhook handler for payment events"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400
    
    # Handle payment intent succeeded
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        booking_id = payment_intent['metadata'].get('booking_id')
        
        if booking_id:
            booking = Booking.query.get(booking_id)
            if booking:
                booking.payment_status = 'paid'
                booking.paid_at = datetime.utcnow()
                booking.transaction_id = payment_intent['id']
                db.session.commit()
    
    return jsonify({"status": "success"}), 200

@app.route('/chatbot', methods=['GET', 'POST'])
@login_required
def chatbot():
    if request.method == 'POST':
        data = request.get_json()
        user_message = data.get('message', '').strip()
        action = data.get('action')  # For booking actions
        step = data.get('step')  # For step-by-step booking
        booking_data = data.get('booking_data', {})  # Store booking data
        
        if not user_message and not action:
            return jsonify({"response": "Please ask me a question! I can help with booking tickets, exhibits, and more."})
        
        # Initialize booking session if starting booking
        if action == 'start_booking':
            if "user_id" not in session:
                return jsonify({
                    "response": "🔒 You need to be logged in to book tickets.\n\nPlease log in first, then I can help you complete your booking!",
                    "requires_login": True,
                    "buttons": [{"text": "🔗 Log In", "action": "login", "url": "/login"}]
                })
            
            # Initialize booking state
            session['chatbot_booking'] = {
                'step': 'select_date',
                'date': None,
                'time_slot': None,
                'visitors': None
            }
            session.modified = True  # Mark session as modified
            
            today = date.today()
            tomorrow = today + timedelta(days=1)
            next_week = today + timedelta(days=7)
            
            return jsonify({
                "response": "🎫 Great! Let's book your ticket step by step!\n\n**Step 1: Select Date**\n\nWhen would you like to visit?",
                "step": "select_date",
                "buttons": [
                    {"text": f"📅 Today ({today.strftime('%b %d')})", "action": "select_date", "value": "today"},
                    {"text": f"📅 Tomorrow ({tomorrow.strftime('%b %d')})", "action": "select_date", "value": "tomorrow"},
                    {"text": f"📅 Next Week ({next_week.strftime('%b %d')})", "action": "select_date", "value": next_week.isoformat()},
                    {"text": "📅 Choose Another Date", "action": "custom_date"}
                ],
                "booking_data": session['chatbot_booking']
            })
        
        # Handle step-by-step booking
        if step == 'select_date' or action == 'select_date':
            selected_date = data.get('date') or booking_data.get('date')
            if not selected_date:
                return jsonify({"response": "Please select a date to continue."})
            
            # Store date in session
            if 'chatbot_booking' not in session:
                session['chatbot_booking'] = {}
            session['chatbot_booking']['date'] = selected_date
            session['chatbot_booking']['step'] = 'select_time'
            session.modified = True  # Mark session as modified
            
            # Parse date
            if selected_date == 'today':
                target_date = date.today()
            elif selected_date == 'tomorrow':
                target_date = date.today() + timedelta(days=1)
            else:
                try:
                    target_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
                except:
                    target_date = date.today()
            
            # Get availability
            slots_data = []
            for slot in TIME_SLOTS:
                booked_sum = db.session.query(db.func.coalesce(db.func.sum(Booking.visitors), 0))\
                    .filter_by(date=target_date, time_slot=slot).scalar() or 0
                capacity = SLOT_CAPACITY.get(slot, 20)
                remaining = max(0, capacity - booked_sum)
                slots_data.append({
                    "time_slot": slot,
                    "remaining": remaining,
                    "is_full": booked_sum >= capacity,
                    "capacity": capacity
                })
            
            available_slots = [s for s in slots_data if not s['is_full']]
            
            if not available_slots:
                return jsonify({
                    "response": f"⚠️ All slots are full for {target_date.strftime('%B %d, %Y')}.\n\nWould you like to try another date?",
                    "step": "select_date",
                    "buttons": [
                        {"text": "📅 Try Tomorrow", "action": "select_date", "value": "tomorrow"},
                        {"text": "📅 Try Next Week", "action": "select_date", "value": (target_date + timedelta(days=7)).isoformat()},
                        {"text": "🔄 Start Over", "action": "start_booking"}
                    ]
                })
            
            # Create time slot buttons
            slot_buttons = []
            for slot_info in slots_data:
                if not slot_info['is_full']:
                    slot_buttons.append({
                        "text": f"⏰ {slot_info['time_slot']} ({slot_info['remaining']} spots)",
                        "action": "select_time",
                        "value": slot_info['time_slot']
                    })
            
            return jsonify({
                "response": f"✅ Date selected: **{target_date.strftime('%B %d, %Y')}**\n\n**Step 2: Select Time Slot**\n\nAvailable time slots:",
                "step": "select_time",
                "buttons": slot_buttons,
                "booking_data": session['chatbot_booking']
            })
        
        elif step == 'select_time' or action == 'select_time':
            selected_slot = data.get('time_slot') or booking_data.get('time_slot')
            if not selected_slot:
                return jsonify({"response": "Please select a time slot to continue."})
            
            session['chatbot_booking']['time_slot'] = selected_slot
            session['chatbot_booking']['step'] = 'select_visitors'
            session.modified = True  # Mark session as modified
            
            return jsonify({
                "response": f"✅ Time slot selected: **{selected_slot}**\n\n**Step 3: Number of Visitors**\n\nHow many visitors? (Maximum 10 per booking)",
                "step": "select_visitors",
                "buttons": [
                    {"text": "👤 1 Visitor", "action": "select_visitors", "value": "1"},
                    {"text": "👥 2 Visitors", "action": "select_visitors", "value": "2"},
                    {"text": "👥 3 Visitors", "action": "select_visitors", "value": "3"},
                    {"text": "👥 4 Visitors", "action": "select_visitors", "value": "4"},
                    {"text": "👥 5+ Visitors", "action": "custom_visitors"}
                ],
                "booking_data": session['chatbot_booking']
            })
        
        elif step == 'select_visitors' or action == 'select_visitors':
            visitors = int(data.get('visitors') or booking_data.get('visitors') or 1)
            if visitors < 1 or visitors > 10:
                return jsonify({"response": "Please select between 1 and 10 visitors."})
            
            session['chatbot_booking']['visitors'] = visitors
            session['chatbot_booking']['step'] = 'confirm_booking'
            session.modified = True  # Mark session as modified
            
            # Calculate amount
            amount = visitors * TICKET_PRICE
            booking_date = session['chatbot_booking'].get('date')
            time_slot = session['chatbot_booking'].get('time_slot')
            
            # Parse date for display
            if booking_date == 'today':
                display_date = date.today()
            elif booking_date == 'tomorrow':
                display_date = date.today() + timedelta(days=1)
            else:
                try:
                    display_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
                except:
                    display_date = date.today()
            
            return jsonify({
                "response": f"✅ **Booking Summary**\n\n📅 **Date:** {display_date.strftime('%B %d, %Y')}\n⏰ **Time Slot:** {time_slot}\n👥 **Visitors:** {visitors}\n💰 **Total Amount:** ${amount:.2f} USD\n\n**Step 4: Confirm & Pay**\n\nReady to confirm your booking?",
                "step": "confirm_booking",
                "buttons": [
                    {"text": "💳 Pay Online Now", "action": "confirm_and_pay", "payment_type": "online"},
                    {"text": "💵 Pay Later (Cash)", "action": "confirm_and_pay", "payment_type": "cash"},
                    {"text": "✏️ Edit Booking", "action": "start_booking"}
                ],
                "booking_data": session['chatbot_booking'],
                "amount": amount
            })
        
        elif action == 'confirm_and_pay':
            payment_type = data.get('payment_type', 'online')
            
            # Try to get booking data from multiple sources
            booking_info = session.get('chatbot_booking', {})
            booking_data_from_request = data.get('booking_data', {})
            
            # Merge request data with session data (request data takes precedence)
            if booking_data_from_request:
                # Update session with request data
                if 'chatbot_booking' not in session:
                    session['chatbot_booking'] = {}
                session['chatbot_booking'].update(booking_data_from_request)
                booking_info = session['chatbot_booking']
                session.modified = True  # Mark session as modified
            
            # Get values with fallbacks
            date_str = booking_info.get('date') or booking_data_from_request.get('date') or data.get('date')
            time_slot = booking_info.get('time_slot') or booking_data_from_request.get('time_slot') or data.get('time_slot')
            visitors_value = booking_info.get('visitors') or booking_data_from_request.get('visitors') or data.get('visitors')
            
            # Handle None case properly for visitors
            if visitors_value is None:
                visitors = 1
            else:
                try:
                    visitors = int(visitors_value)
                except (ValueError, TypeError):
                    visitors = 1
            
            # Final check - if still missing, return error with helpful message
            if not date_str or not time_slot:
                # Try to restore from session one more time
                booking_info = session.get('chatbot_booking', {})
                if booking_info:
                    date_str = booking_info.get('date') or date_str
                    time_slot = booking_info.get('time_slot') or time_slot
                    visitors_value = booking_info.get('visitors')
                    if visitors_value:
                        try:
                            visitors = int(visitors_value)
                        except:
                            visitors = 1
                
                if not date_str or not time_slot:
                    return jsonify({
                        "response": "❌ Booking information incomplete. Let's start over.\n\nI'll guide you through the booking process step by step!",
                        "action": "start_booking",
                        "buttons": [
                            {"text": "🎫 Start New Booking", "action": "start_booking"}
                        ]
                    })
            
            try:
                # Parse date
                if date_str == 'today':
                    target_date = date.today()
                elif date_str == 'tomorrow':
                    target_date = date.today() + timedelta(days=1)
                else:
                    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # Check availability again
                booked_sum = db.session.query(db.func.coalesce(db.func.sum(Booking.visitors), 0))\
                    .filter_by(date=target_date, time_slot=time_slot).scalar() or 0
                capacity = SLOT_CAPACITY.get(time_slot, 20)
                
                if booked_sum + visitors > capacity:
                    available = max(0, capacity - booked_sum)
                    return jsonify({
                        "response": f"❌ Sorry! Only {available} spot(s) available for {time_slot}.\n\nWould you like to choose a different time slot?",
                        "step": "select_time",
                        "buttons": [
                            {"text": "🔄 Choose Different Slot", "action": "select_date", "value": date_str},
                            {"text": "🔄 Start Over", "action": "start_booking"}
                        ]
                    })
                
                # Create booking
                booking = Booking(user_id=session["user_id"], date=target_date, time_slot=time_slot, visitors=visitors)
                booking.amount = booking.calculate_amount(TICKET_PRICE)
                booking.currency = 'USD'
                
                if payment_type == 'cash':
                    booking.payment_status = 'cash_pending'
                    booking.payment_method = 'cash'
                else:
                    booking.payment_status = 'pending'
                
                db.session.add(booking)
                db.session.commit()
                
                # Clear booking session
                session.pop('chatbot_booking', None)
                
                if payment_type == 'cash':
                    return jsonify({
                        "response": f"✅ **Booking Confirmed!**\n\n🎫 **Booking ID:** #{booking.id}\n📅 **Date:** {target_date.strftime('%B %d, %Y')}\n⏰ **Time Slot:** {time_slot}\n👥 **Visitors:** {visitors}\n💰 **Amount:** ${booking.amount:.2f} USD\n💵 **Payment:** Cash at Museum\n\n📝 **Instructions:**\n• Bring exact cash: ${booking.amount:.2f}\n• Show Booking ID #{booking.id} at entrance\n• Arrive on time for {time_slot}\n\n🎉 Your booking is confirmed!",
                        "success": True,
                        "booking": booking.to_dict(),
                        "payment_type": "cash",
                        "buttons": [
                            {"text": "💳 Pay Online Now ($" + f"{booking.amount:.2f})", "action": "pay_online", "booking_id": booking.id, "url": f"/payment/{booking.id}"},
                            {"text": "📋 View All Bookings", "action": "view_bookings", "url": "/my_bookings"}
                        ]
                    })
                else:
                    # For online payment, return payment link
                    return jsonify({
                        "response": f"✅ **Booking Created!**\n\n🎫 **Booking ID:** #{booking.id}\n📅 **Date:** {target_date.strftime('%B %d, %Y')}\n⏰ **Time Slot:** {time_slot}\n👥 **Visitors:** {visitors}\n💰 **Amount:** ${booking.amount:.2f} USD\n\n💳 **Complete Payment:**",
                        "success": True,
                        "booking": booking.to_dict(),
                        "payment_type": "online",
                        "payment_required": True,
                        "buttons": [
                            {"text": "💳 Pay Now ($" + f"{booking.amount:.2f})", "action": "pay_online", "booking_id": booking.id, "url": f"/payment/{booking.id}"},
                            {"text": "💵 Pay Later (Cash)", "action": "change_to_cash", "booking_id": booking.id},
                            {"text": "📋 View All Bookings", "action": "view_bookings", "url": "/my_bookings"}
                        ]
                    })
            except Exception as e:
                return jsonify({"response": f"❌ Error creating booking: {str(e)}\n\nLet's try again!", "action": "start_booking"})
        
        elif action == 'change_to_cash':
            booking_id = data.get('booking_id')
            if booking_id:
                booking = Booking.query.get(booking_id)
                if booking and booking.user_id == session.get('user_id'):
                    booking.payment_status = 'cash_pending'
                    booking.payment_method = 'cash'
                    db.session.commit()
                    return jsonify({
                        "response": f"✅ **Payment method changed to Cash!**\n\n💵 You can pay ${booking.amount:.2f} USD in cash when you visit.\n\n📝 **Instructions:**\n• Bring exact cash: ${booking.amount:.2f}\n• Show Booking ID #{booking.id} at entrance\n• Arrive on time for {booking.time_slot}\n\n🎉 Your booking is confirmed!",
                        "success": True,
                        "booking": booking.to_dict()
                    })
        
        elif action == 'custom_date':
            return jsonify({
                "response": "📅 Please enter the date in YYYY-MM-DD format (e.g., 2024-12-25)\n\nOr type the date you'd like to visit.",
                "step": "custom_date_input",
                "input_type": "date"
            })
        
        elif action == 'custom_visitors':
            return jsonify({
                "response": "👥 Please enter the number of visitors (1-10)\n\nOr type the number of visitors.",
                "step": "custom_visitors_input",
                "input_type": "number",
                "buttons": [
                    {"text": "👤 1", "action": "select_visitors", "value": "1"},
                    {"text": "👥 2", "action": "select_visitors", "value": "2"},
                    {"text": "👥 3", "action": "select_visitors", "value": "3"},
                    {"text": "👥 4", "action": "select_visitors", "value": "4"},
                    {"text": "👥 5", "action": "select_visitors", "value": "5"}
                ]
            })
        
        elif action == 'book_from_availability':
            # Start booking with pre-selected date and time slot
            date_str = data.get('date')
            time_slot = data.get('time_slot')
            
            if "user_id" not in session:
                return jsonify({
                    "response": "🔒 You need to be logged in to book tickets.",
                    "requires_login": True,
                    "buttons": [{"text": "🔗 Log In", "action": "login", "url": "/login"}]
                })
            
            # Initialize booking with pre-selected values
            session['chatbot_booking'] = {
                'step': 'select_visitors',
                'date': date_str,
                'time_slot': time_slot,
                'visitors': None
            }
            session.modified = True  # Mark session as modified
            
            return jsonify({
                "response": f"✅ Great choice! **{time_slot}** on {date_str}\n\n**Step 3: Number of Visitors**\n\nHow many visitors? (Maximum 10 per booking)",
                "step": "select_visitors",
                "buttons": [
                    {"text": "👤 1 Visitor", "action": "select_visitors", "value": "1"},
                    {"text": "👥 2 Visitors", "action": "select_visitors", "value": "2"},
                    {"text": "👥 3 Visitors", "action": "select_visitors", "value": "3"},
                    {"text": "👥 4 Visitors", "action": "select_visitors", "value": "4"},
                    {"text": "👥 5+ Visitors", "action": "custom_visitors"}
                ],
                "booking_data": session['chatbot_booking']
            })
        
        # Handle booking actions from chatbot
        if action == 'check_availability':
            date_str = data.get('date')
            if not date_str:
                return jsonify({"response": "Please provide a date to check availability."})
            
            try:
                if date_str == 'today':
                    target_date = date.today()
                elif date_str == 'tomorrow':
                    target_date = date.today() + timedelta(days=1)
                else:
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y']:
                        try:
                            target_date = datetime.strptime(date_str, fmt).date()
                            break
                        except:
                            continue
                    else:
                        return jsonify({"response": "Invalid date format. Please use YYYY-MM-DD format."})
                
                slots_data = []
                for slot in TIME_SLOTS:
                    booked_sum = db.session.query(db.func.coalesce(db.func.sum(Booking.visitors), 0))\
                        .filter_by(date=target_date, time_slot=slot).scalar() or 0
                    capacity = SLOT_CAPACITY.get(slot, 20)
                    remaining = max(0, capacity - booked_sum)
                    slots_data.append({
                        "time_slot": slot,
                        "remaining": remaining,
                        "is_full": booked_sum >= capacity,
                        "capacity": capacity
                    })
                
                response = f"📅 Availability for {target_date.strftime('%B %d, %Y')}:\n\n"
                available_slots = []
                for slot_info in slots_data:
                    if not slot_info['is_full']:
                        status = f"✅ Available ({slot_info['remaining']} spots left)"
                        available_slots.append(slot_info['time_slot'])
                    else:
                        status = "❌ Full"
                    response += f"• {slot_info['time_slot']}: {status}\n"
                
                if available_slots:
                    response += f"\n💡 **Available slots:** {', '.join(available_slots)}\n\nWould you like to book one of these slots?"
                    
                    # Create buttons for available slots
                    slot_buttons = []
                    for slot_info in slots_data:
                        if not slot_info['is_full']:
                            slot_buttons.append({
                                "text": f"⏰ {slot_info['time_slot']} ({slot_info['remaining']} spots)",
                                "action": "book_from_availability",
                                "time_slot": slot_info['time_slot'],
                                "date": date_str
                            })
                    
                    slot_buttons.append({"text": "🎫 Start New Booking", "action": "start_booking"})
                    
                    return jsonify({
                        "response": response, 
                        "slots": slots_data, 
                        "date": date_str,
                        "buttons": slot_buttons
                    })
                else:
                    response += "\n⚠️ All slots are full for this date. Please try another date."
                    return jsonify({
                        "response": response,
                        "buttons": [
                            {"text": "📅 Try Tomorrow", "action": "check_availability", "date": "tomorrow"},
                            {"text": "📅 Try Next Week", "action": "check_availability", "date": (target_date + timedelta(days=7)).isoformat()},
                            {"text": "🔄 Start Booking", "action": "start_booking"}
                        ]
                    })
            except Exception as e:
                return jsonify({"response": f"Error checking availability: {str(e)}"})
        
        elif action == 'book_ticket':
            # Check if user is logged in
            if "user_id" not in session:
                return jsonify({
                    "response": "🔒 You need to be logged in to book tickets.\n\nPlease log in first, then I can help you complete your booking!",
                    "requires_login": True
                })
            
            date_str = data.get('date')
            time_slot = data.get('time_slot')
            visitors = int(data.get('visitors', 1))
            
            if not date_str or not time_slot:
                return jsonify({"response": "Please provide date, time slot, and number of visitors to complete booking."})
            
            try:
                if date_str == 'today':
                    target_date = date.today()
                elif date_str == 'tomorrow':
                    target_date = date.today() + timedelta(days=1)
                else:
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y']:
                        try:
                            target_date = datetime.strptime(date_str, fmt).date()
                            break
                        except:
                            continue
                    else:
                        return jsonify({"response": "Invalid date format. Please use YYYY-MM-DD format."})
                
                if time_slot not in TIME_SLOTS:
                    return jsonify({"response": f"Invalid time slot. Available slots: {', '.join(TIME_SLOTS)}"})
                
                # Check availability
                booked_sum = db.session.query(db.func.coalesce(db.func.sum(Booking.visitors), 0))\
                    .filter_by(date=target_date, time_slot=time_slot).scalar() or 0
                capacity = SLOT_CAPACITY.get(time_slot, 20)
                
                if booked_sum + visitors > capacity:
                    available = max(0, capacity - booked_sum)
                    return jsonify({
                        "response": f"❌ Sorry! Only {available} spot(s) available for {time_slot} on {target_date.strftime('%B %d, %Y')}.\n\nPlease choose a different time slot or reduce the number of visitors."
                    })
                
                # Create booking
                booking = Booking(user_id=session["user_id"], date=target_date, time_slot=time_slot, visitors=visitors)
                db.session.add(booking)
                db.session.commit()
                
                # Calculate and set amount
                booking.amount = booking.calculate_amount(TICKET_PRICE)
                booking.currency = 'USD'
                db.session.commit()
                
                response = f"✅ Booking Confirmed!\n\n"
                response += f"📅 Date: {target_date.strftime('%B %d, %Y')}\n"
                response += f"⏰ Time Slot: {time_slot}\n"
                response += f"👥 Visitors: {visitors}\n"
                response += f"🎫 Booking ID: {booking.id}\n"
                response += f"💰 Amount: ${booking.amount:.2f}\n\n"
                response += "Please complete payment to confirm your booking!"
                
                return jsonify({
                    "response": response,
                    "booking": booking.to_dict(),
                    "success": True,
                    "payment_required": True,
                    "payment_url": f"/payment/{booking.id}"
                })
            except Exception as e:
                return jsonify({"response": f"Error creating booking: {str(e)}"})
        
        # Handle custom date/visitor input
        booking_state = session.get('chatbot_booking', {})
        current_step = booking_state.get('step') or step
        
        if current_step == 'custom_date_input' and user_message:
            # Try to parse date from message
            date_pattern = r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|today|tomorrow)\b'
            date_match = re.search(date_pattern, user_message.lower())
            if date_match:
                date_value = date_match.group(1).lower()
                return jsonify({
                    "action": "select_date",
                    "date": date_value,
                    "step": "select_date",
                    "booking_data": booking_state
                })
            else:
                return jsonify({
                    "response": "I couldn't understand that date. Please use format YYYY-MM-DD (e.g., 2024-12-25) or say 'today'/'tomorrow'.",
                    "step": "custom_date_input",
                    "buttons": [
                        {"text": "📅 Today", "action": "select_date", "value": "today"},
                        {"text": "📅 Tomorrow", "action": "select_date", "value": "tomorrow"},
                        {"text": "🔄 Start Over", "action": "start_booking"}
                    ]
                })
        
        elif current_step == 'custom_visitors_input' and user_message:
            # Try to extract number
            visitor_match = re.search(r'(\d+)', user_message)
            if visitor_match:
                visitors = int(visitor_match.group(1))
                if 1 <= visitors <= 10:
                    return jsonify({
                        "action": "select_visitors",
                        "visitors": str(visitors),
                        "step": "select_visitors",
                        "booking_data": booking_state
                    })
                else:
                    return jsonify({
                        "response": "Please enter a number between 1 and 10.",
                        "step": "custom_visitors_input",
                        "buttons": [
                            {"text": "👤 1 Visitor", "action": "select_visitors", "value": "1"},
                            {"text": "👥 2 Visitors", "action": "select_visitors", "value": "2"},
                            {"text": "👥 3 Visitors", "action": "select_visitors", "value": "3"},
                            {"text": "🔄 Back", "action": "select_time", "time_slot": booking_state.get('time_slot')}
                        ]
                    })
            else:
                return jsonify({
                    "response": "I couldn't understand that number. Please enter a number between 1 and 10.",
                    "step": "custom_visitors_input",
                    "buttons": [
                        {"text": "👤 1 Visitor", "action": "select_visitors", "value": "1"},
                        {"text": "👥 2 Visitors", "action": "select_visitors", "value": "2"},
                        {"text": "👥 3 Visitors", "action": "select_visitors", "value": "3"}
                    ]
                })
        
        # Regular chatbot responses
        if user_message:
            # Check if user is asking about availability for a specific date
            date_pattern = r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|today|tomorrow)\b'
            date_match = re.search(date_pattern, user_message.lower())
            
            if date_match:
                try:
                    date_str = date_match.group(1)
                    if date_str == 'today':
                        target_date = date.today()
                    elif date_str == 'tomorrow':
                        target_date = date.today() + timedelta(days=1)
                    else:
                        # Try to parse the date
                        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y']:
                            try:
                                target_date = datetime.strptime(date_str, fmt).date()
                                break
                            except:
                                continue
                        else:
                            target_date = None
                    
                    if target_date:
                        # Get availability for that date
                        slots_data = []
                        for slot in TIME_SLOTS:
                            booked_sum = db.session.query(db.func.coalesce(db.func.sum(Booking.visitors), 0))\
                                .filter_by(date=target_date, time_slot=slot).scalar() or 0
                            capacity = SLOT_CAPACITY.get(slot, 20)
                            remaining = max(0, capacity - booked_sum)
                            slots_data.append({
                                "time_slot": slot,
                                "remaining": remaining,
                                "is_full": booked_sum >= capacity
                            })
                        
                        response = f"📅 Availability for {target_date.strftime('%B %d, %Y')}:\n\n"
                        available_slots = []
                        for slot_info in slots_data:
                            if not slot_info['is_full']:
                                status = f"✅ Available ({slot_info['remaining']} spots left)"
                                available_slots.append(slot_info['time_slot'])
                            else:
                                status = "❌ Full"
                            response += f"• {slot_info['time_slot']}: {status}\n"
                        
                        if available_slots:
                            response += f"\n💡 I can help you book! Just tell me:\n"
                            response += "1. Which time slot? (e.g., '9AM–10AM')\n"
                            response += "2. How many visitors?\n\n"
                            if "user_id" not in session:
                                response += "⚠️ Note: You'll need to log in first to complete the booking."
                            else:
                                response += "I'll create the booking for you right away!"
                        else:
                            response += "\n⚠️ All slots are full for this date. Please try another date."
                        
                        bot_response = response
                    else:
                        bot_response = get_chatbot_response(user_message)
                except Exception as e:
                    bot_response = get_chatbot_response(user_message)
            else:
                bot_response = get_chatbot_response(user_message)
            
            return jsonify({"response": bot_response})
        else:
            return jsonify({"response": "Please provide a message or action."})
    else:
        return render_template('chatbot.html')

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

# WebSocket Events
@socketio.on('connect')
def handle_connect(auth):
    """Handle WebSocket connection"""
    token = auth.get('token') if auth else None
    if not token:
        emit('error', {'message': 'Authentication required'})
        return False
    
    # Authenticate token
    channel = get_website_channel()
    user_id = channel.authenticate(token)
    if not user_id:
        emit('error', {'message': 'Invalid token'})
        return False
    
    # Store user_id in session
    session['user_id'] = user_id
    session['socket_id'] = request.sid
    emit('connected', {'message': 'Connected successfully'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    session_id = session.get('session_id')
    if session_id:
        leave_room(session_id)

@socketio.on('join_session')
def handle_join_session(data):
    """Join a conversation session"""
    session_id = data.get('session_id')
    if session_id:
        join_room(session_id)
        session['session_id'] = session_id
        emit('joined', {'session_id': session_id})

@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle chat message via WebSocket"""
    user_id = session.get('user_id')
    if not user_id:
        emit('error', {'message': 'Not authenticated'})
        return
    
    message = data.get('message', '')
    session_id = data.get('session_id')
    
    # Get or create session
    channel = get_website_channel()
    if session_id:
        session_obj = channel.get_session(session_id=session_id)
    else:
        session_obj = channel.create_session(
            user_id=user_id,
            channel_user_id=str(user_id)
        )
        session_id = session_obj.session_id
        join_room(session_id)
    
    # Save incoming message
    result = channel.receive_message(
        {'message': message},
        user_id=user_id,
        session_id=session_id
    )
    
    # Get chatbot response
    bot_response = get_chatbot_response(message)
    
    # Save bot response
    channel.send_message(session_obj, bot_response)
    
    # Emit response to room
    emit('bot_response', {
        'message': bot_response,
        'session_id': session_id
    }, room=session_id)

# Error handler for escalations (only for unhandled exceptions)
@app.errorhandler(500)
def handle_500_error(e):
    """Handle 500 errors"""
    error_code = type(e).__name__ if hasattr(e, '__class__') else 'UnknownError'
    error_message = str(e) if e else 'Unknown error'
    
    # Only log critical errors, don't block the response
    try:
        with app.app_context():
            escalation = Escalation(
                type='error',
                severity='high',
                status='open',
                title=f"Error: {error_code}",
                description=error_message[:500],  # Limit description length
                error_code=error_code
            )
            db.session.add(escalation)
            db.session.commit()
    except Exception as db_error:
        # Don't fail if escalation creation fails
        print(f"Could not create escalation: {db_error}")
    
    # Return appropriate response based on request type
    if request.path.startswith('/api/'):
        return jsonify({
            "error": "An error occurred",
            "message": error_message[:200] if error_message else "Internal server error"
        }), 500
    else:
        # For HTML requests, render error page
        return render_template('error.html', error_message=error_message), 500

@app.errorhandler(404)
def handle_404_error(e):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not found", "path": request.path}), 404
    return render_template('error.html', error_message="Page not found"), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    print("\n🚀 Flask-SocketIO Chatbot Server is running!")
    print(f"📡 Main Server:     http://127.0.0.1:5001")
    
    try:
        # Use app.run for better compatibility, socketio will work with it
        print("✅ Starting Flask-SocketIO server...\n")
        socketio.run(app, debug=True, host='127.0.0.1', port=5001, allow_unsafe_werkzeug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user. Goodbye!")
        import sys
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
