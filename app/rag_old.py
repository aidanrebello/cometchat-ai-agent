from pathlib import Path
from sentence_transformers import SentenceTransformer


# Knowledge-base directory
KB_DIR = Path(__file__).resolve().parent.parent / "knowledge-base"


# Local embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Load the model once when the application starts
embedding_model = SentenceTransformer(EMBEDDING_MODEL)


def load_documents():
    """
    Load all Markdown documents from the knowledge base.
    """

    documents = []

    for file_path in sorted(KB_DIR.glob("*.md")):

        text = file_path.read_text(encoding="utf-8")

        documents.append(
            {
                "source": file_path.name,
                "content": text,
            }
        )

    return documents


def create_embedding(text):
    """
    Convert text into a local embedding vector.
    """

    embedding = embedding_model.encode(text)

    return embedding.tolist()


def cosine_similarity(a, b):
    """
    Calculate cosine similarity between two vectors.
    """

    dot_product = sum(x * y for x, y in zip(a, b))

    magnitude_a = sum(x * x for x in a) ** 0.5
    magnitude_b = sum(x * x for x in b) ** 0.5

    if magnitude_a == 0 or magnitude_b == 0:
        return 0

    return dot_product / (magnitude_a * magnitude_b)


def search_knowledge_base(query, top_k=3):
    """
    Search the knowledge base and return the most relevant documents.
    """

    documents = load_documents()

    query_embedding = create_embedding(query)

    results = []

    for document in documents:

        document_embedding = create_embedding(document["content"])

        similarity = cosine_similarity(
            query_embedding,
            document_embedding,
        )

        results.append(
            {
                "source": document["source"],
                "content": document["content"],
                "score": similarity,
            }
        )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:top_k]