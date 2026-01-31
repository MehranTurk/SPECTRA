import subprocess

class ScannerUnit:
    def __init__(self, target):
        self.target = target

    def scan_services(self):
        return subprocess.getoutput(f"nmap -sV -Pn --open {self.target}")

    def scan_web(self):
        return subprocess.getoutput(f"nmap -p 80,443 --script http-enum {self.target}")

    def scan_sqli(self):
        # Placeholder for future SQLi module integration (e.g., sqlmap API)
        return "SQLi Scan Module: Pending Integration"
