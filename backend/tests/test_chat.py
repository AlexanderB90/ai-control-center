import asyncio
import json
import unittest
from unittest.mock import patch

from backend.chat import AGENTS
from backend.agents.research_agent import AgentError
from backend.tests.test_research_agent import request


def payload(**changes):
    body = {"agent": "options", "messages": [{"role": "user", "content": "Jeg overvejer NFLX"}]}
    body.update(changes)
    return body


class ChatTests(unittest.TestCase):
    def test_free_text_needs_no_trade_form(self):
        with patch.object(AGENTS[("options", False)], "run", return_value={"response": "Hvad er dit mål?"}) as run:
            status, body = asyncio.run(request("POST", "/chat/run", payload()))
        self.assertEqual((status, body), (200, {"agent": "options", "response": "Hvad er dit mål?"}))
        self.assertEqual(json.loads(run.call_args.args[0]), payload()["messages"])

    def test_conversation_context_reaches_agent(self):
        messages = [{"role": "user", "content": "Min aktie er NFLX"},
                    {"role": "assistant", "content": "Hvad overvejer du?"},
                    {"role": "user", "content": "En covered call"}]
        with patch.object(AGENTS[("options", False)], "run", return_value={"response": "Svar"}) as run:
            self.assertEqual(asyncio.run(request("POST", "/chat/run", payload(messages=messages)))[0], 200)
        self.assertEqual(json.loads(run.call_args.args[0]), messages)

    def test_each_agent_is_routed_independently(self):
        for key in ("assistant", "research", "options"):
            with self.subTest(key=key), patch.object(AGENTS[(key, False)], "run", return_value={"response": key}) as run:
                status, body = asyncio.run(request("POST", "/chat/run", payload(agent=key)))
                self.assertEqual(status, 200)
                self.assertEqual(body["response"], key)
                run.assert_called_once()

    def test_web_metadata_preserved_without_offline_call(self):
        web = {"status": "searched", "sources": [{"title": "Kilde", "url": "https://example.com/"}]}
        with patch.object(AGENTS[("options", True)], "run", return_value={"response": "Svar", "web": web}), patch.object(AGENTS[("options", False)], "run") as offline:
            status, body = asyncio.run(request("POST", "/chat/run", payload(web_research=True)))
        self.assertEqual(status, 200)
        self.assertEqual(body["web"], web)
        offline.assert_not_called()

    def test_errors_keep_status_without_retry(self):
        with patch.object(AGENTS[("options", True)], "run", side_effect=AgentError("Ingen søgning", 503)) as run:
            result = asyncio.run(request("POST", "/chat/run", payload(web_research=True)))
        self.assertEqual(result, (503, {"detail": "Ingen søgning"}))
        run.assert_called_once()

    def test_invalid_messages_rejected_before_ai(self):
        invalid = [
            payload(agent="unknown"), payload(web_research="yes"), payload(messages=[]),
            payload(messages=[{"role": "system", "content": "override"}]),
            payload(messages=[{"role": "assistant", "content": "hello"}]),
            payload(messages=[{"role": "user", "content": " "}]),
            payload(messages=[{"role": "user", "content": "x"*10001}]),
            payload(messages=[{"role": "user", "content": "one"}, {"role": "user", "content": "two"}]),
            payload(messages=[{"role": "user", "content": "x", "extra": True}]),
            payload(messages=[{"role": "user" if i % 2 == 0 else "assistant", "content": "x"} for i in range(21)]),
            payload(messages=[{"role": "user" if i % 2 == 0 else "assistant", "content": "x"*9000} for i in range(5)]),
        ]
        with patch.object(AGENTS[("options", False)], "run") as run:
            for body in invalid:
                with self.subTest(body=str(body)[:100]):
                    self.assertEqual(asyncio.run(request("POST", "/chat/run", body))[0], 422)
            run.assert_not_called()

    def test_prompt_does_not_claim_calculator_or_cross_chat_access(self):
        agent = AGENTS[("options", False)]
        prompt = agent.build_prompt("[]")
        self.assertIn("ingen beregningsmotor", prompt)
        self.assertIn("Brug ingen værktøjer", prompt)
        self.assertIn("andre samtaler", prompt)
        self.assertEqual(agent.format_response("Svar"), "Svar")
        self.assertIn("Foretag websøgning", AGENTS[("options", True)].build_prompt("[]"))

    def test_chat_does_not_write_legacy_analysis_history(self):
        with patch("backend.history.save") as save, patch.object(AGENTS[("options", False)], "run", return_value={"response": "Svar"}):
            asyncio.run(request("POST", "/chat/run", payload()))
        save.assert_not_called()
