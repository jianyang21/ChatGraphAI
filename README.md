# ChatGraph AI - SAP Order-to-Cash Explorer

Graph-based data modeling and query system for SAP O2C data. Combines interactive graph visualization with an LLM-powered natural language interface to explore relationships between sales orders, deliveries, billing documents, payments, and more.

## Architecture

```
React Frontend (Vite)
  - GraphView: force-directed canvas graph (react-force-graph-2d)
  - ChatPanel: conversational query interface
  - NodeDetail: entity inspector with connections
  - SearchBar: node search with autocomplete
        |
        | REST API
        v
FastAPI Backend
  - Graph API: node/edge data, subgraph extraction, search
  - Chat API: NL query -> SQL generation -> result summarization
  - NetworkX: in-memory directed graph (1,523 nodes, 5,312 edges)
  - Groq LLM (Llama 3.1 8B): query translation and response generation
  - SQLite: 19 tables holding the full O2C dataset
```

## Design Decisions

**SQLite** was chosen because the dataset is relatively small (~20K records across 19 tables) and the workload is read-heavy. A single-file database means zero setup and easy deployment. The tradeoff is no concurrent write support, which isn't needed here.

**NetworkX** handles the graph in-memory. With ~1,500 nodes and ~5,300 edges, everything fits in RAM with room to spare. BFS-based subgraph extraction runs in milliseconds. For a production system with millions of nodes, something like Neo4j would be more appropriate.

**Groq (Llama 3.1 8B)** provides fast inference on a free tier. The model receives the full database schema (all 19 tables with column names, primary keys, and foreign key relationships) plus example SQL queries in the system prompt. A two-pass approach is used: the first call generates SQL from the user's question, and after execution, a second call summarizes the results in plain language.

**react-force-graph-2d** renders the graph on a canvas element, which handles hundreds of nodes smoothly without DOM overhead. Nodes are color-coded by entity type and sized by importance.

## Graph Model

11 entity types with 13 relationship types covering the full O2C flow:

- Sales Orders and Items
- Outbound Deliveries and Items
- Billing Documents and Items
- Journal Entries
- Payments
- Customers (Business Partners)
- Products
- Plants

Key relationships trace the O2C lifecycle: Sales Order -> Delivery -> Billing -> Journal Entry -> Payment, with cross-references to Customers, Products, and Plants.

## LLM Prompting Strategy

The system prompt includes the complete database schema with all column names, types, primary keys, and foreign key relationships. Three example SQL queries demonstrate common patterns (aggregation, flow tracing, gap analysis). The LLM returns structured JSON with `sql` and `explanation` fields.

After SQL execution, a second LLM call summarizes the raw query results into a human-readable answer with specific numbers and bullet points.

## Guardrails

1. Regex-based pre-filter catches obviously off-topic queries (weather, recipes, coding help, etc.)
2. System prompt instructs the model to reject non-dataset questions
3. Only SELECT/WITH statements are executed - DML keywords (DROP, DELETE, INSERT, UPDATE, ALTER) are blocked
4. If the LLM response contains rejection language, it's surfaced as a guardrail message

## Setup

### Backend
```bash
cd backend
pip install -r requirements.txt
python ingest.py          # run once to build db + graph
echo "GROQ_API_KEY=your_key" > .env
python app.py             # starts on port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev               # starts on port 5173
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python, FastAPI |
| Database | SQLite |
| Graph | NetworkX |
| LLM | Groq (Llama 3.1 8B) |
| Frontend | React 19, Vite |
| Visualization | react-force-graph-2d |
| Chat rendering | react-markdown |
