"""
Unit tests for Dynamic STT Keyword Generation, Tenant Isolation, KB Exclusion, Caller Name Extraction, Caller Corrections, Spelling Normalization, and Retry Safeguards.
"""

import unittest
from name_service import build_stt_keywords, parse_caller_name, normalize_spelled_name, NameCaptureState


class TestNameCaptureAndSTT(unittest.TestCase):

    def test_dynamic_stt_keywords_agent_isolation(self):
        """Test 1 - Verify Agent A and Agent B STT hints are completely isolated and immune to mutation leakage."""
        agent_A = {
            "name": "Agent Alpha",
            "client_name": "Company Alpha"
        }
        keywords_A = build_stt_keywords(agent_A)
        words_A = [kw[0] for kw in keywords_A]

        self.assertIn("Agent Alpha", words_A)
        self.assertIn("Company Alpha", words_A)

        agent_B = {
            "name": "Agent Beta",
            "client_name": "Company Beta"
        }
        keywords_B = build_stt_keywords(agent_B)
        words_B = [kw[0] for kw in keywords_B]

        self.assertIn("Agent Beta", words_B)
        self.assertIn("Company Beta", words_B)

        # Assert no cross-tenant leakage
        self.assertNotIn("Agent Beta", words_A)
        self.assertNotIn("Company Beta", words_A)
        self.assertNotIn("Agent Alpha", words_B)
        self.assertNotIn("Company Alpha", words_B)

        # Mutate returned Agent A list and prove Agent B is unaffected
        keywords_A.append(("Mutated Entity", 3.0))
        self.assertNotIn("Mutated Entity", [kw[0] for kw in build_stt_keywords(agent_B)])

    def test_knowledge_items_excluded_from_stt_hints(self):
        """Test 2 - Verify arbitrary KB items (URLs, policies, addresses) are excluded from STT hints."""
        agent_data = {
            "name": "Support Bot",
            "client_name": "Tech Corp",
            "knowledge_items": [
                {"label": "Website", "value": "https://example.com"},
                {"label": "Refund Policy", "value": "Refunds are allowed within thirty days"},
                {"label": "Office Address", "value": "123 Example Street"}
            ]
        }
        keywords = [kw[0] for kw in build_stt_keywords(agent_data)]

        # Verify only structured agent/client entities are in hints
        self.assertIn("Support Bot", keywords)
        self.assertIn("Tech Corp", keywords)

        # Verify arbitrary KB text is excluded
        self.assertNotIn("Website", keywords)
        self.assertNotIn("https://example.com", keywords)
        self.assertNotIn("Refund Policy", keywords)
        self.assertNotIn("Office Address", keywords)

    def test_parse_caller_name_false_positive_protections(self):
        """Test 3 - Verify sentence fragments like 'I am calling about billing' are NOT mistaken for caller names."""
        self.assertIsNone(parse_caller_name("I am calling about billing"))
        self.assertIsNone(parse_caller_name("I'm trying to book an appointment"))
        self.assertIsNone(parse_caller_name("I am looking for help"))
        self.assertIsNone(parse_caller_name("I am asking about pricing"))

        # Clear name utterances should still parse cleanly
        self.assertEqual(parse_caller_name("My name is Lokesh."), "Lokesh")
        self.assertEqual(parse_caller_name("My name is Alex."), "Alex")
        self.assertEqual(parse_caller_name("I am John"), "John")

    def test_unlisted_caller_names_accepted(self):
        """Test 4 - Verify arbitrary caller names are accepted directly even when not in STT keywords."""
        agent_data = {"name": "Bot", "client_name": "Acme"}
        keywords = [kw[0] for kw in build_stt_keywords(agent_data)]

        # Ensure caller names are not present in keywords
        for name in ["Lokesh", "Ahmed", "Ximena", "John", "Fatima"]:
            self.assertNotIn(name, keywords)
            extracted = parse_caller_name(f"My name is {name}.")
            self.assertEqual(extracted, name)

    def test_caller_name_correction(self):
        """Test 5 - Verify caller correction ('No, Lokesh.') replaces previous captured name ('Lopez')."""
        state = NameCaptureState()
        # Initial STT misheard name as Lopez
        res1 = state.process_utterance("My name is Lopez.")
        self.assertEqual(res1["action"], "accept")
        self.assertEqual(res1["name"], "Lopez")

        # Caller corrects: "No, Lokesh."
        res2 = state.process_utterance("No, Lokesh.")
        self.assertEqual(res2["action"], "corrected")
        self.assertEqual(res2["name"], "Lokesh")
        self.assertEqual(state.captured_name, "Lokesh")

    def test_letter_spelling_normalization(self):
        """Test 6 - Verify letter-by-letter spelled names normalize to proper capitalized names."""
        test_cases = [
            ("L O K E S H", "Lokesh"),
            ("J O H N", "John"),
            ("A H M E D", "Ahmed"),
            ("X I M E N A", "Ximena"),
            ("L. O. K. E. S. H.", "Lokesh")
        ]
        for spelled, expected in test_cases:
            name, valid = normalize_spelled_name(spelled)
            self.assertTrue(valid)
            self.assertEqual(name, expected)

    def test_numeric_spelling_rejection(self):
        """Test 7 - Verify spoken numbers/digits are rejected when spelling is requested."""
        name1, valid1 = normalize_spelled_name("Seven four eight eight eight")
        self.assertFalse(valid1)
        self.assertIsNone(name1)

        name2, valid2 = normalize_spelled_name("7 4 8 8 8")
        self.assertFalse(valid2)
        self.assertIsNone(name2)

    def test_spelling_retry_limit_no_infinite_loop(self):
        """Test 8 - Verify spelling retries are capped at maximum 2 attempts without infinite loops."""
        state = NameCaptureState(max_spelling_retries=2)
        state.state = "WAITING_FOR_NAME_SPELLING"

        # Attempt 1: Invalid numeric spelling
        res1 = state.process_utterance("Seven four eight")
        self.assertEqual(res1["action"], "retry_spelling")
        self.assertEqual(res1["retry_count"], 1)

        # Attempt 2: Invalid numeric spelling again
        res2 = state.process_utterance("7 4 8 8 8")
        self.assertEqual(res2["action"], "continue_without_spelling")
        self.assertEqual(state.state, "NAME_ACCEPTED")

    def test_direct_name_acceptance_state_flow(self):
        """Test 9 - Verify clear names transition state machine directly to NAME_ACCEPTED."""
        state = NameCaptureState(max_spelling_retries=2)
        res = state.process_utterance("My name is Lokesh.")

        self.assertEqual(res["action"], "accept")
        self.assertEqual(res["name"], "Lokesh")
        self.assertEqual(state.state, "NAME_ACCEPTED")


if __name__ == "__main__":
    unittest.main()


