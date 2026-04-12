# QuadTax 🚀

A comprehensive tax preparation platform specifically designed for **Nonresident Alien (NRA)** international students and professionals (F-1/J-1 visas).

QuadTax combines a modern user interface with a sophisticated reasoning engine to handle complex tax scenarios, treaties, and residency determinations with precision.

## 📂 Repository Structure

This repository is organized as a monorepo containing two primary applications:

| Component | Path | Description | Tech Stack |
|-----------|------|-------------|------------|
| **Client** | [`nra-tax-client/`](./nra-tax-client) | Modern web interface for tax intake, document upload, and result visualization. | Next.js, TypeScript, Tailwind CSS |
| **Engine** | [`nra-tax-engine/`](./nra-tax-engine) | Hybrid tax reasoning engine that handles residency logic, treaty evaluation, and deterministic tax math. | Python 3.11+, Pydantic, LLM Agents |

---

## 🛠 Features

### 🧠 Intelligent Tax Reasoning
The backend uses a **Hybrid Execution Architecture**:
- **Reasoning Zone**: LLM-powered agents handle edge cases, classification, and ambiguity in tax forms.
- **Deterministic Zone**: Pure Python functions handle exact math, tax brackets, and regulatory lookups without LLM variance.

### 📱 User-Centric Intake
- OCR-ready document processing for tax forms.
- Guided MCQ (Multiple Choice Question) routing to determine residency and income types.
- Real-time status tracking via a state-managed orchestrator.

### 📄 Compliance & Output
- Accurate calculation of **1040-NR** and **IT-203** (New York) liabilities.
- Built-in treaty evaluation for various international student profiles.

---

## 🚀 Getting Started

To get the full project running locally:

### 1. Backend Setup (Engine)
```bash
cd nra-tax-engine
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # Configure your API keys here
```

### 2. Frontend Setup (Client)
```bash
cd nra-tax-client
npm install
npm run dev
```

The application will be accessible at `http://localhost:3000`.

---

## 🤝 Contributing

QuadTax is built to make tax season less stressful for the international community. Contributions are welcome!

- Ensure you follow the hybrid architecture rules in the `nra-tax-engine` (Reasoning vs. Deterministic).
- Maintain strict typing with Pydantic and TypeScript.

---

## ⚖️ Disclaimer

*QuadTax is an automated tool intended to assist in tax preparation. It is not a substitute for professional tax advice from a CPA or qualified tax attorney.*
