"""
API Routes for Multi-Channel Communication
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps
from models import db, User, ConversationSession, AuthenticationToken
from channels import WebsiteChannel, InstagramChannel, VoiceChannel
from session_manager import SessionManager
from chatbot import get_chatbot_response
import json

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Session manager will be initialized lazily
def get_session_manager():
    """Get session manager instance"""
    if not hasattr(get_session_manager, '_instance'):
        get_session_manager._instance = SessionManager()
    return get_session_manager._instance

def get_website_channel():
    """Get website channel"""
    return get_session_manager()._get_channel('website')

def token_required(f):
    """Decorator for token-based authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if token:
            token = token.replace('Bearer ', '')
        else:
            token = request.args.get('token')
        
        if not token:
            return jsonify({"error": "Token required"}), 401
        
        auth_token = AuthenticationToken.query.filter_by(
            token=token,
            is_active=True
        ).first()
        
        if not auth_token or not auth_token.is_valid():
            return jsonify({"error": "Invalid or expired token"}), 401
        
        request.user_id = auth_token.user_id
        return f(*args, **kwargs)
    
    return decorated_function

# Website Chat API

@api_bp.route('/chat/websocket', methods=['GET'])
def websocket_info():
    """Get WebSocket connection info"""
    return jsonify({
        "websocket_url": "/socket.io/",
        "token_required": True
    })

@api_bp.route('/chat/message', methods=['POST'])
def chat_message():
    """Handle chat message via API"""
    try:
        # Allow both token and session auth
        user_id = None
        if 'user_id' in session:
            user_id = session['user_id']
        else:
            token = request.headers.get('Authorization', '').replace('Bearer ', '') or request.args.get('token')
            if token and AuthenticationToken:
                auth_token = AuthenticationToken.query.filter_by(token=token, is_active=True).first()
                if auth_token and auth_token.is_valid():
                    user_id = auth_token.user_id
        
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        data = request.json or {}
        message = data.get('message', '')
        session_id = data.get('session_id')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        channel = get_website_channel()
        
        # Get or create session
        if session_id:
            session_obj = channel.get_session(session_id=session_id)
            if not session_obj:
                session_obj = channel.create_session(
                    user_id=user_id,
                    channel_user_id=str(user_id)
                )
        else:
            session_obj = channel.create_session(
                user_id=user_id,
                channel_user_id=str(user_id)
            )
        
        # Save incoming message
        result = channel.receive_message(
            {'message': message},
            user_id=user_id,
            session_id=session_obj.session_id
        )
        
        # Get chatbot response
        if get_chatbot_response:
            bot_response = get_chatbot_response(message)
        else:
            bot_response = "I'm sorry, the chatbot service is temporarily unavailable."
        
        # Save bot response
        channel.send_message(session_obj, bot_response)
        
        return jsonify({
            "session_id": session_obj.session_id,
            "response": bot_response,
            "message_id": result['message'].id if result and 'message' in result else None
        })
    except Exception as e:
        print(f"Chat message error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to process message", "message": str(e)}), 500

@api_bp.route('/chat/session', methods=['POST'])
@token_required
def create_chat_session():
    """Create a new chat session"""
    channel = get_website_channel()
    token = request.headers.get('Authorization', '').replace('Bearer ', '') or request.args.get('token')
    
    session_obj = channel.create_session(
        user_id=request.user_id,
        channel_user_id=str(request.user_id)
    )
    
    return jsonify({
        "session_id": session_obj.session_id,
        "created_at": session_obj.created_at.isoformat()
    })

