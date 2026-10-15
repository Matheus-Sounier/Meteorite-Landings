import json
import os
import unittest
from unittest.mock import patch

from meteorite_pipeline.analytics.meteorite_chat import (
    MAX_RESULT_ROWS,
    answer_question,
    build_meteorite_query,
    query_meteorites,
)


class MeteoriteQueryBuilderTests(unittest.TestCase):
    def test_filter_values_are_parameters_and_limits_are_bounded(self) -> None:
        injection = "Found' OR TRUE; DROP TABLE meteorite_landings --"

        query, parameters = build_meteorite_query(
            {
                "action": "list",
                "fields": ["name", "id", "mass_g"],
                "filters": [
                    {"field": "fall", "operator": "eq", "value": "Found"},
                    {"field": "name", "operator": "contains", "value": injection},
                ],
                "limit": 10000,
            }
        )

        query_text = query.as_string(None)
        self.assertNotIn(injection, query_text)
        self.assertEqual(parameters, ("Found", f"%{injection}%", MAX_RESULT_ROWS))
        self.assertIn('"mass (g)"', query_text)

    def test_rejects_unknown_fields_operators_and_non_finite_numbers(self) -> None:
        with self.assertRaises(ValueError):
            build_meteorite_query({"action": "list", "fields": ["id; DROP TABLE x"]})
        with self.assertRaises(ValueError):
            build_meteorite_query(
                {
                    "action": "count",
                    "filters": [{"field": "fall", "operator": "= TRUE; DROP TABLE x", "value": "Found"}],
                }
            )
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            build_meteorite_query(
                {
                    "action": "count",
                    "filters": [{"field": "id", "operator": "eq", "value": 1.5}],
                }
            )
        with self.assertRaises(ValueError):
            build_meteorite_query(
                {
                    "action": "count",
                    "filters": [{"field": "reclat", "operator": "gt", "value": "Infinity"}],
                }
            )

    def test_grouped_count_uses_only_allowlisted_fields(self) -> None:
        query, parameters = build_meteorite_query(
            {"action": "count", "group_by": ["fall"], "limit": 500}
        )

        self.assertIn('GROUP BY "fall"', query.as_string(None))
        self.assertEqual(parameters, (MAX_RESULT_ROWS,))

    def test_query_executes_in_read_only_transaction_with_statement_timeout(self) -> None:
        connection = unittest.mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.description = [type("Column", (), {"name": "record_count"})()]
        cursor.fetchmany.return_value = [(2,)]

        with patch(
            "meteorite_pipeline.analytics.meteorite_chat.get_dash_connection",
            return_value=connection,
        ):
            result = query_meteorites({"action": "count"})

        self.assertEqual(result, {"columns": ["record_count"], "rows": [{"record_count": 2}], "row_count": 1})
        cursor.execute.assert_any_call("SET TRANSACTION READ ONLY")
        cursor.execute.assert_any_call("SET LOCAL statement_timeout = '5s'")
        connection.close.assert_called_once_with()


class MeteoriteChatAgentTests(unittest.TestCase):
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "test/model"})
    @patch("meteorite_pipeline.analytics.meteorite_chat.query_meteorites")
    @patch("meteorite_pipeline.analytics.meteorite_chat._post_openrouter")
    def test_tool_call_uses_local_data_and_model_decides_when_to_search(
        self, post_mock, query_mock
    ) -> None:
        tool_message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "query-1",
                    "type": "function",
                    "function": {
                        "name": "query_meteorites",
                        "arguments": json.dumps({"action": "count", "filters": []}),
                    },
                }
            ],
        }
        final_message = {
            "role": "assistant",
            "content": "The local dataset contains two records.",
            "annotations": [
                {
                    "type": "url_citation",
                    "url_citation": {"url": "https://example.org/source", "title": "Example"},
                }
            ],
        }
        post_mock.side_effect = [
            {"choices": [{"message": tool_message}]},
            {"choices": [{"message": final_message}]},
        ]
        query_mock.return_value = {"columns": ["record_count"], "rows": [{"record_count": 2}], "row_count": 1}

        answer = answer_question("How many meteorites are recorded?", [])

        self.assertIn("two records", answer)
        self.assertIn("[Example](https://example.org/source)", answer)
        self.assertEqual(query_mock.call_count, 1)
        first_payload = post_mock.call_args_list[0].args[0]
        self.assertEqual(
            first_payload["tools"][1],
            {
                "type": "openrouter:web_search",
                "parameters": {"max_results": 5, "max_total_results": 10, "max_uses": 2},
            },
        )
        self.assertEqual(first_payload["max_tool_calls"], 8)
        second_messages = post_mock.call_args_list[1].args[0]["messages"]
        self.assertTrue(any(message.get("role") == "tool" for message in second_messages))

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "OPENROUTER_MODEL": ""})
    @patch("meteorite_pipeline.analytics.meteorite_chat._post_openrouter")
    def test_missing_model_configuration_fails_without_network_call(self, post_mock) -> None:
        with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
            answer_question("question", [])

        post_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()