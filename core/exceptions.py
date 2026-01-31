from __future__ import annotations
import traceback
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Any, Dict


class FailureReason(str, Enum):
    PATCHED = "TARGET_PATCHED_OR_NOT_VULNERABLE"
    INCOMPATIBLE = "PAYLOAD_OR_ARCH_MISMATCH"
    NETWORK_BLOCK = "CONNECTION_REFUSED_OR_IPS_BLOCK"
    RPC_FAIL = "MSF_RPC_SYNC_ISSUE"
    LLM_FAIL = "LLM_FAILURE"
    VALIDATION_FAIL = "VALIDATION_ERROR"
    UNDEFINED = "UNDEFINED_INTERNAL_ERROR"


@dataclass
class SpectraException(Exception):
    """
    Structured exception used across SPECTRA.

    - message: human readable message
    - reason: machine-friendly FailureReason
    - details: optional contextual data (e.g. command, payload, response)
    - original: optional wrapped original exception
    - traceback: captured traceback string (if original provided, captured from it)
    """
    message: str
    reason: FailureReason = FailureReason.UNDEFINED
    details: Optional[Dict[str, Any]] = field(default_factory=dict)
    original: Optional[BaseException] = None
    tb: Optional[str] = None

    def __post_init__(self):
        # Populate traceback if original exception was provided
        if self.original and not self.tb:
            # If original has __traceback__, capture its formatted traceback; otherwise capture current
            try:
                self.tb = "".join(traceback.format_exception(type(self.original), self.original, self.original.__traceback__))
            except Exception:
                # fallback: current stack
                self.tb = "".join(traceback.format_stack())

        # ensure base Exception is initialized with message for compatibility
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Return a serializable representation useful for structured logging / reporting."""
        return {
            "message": self.message,
            "reason": self.reason.value,
            "details": self.details or {},
            "original_type": type(self.original).__name__ if self.original else None,
            "traceback": self.tb,
        }

    def __str__(self) -> str:
        base = f"{self.reason.value}: {self.message}"
        if self.original:
            base += f" (caused by {type(self.original).__name__}: {self.original})"
        return base


# Domain-specific convenience subclasses -------------------------------------------------
class MSFRPCException(SpectraException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original: Optional[BaseException] = None):
        super().__init__(message=message, reason=FailureReason.RPC_FAIL, details=details or {}, original=original)


class ExploitExecutionException(SpectraException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original: Optional[BaseException] = None):
        super().__init__(message=message, reason=FailureReason.INCOMPATIBLE, details=details or {}, original=original)


class NetworkBlockException(SpectraException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original: Optional[BaseException] = None):
        super().__init__(message=message, reason=FailureReason.NETWORK_BLOCK, details=details or {}, original=original)


class LLMException(SpectraException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original: Optional[BaseException] = None):
        super().__init__(message=message, reason=FailureReason.LLM_FAIL, details=details or {}, original=original)


class ValidationException(SpectraException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original: Optional[BaseException] = None):
        super().__init__(message=message, reason=FailureReason.VALIDATION_FAIL, details=details or {}, original=original)
