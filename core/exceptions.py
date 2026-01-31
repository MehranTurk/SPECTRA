class FailureReason:
    PATCHED = "TARGET_PATCHED_OR_NOT_VULNERABLE"
    INCOMPATIBLE = "PAYLOAD_OR_ARCH_MISMATCH"
    NETWORK_BLOCK = "CONNECTION_REFUSED_OR_IPS_BLOCK"
    RPC_FAIL = "MSF_RPC_SYNC_ISSUE"
    UNDEFINED = "UNDEFINED_INTERNAL_ERROR"

class SpectraException(Exception):
    def __init__(self, message, reason=FailureReason.UNDEFINED):
        super().__init__(message)
        self.reason = reason
