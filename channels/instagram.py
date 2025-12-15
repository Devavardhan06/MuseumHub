"""
Instagram channel via Meta API
"""
from .base import BaseChannel
from models import db
import requests
import os

class InstagramChannel(BaseChannel):
    """Instagram channel implementation using Meta API"""
    
    def __init__(self):
        super().__init__('instagram', 'social')
        self.page_access_token = os.getenv('INSTAGRAM_PAGE_ACCESS_TOKEN')
        self.api_version = os.getenv('INSTAGRAM_API_VERSION', 'v18.0')
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
    
    def authenticate(self, verify_token, mode, challenge):
        """Verify webhook authentication"""
        verify_token_set = os.getenv('INSTAGRAM_VERIFY_TOKEN')
        if mode == 'subscribe' and verify_token == verify_token_set:
            return challenge
        return None
    
    def send_message(self, session, message, **kwargs):
        """Send DM via Instagram API"""
        recipient_id = session.channel_user_id
        
        if not recipient_id:
            raise ValueError("No recipient ID in session")
        
        url = f"{self.base_url}/me/messages"
        params = {
            'access_token': self.page_access_token
        }
        payload = {
            'recipient': {'id': recipient_id},
            'message': {'text': message}
        }
        
        try:
            response = requests.post(url, params=params, json=payload)
            response.raise_for_status()
            
            # Save message to database
            saved_message = self.save_message(
                session=session,
                content=message,
                direction='outbound',
                message_type='text',
                channel_message_id=response.json().get('message_id')
            )
            return saved_message
        except requests.exceptions.RequestException as e:
            # Log error
            print(f"Error sending Instagram message: {e}")
            raise
    
    def receive_message(self, data, **kwargs):
        """Receive DM from Instagram webhook"""
        entry = data.get('entry', [{}])[0]
        messaging = entry.get('messaging', [{}])[0]
        
        sender_id = messaging.get('sender', {}).get('id')
        message = messaging.get('message', {})
        message_text = message.get('text', '')
        message_id = message.get('mid')
        
        if not sender_id:
            return None
        
        # Get or create session
        session = self.get_session(channel_user_id=sender_id)
        if not session:
            session = self.create_session(
                channel_user_id=sender_id
            )
        
        # Save incoming message
        saved_message = self.save_message(
            session=session,
            content=message_text,
            direction='inbound',
            message_type='text',
            channel_message_id=message_id
        )
        
        return {
            'session': session,
            'message': saved_message
        }
    
    def setup_webhook(self, callback_url):
        """Setup webhook for Instagram"""
        # This would typically be done via Meta Developer Console
        # But we can provide instructions
        return {
            'instructions': f"""
            To set up Instagram webhook:
            1. Go to Meta Developer Console
            2. Navigate to your Instagram app
            3. Add webhook URL: {callback_url}
            4. Subscribe to 'messages' and 'messaging_postbacks' events
            5. Set verify token in environment variable INSTAGRAM_VERIFY_TOKEN
            """
        }

