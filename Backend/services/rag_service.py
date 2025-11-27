import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import requests
from groq import Groq
from pinecone import Pinecone, PineconeException

logger = logging.getLogger(__name__)
DEFAULT_SYSTEM_PROMPT = (
    "You are Astral Assist, an enterprise knowledge assistant. "
    "Use only the provided context to answer the user. "
    "Be concise. Do not list document names, scores, or raw citations. "
    "Ask at most one brief clarifying question only if truly needed. "
    "Do not propose emails or actions unless explicitly requested. "
    "When information is missing, say so briefly."
)


class EmbeddingClient(Protocol):
    """Protocol so different embedding providers can be swapped in."""

    def embed(self, text: str) -> List[float]:
        ...


class LLMClient(Protocol):
    """Protocol for large language model chat/generation clients."""

    def generate(self, prompt: str, context_blocks: List[str], history: Optional[List[Dict[str, str]]] = None) -> str:
        ...


@dataclass
class PineconeConfig:
    api_key: str
    index_name: str
    host: Optional[str] = None
    namespace: str = "main"
    top_k: int = 5
    dimension: Optional[int] = None


@dataclass
class JinaConfig:
    api_key: str
    model: str = "jina-embeddings-v2-base-en"


@dataclass
class GroqConfig:
    api_key: str
    model: str = "llama3-70b-8192"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


class JinaEmbeddingClient:
    """Calls Jina's embeddings endpoint for query vectors."""

    def __init__(self, config: JinaConfig):
        self.config = config
        self.endpoint = "https://api.jina.ai/v1/embeddings"

    def embed(self, text: str) -> List[float]:
        response = requests.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.config.model, "input": text},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


class PineconeVectorStore:
    """Thin wrapper that exposes query functionality."""

    def __init__(self, config: PineconeConfig):
        self.config = config
        self.client = Pinecone(api_key=config.api_key)
        # Pinecone serverless deployments require both the index name and the
        # host value returned from the console. For legacy pods the host is optional.
        self.index = self.client.Index(name=config.index_name, host=config.host)

    def _align_vector(self, vector: List[float]) -> List[float]:
        """
        Ensure vector length matches the Pinecone index dimension.
        If dimension is set and vectors are shorter/longer, pad or truncate to fit.
        """
        if not self.config.dimension:
            return vector
        if len(vector) == self.config.dimension:
            return vector
        if len(vector) < self.config.dimension:
            padded = vector + [0.0] * (self.config.dimension - len(vector))
            return padded
        # Truncate if longer than expected
        return vector[: self.config.dimension]

    def similarity_search(self, vector: List[float], top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            result = self.index.query(
                vector=self._align_vector(vector),
                top_k=top_k or self.config.top_k,
                include_metadata=True,
                namespace=self.config.namespace,
            )
        except PineconeException as exc:
            logger.exception("Pinecone query failed")
            raise RuntimeError(f"Pinecone query failed: {exc}") from exc

        matches = result.get("matches", [])
        contexts: List[Dict[str, Any]] = []
        for match in matches:
            metadata = match.get("metadata") or {}
            contexts.append(
                {
                    "id": match.get("id"),
                    "score": match.get("score"),
                    "text": metadata.get("text") or metadata.get("content") or "",
                    "metadata": metadata,
                }
            )
        return contexts

    def upsert(self, items: List[Dict[str, Any]]):
        """Insert or update vectors in Pinecone."""
        vectors = [
            {
                "id": item["id"],
                "values": self._align_vector(item["vector"]),
                "metadata": item.get("metadata") or {},
            }
            for item in items
        ]
        try:
            self.index.upsert(vectors=vectors, namespace=self.config.namespace)
        except PineconeException as exc:
            logger.exception("Pinecone upsert failed")
            raise RuntimeError(f"Pinecone upsert failed: {exc}") from exc

    def wipe_namespace(self, namespace: Optional[str] = None):
        """Delete all vectors in the given namespace (or default)."""
        target = namespace or self.config.namespace
        try:
            self.index.delete(delete_all=True, namespace=target)
        except PineconeException as exc:
            logger.exception("Pinecone delete failed")
            raise RuntimeError(f"Pinecone delete failed: {exc}") from exc


class GroqLLMClient:
    """Handles Groq chat completions."""

    def __init__(self, config: GroqConfig):
        self.config = config
        self.client = Groq(api_key=config.api_key)

    def generate(self, prompt: str, context_blocks: List[str], history: Optional[List[Dict[str, str]]] = None) -> str:
        context_string = "\n\n".join(context_blocks) if context_blocks else "Context unavailable."
        messages: List[Dict[str, str]] = [{"role": "system", "content": self.config.system_prompt}]

        # Include short history for conversational continuity.
        if history:
            for msg in history[-10:]:  # limit to last 10 turns
                role = "assistant" if msg.get("role") == "assistant" else "user"
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        messages.append(
            {
                "role": "user",
                "content": (
                    "Context:\n"
                    f"{context_string}\n\n"
                    "User question:\n"
                    f"{prompt}\n"
                    "Always cite the provided files where possible."
                ),
            }
        )

        completion = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=0.2,
        )
        return completion.choices[0].message.content.strip()


