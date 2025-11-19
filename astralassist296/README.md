# Astral Assist Frontend

Next.js 14 (App Router) interface for the Astral Assist multi-agent orchestrator with Groq + Pinecone RAG.

## 1. Configure environment variables

Create a local env file and point it at the Flask backend (defaults to `http://localhost:5001` if unset):

```bash
cd astralassist296
cp .env.local.example .env.local
```

Update `NEXT_PUBLIC_BACKEND_URL` if your backend runs elsewhere (for example, a deployed Flask URL or a tunnel).

## 2. Run the backend

Make sure `python Backend/app.py` is running in another terminal so the frontend can reach `/api/query`.

## 3. Start the Next.js dev server

```bash
npm run dev
# or: pnpm dev / yarn dev / bun dev
```

Visit [http://localhost:3000](http://localhost:3000) and send a prompt; the UI will call `POST /api/query`, render the orchestrator reasoning, and surface the supporting Pinecone contexts inline.

## Deploying

When deploying (e.g., to Vercel), add `NEXT_PUBLIC_BACKEND_URL` (pointing at your hosted Flask API) to the project’s environment variables.
