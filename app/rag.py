from pathlib import Path

import pickle
import re

from sentence_transformers import SentenceTransformer


# ============================================================
# PATHS
# ============================================================

KB_DIR = (
    Path(__file__).resolve().parent.parent
    / "knowledge-base"
)

RAG_DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "rag_data"
)

EMBEDDINGS_FILE = RAG_DATA_DIR / "embeddings.pkl"


# ============================================================
# EMBEDDING MODEL
# ============================================================

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL
)


# ============================================================
# CHUNKING SETTINGS
# ============================================================

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


# ============================================================
# RAG SETTINGS
# ============================================================

MIN_SIMILARITY = 0.35

KEYWORD_BOOST = 0.20

TOPIC_BOOST = 0.40


# ============================================================
# TOPIC RULES
# ============================================================

TOPIC_RULES = {

    # --------------------------------------------------------
    # WRONG / DAMAGED ITEMS
    # --------------------------------------------------------

    "wrong_or_damaged": {

        "keywords": [

            "wrong item",
            "wrong product",

            "incorrect item",
            "incorrect product",

            "different item",
            "different product",

            "damaged",

            "damaged item",
            "damaged product",

            "defective item",
            "defective product",

            "item arrived damaged",
            "item was damaged",

            "arrived damaged",

            "received damaged",

            "item received damaged",

            "item i received was damaged",

            "wrong item was sent",
            "incorrect order",
        ],

        "documents": [

            "04-damaged-or-wrong-items.md"

        ]
    },


    # --------------------------------------------------------
    # FINAL SALE
    # --------------------------------------------------------

    "final_sale": {

        "keywords": [

            "final sale",
            "final-sale",
            "finalsale",

        ],

        "documents": [

            "03-final-sale-and-promotions.md"

        ]
    },


    # --------------------------------------------------------
    # RETURNS
    # --------------------------------------------------------

    "returns": {

        "keywords": [

            "return policy",
            "return an item",
            "return item",

            "refund policy",
            "refund",

            "return shipping",
            "return window",

        ],

        "documents": [

            "01-returns-policy-current.md"

        ]
    },


    # --------------------------------------------------------
    # WARRANTY
    # --------------------------------------------------------

    "warranty": {

        "keywords": [

            "warranty",

            "manufacturing defect",
            "defect after",
            "defective after",

        ],

        "documents": [

            "07-warranty.md"

        ]
    }
}


# ============================================================
# LOAD DOCUMENTS
# ============================================================

def load_documents():
    """
    Load all Markdown documents from the knowledge base.
    """

    documents = []

    for file_path in sorted(
        KB_DIR.glob("*.md")
    ):

        text = file_path.read_text(
            encoding="utf-8"
        )

        documents.append(
            {
                "source": file_path.name,
                "content": text,
            }
        )

    return documents


# ============================================================
# DOCUMENT STATUS
# ============================================================

def get_document_status(text):
    """
    Detect whether a document is current,
    superseded, or unknown.
    """

    status_match = re.search(
        r"(?im)^status\s*:\s*([^\n]+)",
        text
    )

    if status_match:

        status = (
            status_match
            .group(1)
            .strip()
            .lower()
        )

        if "superseded" in status:

            return "superseded"

        if "current" in status:

            return "current"

        if "active" in status:

            return "current"


    # --------------------------------------------------------
    # Detect legacy wording
    # --------------------------------------------------------

    if re.search(
        r"\b(legacy|superseded|obsolete|deprecated)\b",
        text,
        re.IGNORECASE
    ):

        return "superseded"


    return "current"


# ============================================================
# CHUNK DOCUMENT
# ============================================================

def chunk_text(
    text,
    chunk_size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP
):
    """
    Split a document into overlapping text chunks.
    """

    text = text.strip()

    if not text:

        return []


    chunks = []

    start = 0


    while start < len(text):

        end = start + chunk_size

        chunk = text[
            start:end
        ].strip()


        if chunk:

            chunks.append(
                chunk
            )


        if end >= len(text):

            break


        start = end - overlap


    return chunks


# ============================================================
# CREATE KNOWLEDGE-BASE CHUNKS
# ============================================================

def create_chunks():
    """
    Load documents, detect their status,
    and split them into chunks.
    """

    documents = load_documents()

    chunks = []


    for document in documents:

        status = get_document_status(
            document["content"]
        )


        document_chunks = chunk_text(
            document["content"]
        )


        for index, chunk in enumerate(
            document_chunks
        ):

            chunks.append(
                {
                    "source": document["source"],

                    "chunk_id": index,

                    "status": status,

                    "content": chunk,
                }
            )


    return chunks


# ============================================================
# CREATE EMBEDDING
# ============================================================

def create_embedding(text):
    """
    Convert text into a local embedding vector.
    """

    embedding = embedding_model.encode(
        text,
        normalize_embeddings=True,
    )

    return embedding.tolist()


# ============================================================
# BUILD EMBEDDING INDEX
# ============================================================

def build_index():
    """
    Create chunks and embeddings
    and save them locally.
    """

    print(
        "Building RAG index..."
    )


    chunks = create_chunks()


    if not chunks:

        print(
            "No documents found in knowledge base."
        )

        return []


    texts = [

        chunk["content"]

        for chunk in chunks

    ]


    print(
        f"Creating embeddings for "
        f"{len(texts)} chunks..."
    )


    embeddings = embedding_model.encode(

        texts,

        normalize_embeddings=True,

        show_progress_bar=True,

    )


    for chunk, embedding in zip(
        chunks,
        embeddings
    ):

        chunk["embedding"] = (
            embedding.tolist()
        )


    RAG_DATA_DIR.mkdir(

        parents=True,

        exist_ok=True,

    )


    with open(

        EMBEDDINGS_FILE,

        "wb",

    ) as file:

        pickle.dump(

            chunks,

            file,

        )


    print(
        f"RAG index saved to: "
        f"{EMBEDDINGS_FILE}"
    )


    return chunks


