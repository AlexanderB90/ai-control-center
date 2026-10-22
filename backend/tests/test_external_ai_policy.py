"""Tests for the fail-closed AI gate; no real external calls."""
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from backend.external_ai_policy import require_external_ai_approval

class ExternalAIPolicyTests(unittest.TestCase):
    def test_off_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                require_external_ai_approval("true")
        self.assertEqual(raised.exception.status_code, 403)

    def test_needs_per_run_confirmation(self):
        with patch.dict(os.environ, {"AIC_EXTERNAL_AI_ENABLED": "1"}):
            for decision in (None, "", "false", "TRUE"):
                with self.subTest(decision=decision):
                    with self.assertRaises(HTTPException) as raised:
                        require_external_ai_approval(decision)
                    self.assertEqual(raised.exception.status_code, 403)

    def test_both_switches_required(self):
        with patch.dict(os.environ, {"AIC_EXTERNAL_AI_ENABLED": "1"}):
            self.assertIsNone(require_external_ai_approval("true"))
