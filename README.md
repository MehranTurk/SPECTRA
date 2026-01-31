# SPECTRA — Full‑Spectrum Tactical Penetration Framework

> **Author:** MehranTurk (M.T)
>
> **Status:** Prototype / Research Framework
>
> **Scope:** Authorized security testing, research, and lab environments only.

---

## 🚀 Overview
**SPECTRA** is a modular, research‑grade penetration testing framework designed around **clean architecture**, **explicit failure taxonomy**, and an **AI‑assisted decision engine**. Rather than being a single script, SPECTRA separates reconnaissance, decision‑making, execution, and post‑exploitation into well‑defined components that can evolve independently.

**What makes SPECTRA different?**
- 🧠 **AI‑assisted strategy** (Ollama / LLM‑driven planning)
- 🧩 **Strict modularity** (scanner, exploiter, post‑exploit)
- 🧪 **Failure taxonomy** (clear reasons for why an action failed)
- 🔌 **Metasploit RPC abstraction** (no tight coupling to msfrpc internals)
- 🧭 **Lifecycle thinking** (from recon → access → upgrade)

---

## 🏗️ Project Structure
```
SPECTRA_PROJECT/
├── main.py                 # Entry point
├── core/
│   ├── orchestrator.py     # Central workflow controller
│   ├── rpc_client.py       # Metasploit RPC abstraction
│   └── exceptions.py       # Failure taxonomy & custom exceptions
├── modules/
│   ├── scanner.py          # Reconnaissance (Nmap, web surface)
│   ├── exploiter.py        # Exploit execution & error classification
│   └── post_exploit.py     # Session lifecycle & upgrades
└── brain/
    └── ai_engine.py        # AI decision engine (Ollama)
```

Each layer has **one responsibility** and can be replaced or extended without breaking the rest of the framework.

---

## 🧠 Architecture Philosophy

### 1️⃣ Separation of Concerns
- **ScannerUnit** → Collects facts (no decisions)
- **AIEngine** → Suggests a strategy (no execution)
- **ExploiterUnit** → Executes actions (no recon)
- **PostExploitUnit** → Handles session lifecycle
- **Orchestrator** → Coordinates everything

This design keeps SPECTRA **auditable, testable, and extensible**.

### 2️⃣ Failure Taxonomy
Instead of vague errors, SPECTRA classifies failures explicitly:
- `TARGET_PATCHED_OR_NOT_VULNERABLE`
- `PAYLOAD_OR_ARCH_MISMATCH`
- `CONNECTION_REFUSED_OR_IPS_BLOCK`
- `MSF_RPC_SYNC_ISSUE`
- `UNDEFINED_INTERNAL_ERROR`

This enables:
- Smarter retries
- Better reporting
- Cleaner automation logic

---

## 🤖 AI Decision Engine
The **AIEngine** analyzes reconnaissance output and returns a **strict JSON strategy**:
```json
{
  "module": "exploit/path",
  "payload": "payload/path",
  "options": {},
  "vector": "system | web"
}
```

Key properties:
- Deterministic (temperature = 0)
- JSON‑only output enforcement
- Graceful fallback if AI fails

> ⚠️ AI suggests strategies — it does **not** blindly execute actions.

---

## 🔌 Metasploit Integration
SPECTRA communicates with Metasploit **only** through RPC using `pymetasploit3`.

Benefits:
- No shelling into `msfconsole`
- Cleaner automation
- Easier future migration (REST, alternative engines)

---

## 📦 Requirements
All Python dependencies are listed in **`requirements.txt`**.

### `requirements.txt`
```txt
pymetasploit3
pydantic
langchain-community
ollama
```

### System Requirements
- Linux (recommended: **Kali Linux**)
- Python **3.9+**
- Metasploit Framework
- Ollama running locally
- Nmap installed and accessible in PATH

---

## ⚙️ Setup & Installation

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/MehranTurk/SPECTRA.git
cd SPECTRA
```

### 2️⃣ Create Virtual Environment (Recommended)
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4️⃣ Start Required Services
- **Metasploit RPC** (example):
```bash
msfrpcd -P <password> -u msf -S false
```

- **Ollama** (ensure model is pulled):
```bash
ollama pull dolphin-llama3
```

---

## ▶️ Running SPECTRA
```bash
python3 main.py <TARGET> <LHOST>
```

Where:
- `<TARGET>` → Authorized target IP / host
- `<LHOST>` → Local callback address

> 🔒 **IMPORTANT:** Only run SPECTRA against systems you **own or have explicit permission to test**.

---

## 🧪 Intended Use Cases
- Security research & education
- Red team prototyping
- Framework architecture experiments
- AI‑assisted decision modeling

**Not intended for:**
- Unauthenticated mass scanning
- Autonomous exploitation
- Unauthorized testing

---

## 🛣️ Roadmap (Planned)
- ✔️ Modular architecture
- ✔️ Failure taxonomy
- ✔️ AI strategy engine
- ⏳ Strategy validation layer
- ⏳ Stateful decision engine
- ⏳ Plugin system
- ⏳ Reporting / JSON export

---

## ⚠️ Legal & Ethical Disclaimer
This project is provided **for educational and authorized security testing only**.

The author assumes **no liability** for misuse of this software. Always comply with:
- Local laws
- Organizational policies
- Explicit written authorization

---

## ⭐ Final Notes
SPECTRA is intentionally **minimal but structured**.

It is designed to grow — not to impress with volume, but with **clarity, control, and intent**.

If you find this project useful, consider starring the repository and contributing ideas.

— **MehranTurk (M.T)**
