"""
Base channel class for multi-channel communication
"""
from abc import ABC, abstractmethod
from datetime import datetime
from models import db, ConversationSession, ConversationMessage, Channel
import uuid

class BaseChannel(ABC):
    """Base class for all communication channels"""
    
    def __init__(self, channel_name, channel_type):
        self.channel_name = channel_name
        self.channel_type = channel_type
        self.channel_db = self._get_or_create_channel()
    
    def _get_or_create_channel(self):
        """Get or create channel in database"""
        channel = Channel.query.filter_by(name=self.channel_name).first()
        if not channel:
            channel = Channel(
                name=self.channel_name,
                type=self.channel_type,
                is_active=True
            )
            db.session.add(channel)
            db.session.commit()
        return channel
    
    def create_session(self, user_id=None, channel_user_id=None, context=None):
        """Create a new conversation session"""
        session_id = str(uuid.uuid4())
        session = ConversationSession(
            session_id=session_id,
            user_id=user_id,
            channel_id=self.channel_db.id,
            channel_user_id=channel_user_id,
            status='active',
            context=context
        )
        if context:
            session.set_context(context)
        db.session.add(session)
        db.session.commit()
        return session
    
    def get_session(self, session_id=None, channel_user_id=None):
        """Get existing session by session_id or channel_user_id"""
        if session_id:
            return ConversationSession.query.filter_by(
                session_id=session_id,
                channel_id=self.channel_db.id
            ).first()
        elif channel_user_id:
            return ConversationSession.query.filter_by(
                channel_user_id=channel_user_id,
                channel_id=self.channel_db.id,
                status='active'
            ).order_by(ConversationSession.last_activity.desc()).first()
        return None
    
    def save_message(self, session, content, direction='inbound', message_type='text', 
                     content_url=None, channel_message_id=None, metadata=None):
        """Save a message to the database"""
        message = ConversationMessage(
            session_id=session.id,
            message_type=message_type,
            direction=direction,
            content=content,
            content_url=content_url,
            channel_message_id=channel_message_id,
            metadata=metadata
        )
        db.session.add(message)
        
        # Update session activity
        session.last_activity = datetime.utcnow()
        db.session.commit()
        return message
    
    def update_session_context(self, session, context_updates):
        """Update session context"""
        current_context = session.get_context()
        current_context.update(context_updates)
        session.set_context(current_context)
        db.session.commit()
    
    @abstractmethod
    def send_message(self, session, message, **kwargs):
        """Send a message through this channel (implemented by subclasses)"""
        pass
    
    @abstractmethod
    def receive_message(self, data, **kwargs):
        """Receive a message from this channel (implemented by subclasses)"""
        pass
    
    @abstractmethod
    def authenticate(self, token_or_credentials):
        """Authenticate request for this channel"""
        pass