class RAGService:
    """Coordinates embedding, retrieval, and response generation."""

    def __init__(
        self,
        embedder: EmbeddingClient,
        vector_store: PineconeVectorStore,
        llm_client: LLMClient,
        pinecone_config: PineconeConfig,
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.pinecone_config = pinecone_config

    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        vector = self.embedder.embed(query)
        contexts = self.vector_store.similarity_search(vector)
        # Drop empty/garbage contexts
        return [c for c in contexts if (c.get("text") or "").strip()]

    def answer(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        if _is_smalltalk(query):
            return {
                "response": "Hello! How can I help today?",
                "contexts": [],
                "agent_strategy": "rag_only",
                "agents_used": ["rag"],
            }
        contexts = self.retrieve(query)
        blocks = self._format_context_blocks(contexts)
        response = self.llm_client.generate(query, blocks, history=history)
        # Return metadata-only contexts (no text) to reduce leakage but preserve routing hints.
        client_contexts = [
            {
                "score": ctx.get("score"),
                "metadata": ctx.get("metadata") or {},
            }
            for ctx in contexts
        ]
        return {
            "response": response,
            "contexts": client_contexts,
            "agent_strategy": "rag_only",
            "agents_used": ["rag"],
        }

    def wipe(self, namespace: Optional[str] = None):
        """Clear all vectors in the namespace."""
        self.vector_store.wipe_namespace(namespace)

    @staticmethod
    def _format_context_blocks(contexts: List[Dict[str, Any]]) -> List[str]:
        blocks: List[str] = []
        for idx, context in enumerate(contexts, start=1):
            text = context["text"]
            blocks.append(f"{text}")
        return blocks


def build_rag_service_from_env() -> RAGService:
    """Factory that wires everything up via environment variables."""
    pinecone_config = PineconeConfig(
        api_key=_require_env("PINECONE_API_KEY"),
        index_name=os.getenv("PINECONE_INDEX_NAME", "astralassist"),
        host=os.getenv("PINECONE_HOST"),
        namespace=os.getenv("PINECONE_DEFAULT_NAMESPACE", "main"),
        top_k=int(os.getenv("PINECONE_TOP_K", "5")),
        dimension=int(os.getenv("PINECONE_DIMENSION", "0")) or None,
    )
    jina_config = JinaConfig(api_key=_require_env("JINA_API_KEY"), model=os.getenv("JINA_EMBEDDING_MODEL", "jina-embeddings-v2-base-en"))
    groq_config = GroqConfig(
        api_key=_require_env("GROQ_API_KEY"),
        model=os.getenv("GROQ_MODEL", "llama3-70b-8192"),
        system_prompt=os.getenv("GROQ_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
    )

    embedder = JinaEmbeddingClient(jina_config)
    vector_store = PineconeVectorStore(pinecone_config)
    llm_client = GroqLLMClient(groq_config)
    return RAGService(embedder, vector_store, llm_client, pinecone_config)


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Environment variable '{key}' is required for the RAG service.")
    return value


def _is_smalltalk(query: str) -> bool:
    lower = query.strip().lower()
    return lower in {"hi", "hello", "hey", "hey there", "yo", "hola"}
