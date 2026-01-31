import sys
import logging
from core.rpc_client import MSFClient
from core.orchestrator import SpectraOrchestrator

BANNER = """
   S P E C T R A  -  V1.0
   Tactical Penetration Framework
   Author: MehranTurk (M.T)
"""

def main():
    print(BANNER)
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    if len(sys.argv) < 3:
        print("Usage: python3 main.py <TARGET> <LHOST>")
        return

    target, lhost = sys.argv[1], sys.argv[2]
    msf = MSFClient(password='mehran123')
    
    if msf.connect():
        engine = SpectraOrchestrator(target, lhost, msf)
        engine.run()
    else:
        print("[!] Failed to connect to MSF RPC")

if __name__ == "__main__":
    main()