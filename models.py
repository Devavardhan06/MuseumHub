from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Index
import json

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Role-based access (admin, manager, staff, user)
    role = db.Column(db.String(20), default='user')  # admin, manager, staff, user

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('tickets', lazy=True))

# NEW: Booking model (museum-ticket-style)
class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(50), nullable=False)   # e.g. "10AM–11AM"
    visitors = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Payment fields
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, failed, refunded, cash_pending
    amount = db.Column(db.Numeric(10, 2), nullable=True)  # Amount in currency
    currency = db.Column(db.String(3), default='USD')
    payment_intent_id = db.Column(db.String(255), nullable=True)  # Stripe Payment Intent ID
    payment_method = db.Column(db.String(50), nullable=True)  # card, cash, etc.
    transaction_id = db.Column(db.String(255), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('bookings', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat(),
            "time_slot": self.time_slot,
            "visitors": self.visitors,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "payment_status": self.payment_status,
            "amount": float(self.amount) if self.amount else None,
            "currency": self.currency,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None
        }
    
    def calculate_amount(self, price_per_visitor=100):
        """Calculate total amount for this booking"""
        return float(self.visitors * price_per_visitor)

# Multi-Channel Communication Models

class Channel(db.Model):
    """Represents a communication channel (website, instagram, voice, etc.)"""
    __tablename__ = "channels"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # website, instagram, voice, sms
    type = db.Column(db.String(50), nullable=False)  # chat, voice, social
    is_active = db.Column(db.Boolean, default=True)
    config = db.Column(db.Text, nullable=True)  # JSON config for channel-specific settings
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_config(self):
        """Parse and return config JSON"""
        if self.config:
            return json.loads(self.config)
        return {}
    
    def set_config(self, config_dict):
        """Set config as JSON"""
        self.config = json.dumps(config_dict)

class ConversationSession(db.Model):
    """Manages conversation sessions across channels"""
    __tablename__ = "conversation_sessions"
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    channel_user_id = db.Column(db.String(255), nullable=True)  # User ID in the channel (e.g., Instagram user ID)
    
    # Session state
    status = db.Column(db.String(20), default='active')  # active, closed, escalated
    context = db.Column(db.Text, nullable=True)  # JSON context data
    session_metadata = db.Column(db.Text, nullable=True)  # Additional metadata (renamed from metadata to avoid SQLAlchemy conflict)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('sessions', lazy=True))
    channel = db.relationship('Channel', backref=db.backref('sessions', lazy=True))
    
    def get_context(self):
        """Parse and return context JSON"""
        if self.context:
            return json.loads(self.context)
        return {}
    
    def set_context(self, context_dict):
        """Set context as JSON"""
        self.context = json.dumps(context_dict)
        self.updated_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()

class ConversationMessage(db.Model):
    """Stores all conversation messages across channels"""
    __tablename__ = "conversation_messages"
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('conversation_sessions.id'), nullable=False, index=True)
    message_type = db.Column(db.String(20), nullable=False)  # text, audio, image, file
    direction = db.Column(db.String(10), nullable=False)  # inbound, outbound
    content = db.Column(db.Text, nullable=False)
    content_url = db.Column(db.String(500), nullable=True)  # For audio, images, files
    
    # Channel-specific metadata
    channel_message_id = db.Column(db.String(255), nullable=True)  # Message ID from channel
    message_metadata = db.Column(db.Text, nullable=True)  # Additional metadata as JSON (renamed from metadata to avoid SQLAlchemy conflict)
    
    # Processing info
    processed = db.Column(db.Boolean, default=False)
    intent = db.Column(db.String(100), nullable=True)
    entities = db.Column(db.Text, nullable=True)  # JSON entities
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    session = db.relationship('ConversationSession', backref=db.backref('messages', lazy=True, order_by='ConversationMessage.created_at'))
    
    def get_entities(self):
        """Parse and return entities JSON"""
        if self.entities:
            return json.loads(self.entities)
        return []
    
    def set_entities(self, entities_list):
        """Set entities as JSON"""
        self.entities = json.dumps(entities_list)

class AuthenticationToken(db.Model):
    """Token-based authentication for API access"""
    __tablename__ = "authentication_tokens"
    
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=True)
    
    # Token properties
    name = db.Column(db.String(100), nullable=True)  # Token name/description
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    last_used = db.Column(db.DateTime, nullable=True)
    
    # Permissions (JSON)
    permissions = db.Column(db.Text, nullable=True)  # JSON array of permissions
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('tokens', lazy=True))
    channel = db.relationship('Channel', backref=db.backref('tokens', lazy=True))
    
    def get_permissions(self):
        """Parse and return permissions JSON"""
        if self.permissions:
            return json.loads(self.permissions)
        return []
    
    def is_valid(self):
        """Check if token is valid and not expired"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True

# Admin Portal Models

class ContentKnowledge(db.Model):
    """Knowledge base content for chatbot"""
    __tablename__ = "content_knowledge"
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=True)
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags
    
    # Content metadata
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)  # Higher priority = shown first
    views = db.Column(db.Integer, default=0)
    
    # Audit fields
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator = db.relationship('User', foreign_keys=[created_by], backref=db.backref('created_content', lazy=True))
    updater = db.relationship('User', foreign_keys=[updated_by], backref=db.backref('updated_content', lazy=True))

class ConversationLog(db.Model):
    """Logs for analytics and monitoring"""
    __tablename__ = "conversation_logs"
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('conversation_sessions.id'), nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    
    # Metrics
    message_count = db.Column(db.Integer, default=0)
    booking_count = db.Column(db.Integer, default=0)
    conversion_rate = db.Column(db.Numeric(5, 2), nullable=True)
    avg_response_time = db.Column(db.Numeric(10, 2), nullable=True)  # in seconds
    
    # Timestamps
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.Integer, nullable=True)  # in seconds
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    session = db.relationship('ConversationSession', backref=db.backref('logs', lazy=True))
    channel = db.relationship('Channel', backref=db.backref('logs', lazy=True))

class Escalation(db.Model):
    """Error and escalation management"""
    __tablename__ = "escalations"
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('conversation_sessions.id'), nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    
    # Escalation details
    type = db.Column(db.String(50), nullable=False)  # error, complaint, technical, booking_issue
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    status = db.Column(db.String(20), default='open')  # open, in_progress, resolved, closed
    
    # Details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    error_code = db.Column(db.String(100), nullable=True)
    stack_trace = db.Column(db.Text, nullable=True)
    
    # Assignment
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    session = db.relationship('ConversationSession', backref=db.backref('escalations', lazy=True))
    channel = db.relationship('Channel', backref=db.backref('escalations', lazy=True))
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref=db.backref('assigned_escalations', lazy=True))
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref=db.backref('resolved_escalations', lazy=True))

# Indexes for performance
Index('idx_session_id', ConversationMessage.session_id)
Index('idx_channel_id', ConversationMessage.session_id)
Index('idx_created_at', ConversationMessage.created_at)
Index('idx_conversation_logs_created', ConversationLog.created_at)
Index('idx_escalations_status', Escalation.status)
