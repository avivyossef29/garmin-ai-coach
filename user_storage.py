"""
User data persistence layer for conversations and Garmin tokens.
Uses simple file-based storage for POC.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Optional, List, Dict


def get_user_id(email: str) -> str:
    """Create consistent user ID from email."""
    return hashlib.md5(email.encode()).hexdigest()[:12]


def ensure_data_dir():
    """Ensure user_data directory exists."""
    os.makedirs("user_data", exist_ok=True)


def save_conversation(user_email: str, messages: List[Dict]):
    """Save chat history to file."""
    ensure_data_dir()
    user_id = get_user_id(user_email)
    
    data = {
        "user_id": user_id,
        "user_email": user_email,
        "last_updated": datetime.now().isoformat(),
        "messages": messages
    }
    
    filepath = f"user_data/{user_id}_conversation.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_conversation(user_email: str) -> List[Dict]:
    """Load previous chat history."""
    user_id = get_user_id(user_email)
    filepath = f"user_data/{user_id}_conversation.json"
    
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                return data.get("messages", [])
        except Exception as e:
            print(f"Error loading conversation: {e}")
            return []
    return []


def save_garmin_token(user_email: str, token_data: dict):
    """
    Save Garmin OAuth tokens for persistent login.
    token_data should contain oauth1_token and oauth2_token from garth.
    """
    ensure_data_dir()
    user_id = get_user_id(user_email)
    
    data = {
        "user_id": user_id,
        "user_email": user_email,
        "saved_at": datetime.now().isoformat(),
        "tokens": token_data
    }
    
    filepath = f"user_data/{user_id}_garmin_token.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_garmin_token(user_email: str) -> Optional[dict]:
    """Load saved Garmin OAuth tokens."""
    user_id = get_user_id(user_email)
    filepath = f"user_data/{user_id}_garmin_token.json"
    
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                return data.get("tokens")
        except Exception as e:
            print(f"Error loading token: {e}")
            return None
    return None
