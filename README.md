# Order-to-Cash (O2C) Graph Query System

A production-ready system for exploring SAP Order-to-Cash business processes through interactive graph visualization and natural language queries.

![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)

---

## What is This?

This system provides:
- **Interactive Graph Visualization** - Explore 16+ entity types and their relationships
- **Natural Language Queries** - Ask questions in plain English, get instant answers
- **Complete O2C Tracing** - Follow orders from creation through payment
- **LLM-Powered Analysis** - Groq API integration for intelligent SQL generation

Example queries:
- "Which products have the highest billing?"
- "Show me orders with no corresponding invoices"
- "What is the total revenue by customer?"

---

## ⚡ Quick Start (5 Minutes)

### Prerequisites

- **Python 3.10+** ([download](https://www.python.org/downloads/))
- **Groq API Key** (free from [console.groq.com](https://console.groq.com))
- SAP O2C JSONL Data (provided)

### Step 1: Environment Setup

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
export GROQ_API_KEY="your-api-key-here"
```

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
$env:GROQ_API_KEY = "your-api-key-here"
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Run the System

```bash
python main.py
```

You should see:
```
Loading JSONL data from ./sap-o2c-data...
Building graph...
INFO:     Uvicorn running on http://0.0.0.0:5552
```

### Step 4: Open Browser

Navigate to: **http://localhost:5552**

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────┐
│  SAP O2C JSONL Data                             │
│  (16 entity types: orders, invoices, payments)  │
└────────────────┬────────────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │  FastAPI Backend        │
    ├─────────────────────────┤
    │ • Data Loader (Pandas)  │
    │ • SQLite Database       │
    │ • NetworkX Graph        │
    │ • LLM (Groq) Integration│
    └────────────┬────────────┘
                 │
    ┌────────────┴─────────────┐
    │                          │
    ▼                          ▼
GET /graph               POST /chat
(Visualization)      (Natural Language)
    │                          │
    └────────────┬─────────────┘
                 │
    ┌────────────▼────────────┐
    │  Browser (D3.js)        │
    ├─────────────────────────┤
    │ • Graph Visualization   │
    │ • Chat Interface        │
    │ • Entity Inspection     │
    └─────────────────────────┘
```

---

## 📊 Key Features

| Feature | Details |
|---------|---------|
| **Entities** | 16 types: Orders, deliveries, invoices, payments, customers, products, plants |
| **Relationships** | 15+ edge types connecting all O2C entities |
| **Query Types** | SQL aggregations, multi-table joins, flow tracing, data quality checks |
| **Security** | SELECT-only queries, table whitelist, injection prevention |
| **Performance** | In-memory SQLite, ~10 second startup for 1000+ records |
| **Scaling** | Handles complete SAP O2C datasets |

---

##  Configuration

Create a `.env` file (or use `.env.example` as template):

```bash
# LLM Configuration
GROQ_API_KEY=your-api-key-here

# Data Configuration
DATA_PATH=./sap-o2c-data

# Server Configuration
PORT=5552
HOST=0.0.0.0

# Logging
LOG_LEVEL=INFO
```

---

##  Query Examples

### Get Started
```
"How many customers do we have?"
→ Returns total customer count
```

### Aggregations
```
"What is the total revenue by product?"
→ SUM(billing_amount) GROUP BY product
```

### Flow Tracing
```
"Show me orders that have no billing document"
→ LEFT JOIN orders to invoices, finds unmatched rows
```

### Data Quality
```
"Find incomplete order-to-cash flows"
→ Uses graph traversal to detect broken chains
```

---

##  Project Structure

```
Dodge/
├── main.py                  # FastAPI backend
├── llm_utils.py            # LLM integration
├── frontend/
│   └── index.html          # D3.js UI (single file)
├── requirements.txt        # Dependencies
├── .env.example            # Configuration template
├── setup.py                # Setup validation
├── README.md               # This file
├── DOCUMENTATION.md        # Full technical docs
└── sap-o2c-data/           # Data folder
    └── [16 entity folders with JSONL files]
```

---

##  Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Serve frontend UI |
| GET | `/health` | System health check |
| GET | `/graph` | Graph data (nodes & edges) |
| GET | `/graph/entity/{type}/{id}` | Entity details |
| POST | `/chat` | Natural language query |

**Example POST to `/chat`:**
```json
{
  "user_query": "Which products have highest revenue?"
}
```

**Response:**
```json
{
  "response": "Based on our data, the products with highest revenue are...",
  "query_type": "sql",
  "referenced_nodes": ["product_1", "product_2"]
}
```

---

##  Security & Validation

✅ **Query Validation**
- Only SELECT statements
- 16 whitelisted tables
- No schema modifications
- Injection attack prevention

✅ **Scope Enforcement**
- O2C domain keywords required
- Out-of-scope queries return helpful guidance
- No 500 errors for invalid queries

✅ **Data Safety**
- Read-only access
- Result limit: 1000 rows
- All responses grounded in actual data

---

##  Verification

All system features have been verified:
- ✅ Out-of-scope query handling (200 OK responses)
- ✅ SQL query execution
- ✅ Aggregation queries
- ✅ Multi-hop graph traversal
- ✅ Frontend accessibility
- ✅ Error handling & graceful fallbacks

See `DOCUMENTATION.md` for detailed verification results.

---

##  Support & Documentation

- **Quick Start**: See "Quick Start" section above
- **Full Documentation**: See `DOCUMENTATION.md`
- **Technical Details**: See `DOCUMENTATION.md` → Architecture section
- **API Reference**: See `DOCUMENTATION.md` → Endpoints section

---

##  License

Provided as-is for educational and commercial use.

---


1. Follow Quick Start above to get running
2. Try the example queries
3. Read `DOCUMENTATION.md` for advanced usage
4. Explore the graph visualization to understand your data
5. Deploy to production (see DOCUMENTATION.md → Deployment)

**Enjoy exploring your Order-to-Cash data!**
