import json
import shutil
import subprocess
import time
import logging
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional, List

from core.exceptions import SpectraException

logger = logging.getLogger("modules.scanner")


class ScannerUnit:
    """
    Robust scanner unit.

    - Prefers using `nmap` CLI with XML output (-oX -) then parses it to structured dict.
    - Provides several scan helpers (services, web, ports) and a parallel `scan_all`.
    - Returns structured result dict: {status, command, elapsed, raw, parsed}
    - Graceful fallback and clear error messages if nmap missing or timed out.
    """

    def __init__(self, target: str, nmap_path: Optional[str] = None):
        self.target = target
        # detect nmap binary if not explicitly provided
        self.nmap_bin = nmap_path or shutil.which("nmap")
        if not self.nmap_bin:
            logger.warning("nmap not found in PATH; scanning will fail unless nmap is installed.")
        self.default_timeout = 120  # seconds per nmap invocation
        self.default_retries = 1

    # --------------------
    # Low-level helpers
    # --------------------
    def _run_nmap(self, args: List[str], timeout: Optional[int] = None, retries: int = 1) -> Dict[str, Any]:
        """
        Run nmap with provided args and return structured result.
        Uses nmap -oX - to capture XML on stdout for parsing.
        """
        if not self.nmap_bin:
            return {"status": "error", "error": "nmap_not_installed", "command": None}

        cmd = [self.nmap_bin] + args + ["-oX", "-"]
        timeout = timeout or self.default_timeout

        last_exc = None
        for attempt in range(1, max(1, retries) + 1):
            start = time.time()
            try:
                logger.debug("Running nmap (attempt %d): %s", attempt, " ".join(cmd))
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                elapsed = time.time() - start
                raw = proc.stdout or proc.stderr or ""
                rc = proc.returncode
                status = "ok" if rc == 0 else "warning"  # nmap may return non-zero for no hosts, etc.
                return {"status": status, "command": " ".join(cmd), "elapsed": elapsed, "returncode": rc, "raw": raw}
            except subprocess.TimeoutExpired as e:
                last_exc = e
                logger.warning("nmap timed out (attempt %d): %s", attempt, e)
            except Exception as e:
                last_exc = e
                logger.exception("nmap execution failed (attempt %d): %s", attempt, e)
            # backoff between retries
            if attempt < retries:
                time.sleep(1 * attempt)

        # all attempts failed
        return {"status": "error", "error": "nmap_failed", "command": " ".join(cmd), "last_error": str(last_exc)}

    def _parse_nmap_xml(self, xml_text: str) -> Dict[str, Any]:
        """
        Parse nmap XML output into a concise structured dict:
        {hosts: [{addr, hostnames, ports: [{port, proto, state, service, product, version}], uptime:..., os:...}], scan_info: {...}}
        """
        if not xml_text:
            return {}

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.debug("Failed to parse nmap XML: %s", e)
            return {"parse_error": str(e), "raw_excerpt": xml_text[:1024]}

        results = {"hosts": [], "scan_info": {}}

        # scaninfo
        scaninfo = root.find("scaninfo")
        if scaninfo is not None:
            results["scan_info"] = scaninfo.attrib

        for host in root.findall("host"):
            h = {"addresses": [], "hostnames": [], "ports": [], "status": {}, "os": {}}
            # addresses
            for addr in host.findall("address"):
                h["addresses"].append(addr.attrib)
            # hostnames
            hn = host.find("hostnames")
            if hn is not None:
                for name in hn.findall("hostname"):
                    h["hostnames"].append(name.attrib.get("name"))
            # status
            st = host.find("status")
            if st is not None:
                h["status"] = st.attrib
            # ports
            ports = host.find("ports")
            if ports is not None:
                for port in ports.findall("port"):
                    p = {
                        "port": int(port.attrib.get("portid", 0)),
                        "protocol": port.attrib.get("protocol"),
                        "state": None,
                        "service": {},
                    }
                    state = port.find("state")
                    if state is not None:
                        p["state"] = state.attrib
                    service = port.find("service")
                    if service is not None:
                        p["service"] = service.attrib
                    # scripts output per port
                    scripts = []
                    for scr in port.findall("script"):
                        scripts.append(scr.attrib.get("id") or {})
                        # some scripts return nested output; capture as text
                        if scr.text and scr.text.strip():
                            scripts.append({"output": scr.text.strip()})
                    if scripts:
                        p["service"]["scripts"] = scripts
                    h["ports"].append(p)
            # os
            os_el = host.find("os")
            if os_el is not None:
                os_matches = []
                for m in os_el.findall(".//osmatch"):
                    os_matches.append(m.attrib)
                h["os"] = {"matches": os_matches}
            results["hosts"].append(h)

        return results

    # --------------------
    # High-level scans
    # --------------------
    def scan_services(self, timeout: Optional[int] = None, retries: int = 1) -> Dict[str, Any]:
        """
        Service/version detection (nmap -sV -Pn --open).
        Returns structured dict with raw and parsed outputs.
        """
        args = ["-sV", "-Pn", "--open", self.target]
        result = self._run_nmap(args, timeout=timeout, retries=retries)
        if result.get("status") in ("ok", "warning") and result.get("raw"):
            parsed = self._parse_nmap_xml(result["raw"])
            result["parsed"] = parsed
        return result

    def scan_web(self, timeout: Optional[int] = None, retries: int = 1) -> Dict[str, Any]:
        """
        Web surface discovery using http-enum script on ports 80 and 443.
        """
        args = ["-p", "80,443", "--script", "http-enum", self.target]
        result = self._run_nmap(args, timeout=timeout, retries=retries)
        if result.get("status") in ("ok", "warning") and result.get("raw"):
            result["parsed"] = self._parse_nmap_xml(result["raw"])
        return result

    def scan_ports(self, ports: str = "1-1024", timeout: Optional[int] = None, retries: int = 1) -> Dict[str, Any]:
        """
        Port scan for given ports string (e.g., "1-65535" or "22,80,443").
        """
        args = ["-p", ports, "-sT", "-Pn", self.target]
        result = self._run_nmap(args, timeout=timeout, retries=retries)
        if result.get("status") in ("ok", "warning") and result.get("raw"):
            result["parsed"] = self._parse_nmap_xml(result["raw"])
        return result

    def scan_all(self, timeout: Optional[int] = None, retries: int = 1, parallel: bool = True) -> Dict[str, Any]:
        """
        Run a set of common scans (services, web, top-ports) possibly in parallel.
        Returns a dict of scan_name -> result.
        """
        scans = {
            "services": (self.scan_services, {"timeout": timeout, "retries": retries}),
            "web": (self.scan_web, {"timeout": timeout, "retries": retries}),
            "ports": (self.scan_ports, {"timeout": timeout, "retries": retries}),
        }

        results: Dict[str, Any] = {}
        if parallel:
            with ThreadPoolExecutor(max_workers=min(3, len(scans))) as ex:
                futures = {ex.submit(fn, **kwargs): name for name, (fn, kwargs) in scans.items()}
                for fut in as_completed(futures):
                    name = futures[fut]
                    try:
                        results[name] = fut.result()
                    except Exception as e:
                        logger.exception("Scan %s failed: %s", name, e)
                        results[name] = {"status": "error", "error": str(e)}
        else:
            for name, (fn, kwargs) in scans.items():
                try:
                    results[name] = fn(**kwargs)
                except Exception as e:
                    logger.exception("Scan %s failed: %s", name, e)
                    results[name] = {"status": "error", "error": str(e)}
        # aggregated summary
        summary = {"target": self.target, "timestamp": int(time.time()), "scans": results}
        return summary

    # --------------------
    # Utilities
    # --------------------
    def save_scan(self, result: Dict[str, Any], path: str) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info("Saved scan to %s", path)
        except Exception:
            logger.exception("Failed to save scan result to %s", path)

    # backward-compatible simple placeholder kept, but more powerful methods exist
    def scan_sqli(self) -> str:
        """
        Placeholder for SQLi integration. Keep backward compatibility by returning a short message.
        Future: integrate sqlmap API or run sqlmap subprocess with proper consent.
        """
        return "SQLi Scan Module: Pending Integration (use sqlmap with explicit consent)"
