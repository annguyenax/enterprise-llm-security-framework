import sys
import os
import uuid
import hashlib
from datetime import datetime, timedelta

# Add root to sys path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workspace.store import connect

def create_session(username):
    token = str(uuid.uuid4())
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = (datetime.now() + timedelta(days=1)).isoformat()
    
    with connect() as db:
        user = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            print(f"User {username} not found")
            return
            
        db.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user["id"], expires_at)
        )
    print(token)

if __name__ == "__main__":
    create_session("it.user1")
