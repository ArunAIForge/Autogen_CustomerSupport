# 👗 ClothesSpot – AI Customer Support Automation Desk

> Customer-support dashboard with four role-specific agents, a local hybrid policy search, a FastAPI API, and a Streamlit frontend.

## 📌 Project Overview

The application classifies customer complaints, searches local Markdown policies, cites retrieved passages, applies escalation rules, and records tickets and workflow steps in CSV. AutoGen model inference is opt-in (`AUTOGEN_ENABLED=true`); by default, processing is local and deterministic. Retrieval, escalation, and audit logging remain local in both modes.

---

## 🏛️ System Architecture

ClothesSpot enforces an **API-first, modular architecture**:

```
customer-support-agents/
├── app.py                      # Root application entrypoint (Streamlit / Web fallback)
├── run_backend.py              # FastAPI server runner (Uvicorn on port 8000)
├── run_tests.py                # Offline unit, API, and benchmark test runner
├── docker-compose.yml          # Container orchestration (Backend + Frontend)
├── requirements.txt            # Project dependencies
├── .env.example                # Environment variables template
├── .gitignore                  # Excludes .env, logs/*.csv, and build files
├── .dockerignore               # Excludes local and secret files from image builds
├── README.md                   # Setup, architecture, and usage
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI REST endpoints & embedded Web Dashboard
│   │   ├── models/schemas.py   # Pydantic data schemas
│   │   ├── agents/             # Deterministic complaint-processing workflow
│   │   │   ├── query_agent.py      # Customer Query Agent
│   │   │   ├── knowledge_agent.py  # Knowledge Base Agent + search_kb tool
│   │   │   ├── resolution_agent.py # Resolution Agent (confidence scoring)
│   │   │   ├── log_agent.py        # Log Agent (5-point escalation engine)
│   │   │   └── team.py             # Sequential workflow orchestration
│   │   ├── retrieval/          # Advanced Search & Retrieval Engine
│   │   │   ├── bm25.py             # Okapi BM25 keyword search
│   │   │   ├── vector_search.py    # Dense semantic cosine similarity search
│   │   │   ├── hybrid_search.py    # Reciprocal Rank Fusion (RRF) & score weighting
│   │   │   ├── query_expansion.py  # Synonym expansion & query normalization
│   │   │   ├── reranker.py         # Query/topic overlap passage reranking
│   │   │   └── kb_manager.py       # Document chunking & unified search_kb tool
│   │   ├── guardrails/         # Multi-Layer AI Safety
│   │   │   ├── input_guardrails.py # Prompt injection defense, PII & card redaction
│   │   │   └── output_guardrails.py# Hallucination prevention & leakage checks
│   │   ├── evaluation/         # Local benchmark metrics and evaluation
│   │   │   ├── deepeval_metrics.py # Relevance, Faithfulness, Hallucination metrics
│   │   │   └── benchmark_evaluator.py # Evaluates all 8 benchmark complaints
│   │   └── services/           # Business Logic Layer
│   │       ├── ticket_logger.py    # Thread-safe audit logging to tickets.csv
│   │       └── orchestrator.py     # High-level pipeline execution wrapper
│   └── tests/                  # Unit, API, guardrail, and benchmark tests
├── frontend/
│   ├── streamlit_app.py        # Streamlit host for shared dashboard
│   ├── index.html              # Dashboard structure
│   ├── dashboard.css           # Responsive dashboard styles
│   └── dashboard.js            # Navigation and API interactions
├── knowledge_base/             # Grounding Policy Documents
│   ├── shipping_policy.md      # Timelines (3-5 days), courier tracking, 24-48h scans
│   ├── refund_policy.md        # 30-day returns, shoe boxes, 5-7 day refunds
│   ├── account_and_login.md    # Password reset link (15m), lockout (30m)
│   ├── product_faq.md          # 14-day broken replacements, gift card limits
│   └── billing_and_payments.md # Duplicate charges, fraud defense, chargebacks
├── logs/
│   └── tickets.csv             # Audit log of all submitted complaints
└── docker/
    ├── Dockerfile.backend      # Container image for FastAPI
    └── Dockerfile.frontend     # Container image for Streamlit
```

---

## 🔍 Advanced Search & Retrieval Mechanism

ClothesSpot employs a multi-stage **Hybrid Retrieval Pipeline**:
1. **Query Expansion & Normalization (`query_expansion.py`)**: Cleans punctuation, strips noise, and expands domain-specific synonyms (e.g. `"shoes return"` → `"footwear returns 30 days return window prepaid label unworn original tags"`).
2. **BM25 Keyword Retrieval (`bm25.py`)**: Computes exact Okapi BM25 term frequency, inverse document frequency (IDF), and document length normalization ($k_1=1.5, b=0.75$).
3. **Vector Semantic Search (`vector_search.py`)**: Computes dense feature embeddings using sub-word n-gram hashing and semantic projection with cosine similarity.
4. **Reciprocal Rank Fusion (`hybrid_search.py`)**: Combines BM25 and Vector search results using RRF ($k=60$) and weighted linear fusion ($\alpha=0.55$), alongside category metadata filtering.
5. **Passage Reranker (`reranker.py`)**: Re-scores candidate chunks using query/topic token overlap.

---

## 🛡️ Guardrails & Benchmark Evaluation

