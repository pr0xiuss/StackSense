"""Sample Python module for M3 IR normalization fixtures."""

from typing import Any
from functools import wraps


def audit_log(func: Any) -> Any:
    """Decorator auditing function execution."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)
    return wrapper


class OrderProcessor:
    """Processes customer orders."""

    def __init__(self, gateway: Any) -> None:
        self.gateway = gateway

    @audit_log
    def process_order(self, order_id: str, amount: float) -> bool:
        """Execute payment charge."""
        return bool(self.gateway.charge(order_id, amount))

