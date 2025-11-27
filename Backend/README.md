# Flask Backend Setup

## 1. Configure environment variables
Copy the sample file and add your keys:

```zsh
cd Backend
cp .env.example .env
```

Fill in values for:
- `GROQ_API_KEY` (LLM)
- `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `PINECONE_HOST`, etc.
- `JINA_API_KEY` for embeddings (used for both ingestion and query-time retrieval)

> The backend automatically loads `.env` from both the repo root and the `Backend/` folder, so keep secrets in whichever location fits your deployment.

## 2. Install dependencies
```zsh
pip install -r Backend/requirements.txt
```

## 3. Run the server
```zsh
python Backend/app.py
```

## 4. Available endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/hello` | GET | Health-check |
| `/api/query` | POST | RAG orchestrator. Body: `{ "query": "<user prompt>", "session_id": "abc123" }` |
| `/api/hr/email` | POST | Fetch HR record, render email, and optionally send via Gmail. |
| `/api/drive/sync` | POST | Refresh `employee_database.csv` in the shared Drive folder using the HR API. Also triggers RAG ingestion by default. |
| `/api/hr/employee` | GET | Fetch a single employee by `employee_id` or `name` via the HR API. |
| `/api/rag/reset` | POST | Delete all vectors in a namespace (default: `PINECONE_DEFAULT_NAMESPACE`). |

`/api/query` returns the orchestrator decision, the RAG response, and the supporting documents pulled from Pinecone. The orchestrator is currently wired only to the RAG agent, but the structure leaves room to add the Email, Drive, and HR agents later.

Drive sync ingestion toggles:
- Default: POST to `/api/drive/sync` will re-fetch the CSV and then ingest `Backend/employee_database.csv` + `scripts/downloads/` into Pinecone.
- Disable ingestion: include `"ingest": false` in the POST body.
- Target a different namespace: include `"namespace": "staging"` (or any name).

Resetting the RAG namespace:
```zsh
curl -X POST http://localhost:5001/api/rag/reset -H "Content-Type: application/json" -d '{}'
# or specify a namespace:
curl -X POST http://localhost:5001/api/rag/reset -H "Content-Type: application/json" -d '{"namespace":"staging"}'
```

### Agentic email command (chat)
The orchestrator now recognizes a lightweight email command in chat queries:
```
email employee 3 subject: Welcome aboard body: Hi {first_name}, welcome! send
```
- `employee <id>`: required (id must exist in the HR API).
- `subject:` and `body:` are required.
- Include the word `send` to actually deliver; omit it for a draft/dry-run.

### Ingest knowledge into Pinecone
Populate the vector DB with the employee CSV and any Drive downloads (from `scripts/downloads`) so RAG has context:
```zsh
python -m services.rag_ingest            # uses defaults if they exist
# or specify paths explicitly:
python -m services.rag_ingest --path Backend/employee_database.csv --path scripts/downloads
```
The CLI loads the same `.env` as the Flask app. Override the namespace with `--namespace` if you need separate environments.
