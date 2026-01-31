import json
import re

class AIEngine:
    def __init__(self, model_name="dolphin-llama3"):
        from langchain_community.llms import Ollama
        self.model = Ollama(model=model_name, temperature=0)

    def get_strategy(self, recon_data):
        prompt = f"Analyze Recon: {recon_data}. Return ONLY JSON: {{'module': '...', 'payload': '...', 'options': {{}}, 'vector': 'system|web'}}"
        try:
            res = self.model.predict(prompt)
            match = re.search(r'\{.*\}', res, re.DOTALL)
            return json.loads(match.group(0))
        except:
            return None
