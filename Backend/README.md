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
| `/api/query` | POST | RAG orchestrator. Body: `{ "query": "<user prompt>" }` |

`/api/query` returns the orchestrator decision, the RAG response, and the supporting documents pulled from Pinecone. The orchestrator is currently wired only to the RAG agent, but the structure leaves room to add the Email, Drive, and HR agents later.
