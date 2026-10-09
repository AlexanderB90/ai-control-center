import asyncio
from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from backend import history
from backend.tests import test_research_agent

request = test_research_agent.request


class StorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = patch('backend.history.DATABASE_PATH', Path(temporary.name) / 'nested' / 'history.sqlite3')
        database.start()
        self.addCleanup(database.stop)

    def test_persistence_separate_connections_and_parameterized_text(self):
        task = "'); DROP TABLE research_history; --\nDansk æøå"
        with patch('backend.history.sqlite3.connect', wraps=sqlite3.connect) as connect:
            identifier = history.save(task, 'Fuldstændigt svar', 'Research Agent', '0.2.0')
            record = history.detail(identifier)
            listing = history.recent()
        self.assertEqual(connect.call_count, 3)
        self.assertEqual(str(UUID(identifier)), identifier)
        self.assertEqual(datetime.fromisoformat(record['created_at']).utcoffset().total_seconds(), 0)
        self.assertEqual(record['task'], task)
        self.assertEqual(record['response'], 'Fuldstændigt svar')
        self.assertEqual(record['version'], '0.2.0')
        self.assertEqual(listing[0]['id'], identifier)
        self.assertNotIn('response', listing[0])

    def test_latest_fifty_sorted_by_timestamp(self):
        identifiers = [history.save(str(i) + 'x' * 200, 'answer', 'Research Agent', '0.2.0') for i in range(55)]
        # Deliberately make the first inserted record newest.
        with history.connection() as database:
            database.execute('UPDATE research_history SET created_at = ? WHERE id = ?',
                             ('2099-01-01T00:00:00.000000+00:00', identifiers[0]))
        listing = history.recent()
        self.assertEqual(len(listing), 50)
        self.assertEqual([item['id'] for item in listing], [identifiers[0], *reversed(identifiers[6:])])
        self.assertTrue(all(len(item['task_excerpt']) == 160 for item in listing))
        self.assertIsNone(history.detail("' OR 1=1 --"))


class HistoryEndpointTests(test_research_agent.EndpointTests):
    def test_list_detail_and_unknown_id(self):
        result = {'agent': 'Research Agent', 'version': '0.2.0', 'status': 'success',
                  'task': 'Opgave', 'response': 'Fuldt svar'}
        with patch('backend.main.research_agent.run', return_value=result) as run:
            self.assertEqual(asyncio.run(request('POST', '/agents/research/run', {'task': 'Opgave'})), (200, result))
            run.assert_called_once()
        status, listing = asyncio.run(request('GET', '/agents/research/history'))
        self.assertEqual(status, 200)
        self.assertEqual(len(listing), 1)
        self.assertNotIn('response', listing[0])
        status, record = asyncio.run(request('GET', '/agents/research/history/' + listing[0]['id']))
        self.assertEqual(status, 200)
        self.assertEqual(record['task'], 'Opgave')
        self.assertEqual(record['response'], 'Fuldt svar')
        self.assertEqual(asyncio.run(request('GET', '/agents/research/history/unknown'))[0], 404)

    def test_save_failure_keeps_response_without_retry(self):
        result = {'agent': 'Research Agent', 'version': '0.2.0', 'status': 'success',
                  'task': 'Hej', 'response': 'Vellykket svar'}
        for failure in (sqlite3.OperationalError('PRIVATE'), PermissionError('PRIVATE')):
            with self.subTest(failure=failure), patch('backend.main.research_agent.run', return_value=result) as run, patch('backend.history.save', side_effect=failure):
                status, body = asyncio.run(request('POST', '/agents/research/run', {'task': 'Hej'}))
                self.assertEqual(status, 200)
                self.assertEqual(body, {**result, 'history_warning': history.SAVE_WARNING})
                run.assert_called_once_with('Hej')
                self.assertNotIn('PRIVATE', str(body))

    def test_database_errors_hide_internal_details(self):
        history.DATABASE_PATH.parent.mkdir(parents=True)
        with patch('backend.history.DATABASE_PATH', history.DATABASE_PATH.parent):
            for path in ('/agents/research/history', '/agents/research/history/unknown'):
                self.assertEqual(asyncio.run(request('GET', path)), (503, {'detail': history.ERROR_MESSAGE}))

    def test_failed_agent_is_not_saved(self):
        from backend.agents.research_agent import AgentError
        with patch('backend.main.research_agent.run', side_effect=AgentError('Fejl')), patch('backend.history.save') as save:
            self.assertEqual(asyncio.run(request('POST', '/agents/research/run', {'task': 'Hej'}))[0], 502)
            save.assert_not_called()
