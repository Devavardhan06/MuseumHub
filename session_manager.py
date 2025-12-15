"""
Session Manager for cross-channel conversation continuity
"""
from models import db, ConversationSession, ConversationMessage
from datetime import datetime, timedelta
from channels import WebsiteChannel, InstagramChannel, VoiceChannel

class SessionManager:
    """Manages conversation sessions across all channels"""
    
    def __init__(self):
        self._channels = {}
    
    def _get_channel(self, channel_name):
        """Lazy load channel to avoid app context issues"""
        if channel_name not in self._channels:
            if channel_name == 'website':
                self._channels[channel_name] = WebsiteChannel()
            elif channel_name == 'instagram':
                self._channels[channel_name] = InstagramChannel()
            elif channel_name == 'voice':
                self._channels[channel_name] = VoiceChannel()
            else:
                raise ValueError(f"Unknown channel: {channel_name}")
        return self._channels[channel_name]
    
    @property
    def channels(self):
        """Get channels dict (lazy loaded)"""
        return {
            'website': lambda: self._get_channel('website'),
            'instagram': lambda: self._get_channel('instagram'),
            'voice': lambda: self._get_channel('voice')
        }
    
    def get_or_create_session(self, channel_name, user_id=None, channel_user_id=None, context=None):
        """Get existing session or create new one"""
        channel = self._get_channel(channel_name)
        
        # Try to get existing active session
        session = channel.get_session(channel_user_id=channel_user_id)
        
        if not session:
            # Create new session
            session = channel.create_session(
                user_id=user_id,
                channel_user_id=channel_user_id,
                context=context or {}
            )
        elif session.status != 'active':
            # Reactivate closed session or create new one
            session = channel.create_session(
                user_id=user_id,
                channel_user_id=channel_user_id,
                context=context or {}
            )
        
        return session
    
    def get_user_sessions(self, user_id, channel_name=None, active_only=True):
        """Get all sessions for a user"""
        query = ConversationSession.query.filter_by(user_id=user_id)
        
        if channel_name:
            channel = self.channels.get(channel_name)
            if channel:
                query = query.filter_by(channel_id=channel.channel_db.id)
        
        if active_only:
            query = query.filter_by(status='active')
        
        return query.order_by(ConversationSession.last_activity.desc()).all()
    
    def get_session_context(self, session):
        """Get session context"""
        return session.get_context()
    
    def update_session_context(self, session, context_updates):
        """Update session context"""
        channel = self._get_channel(session.channel.name)
        channel.update_session_context(session, context_updates)
    
    def transfer_session(self, session, target_channel_name, target_channel_user_id):
        """Transfer session to another channel"""
        target_channel = self._get_channel(target_channel_name)
        
        # Get context from current session
        context = session.get_context()
        
        # Create new session in target channel
        new_session = target_channel.create_session(
            user_id=session.user_id,
            channel_user_id=target_channel_user_id,
            context=context
        )
        
        # Close old session
        session.status = 'transferred'
        db.session.commit()
        
        return new_session
    
    def close_session(self, session):
        """Close a session"""
        session.status = 'closed'
        session.updated_at = datetime.utcnow()
        db.session.commit()
    
    def get_conversation_history(self, session, limit=50):
        """Get conversation history for a session"""
        messages = ConversationMessage.query.filter_by(
            session_id=session.id
        ).order_by(ConversationMessage.created_at.desc()).limit(limit).all()
        
        return list(reversed(messages))  # Return in chronological order
    
    def cleanup_old_sessions(self, days_inactive=30):
        """Clean up old inactive sessions"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
        
        old_sessions = ConversationSession.query.filter(
            ConversationSession.status == 'closed',
            ConversationSession.updated_at < cutoff_date
        ).all()
        
        count = len(old_sessions)
        for session in old_sessions:
            db.session.delete(session)
        
        db.session.commit()
        return count

