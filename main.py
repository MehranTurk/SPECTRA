#!/usr/bin/env python3
import sys
import logging
import os
import argparse
import signal
import time
import threading
from enum import Enum
from getpass import getpass
from logging.handlers import RotatingFileHandler
from core.rpc_client import MSFClient
from core.orchestrator import SpectraOrchestrator

__version__ = "0.1.0"

BANNER = f"""
   S P E C T R A  -  V{__version__}
   Tactical Penetration Framework
   Author: MehranTurk (M.T)
"""

class RunStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    INTERRUPTED = "interrupted"
    UNKNOWN = "unknown"

def configure_logging(logfile="spectra.log", level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    # console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    # rotating file
    fh = RotatingFileHandler(logfile, maxBytes=5*1024*1024, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

def parse_args():
    p = argparse.ArgumentParser(description="SPECTRA")
    p.add_argument("target", nargs="?", help="Target IP/host")
    p.add_argument("lhost", nargs="?", help="Local callback address")
    p.add_argument("--msf-password", help="Metasploit RPC password (env MSF_PASSWORD)", default=os.getenv("MSF_PASSWORD"))
    p.add_argument("--dry-run", action="store_true", help="Do everything except actually trigger exploits")
    p.add_argument("--yes", action="store_true", help="Automatically confirm actions (USE WITH CAUTION)")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG","INFO","WARNING","ERROR"], help="Logging level")
    p.add_argument("--version", action="store_true", help="Show version and exit")
    return p.parse_args()

def main():
    args = parse_args()
    if args.version:
        print(__version__)
        return

    configure_logging(level=getattr(logging, args.log_level.upper(), logging.INFO))
    logging.info(BANNER)

    if not args.target or not args.lhost:
        logging.error("Usage: python3 main.py <TARGET> <LHOST>")
        return

    msf_password = args.msf_password or getpass("MSF RPC Password: ")

    # shutdown event replaces global running
    shutdown_event = threading.Event()

    def handle_signal(sig, frame):
        logging.info("Received signal, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        msf = MSFClient(password=msf_password)
    except Exception:
        logging.exception("Failed to initialize MSFClient")
        sys.exit(2)

    try:
        logging.info("Connecting to Metasploit RPC...")
        if not msf.connect():
            logging.error("Failed to connect to MSF RPC")
            sys.exit(3)
    except Exception:
        logging.exception("Error while connecting to MSF RPC")
        sys.exit(4)

    try:
        # Pass shutdown_event so orchestrator can stop early if implemented to observe it.
        engine = SpectraOrchestrator(args.target, args.lhost, msf,
                                     dry_run=args.dry_run, auto_confirm=args.yes,
                                     shutdown_event=shutdown_event)
    except TypeError:
        # backward compatibility if orchestrator doesn't accept shutdown_event yet
        engine = SpectraOrchestrator(args.target, args.lhost, msf,
                                     dry_run=args.dry_run, auto_confirm=args.yes)

    try:
        result = engine.run()
        # normalize result into a status string and optional reason
        status = RunStatus.UNKNOWN
        reason = None

        if isinstance(result, dict):
            status = RunStatus(result.get("status")) if result.get("status") in RunStatus._value2member_map_ else RunStatus.UNKNOWN
            reason = result.get("reason")
        elif isinstance(result, RunStatus):
            status = result
        elif isinstance(result, bool):
            status = RunStatus.SUCCESS if result else RunStatus.FAILURE
        elif result is None:
            status = RunStatus.UNKNOWN
        else:
            # fallback: attempt to parse simple strings
            try:
                status = RunStatus(str(result))
            except Exception:
                status = RunStatus.UNKNOWN

        logging.info("Orchestration finished: status=%s, reason=%s", status.value, reason)
    except KeyboardInterrupt:
        logging.warning("Interrupted by user")
        shutdown_event.set()
        logging.info("Orchestration interrupted; setting shutdown flag")
        sys.exit(130)
    except Exception:
        logging.exception("Unhandled error during orchestration")
        sys.exit(5)
    finally:
        try:
            logging.info("Cleaning up MSF connection...")
            msf.disconnect()
        except Exception:
            logging.debug("MSF disconnect failed", exc_info=True)

    if shutdown_event.is_set():
        logging.info("Exited by signal (shutdown_event set)")
    return

if __name__ == "__main__":
    main()
