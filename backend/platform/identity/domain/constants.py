"""Identity domain constants and validation constraints."""

import re

USERNAME_MIN_LENGTH: int = 3
USERNAME_MAX_LENGTH: int = 30
USERNAME_REGEX: str = r"^[A-Za-z0-9_]{3,30}$"
USERNAME_PATTERN: re.Pattern[str] = re.compile(USERNAME_REGEX)
