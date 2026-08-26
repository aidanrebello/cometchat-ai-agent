"""
Regression tests for the conversation-history cross-contamination bugs.

Bug 1 — Order ID leakage
    After a user asks about a specific order (ORD-1007), the order ID
    stored in conversation history must NOT trigger the order-lookup
    hard route for a completely unrelated follow-up question.

Bug 2 — Policy-signal contamination
    After a user asks a warranty question, the "warranty" keyword stored
    in conversation history must NOT cause the warranty hard route to fire
    for a completely unrelated follow-up question.

Both bugs were caused by generate_answer() building combined_question
(current + all previous user messages) and then using that string for:
  - extract_order_id()  → historical_order_id leaked into order lookup
  - is_warranty_query() / is_damaged_or_wrong_query() etc.
    → prior-turn signals fired the wrong hard route

Fix: order_question detection moved before active_order_id so that
historical_order_id is only used when the CURRENT question is order-
related; policy-signal detection switched to question.lower() only.
"""

from app.agent import generate_answer


# ============================================================
# HELPERS
# ============================================================

def _order_history():
    """Simulated conversation history after one ORD-1007 lookup."""
    return [
        {
            "role": "user",
            "content": "Where is my order ORD-1007?",
        },
        {
            "role": "assistant",
            "content": (
                "Order ORD-1007 is currently shipped with UPS. "
                "It is currently estimated to arrive on August 22, 2026."
            ),
        },
    ]


def _warranty_history():
    """Simulated conversation history after one warranty question."""
    return [
        {
            "role": "user",
            "content": "What does the warranty cover?",
        },
        {
            "role": "assistant",
            "content": (
                "A manufacturing defect that develops after receipt is "
                "handled under the Warranty Policy rather than the "
                "standard return policy."
            ),
        },
    ]


ORDER_STATUS_ANSWER = (
    "Order ORD-1007 is currently shipped with UPS. "
    "It is currently estimated to arrive on August 22, 2026."
)

WARRANTY_ANSWER = (
    "A manufacturing defect that develops after receipt is "
    "handled under the Warranty Policy rather than the "
    "standard return policy. Aster & Row may offer a "
    "replacement, refund, or another appropriate resolution "
    "after review."
)


# ============================================================
# BUG 1 — Order ID must not leak from conversation history
# ============================================================

class TestOrderIdLeakage:
    """
    After asking about ORD-1007, a completely different question must
    NOT be answered with the ORD-1007 order-status response.
    """

    def test_warranty_after_order_lookup(self):
        """'What does the warranty cover?' must return warranty answer."""
        history = _order_history()
        result = generate_answer("What does the warranty cover?", history)
        assert result["answer"] == WARRANTY_ANSWER, (
            f"Expected warranty answer, got: {result['answer']!r}"
        )

    def test_warranty_answer_is_not_order_status(self):
        """Warranty answer must not contain ORD-1007 text."""
        history = _order_history()
        result = generate_answer("What does the warranty cover?", history)
        assert "ORD-1007" not in result["answer"], (
            "Order ID leaked into warranty response"
        )
        assert "UPS" not in result["answer"], (
            "Carrier info leaked into warranty response"
        )

    def test_damaged_item_after_order_lookup(self):
        """'My item arrived damaged.' must NOT return the order-status answer.

        If it reaches Ollama (RuntimeError), that proves the order-lookup hard
        route did NOT fire — which is the correct routing outcome.
        """
        history = _order_history()
        try:
            result = generate_answer("My item arrived damaged.", history)
            # If Ollama is running and returns an answer, verify it's not ORD-1007
            assert result["answer"] != ORDER_STATUS_ANSWER, (
                "Order-status answer incorrectly returned for damaged-item question"
            )
            assert "ORD-1007" not in result["answer"], (
                "Order ID leaked into damaged-item response"
            )
        except RuntimeError as e:
            # Ollama is offline but the question REACHED Ollama, which proves
            # the order-lookup hard route correctly did NOT fire.
            assert "Ollama error" in str(e), f"Unexpected RuntimeError: {e}"

    def test_isolated_warranty_baseline(self):
        """Warranty question with no history must still return warranty answer."""
        result = generate_answer("What does the warranty cover?", [])
        assert result["answer"] == WARRANTY_ANSWER


# ============================================================
# BUG 2 — Policy signals must not bleed from conversation history
# ============================================================

class TestPolicySignalContamination:
    """
    After asking a warranty question, an unrelated question must NOT
    be answered with the warranty hard-route response.
    """

    def test_damaged_after_warranty_not_warranty_answer(self):
        """
        'My item arrived damaged.' after a warranty question must NOT
        return the warranty hard-route answer.

        If it reaches Ollama (RuntimeError), that proves the warranty hard
        route did NOT fire — which is the correct routing outcome.
        """
        history = _warranty_history()
        try:
            result = generate_answer("My item arrived damaged.", history)
            assert result["answer"] != WARRANTY_ANSWER, (
                "Warranty answer incorrectly returned for 'My item arrived damaged.'"
            )
        except RuntimeError as e:
            assert "Ollama error" in str(e), f"Unexpected RuntimeError: {e}"

    def test_order_lookup_after_warranty(self):
        """
        A direct order lookup after a warranty question must return
        the order-status answer, not the warranty answer.
        """
        history = _warranty_history()
        result = generate_answer(
            "Where is my order ORD-1007?", history
        )
        assert result["answer"] == ORDER_STATUS_ANSWER, (
            f"Expected order answer, got: {result['answer']!r}"
        )

    def test_return_question_after_warranty(self):
        """
        A standard return question after a warranty question must NOT
        return the warranty answer.

        If it reaches Ollama (RuntimeError), that proves the warranty hard
        route did NOT fire — which is the correct routing outcome.
        """
        history = _warranty_history()
        try:
            result = generate_answer("Can I return my item?", history)
            assert result["answer"] != WARRANTY_ANSWER, (
                "Warranty answer incorrectly returned for return question"
            )
        except RuntimeError as e:
            assert "Ollama error" in str(e), f"Unexpected RuntimeError: {e}"


# ============================================================
# CONVERSATION MEMORY — legitimate follow-up questions
# ============================================================

class TestConversationMemory:
    """
    Conversation history must still work for genuine follow-up questions.
    Order lookup with an order ID in history, and the current question
    explicitly asking about that order, should still resolve correctly.
    """

    def test_order_followup_with_order_keyword(self):
        """
        'When will it arrive?' after ORD-1007 is an order question
        ('when will it arrive' is in is_order_lookup_question keywords),
        so historical_order_id should be used.
        """
        history = _order_history()
        result = generate_answer("When will it arrive?", history)
        # Should return order status (uses historical ORD-1007)
        assert "ORD-1007" in result["answer"], (
            "Follow-up order question should still use historical order ID"
        )

    def test_warranty_question_standalone_still_works(self):
        """Warranty question with no history returns the correct answer."""
        result = generate_answer("What does the warranty cover?", [])
        assert result["answer"] == WARRANTY_ANSWER

    def test_order_lookup_standalone_still_works(self):
        """Direct order lookup with no history returns correct answer."""
        result = generate_answer("Where is my order ORD-1007?", [])
        assert result["answer"] == ORDER_STATUS_ANSWER
