"""
Website chat channel with WebSocket support
"""
from .base import BaseChannel
from models import db, AuthenticationToken
from datetime import datetime, timedelta
import secrets

class WebsiteChannel(BaseChannel):
    """Website chat channel implementation"""
    
    def __init__(self):
        super().__init__('website', 'chat')
    
    def authenticate(self, token):
        """Authenticate using token"""
        if not token:
            return None
        
        auth_token = AuthenticationToken.query.filter_by(
            token=token,
            channel_id=self.channel_db.id,
            is_active=True
        ).first()
        
        if auth_token and auth_token.is_valid():
            # Update last used
            auth_token.last_used = datetime.utcnow()
            db.session.commit()
            return auth_token.user_id
        return None
    
    def generate_token(self, user_id, expires_days=30, name=None):
        """Generate authentication token for user"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        auth_token = AuthenticationToken(
            token=token,
            user_id=user_id,
            channel_id=self.channel_db.id,
            name=name or f"Website Chat Token - {datetime.utcnow().strftime('%Y-%m-%d')}",
            expires_at=expires_at,
            is_active=True
        )
        db.session.add(auth_token)
        db.session.commit()
        return token
    
    def send_message(self, session, message, **kwargs):
        """Send message through website channel"""
        # Save message to database
        saved_message = self.save_message(
            session=session,
            content=message,
            direction='outbound',
            message_type='text'
        )
        return saved_message
    
    def receive_message(self, data, **kwargs):
        """Receive message from website channel"""
        user_id = kwargs.get('user_id')
        session_id = kwargs.get('session_id')
        channel_user_id = kwargs.get('channel_user_id')
        
        # Get or create session
        if session_id:
            session = self.get_session(session_id=session_id)
        else:
            session = self.get_session(channel_user_id=channel_user_id)
            if not session:
                session = self.create_session(
                    user_id=user_id,
                    channel_user_id=channel_user_id
                )
        
        # Save incoming message
        message_content = data.get('message', '')
        saved_message = self.save_message(
            session=session,
            content=message_content,
            direction='inbound',
            message_type='text',
            metadata=str(data)
        )
        
        return {
            'session': session,
            'message': saved_message
        }