# ============================================================
# LOAD EMBEDDING INDEX
# ============================================================

def load_index():
    """
    Load the precomputed RAG index.
    """

    if not EMBEDDINGS_FILE.exists():

        return build_index()


    with open(

        EMBEDDINGS_FILE,

        "rb",

    ) as file:

        return pickle.load(file)


# ============================================================
# COSINE SIMILARITY
# ============================================================

def cosine_similarity(a, b):
    """
    Calculate cosine similarity between
    two vectors.
    """

    dot_product = sum(

        x * y

        for x, y in zip(a, b)

    )


    magnitude_a = sum(

        x * x

        for x in a

    ) ** 0.5


    magnitude_b = sum(

        x * x

        for x in b

    ) ** 0.5


    if (
        magnitude_a == 0
        or magnitude_b == 0
    ):

        return 0


    return dot_product / (

        magnitude_a
        * magnitude_b

    )


# ============================================================
# KEYWORD MATCH SCORE
# ============================================================

def keyword_match_score(
    query,
    content
):
    """
    Calculate keyword overlap between
    query and content.
    """

    query_words = set(

        re.findall(

            r"\b[a-zA-Z0-9]+\b",

            query.lower()

        )

    )


    content_words = set(

        re.findall(

            r"\b[a-zA-Z0-9]+\b",

            content.lower()

        )

    )


    important_words = {

        word

        for word in query_words

        if len(word) >= 4

    }


    if not important_words:

        return 0.0


    matches = (

        important_words
        .intersection(
            content_words
        )

    )


    return (

        len(matches)
        / len(important_words)

    )


# ============================================================
# DETECT QUERY TOPIC
# ============================================================

def detect_topics(query):
    """
    Detect important policy topics
    from the user query.
    """

    query_lower = query.lower()

    detected_topics = []


    for topic_name, rule in (
        TOPIC_RULES.items()
    ):

        for keyword in rule["keywords"]:

            if keyword in query_lower:

                detected_topics.append(
                    topic_name
                )

                break


    return detected_topics


# ============================================================
# TOPIC DOCUMENT BOOST
# ============================================================

def topic_document_boost(
    query,
    source
):
    """
    Give a controlled boost to documents
    that specifically match the detected
    query topic.
    """

    detected_topics = detect_topics(
        query
    )


    if not detected_topics:

        return 0.0


    boost = 0.0


    for topic in detected_topics:

        topic_documents = (
            TOPIC_RULES[
                topic
            ]["documents"]
        )


        if source in topic_documents:

            boost += TOPIC_BOOST


    return boost


# ============================================================
# SEARCH KNOWLEDGE BASE
# ============================================================

def search_knowledge_base(
    query,
    top_k=3
):
    """
    Search the knowledge base using:

    1. Semantic similarity
    2. Keyword matching
    3. Topic/document matching
    4. Minimum similarity threshold

    Superseded documents are excluded.
    """

    chunks = load_index()


    if not chunks:

        return []


    # --------------------------------------------------------
    # Create query embedding
    # --------------------------------------------------------

    query_embedding = create_embedding(
        query
    )


    results = []


    # --------------------------------------------------------
    # Evaluate every chunk
    # --------------------------------------------------------

    for chunk in chunks:

        # ----------------------------------------------------
        # Ignore superseded documents
        # ----------------------------------------------------

        if (
            chunk.get("status")
            == "superseded"
        ):

            continue


        # ----------------------------------------------------
        # Semantic similarity
        # ----------------------------------------------------

        semantic_score = cosine_similarity(

            query_embedding,

            chunk["embedding"],

        )


        # ----------------------------------------------------
        # Keyword score
        # ----------------------------------------------------

        keyword_score = keyword_match_score(

            query,

            chunk["content"]

        )


        # ----------------------------------------------------
        # Topic/document boost
        # ----------------------------------------------------

        topic_boost = topic_document_boost(

            query,

            chunk["source"]

        )


        # ----------------------------------------------------
        # Combined ranking score
        # ----------------------------------------------------

        ranking_score = (

            semantic_score

            + (

                KEYWORD_BOOST

                * keyword_score

            )

            + topic_boost

        )


        # ----------------------------------------------------
        # Store result
        # ----------------------------------------------------

        results.append(

            {
                "source":
                    chunk["source"],

                "chunk_id":
                    chunk["chunk_id"],

                "status":
                    chunk.get(
                        "status",
                        "current"
                    ),

                "content":
                    chunk["content"],

                "score":
                    semantic_score,

                "ranking_score":
                    ranking_score,

            }

        )


    # --------------------------------------------------------
    # Apply semantic similarity threshold
    # --------------------------------------------------------

    results = [

        result

        for result in results

        if result["score"]
        >= MIN_SIMILARITY

    ]


    # --------------------------------------------------------
    # Sort using combined score
    # --------------------------------------------------------

    results.sort(

        key=lambda item:
            item["ranking_score"],

        reverse=True,

    )


    # --------------------------------------------------------
    # Return top K
    # --------------------------------------------------------

    return results[:top_k]