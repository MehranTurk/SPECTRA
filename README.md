# SPECTRA

**Author:** MehranTurk (M.T)  
**Status:** Prototype / Research Framework  
**Scope:** Authorized security testing, research, and lab environments only.

---

## 🚀 Overview
SPECTRA is a modular, research‑grade penetration testing framework built around clean architecture, explicit failure taxonomy, and an AI‑assisted decision engine. It separates reconnaissance, decision‑making, execution, and post‑exploitation into well‑defined components so each part can be extended or replaced independently.

What makes SPECTRA different?
- 🧠 AI‑assisted strategy (local LLM via Ollama / LLM adapter)
- 🧩 Strict modularity (scanner, exploiter, post‑exploit)
- 🧪 Failure taxonomy (clear, machine‑friendly reasons for failures)
- 🔌 Metasploit RPC abstraction (wrapper over pymetasploit3)
- 🧭 Lifecycle thinking (from recon → access → upgrade)

---

## 🏗️ Project Structure
```
SPECTRA_PROJECT/
├── main.py                 # Entry point (logging, flags, graceful shutdown)
├── requirements.txt        # Python dependencies
├── core/
│   ├── orchestrator.py     # Central workflow controller
│   ├── rpc_client.py       # Metasploit RPC abstraction (MSFClient)
│   └── exceptions.py       # Failure taxonomy & structured exceptions
├── modules/
│   ├── scanner.py          # Reconnaissance (nmap parsing, parallel scans)
│   ├── exploiter.py        # Exploit execution (module API + console fallback)
│   └── post_exploit.py     # Session lifecycle & upgrades
└── brain/
    └── ai_engine.py        # AI decision engine (LLM adapter + validation)
```

Each component has one responsibility and can be replaced without breaking the rest of the framework.

---

## 🧠 Architecture Philosophy

### 1️⃣ Separation of Concerns
- **ScannerUnit** → collects facts (no decisions) and returns structured JSON-like dictionaries
- **AIEngine** → suggests a strict JSON strategy (validated)
- **ExploiterUnit** → executes actions (no recon)
- **PostExploitUnit** → handles session lifecycle and upgrades
- **Orchestrator** → coordinates the overall flow

This keeps SPECTRA auditable, testable, and extensible.

### 2️⃣ Failure Taxonomy
Failures are classified with a machine‑friendly enum (FailureReason). Examples:
- `TARGET_PATCHED_OR_NOT_VULNERABLE`
- `PAYLOAD_OR_ARCH_MISMATCH`
- `CONNECTION_REFUSED_OR_IPS_BLOCK`
- `MSF_RPC_SYNC_ISSUE`
- `UNDEFINED_INTERNAL_ERROR`

Structured exceptions (SpectraException and subclasses) include a `to_dict()` helper for logging and reporting.

---

## 🤖 AI Decision Engine
The AI engine analyzes reconnaissance output and returns a strict JSON strategy validated by pydantic:

Example strategy:
```json
{
  "module": "exploit/path",
  "payload": "payload/path",
  "options": {},
  "vector": "system" // or "web"
}
```

Key properties:
- Deterministic (temperature = 0) via LLM adapter
- JSON‑only output enforcement and safe JSON extraction
- Strict validation with pydantic schema
- Graceful fallback: if the LLM cannot safely propose a plan the engine returns `{"manual_review": true, "rationale": "..."}`

> ⚠️ AI suggests strategies — it does **not** blindly execute them when `--dry-run` is off you still control final execution (there is an `--yes` auto-confirm flag for automation).

---

## 🔌 Metasploit Integration
SPECTRA communicates with Metasploit through a safe wrapper over `pymetasploit3` (MSFClient). Improvements include:
- `connect()` and `connect_or_raise()` with retries/backoff
- `disconnect()`, `health_check()` and context‑manager support
- Best‑effort handling when `pymetasploit3` internals differ across versions

Notes:
- Modules (exploiter/post_exploit) receive the underlying msfrpc client and prefer the module API (`msf.modules.use`) with a console fallback.

---

## 📦 Requirements
Python packages are listed in `requirements.txt`.

Suggested minimal runtime requirements (example):
```text
pymetasploit3>=1.1.0
pydantic>=1.10.7
langchain-community>=0.0.20
ollama>=0.1.0
requests>=2.28.2
```

System requirements:
- Linux (recommended: Kali)
- Python 3.9+
- Metasploit Framework (msfrpcd)
- Ollama (if using local LLM) and the chosen model pulled
- nmap installed and accessible in PATH
- PostgreSQL if required by your Metasploit setup

---

## ⚙️ Setup & Installation

1) Clone:
```bash
git clone https://github.com/MehranTurk/SPECTRA.git
cd SPECTRA
```

2) Virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3) Ensure services are running (example):
- Start Metasploit RPC:
```bash
msfrpcd -P "<secure-password>" -u msf -S false &
```
- If using Ollama locally:
```bash
ollama pull dolphin-llama3
ollama serve &
```
- Ensure `nmap` is installed and reachable.

4) Run (safe dry-run first):
```bash
export MSF_PASSWORD="<secure-password>"
python3 main.py <TARGET> <LHOST> --dry-run --log-level DEBUG
```

---

## ▶️ Running SPECTRA
Basic usage:
```bash
python3 main.py <TARGET> <LHOST> [--dry-run] [--yes] [--log-level DEBUG|INFO|...]
```

Flags:
- `--dry-run` — perform all planning steps but do not actually trigger exploits
- `--yes` — auto‑confirm plans (use with caution)
- `--log-level` — logging verbosity
- `--version` — print version and exit

Orchestrator returns a structured result (recommended for automation):
```json
{
  "status": "success|failure|partial|interrupted|unknown",
  "reason": "short_code",
  "details": {...}
}
```

---

## 🛡️ Safety & Ethics
SPECTRA is intended strictly for:
- Educational purposes
- Authorized penetration testing
- Security research on systems you OWN or have EXPLICIT WRITTEN PERMISSION to test

Never run this tool against systems you do not have permission to test. The author accepts no liability for misuse.

---

## 🧪 Testing & CI (Recommended)
- Add unit tests (pytest + pytest-mock) for:
  - AIEngine (mock LLM)
  - RPC wrapper (mock pymetasploit3 client)
  - Exploiter (mock module/console)
  - Scanner (mock subprocess)
- Add a GitHub Actions workflow for lint and tests (black, flake8, mypy, pytest).
- Use a lockfile tool (pip‑compile or poetry) for reproducible installs.

---

## ⭐ Notes & Roadmap
- Current: modular architecture, failure taxonomy, AI strategy engine, safer MSF wrapper.
- Next: stateful decision engine, plugin system, detailed reporting/export, more unit tests and CI coverage.

---

## LICENSE
MIT License with security & ethical use disclaimer. See LICENSE file.

---

— **MehranTurk (M.T)**

## 💰 Donate


| Currency | Address |
|-----------|----------|
| **USDT / TRX** | `TSVd8USqUv1B1dz6Hw3bUCQhLkSz1cLE1v` |
| **BTC** | `32Sxd8UJav7pERtL9QbAStWuFJ4aMHaZ9g` |
| **ETH** | `0xb2ba6B8CbB433Cb7120127474aEF3B1281C796a6` |
| **LTC** | `MEUoFAYLqrwxnUBkT4sBB63wAypKEdyewy` |

---
