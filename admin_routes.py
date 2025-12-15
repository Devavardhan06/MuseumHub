"""
Admin Portal Routes
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from models import (
    db, User, Booking, ConversationSession, ConversationMessage, 
    Channel, ContentKnowledge, Escalation, ConversationLog
)
from utils.analytics import analytics_manager
from utils.backup import backup_manager
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for('login'))
        
        try:
            user = User.query.get(session['user_id'])
            if not user or (not user.is_admin and user.role != 'admin'):
                if request.path.startswith('/api/'):
                    return jsonify({"error": "Admin access required"}), 403
                return redirect(url_for('home'))
        except Exception as e:
            print(f"Error checking admin access: {e}")
            if request.path.startswith('/api/'):
                return jsonify({"error": "Database error"}), 500
            return redirect(url_for('home'))
        
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """Decorator to require specific role(s)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            
            user = User.query.get(session['user_id'])
            if not user or (user.role not in roles and not user.is_admin):
                return jsonify({"error": "Insufficient permissions"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard"""
    try:
        # Get metrics with error handling
        conversation_metrics = {}
        booking_metrics = {}
        channel_metrics = []
        daily_stats = []
        recent_escalations = []
        recent_bookings = []
        
        if analytics_manager:
            try:
                conversation_metrics = analytics_manager.get_conversation_metrics()
                booking_metrics = analytics_manager.get_booking_conversion_metrics()
                channel_metrics = analytics_manager.get_channel_metrics()
                daily_stats = analytics_manager.get_daily_stats(days=30)
            except Exception as e:
                print(f"Analytics error: {e}")
        
        if Escalation and db:
            try:
                recent_escalations = Escalation.query.filter_by(status='open').order_by(
                    Escalation.created_at.desc()
                ).limit(10).all()
            except Exception as e:
                print(f"Escalations query error: {e}")
        
        if Booking and db:
            try:
                recent_bookings = Booking.query.order_by(
                    Booking.created_at.desc()
                ).limit(10).all()
            except Exception as e:
                print(f"Bookings query error: {e}")
        
        return render_template('admin/dashboard.html',
                             conversation_metrics=conversation_metrics,
                             booking_metrics=booking_metrics,
                             channel_metrics=channel_metrics,
                             daily_stats=daily_stats,
                             recent_escalations=recent_escalations,
                             recent_bookings=recent_bookings)
    except Exception as e:
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html', error_message=f"Error loading dashboard: {str(e)}"), 500

@admin_bp.route('/bookings')
@admin_required
def bookings():
    """Manage bookings"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    bookings = Booking.query.order_by(Booking.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/bookings.html', bookings=bookings)

@admin_bp.route('/conversations')
@admin_required
def conversations():
    """View conversations"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    sessions = ConversationSession.query.order_by(
        ConversationSession.last_activity.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/conversations.html', sessions=sessions)

@admin_bp.route('/conversations/<int:session_id>')
@admin_required
def conversation_detail(session_id):
    """View conversation details"""
    session_obj = ConversationSession.query.get_or_404(session_id)
    messages = ConversationMessage.query.filter_by(
        session_id=session_id
    ).order_by(ConversationMessage.created_at.asc()).all()
    
    return render_template('admin/conversation_detail.html',
                         session=session_obj,
                         messages=messages)

@admin_bp.route('/channels')
@admin_required
def channels():
    """Manage channels"""
    channels_list = Channel.query.all()
    return render_template('admin/channels.html', channels=channels_list)

@admin_bp.route('/channels/<int:channel_id>/toggle', methods=['POST'])
@admin_required
def toggle_channel(channel_id):
    """Toggle channel active status"""
    channel = Channel.query.get_or_404(channel_id)
    channel.is_active = not channel.is_active
    db.session.commit()
    return jsonify({"success": True, "is_active": channel.is_active})

@admin_bp.route('/content')
@admin_required
def content():
    """Manage knowledge base content"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    content_items = ContentKnowledge.query.order_by(
        ContentKnowledge.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/content.html', content_items=content_items)

@admin_bp.route('/content/new', methods=['GET', 'POST'])
@admin_required
def content_new():
    """Create new content"""
    if request.method == 'POST':
        content = ContentKnowledge(
            title=request.form.get('title'),
            content=request.form.get('content'),
            category=request.form.get('category'),
            tags=request.form.get('tags'),
            created_by=session['user_id'],
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(content)
        db.session.commit()
        return redirect(url_for('admin.content'))
    
    return render_template('admin/content_form.html')

@admin_bp.route('/content/<int:content_id>/edit', methods=['GET', 'POST'])
@admin_required
def content_edit(content_id):
    """Edit content"""
    content = ContentKnowledge.query.get_or_404(content_id)
    
    if request.method == 'POST':
        content.title = request.form.get('title')
        content.content = request.form.get('content')
        content.category = request.form.get('category')
        content.tags = request.form.get('tags')
        content.is_active = request.form.get('is_active') == 'on'
        content.updated_by = session['user_id']
        db.session.commit()
        return redirect(url_for('admin.content'))
    
    return render_template('admin/content_form.html', content=content)

@admin_bp.route('/escalations')
@admin_required
def escalations():
    """View escalations"""
    status = request.args.get('status', 'open')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    escalations_list = Escalation.query.filter_by(status=status).order_by(
        Escalation.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/escalations.html',
                         escalations=escalations_list,
                         current_status=status)

@admin_bp.route('/escalations/<int:escalation_id>')
@admin_required
def escalation_detail(escalation_id):
    """View escalation details"""
    escalation = Escalation.query.get_or_404(escalation_id)
    return render_template('admin/escalation_detail.html', escalation=escalation)

@admin_bp.route('/escalations/<int:escalation_id>/assign', methods=['POST'])
@admin_required
def assign_escalation(escalation_id):
    """Assign escalation to user"""
    escalation = Escalation.query.get_or_404(escalation_id)
    escalation.assigned_to = request.json.get('user_id')
    escalation.status = 'in_progress'
    db.session.commit()
    return jsonify({"success": True})

@admin_bp.route('/escalations/<int:escalation_id>/resolve', methods=['POST'])
@admin_required
def resolve_escalation(escalation_id):
    """Resolve escalation"""
    escalation = Escalation.query.get_or_404(escalation_id)
    escalation.status = 'resolved'
    escalation.resolved_by = session['user_id']
    escalation.resolved_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True})

@admin_bp.route('/analytics')
@admin_required
def analytics():
    """Analytics dashboard"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.fromisoformat(start_date)
    if end_date:
        end_date = datetime.fromisoformat(end_date)
    
    conversation_metrics = analytics_manager.get_conversation_metrics(start_date, end_date)
    booking_metrics = analytics_manager.get_booking_conversion_metrics(start_date, end_date)
    channel_metrics = analytics_manager.get_channel_metrics(start_date, end_date)
    daily_stats = analytics_manager.get_daily_stats(days=30)
    
    return render_template('admin/analytics.html',
                         conversation_metrics=conversation_metrics,
                         booking_metrics=booking_metrics,
                         channel_metrics=channel_metrics,
                         daily_stats=daily_stats)

@admin_bp.route('/backups')
@admin_required
def backups():
    """Manage backups"""
    backups_list = backup_manager.list_backups()
    return render_template('admin/backups.html', backups=backups_list)

@admin_bp.route('/backups/create', methods=['POST'])
@admin_required
def create_backup():
    """Create a new backup"""
    backup_file = backup_manager.create_backup()
    return jsonify({"success": True, "backup_file": backup_file})

@admin_bp.route('/users')
@role_required('admin', 'manager')
def users():
    """Manage users"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    users_list = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/users.html', users=users_list)

@admin_bp.route('/users/<int:user_id>/update_role', methods=['POST'])
@role_required('admin')
def update_user_role(user_id):
    """Update user role"""
    user = User.query.get_or_404(user_id)
    new_role = request.json.get('role')
    
    if new_role in ['admin', 'manager', 'staff', 'user']:
        user.role = new_role
        if new_role == 'admin':
            user.is_admin = True
        db.session.commit()
        return jsonify({"success": True})
    
    return jsonify({"error": "Invalid role"}), 400