### Multi-Layer AI Guardrails
- **Input Guardrails (`input_guardrails.py`)**:
  - **Prompt Injection & Jailbreak Defense**: Detects instruction override attempts (`"ignore previous instructions"`, `"DAN mode"`, `"system prompt override"`).
  - **PII & Sensitive Data Redaction**: Automatically detects and masks credit card numbers (with Luhn validation), Social Security numbers, plaintext passwords, and API keys before agent processing.
  - **Input Sanitization**: Length bounds checking (3 to 4,000 characters) and script tag stripping.
- **Output Guardrails (`output_guardrails.py`)**:
  - **Fail-Closed Grounding**: Rejects unsupported measurable claims; the workflow returns a human-review message and escalates instead of delivering an unverified answer.
  - **Data Leakage Defense**: Checks output for internal messages, API keys, and workflow termination tokens.

The benchmark evaluator in `backend/app/evaluation/` uses local deterministic checks; it does not depend on the external DeepEval package. Run `python run_tests.py` to execute the benchmark cases and unit/API tests.

---

## 🧪 Benchmark Test Scenarios & Results (Section 8)

| # | Complaint Text | Category | Urgency | Sentiment | Sources Cited | Expected Status | Actual Status | Match |
| :-: | :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: |
| **1** | *"Where is my order? It was supposed to arrive yesterday."* | Shipping | Medium | Neutral | `shipping_policy.md` | **Resolved** | **Resolved** | ✅ |
| **2** | *"I want to return the shoes I bought last week. How do I get a refund?"* | Refund | Medium | Neutral | `refund_policy.md` | **Resolved** | **Resolved** | ✅ |
| **3** | *"I forgot my password and can't log in."* | Account | Low | Neutral | `account_and_login.md` | **Resolved** | **Resolved** | ✅ |
| **4** | *"The blender I received is broken. Can I get a replacement?"* | Product | Medium | Neutral | `product_faq.md` | **Resolved** | **Resolved** | ✅ |
| **5** | *"You charged my card three times! Fix this now or I'm contacting my bank and a lawyer."* | Billing | High | Angry | `billing_and_payments.md` | **Escalated** | **Escalated** | ✅ |
| **6** | *"Do you sell gift cards for a company of 500 employees with custom branding?"* | Product | Low | Neutral | None (Out-of-Scope) | **Escalated** | **Escalated** | ✅ |
| **7** | *"My promotional code SUMMER25 gives an invalid promo code error during checkout."* | Product | Low | Neutral | `product_faq.md` | **Resolved** | **Resolved** | ✅ |
| **8** | *"Someone hacked into my account from a strange location and ordered items using my saved card!"* | Billing | High | Angry | `billing_and_payments.md` | **Escalated** | **Escalated** | ✅ |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- (Optional) Docker & Docker Compose

### 1. Installation
From the project directory, create an environment and install dependencies:
```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment
Copy the `.env.example` template:
```bash
cp .env.example .env
```
No external API key is required for local workflows or benchmark tests.

AutoGen inference is disabled by default. To enable it, set `AUTOGEN_ENABLED=true`, provide `OPENAI_API_KEY`, and optionally configure `OPENAI_MODEL`. Customer text is then sent to the configured OpenAI-compatible provider. Leave it disabled where external processing is not permitted.

### 3. Run the Automated Test Suite
Execute the unit, integration, guardrail, and benchmark tests:
```bash
python run_tests.py
```
Expected output:
```
======================================================================
The test runner reports the pass/fail count for the current test suite.
======================================================================
```

### 4. Launch the Application
- **Recommended: Streamlit UI and API together**:
  Start both services with one command:
  ```bash
  python run_app.py
  ```
  Visit [http://127.0.0.1:8501](http://127.0.0.1:8501). The launcher waits for the API health check before starting the dashboard and stops the services when you press `Ctrl+C`.

- **Alternative: FastAPI Backend + Responsive Web UI (Port 8000)**:
  ```bash
  python run_backend.py
  ```
  Visit:
  - **Interactive Web UI**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
  - **Swagger Interactive API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

- **Advanced: Run the Streamlit frontend separately**:
  Start `python run_backend.py` in one terminal and `streamlit run app.py` in another. If the API is hosted remotely, set `BACKEND_BASE_URL` to an address reachable from the user's browser and configure that dashboard origin in `CORS_ORIGINS`.

- **Option C: Docker Compose**:
  ```bash
  # Create .env from .env.example first, then run:
  docker compose up --build
  ```
  - Backend runs on `http://localhost:8000`
  - Frontend runs on `http://localhost:8501`

---

## 📊 Audit Logging Specification (Section 7)

Every complaint processed is automatically logged to `logs/tickets.csv` with all required columns:
1. `ticket_id`: Unique identifier (e.g., `TKT-0001`)
2. `timestamp`: Format `YYYY-MM-DD HH:MM:SS`
3. `customer_name`: Name provided or `Guest`
4. `order_id`: Order reference or `N/A`
5. `complaint`: Sanitized complaint text
6. `category`: `Shipping`, `Refund`, `Account`, `Product`, or `Billing`
7. `urgency`: `Low`, `Medium`, or `High`
8. `sentiment`: `Positive`, `Neutral`, `Frustrated`, or `Angry`
9. `kb_sources`: Policy documents cited (e.g., `shipping_policy.md`)
10. `response`: Complete customer-facing reply
11. `status`: `Resolved` or `Escalated`
12. `escalation_reason`: Specific triggers activated (e.g., `High urgency + Legal threat + Payment dispute`)
13. `confidence`: Resolution confidence from `0.0` to `1.0`
14. `agent_steps`: JSON list with each agent's output, timestamp, escalation decision, and workflow termination marker.

---

## ⚖️ License
Released under the MIT License.