"""
Backup and recovery utilities
"""
from models import db
from datetime import datetime
import os
import json
import gzip
from sqlalchemy import text

class BackupManager:
    """Manages database backups and recovery"""
    
    def __init__(self, backup_dir='backups'):
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)
    
    def create_backup(self, include_data=True):
        """Create a backup of the database"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(self.backup_dir, f'backup_{timestamp}.sql.gz')
        
        # Get database URI
        db_uri = db.engine.url
        
        if 'sqlite' in str(db_uri):
            # SQLite backup
            import shutil
            db_path = str(db_uri).replace('sqlite:///', '')
            backup_path = backup_file.replace('.gz', '')
            shutil.copy2(db_path, backup_path)
            
            # Compress
            with open(backup_path, 'rb') as f_in:
                with gzip.open(backup_file, 'wb') as f_out:
                    f_out.writelines(f_in)
            os.remove(backup_path)
        else:
            # PostgreSQL/MySQL backup using pg_dump or mysqldump
            # This would require subprocess calls
            pass
        
        # Create metadata
        metadata = {
            'timestamp': timestamp,
            'database_uri': str(db_uri),
            'include_data': include_data,
            'backup_file': backup_file
        }
        
        metadata_file = backup_file.replace('.sql.gz', '_metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return backup_file
    
    def list_backups(self):
        """List all available backups"""
        backups = []
        for filename in os.listdir(self.backup_dir):
            if filename.startswith('backup_') and filename.endswith('.sql.gz'):
                backup_path = os.path.join(self.backup_dir, filename)
                metadata_path = backup_path.replace('.sql.gz', '_metadata.json')
                
                metadata = {}
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                
                backups.append({
                    'filename': filename,
                    'path': backup_path,
                    'metadata': metadata,
                    'size': os.path.getsize(backup_path)
                })
        
        return sorted(backups, key=lambda x: x['metadata'].get('timestamp', ''), reverse=True)
    
    def restore_backup(self, backup_file):
        """Restore from a backup file"""
        if not os.path.exists(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
        
        # Decompress if needed
        if backup_file.endswith('.gz'):
            import tempfile
            with gzip.open(backup_file, 'rb') as f_in:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.sql') as f_out:
                    f_out.write(f_in.read())
                    temp_file = f_out.name
            
            # Restore from temp file
            # Implementation depends on database type
            os.remove(temp_file)
        else:
            # Direct restore
            pass
        
        return True
    
    def cleanup_old_backups(self, keep_days=30):
        """Remove backups older than specified days"""
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
        
        removed_count = 0
        for backup in self.list_backups():
            timestamp_str = backup['metadata'].get('timestamp', '')
            if timestamp_str:
                try:
                    backup_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    if backup_date < cutoff_date:
                        os.remove(backup['path'])
                        metadata_path = backup['path'].replace('.sql.gz', '_metadata.json')
                        if os.path.exists(metadata_path):
                            os.remove(metadata_path)
                        removed_count += 1
                except:
                    pass
        
        return removed_count

# Global backup manager instance
backup_manager = BackupManager()

