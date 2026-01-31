import json
import logging
import time
from typing import Optional, Any, Dict
from pydantic import BaseModel, ValidationError, Field

# --- Strategy schema (strict) ---
class StrategySchema(BaseModel):
    module: str
    payload: str
    options: Dict[str, Any] = Field(default_factory=dict)
    vector: str  # expected "system" or "web"
    rationale: Optional[str] = None
    manual_review: Optional[bool] = False
    confidence: Optional[float] = None  # optional numeric confidence 0..1

    class Config:
        extra = "forbid"  # do not allow unexpected keys

# --- Helper: extract first balanced JSON object from text (safer than greedy regex) ---
def extract_first_json(text: str) -> Optional[str]:
    if not text:
        return None
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if ch == '"' and not escape:
            in_string = not in_string
        if in_string and ch == '\\' and not escape:
            escape = True
            continue
        else:
            escape = False
        if not in_string:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
    return None

# --- LLM adapter: abstracts client, adds retries/backoff and deterministic config ---
class LLMAdapter:
    def __init__(self, model_name: str = "dolphin-llama3", retries: int = 2, backoff: float = 1.0, timeout: int = 15):
        self.logger = logging.getLogger("LLMAdapter")
        self.model_name = model_name
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        try:
            from langchain_community.llms import Ollama
            # enforce deterministic behaviour
            self.client = Ollama(model=self.model_name, temperature=0)
        except Exception as e:
            self.logger.warning("Failed to initialize Ollama client: %s", e)
            self.client = None

    def predict(self, prompt: str) -> str:
        if not self.client:
            raise RuntimeError("LLM client not initialized")
        attempt = 0
        while attempt <= self.retries:
            try:
                # note: Ollama's predict is synchronous; if a timeout is required, caller should handle it
                return self.client.predict(prompt)
            except Exception as e:
                attempt += 1
                self.logger.warning("LLM predict failed (attempt %d/%d): %s", attempt, self.retries, e)
                time.sleep(self.backoff * attempt)
        raise RuntimeError("LLM predict failed after retries")

# --- AI Engine: uses adapter, validates outputs, returns robust strategy object or manual_review hint ---
class AIEngine:
    def __init__(self, model_name: str = "dolphin-llama3", llm_adapter: Optional[LLMAdapter] = None):
        self.logger = logging.getLogger("AIEngine")
        self.llm = llm_adapter or LLMAdapter(model_name=model_name)

    def _build_prompt(self, recon_data: Any) -> str:
        # Keep prompt strict and explicit: request JSON only, schema and allowed values
        schema_example = {
            "module": "exploit/path",
            "payload": "payload/path",
            "options": {},
            "vector": "system | web",
            "rationale": "short explanation (optional)"
        }
        prompt = (
            "You are an assistant that ONLY outputs a single JSON object (no surrounding text, no markdown).\n"
            "Return a JSON object matching this schema: module (string), payload (string), options (object), "
            "vector (either 'system' or 'web'), rationale (optional string).\n"
            "If you cannot safely propose an actionable strategy, return {\"manual_review\": true, \"rationale\": \"<reason>\"}.\n"
            "Do NOT include any shell commands, code execution, or additional commentary.\n\n"
            f"SCHEMA_EXAMPLE: {json.dumps(schema_example)}\n\n"
            f"Recon: {json.dumps(recon_data, default=str)}\n\n"
            "Respond ONLY with the JSON object."
        )
        return prompt

    def get_strategy(self, recon_data: Any, require_manual_approval: bool = False) -> Dict[str, Any]:
        """
        Returns either a validated strategy dict or a manual_review dict:
          - Valid strategy: keys per StrategySchema
          - Manual review: {"manual_review": True, "rationale": "..."}
        """
        prompt = self._build_prompt(recon_data)

        try:
            raw = self.llm.predict(prompt)
            self.logger.debug("LLM raw response: %s", raw)
        except Exception as e:
            self.logger.exception("LLM prediction failed")
            return {"manual_review": True, "rationale": "LLM unavailable or prediction error"}

        # Extract first JSON object safely
        jtext = extract_first_json(raw)
        if not jtext:
            self.logger.error("No JSON object found in LLM response")
            return {"manual_review": True, "rationale": "LLM did not return JSON"}

        try:
            data = json.loads(jtext)
        except json.JSONDecodeError as e:
            self.logger.error("JSON decode error from LLM output: %s", e)
            return {"manual_review": True, "rationale": "Invalid JSON from LLM"}

        # If the model explicitly requested manual review, pass that through
        if isinstance(data, dict) and data.get("manual_review"):
            return {"manual_review": True, "rationale": data.get("rationale", "LLM signaled manual review")}

        # Validate structure strictly with pydantic
        try:
            strat = StrategySchema(**data)
            obj = strat.dict()
            # enforce allowed vector values
            if obj["vector"] not in ("system", "web"):
                self.logger.error("LLM returned invalid vector: %s", obj["vector"])
                return {"manual_review": True, "rationale": f"Invalid vector: {obj['vector']}"}
            if require_manual_approval:
                obj["manual_review"] = True
            return obj
        except ValidationError as e:
            self.logger.error("Strategy validation failed: %s", e)
            return {"manual_review": True, "rationale": f"ValidationError: {e}"}
