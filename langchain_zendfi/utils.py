"""
Utility functions for LangChain ZendFi integration.
"""

from typing import Optional, Dict, Any, List
import os
import hashlib
import uuid
from datetime import datetime, timedelta


def generate_idempotency_key(prefix: str = "pay") -> str:
    """
    Generate a unique idempotency key for payment requests.
    
    Idempotency keys prevent duplicate payments when requests are retried.
    
    Args:
        prefix: Key prefix (e.g., 'pay', 'session')
        
    Returns:
        Unique idempotency key string
        
    Example:
        >>> key = generate_idempotency_key()
        >>> print(key)  # 'pay_a1b2c3d4e5f6...'
    """
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def format_solana_address(address: str, length: int = 8) -> str:
    """
    Format a Solana address for display.
    
    Args:
        address: Full Solana address
        length: Number of characters to show at start/end
        
    Returns:
        Shortened address like '7xKNH...abc'
        
    Example:
        >>> format_solana_address('7xKNHsoap9DpE4bKNWzYXQ1GhGXgRqjCCZ')
        '7xKNHsoa...qjCCZ'
    """
    if len(address) <= length * 2 + 3:
        return address
    return f"{address[:length]}...{address[-length//2:]}"


def format_usd(amount: float, include_symbol: bool = True) -> str:
    """
    Format a USD amount for display.
    
    Args:
        amount: Amount in USD
        include_symbol: Whether to include $ symbol
        
    Returns:
        Formatted string like '$1.50'
        
    Example:
        >>> format_usd(1.5)
        '$1.50'
    """
    formatted = f"{amount:.2f}"
    return f"${formatted}" if include_symbol else formatted


def format_timestamp(iso_timestamp: str) -> str:
    """
    Format an ISO timestamp for human-readable display.
    
    Args:
        iso_timestamp: ISO 8601 timestamp string
        
    Returns:
        Human-readable date/time string
        
    Example:
        >>> format_timestamp('2026-01-20T15:30:00Z')
        'Jan 20, 2026 at 3:30 PM'
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.strftime('%b %d, %Y at %I:%M %p')
    except (ValueError, AttributeError):
        return iso_timestamp


def calculate_days_until(iso_timestamp: str) -> int:
    """
    Calculate days until a future timestamp.
    
    Args:
        iso_timestamp: ISO 8601 timestamp string
        
    Returns:
        Number of days until the timestamp
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo)
        delta = dt - now
        return max(0, delta.days)
    except (ValueError, AttributeError):
        return 0


def validate_solana_address(address: str) -> bool:
    """
    Basic validation for Solana wallet addresses.
    
    Checks length and character set. For production,
    use a proper Solana address validation library.
    
    Args:
        address: Wallet address to validate
        
    Returns:
        True if address appears valid
        
    Example:
        >>> validate_solana_address('7xKNHsoap9DpE4bKNWzYXQ1GhGXgRqjCCZ')
        True
    """
    if not address:
        return False
    # Solana addresses are base58 encoded, 32-44 characters
    if len(address) < 32 or len(address) > 44:
        return False
    # Base58 alphabet (no 0, O, I, l)
    valid_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    return all(c in valid_chars for c in address)


def create_progress_bar(current: float, total: float, width: int = 10) -> str:
    """
    Create a text progress bar.
    
    Args:
        current: Current value
        total: Maximum value
        width: Bar width in characters
        
    Returns:
        Progress bar string like '████████░░'
    """
    if total <= 0:
        return "░" * width
    percentage = min(current / total, 1.0)
    filled = int(percentage * width)
    return "█" * filled + "░" * (width - filled)


def get_env_or_raise(key: str, description: str = "") -> str:
    """
    Get required environment variable or raise with helpful message.
    
    Args:
        key: Environment variable name
        description: Human-readable description for error message
        
    Returns:
        Environment variable value
        
    Raises:
        ValueError: If environment variable is not set
    """
    value = os.getenv(key)
    if not value:
        desc = f" ({description})" if description else ""
        raise ValueError(f"Required environment variable {key}{desc} is not set")
    return value


class SessionKeyCache:
    """
    Simple in-memory cache for session key data.
    
    Useful for avoiding redundant API calls during a single session.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries (default: 5 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple[Any, datetime]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                return value
            del self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set cached value."""
        self._cache[key] = (value, datetime.now())
    
    def invalidate(self, key: str) -> None:
        """Remove cached value."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()


# Export commonly used functions
__all__ = [
    'generate_idempotency_key',
    'format_solana_address',
    'format_usd',
    'format_timestamp',
    'calculate_days_until',
    'validate_solana_address',
    'create_progress_bar',
    'get_env_or_raise',
    'SessionKeyCache',
]