@api_bp.route('/chat/session/<session_id>/history', methods=['GET'])
def get_chat_history(session_id):
    """Get chat history"""
    try:
        # Allow both token and session auth
        user_id = None
        if 'user_id' in session:
            user_id = session['user_id']
        else:
            token = request.headers.get('Authorization', '').replace('Bearer ', '') or request.args.get('token')
            if token and AuthenticationToken:
                auth_token = AuthenticationToken.query.filter_by(token=token, is_active=True).first()
                if auth_token and auth_token.is_valid():
                    user_id = auth_token.user_id
        
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        
        channel = get_website_channel()
        session_obj = channel.get_session(session_id=session_id)
        
        if not session_obj:
            return jsonify({"error": "Session not found"}), 404
        
        if session_obj.user_id != user_id:
            return jsonify({"error": "Unauthorized"}), 403
        
        history = get_session_manager().get_conversation_history(session_obj)
        
        messages = [{
            "id": msg.id,
            "content": msg.content,
            "direction": msg.direction,
            "message_type": msg.message_type,
            "created_at": msg.created_at.isoformat()
        } for msg in history]
        
        return jsonify({
            "session_id": session_id,
            "messages": messages
        })
    except Exception as e:
        print(f"Get chat history error: {e}")
        return jsonify({"error": "Failed to get history", "message": str(e)}), 500

# Instagram Webhook

@api_bp.route('/instagram/webhook', methods=['GET', 'POST'])
def instagram_webhook():
    """Instagram webhook handler"""
    try:
        if not InstagramChannel:
            return jsonify({"error": "Instagram channel not available"}), 503
        
        instagram_channel = InstagramChannel()
        
        if request.method == 'GET':
            # Webhook verification
            mode = request.args.get('hub.mode')
            token = request.args.get('hub.verify_token')
            challenge = request.args.get('hub.challenge')
            
            result = instagram_channel.authenticate(token, mode, challenge)
            if result:
                return result, 200
            return "Forbidden", 403
        
        # Handle webhook event
        data = request.json or {}
        entry = data.get('entry', [])
        
        for entry_item in entry:
            messaging = entry_item.get('messaging', [])
            for message_event in messaging:
                result = instagram_channel.receive_message({'entry': [entry_item]})
                
                if result:
                    session_obj = result['session']
                    message_text = result['message'].content
                    
                    # Get chatbot response
                    if get_chatbot_response:
                        bot_response = get_chatbot_response(message_text)
                    else:
                        bot_response = "Thank you for your message!"
                    
                    # Send response via Instagram
                    instagram_channel.send_message(session_obj, bot_response)
        
        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"Instagram webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Webhook processing failed", "message": str(e)}), 500

# Voice API

@api_bp.route('/voice/transcribe', methods=['POST'])
def voice_transcribe():
    """Transcribe audio to text"""
    try:
        if not VoiceChannel:
            return jsonify({"error": "Voice channel not available"}), 503
        
        voice_channel = VoiceChannel()
        
        audio_data = request.files.get('audio')
        language = request.form.get('language', 'en-US')
        
        if not audio_data:
            return jsonify({"error": "No audio file provided"}), 400
        
        audio_bytes = audio_data.read()
        transcription = voice_channel.transcribe_audio(audio_bytes, language)
        
        if not transcription:
            return jsonify({"error": "Transcription failed"}), 500
        
        return jsonify({
            "text": transcription['text'],
            "confidence": transcription.get('confidence', 0)
        })
    except Exception as e:
        print(f"Voice transcribe error: {e}")
        return jsonify({"error": "Transcription error", "message": str(e)}), 500

@api_bp.route('/voice/synthesize', methods=['POST'])
def voice_synthesize():
    """Synthesize text to speech"""
    try:
        if not VoiceChannel:
            return jsonify({"error": "Voice channel not available"}), 503
        
        voice_channel = VoiceChannel()
        
        data = request.json or {}
        text = data.get('text')
        language = data.get('language', 'en-US')
        voice = data.get('voice', 'en-US-Standard-B')
        
        if not text:
            return jsonify({"error": "No text provided"}), 400
        
        audio_result = voice_channel.synthesize_speech(text, language, voice)
        
        if not audio_result:
            return jsonify({"error": "Synthesis failed"}), 500
        
        # Return audio as base64
        import base64
        audio_base64 = base64.b64encode(audio_result['audio_data']).decode()
        
        return jsonify({
            "audio_data": audio_base64,
            "format": audio_result['format']
        })
    except Exception as e:
        print(f"Voice synthesize error: {e}")
        return jsonify({"error": "Synthesis error", "message": str(e)}), 500

