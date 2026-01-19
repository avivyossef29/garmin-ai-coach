"""
UI helper functions for the Garmin AI Running Coach.
"""

def friendly_error(error):
    """Convert technical errors to user-friendly messages."""
    error_str = str(error).lower()
    
    if "401" in error_str or "unauthorized" in error_str:
        return "Invalid email or password. Please check your credentials."
    elif "mfa" in error_str or "2fa" in error_str:
        return "Two-factor authentication required."
    elif "timeout" in error_str or "timed out" in error_str:
        return "Connection timed out. Please try again."
    elif "name resolution" in error_str or "failed to resolve" in error_str:
        return "Network error. Please check your internet connection and try again."
    elif "connectionerror" in error_str or "connection" in error_str:
        return "Network error. Please check your internet connection."
    elif "rate limit" in error_str or "429" in error_str:
        return "Too many requests. Please wait a moment and try again."
    elif "404" in error_str:
        return "Service temporarily unavailable. Please try again later."
    elif "openai" in error_str or "api_key" in error_str:
        return "OpenAI API key is invalid or missing."
    elif "invalid" in error_str and "code" in error_str:
        return "Invalid 2FA code. Please check and try again."
    else:
        # Keep it short - just the first line, no stack trace
        first_line = str(error).split('\n')[0]
        if len(first_line) > 100:
            return first_line[:100] + "..."
        return first_line
