from typing import Optional
import re


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """Validate file extension"""
    ext = filename.lower().split('.')[-1]
    return f'.{ext}' in allowed_extensions


def sanitize_filename(filename: str) -> str:
    """Sanitize filename"""
    # Remove special characters
    return re.sub(r'[^\w\s.-]', '', filename)