@api_bp.route('/voice/message', methods=['POST'])
def voice_message():
    """Handle voice message (transcribe, process, synthesize)"""
    try:
        if not VoiceChannel:
            return jsonify({"error": "Voice channel not available"}), 503
        
        voice_channel = VoiceChannel()
        
        audio_data = request.files.get('audio')
        phone_number = request.form.get('phone_number')
        language = request.form.get('language', 'en-US')
        
        if not audio_data:
            return jsonify({"error": "No audio file provided"}), 400
        
        audio_bytes = audio_data.read()
        
        # Receive and transcribe
        result = voice_channel.receive_message(
            {'audio_data': audio_bytes},
            phone_number=phone_number,
            language=language
        )
        
        if not result:
            return jsonify({"error": "Failed to process voice message"}), 500
        
        session_obj = result['session']
        message_text = result['message'].content
        
        # Get chatbot response
        if get_chatbot_response:
            bot_response = get_chatbot_response(message_text)
        else:
            bot_response = "Thank you for your message!"
        
        # Synthesize response
        audio_result = voice_channel.synthesize_speech(bot_response, language)
        
        if not audio_result:
            return jsonify({"error": "Failed to synthesize response"}), 500
        
        # Save bot response
        voice_channel.send_message(session_obj, bot_response, language=language)
        
        import base64
        audio_base64 = base64.b64encode(audio_result['audio_data']).decode()
        
        return jsonify({
            "session_id": session_obj.session_id,
            "response_text": bot_response,
            "response_audio": audio_base64,
            "format": audio_result['format']
        })
    except Exception as e:
        print(f"Voice message error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Voice message processing failed", "message": str(e)}), 500

# Token Management

@api_bp.route('/tokens', methods=['POST'])
def create_token():
    """Create authentication token (requires login)"""
    if 'user_id' not in session:
        return jsonify({"error": "Login required"}), 401
    
    data = request.json
    expires_days = data.get('expires_days', 30)
    name = data.get('name')
    
    channel = get_website_channel()
    token = channel.generate_token(
        user_id=session['user_id'],
        expires_days=expires_days,
        name=name
    )
    
    return jsonify({
        "token": token,
        "expires_days": expires_days
    })

@api_bp.route('/tokens', methods=['GET'])
def list_tokens():
    """List user's tokens"""
    try:
        if 'user_id' not in session:
            return jsonify({"error": "Login required"}), 401
        
        if not AuthenticationToken:
            return jsonify({"error": "Token system not available"}), 503
        
        tokens = AuthenticationToken.query.filter_by(
            user_id=session['user_id'],
            is_active=True
        ).all()
        
        return jsonify({
            "tokens": [{
                "id": token.id,
                "name": token.name,
                "created_at": token.created_at.isoformat(),
                "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                "last_used": token.last_used.isoformat() if token.last_used else None
            } for token in tokens]
        })
    except Exception as e:
        print(f"List tokens error: {e}")
        return jsonify({"error": "Failed to list tokens", "message": str(e)}), 500

@api_bp.route('/tokens/<int:token_id>', methods=['DELETE'])
def revoke_token(token_id):
    """Revoke a token"""
    try:
        if 'user_id' not in session:
            return jsonify({"error": "Login required"}), 401
        
        if not AuthenticationToken or not db:
            return jsonify({"error": "Token system not available"}), 503
        
        token = AuthenticationToken.query.get_or_404(token_id)
        
        if token.user_id != session['user_id']:
            return jsonify({"error": "Unauthorized"}), 403
        
        token.is_active = False
        db.session.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Revoke token error: {e}")
        return jsonify({"error": "Failed to revoke token", "message": str(e)}), 500

