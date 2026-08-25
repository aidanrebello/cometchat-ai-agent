from app.rag import search_knowledge_base


def test_rag_search():
    query = (
        "How long does a regular customer have "
        "to return an unused backpack?"
    )

    results = search_knowledge_base(
        query,
        top_k=3
    )

    # Make sure the RAG system returns results
    assert len(results) > 0

    # The current returns policy should be the
    # most relevant document.
    assert (
        results[0]["source"]
        == "01-returns-policy-current.md"
    )

    print("\nTop results:\n")

    for result in results:

        print("=" * 60)

        print(
            "SOURCE:",
            result["source"]
        )

        print(
            "SCORE:",
            round(
                result["score"],
                4
            )
        )

        print("=" * 60)

        print(
            result["content"][:500]
        )

        print()