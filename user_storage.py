"""
User data persistence layer for conversations and Garmin tokens.
Uses simple file-based storage for POC.

Security Model:
- user_id = hash(email + password)
- Data files are named with user_id
- Only someone with correct credentials can compute the hash and access their data
- No sensitive data (password) is stored on disk
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Optional, List, Dict


DATA_DIR = "user_data"
LAST_EMAIL_FILE = os.path.join(DATA_DIR, ".last_email")


def get_user_id(email: str, password: str) -> str:
    """
    Create secure user ID from email + password.
    This ensures only someone with both credentials can access the saved data.
    """
    combined = email.lower() + password
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def ensure_data_dir():
    """Ensure user_data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


# --- Last Email (for pre-filling login form) ---

def save_last_email(email: str):
    """Save last used email for convenience (pre-fill on refresh)."""
    ensure_data_dir()
    with open(LAST_EMAIL_FILE, "w") as f:
        f.write(email.lower())


def get_last_email() -> Optional[str]:
    """Get last used email to pre-fill login form."""
    if os.path.exists(LAST_EMAIL_FILE):
        try:
            with open(LAST_EMAIL_FILE, "r") as f:
                return f.read().strip()
        except Exception:
            pass
    return None


# --- Conversation Storage ---

def save_conversation(email: str, password: str, messages: List[Dict]):
    """Save chat history to file."""
    user_id = get_user_id(email, password)
    save_conversation_by_id(user_id, messages)


def load_conversation(email: str, password: str) -> List[Dict]:
    """Load previous chat history."""
    user_id = get_user_id(email, password)
    return load_conversation_by_id(user_id)


def save_conversation_by_id(user_id: str, messages: List[Dict]):
    """Save chat history by user_id directly."""
    ensure_data_dir()
    
    data = {
        "user_id": user_id,
        "last_updated": datetime.now().isoformat(),
        "messages": messages
    }
    
    filepath = f"user_data/{user_id}_conversation.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_conversation_by_id(user_id: str) -> List[Dict]:
    """Load previous chat history by user_id directly."""
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


# --- Garmin Token Storage ---

def save_garmin_token(email: str, password: str, token_data: str, username: str = None):
    """
    Save Garmin OAuth tokens and username for persistent login.
    token_data should be the base64 string from garth.dumps().
    """
    ensure_data_dir()
    user_id = get_user_id(email, password)
    
    data = {
        "user_id": user_id,
        "username": username,
        "saved_at": datetime.now().isoformat(),
        "tokens": token_data
    }
    
    filepath = f"user_data/{user_id}_garmin_token.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_garmin_token(email: str, password: str) -> Optional[str]:
    """Load saved Garmin OAuth tokens (returns base64 string for garth.loads())."""
    user_id = get_user_id(email, password)
    return load_garmin_token_by_id(user_id)


def load_garmin_token_by_id(user_id: str) -> Optional[str]:
    """Load saved Garmin OAuth tokens by user_id directly."""
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


def load_garmin_username_by_id(user_id: str) -> Optional[str]:
    """Load saved username by user_id directly."""
    filepath = f"user_data/{user_id}_garmin_token.json"
    
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                return data.get("username")
        except Exception:
            pass
    return None
