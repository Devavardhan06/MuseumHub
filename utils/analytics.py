"""
Analytics and metrics utilities
"""
from models import db, ConversationSession, ConversationMessage, ConversationLog, Booking, Channel
from datetime import datetime, timedelta
from sqlalchemy import func, and_

class AnalyticsManager:
    """Manages analytics and metrics collection"""
    
    def get_conversation_metrics(self, start_date=None, end_date=None, channel_id=None):
        """Get conversation metrics"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        query = ConversationSession.query.filter(
            ConversationSession.created_at >= start_date,
            ConversationSession.created_at <= end_date
        )
        
        if channel_id:
            query = query.filter_by(channel_id=channel_id)
        
        total_sessions = query.count()
        active_sessions = query.filter_by(status='active').count()
        closed_sessions = query.filter_by(status='closed').count()
        
        # Average messages per session
        avg_messages = db.session.query(
            func.avg(func.count(ConversationMessage.id))
        ).join(
            ConversationSession
        ).filter(
            ConversationSession.created_at >= start_date,
            ConversationSession.created_at <= end_date
        ).group_by(ConversationSession.id).scalar() or 0
        
        # Average session duration
        sessions_with_duration = query.filter(
            ConversationSession.status == 'closed'
        ).all()
        
        total_duration = 0
        count = 0
        for session in sessions_with_duration:
            if session.updated_at and session.created_at:
                duration = (session.updated_at - session.created_at).total_seconds()
                total_duration += duration
                count += 1
        
        avg_duration = total_duration / count if count > 0 else 0
        
        return {
            'total_sessions': total_sessions,
            'active_sessions': active_sessions,
            'closed_sessions': closed_sessions,
            'avg_messages_per_session': round(avg_messages, 2),
            'avg_session_duration_seconds': round(avg_duration, 2),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def get_booking_conversion_metrics(self, start_date=None, end_date=None):
        """Get booking conversion metrics"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Total conversations
        total_conversations = ConversationSession.query.filter(
            ConversationSession.created_at >= start_date,
            ConversationSession.created_at <= end_date
        ).count()
        
        # Conversations that led to bookings
        sessions_with_bookings = db.session.query(ConversationSession).join(
            Booking, ConversationSession.user_id == Booking.user_id
        ).filter(
            Booking.created_at >= start_date,
            Booking.created_at <= end_date
        ).distinct().count()
        
        # Total bookings
        total_bookings = Booking.query.filter(
            Booking.created_at >= start_date,
            Booking.created_at <= end_date
        ).count()
        
        # Successful bookings (paid)
        successful_bookings = Booking.query.filter(
            Booking.created_at >= start_date,
            Booking.created_at <= end_date,
            Booking.payment_status == 'paid'
        ).count()
        
        conversion_rate = (sessions_with_bookings / total_conversations * 100) if total_conversations > 0 else 0
        success_rate = (successful_bookings / total_bookings * 100) if total_bookings > 0 else 0
        
        return {
            'total_conversations': total_conversations,
            'conversations_with_bookings': sessions_with_bookings,
            'total_bookings': total_bookings,
            'successful_bookings': successful_bookings,
            'conversion_rate': round(conversion_rate, 2),
            'success_rate': round(success_rate, 2),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def get_channel_metrics(self, start_date=None, end_date=None):
        """Get metrics by channel"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        channels = Channel.query.all()
        channel_metrics = []
        
        for channel in channels:
            sessions = ConversationSession.query.filter(
                ConversationSession.channel_id == channel.id,
                ConversationSession.created_at >= start_date,
                ConversationSession.created_at <= end_date
            ).all()
            
            total_sessions = len(sessions)
            total_messages = ConversationMessage.query.join(
                ConversationSession
            ).filter(
                ConversationSession.channel_id == channel.id,
                ConversationMessage.created_at >= start_date,
                ConversationMessage.created_at <= end_date
            ).count()
            
            channel_metrics.append({
                'channel_id': channel.id,
                'channel_name': channel.name,
                'channel_type': channel.type,
                'total_sessions': total_sessions,
                'total_messages': total_messages,
                'avg_messages_per_session': round(total_messages / total_sessions, 2) if total_sessions > 0 else 0
            })
        
        return channel_metrics
    
    def get_daily_stats(self, days=30):
        """Get daily statistics"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        daily_stats = []
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())
            
            sessions = ConversationSession.query.filter(
                ConversationSession.created_at >= day_start,
                ConversationSession.created_at <= day_end
            ).count()
            
            messages = ConversationMessage.query.filter(
                ConversationMessage.created_at >= day_start,
                ConversationMessage.created_at <= day_end
            ).count()
            
            bookings = Booking.query.filter(
                Booking.created_at >= day_start,
                Booking.created_at <= day_end
            ).count()
            
            daily_stats.append({
                'date': current_date.isoformat(),
                'sessions': sessions,
                'messages': messages,
                'bookings': bookings
            })
            
            current_date += timedelta(days=1)
        
        return daily_stats

# Global analytics manager instance
analytics_manager = AnalyticsManager()

