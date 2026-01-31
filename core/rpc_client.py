from pymetasploit3.msfrpc import MsfRpcClient

class MSFClient:
    def __init__(self, password, port=55553):
        self.password = password
        self.port = port
        self.client = None

    def connect(self):
        try:
            self.client = MsfRpcClient(self.password, port=self.port, ssl=False)
            self.client.core.version
            return True
        except:
            return False
