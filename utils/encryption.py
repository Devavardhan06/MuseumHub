"""
Encryption utilities for data at rest and in transit
"""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

class EncryptionManager:
    """Manages encryption for sensitive data"""
    
    def __init__(self, key=None):
        if key:
            self.key = key.encode() if isinstance(key, str) else key
        else:
            # Get from environment or generate
            key_env = os.getenv('ENCRYPTION_KEY')
            if key_env:
                self.key = key_env.encode()
            else:
                # Generate and store (in production, use proper key management)
                self.key = Fernet.generate_key()
        
        self.cipher = Fernet(self.key)
    
    def encrypt(self, data):
        """Encrypt data"""
        if isinstance(data, str):
            data = data.encode()
        encrypted = self.cipher.encrypt(data)
        return base64.b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data):
        """Decrypt data"""
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        decrypted = self.cipher.decrypt(encrypted_bytes)
        return decrypted.decode()
    
    def encrypt_dict(self, data_dict):
        """Encrypt dictionary values"""
        encrypted = {}
        for key, value in data_dict.items():
            if isinstance(value, str) and value:
                encrypted[key] = self.encrypt(value)
            else:
                encrypted[key] = value
        return encrypted
    
    def decrypt_dict(self, encrypted_dict):
        """Decrypt dictionary values"""
        decrypted = {}
        for key, value in encrypted_dict.items():
            if isinstance(value, str) and value:
                try:
                    decrypted[key] = self.decrypt(value)
                except:
                    decrypted[key] = value  # If decryption fails, return original
            else:
                decrypted[key] = value
        return decrypted

# Global encryption manager instance
encryption_manager = EncryptionManager()

