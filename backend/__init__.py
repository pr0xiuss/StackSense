"""StackSense backend package.

Includes runtime compatibility shims for Python 3.14 dataclass slots handling.
"""

from __future__ import annotations

import dataclasses
import inspect
import types
from typing import Any


def _apply_dataclass_slots_compat() -> None:
    """Workaround for CPython 3.14 issue with frozen=True and slots=True dataclasses.

    In Python 3.14, dataclasses._add_slots creates a new slotted class but fails
    to update closure cells referencing the original class in dynamically generated
    methods like __setattr__ and __delattr__. This causes attribute assignment
    or deletion on unexpected attributes to fail with TypeError: super(type, obj):
    obj is not an instance or subtype of type, instead of raising FrozenInstanceError
    (subclass of AttributeError).
    """
    orig_add_slots = getattr(dataclasses, "_add_slots", None)
    if orig_add_slots is None or getattr(orig_add_slots, "_is_compat_patched", False):
        return

    def _patched_add_slots(
        cls: type[Any],
        is_frozen: bool,
        weakref_slot: bool,
        defined_fields: Any,
    ) -> type[Any]:
        newcls: type[Any] = orig_add_slots(cls, is_frozen, weakref_slot, defined_fields)
        for member in newcls.__dict__.values():
            if isinstance(member, (classmethod, staticmethod)):
                member = member.__func__
            unwrapped = inspect.unwrap(member)
            funcs: list[types.FunctionType] = []
            if isinstance(unwrapped, types.FunctionType):
                funcs.append(unwrapped)
            elif isinstance(unwrapped, property):
                for f in (unwrapped.fget, unwrapped.fset, unwrapped.fdel):
                    if f is not None:
                        funcs.append(inspect.unwrap(f))
            for f in funcs:
                if f.__closure__:
                    for cell in f.__closure__:
                        try:
                            if cell.cell_contents is cls:
                                cell.cell_contents = newcls
                        except ValueError:
                            pass
        return newcls

    _patched_add_slots._is_compat_patched = True  # type: ignore[attr-defined]
    dataclasses._add_slots = _patched_add_slots  # type: ignore[attr-defined]


_apply_dataclass_slots_compat()
