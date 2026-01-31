import logging
import time
from typing import Optional, Any, Dict
from pymetasploit3.msfrpc import MsfRpcClient

from core.exceptions import MSFRPCException

logger = logging.getLogger("core.rpc_client")


class MSFClient:
    """
    Thin, safer wrapper around pymetasploit3.MsfRpcClient.

    Backwards-compatible notes:
    - connect() still returns True/False (like original) for compatibility with main.py.
    - New helpers available: connect_or_raise(), disconnect(), is_connected(), health_check(), ensure_connected().
    - Provides a context-manager interface for deterministic cleanup.

    Usage:
      msf = MSFClient(password="pw", host="127.0.0.1", port=55553)
      if msf.connect():
          ... # use msf.client
      msf.disconnect()
    """

    def __init__(
        self,
        password: str,
        host: str = "127.0.0.1",
        port: int = 55553,
        user: str = "msf",
        ssl: bool = False,
        timeout: int = 10,
        connect_retries: int = 1,
        connect_backoff: float = 1.0,
    ):
        self.password = password
        self.host = host
        self.port = int(port)
        self.user = user
        self.ssl = bool(ssl)
        self.timeout = int(timeout)
        self.connect_retries = int(connect_retries)
        self.connect_backoff = float(connect_backoff)

        self.client: Optional[MsfRpcClient] = None
        self._connected = False

    # ---------------------
    # Connection management
    # ---------------------
    def connect(self) -> bool:
        """
        Attempt to connect to MSF RPC. Returns True on success, False on failure.
        Use connect_or_raise() to get an exception on failure.
        """
        try:
            return self._connect_internal()
        except Exception as e:
            logger.debug("MSF connect() caught exception: %s", e, exc_info=True)
            return False

    def connect_or_raise(self) -> None:
        """
        Attempt to connect, raising MSFRPCException on failure.
        """
        try:
            ok = self._connect_internal()
            if not ok:
                raise MSFRPCException("Unknown failure connecting to MSF RPC", details={"host": self.host, "port": self.port})
        except MSFRPCException:
            raise
        except Exception as e:
            raise MSFRPCException("Failed to connect to MSF RPC", details={"host": self.host, "port": self.port}, original=e)

    def _connect_internal(self) -> bool:
        last_exc = None
        attempt = 0
        while attempt <= self.connect_retries:
            attempt += 1
            try:
                logger.info("Connecting to Metasploit RPC at %s:%d (attempt %d)", self.host, self.port, attempt)
                # Create client
                self.client = MsfRpcClient(self.password, server=self.host, port=self.port, ssl=self.ssl, user=self.user)
                # simple health probe (accessing core.version)
                _ = getattr(self.client.core, "version", None)
                self._connected = True
                logger.info("Connected to Metasploit RPC")
                return True
            except Exception as e:
                last_exc = e
                logger.warning("Connection attempt %d failed: %s", attempt, e)
                if attempt <= self.connect_retries:
                    time.sleep(self.connect_backoff * attempt)
                else:
                    break

        # failed after retries
        logger.error("Failed to connect to Metasploit RPC after %d attempts", attempt)
        raise MSFRPCException("Failed to connect to MSF RPC", details={"host": self.host, "port": self.port}, original=last_exc)

    def disconnect(self) -> None:
        """
        Cleanly close/dispose the client. pymetasploit3 doesn't provide an explicit disconnect API,
        so we attempt best-effort cleanup and mark the wrapper as disconnected.
        """
        try:
            if self.client:
                # Attempt to clear references; if MsfRpcClient exposes close we could call it here.
                try:
                    # Some versions expose client.logout or close; call if present
                    if hasattr(self.client, "logout"):
                        try:
                            self.client.logout()
                        except Exception:
                            logger.debug("Client.logout failed", exc_info=True)
                    if hasattr(self.client, "close"):
                        try:
                            self.client.close()
                        except Exception:
                            logger.debug("Client.close failed", exc_info=True)
                except Exception:
                    logger.debug("Optional client cleanup failed", exc_info=True)

            self.client = None
            self._connected = False
            logger.info("MSF client disconnected (best-effort)")
        except Exception as e:
            logger.warning("Error during disconnect: %s", e, exc_info=True)
            self.client = None
            self._connected = False

    # ---------------------
    # Helpers / health
    # ---------------------
    def is_connected(self) -> bool:
        return bool(self._connected and self.client is not None)

    def health_check(self) -> bool:
        """
        Lightweight check that client is responsive.
        Returns True if OK, False otherwise.
        """
        if not self.client:
            return False
        try:
            # access a lightweight property
            _ = getattr(self.client.core, "version", None)
            return True
        except Exception:
            logger.debug("Health check failed", exc_info=True)
            return False

    def ensure_connected(self, raise_on_fail: bool = False) -> bool:
        """
        Ensure client is connected. If not connected, attempts to connect.
        If raise_on_fail is True, raises MSFRPCException on failure; otherwise returns False.
        """
        if self.is_connected() and self.health_check():
            return True
        try:
            self.connect_or_raise()
            return True
        except MSFRPCException as e:
            if raise_on_fail:
                raise
            logger.error("ensure_connected failed: %s", e)
            return False

    # ---------------------
    # Convenience accessors
    # ---------------------
    @property
    def sessions(self) -> Dict:
        """
        Return sessions list mapping if available, otherwise empty dict.
        Usage: msf_client.sessions.get(session_id) etc.
        """
        try:
            if self.client and hasattr(self.client, "sessions"):
                # pymetasploit3 client.sessions.list is the sessions map
                return getattr(self.client.sessions, "list", {}) or {}
        except Exception:
            logger.debug("Failed to read sessions", exc_info=True)
        return {}

    # context manager support
    def __enter__(self):
        # attempt to connect (may raise)
        self.connect_or_raise()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.disconnect()
        except Exception:
            logger.debug("Exception during context disconnect", exc_info=True)
