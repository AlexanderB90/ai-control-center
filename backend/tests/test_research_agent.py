import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from backend.agents.research_agent import AgentError, NOTICE, ResearchAgent, command, log_failure
from backend.main import app
from backend import history


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fake = Path(self.tmp.name) / 'fake_codex.py'
        self.fake.write_text('''import os, sys, time
from pathlib import Path
args = sys.argv[1:]
prompt = sys.stdin.read()
assert args[-1] == '-'
assert '--sandbox' in args and args[args.index('--sandbox')+1] == 'read-only'
assert 'OPENAI_API_KEY' not in os.environ
assert 'OTHER_API_KEY' not in os.environ
assert 'Svar på dansk' in prompt
assert not list(Path.cwd().glob('.env*'))
mode = MODE
if mode == 'timeout':
    time.sleep(60)
if mode == 'error':
    print(ERROR, file=sys.stderr)
    sys.exit(1)
if mode == 'success':
    Path(args[args.index('--output-last-message')+1]).write_text('Dansk svar\\nAnden linje')
print('PRIVATE PROCESS LOG')
''')
        self.agent = ResearchAgent()
        self.agent.timeout_seconds = 2
        self.original_popen = subprocess.Popen
        self.calls = []

    def simulate(self, mode='success', error=''):
        script = self.fake.read_text().replace('mode = MODE', f'mode = {mode!r}').replace('print(ERROR,', f'print({error!r},')
        self.fake.write_text(script)
        def spawn(args, **kwargs):
            self.calls.append((args, kwargs))
            return self.original_popen([sys.executable, str(self.fake), *args[1:]], **kwargs)
        return patch('backend.agents.research_agent.subprocess.Popen', side_effect=spawn)

    def test_success_stdin_and_security(self):
        task = '--dangerously-bypass-approvals-and-sandbox; $(echo nope)'
        with self.simulate(), patch.dict(os.environ, {'OPENAI_API_KEY': 'secret', 'OTHER_API_KEY': 'secret'}):
            result = self.agent.run(task)
        self.assertEqual(result['response'], NOTICE + '\n\nDansk svar\nAnden linje')
        self.assertNotIn('PRIVATE', result['response'])
        args, kwargs = self.calls[0]
        self.assertNotIn(task, args)
        self.assertFalse(kwargs['shell'])
        self.assertTrue(kwargs['start_new_session'])
        self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
        self.assertFalse(Path(kwargs['cwd']).exists())
        for setting in ['web_search="disabled"', 'forced_login_method="chatgpt"',
                        'model_provider="research_chatgpt"']:
            self.assertIn(setting, args)
        for feature in ['shell_tool', 'unified_exec', 'apps', 'plugins', 'browser_use', 'multi_agent']:
            index = args.index(feature)
            self.assertEqual(args[index-1], '--disable')
        self.assertEqual(len(self.calls), 1)

    def test_custom_provider_configuration(self):
        args = command(Path('/tmp/answer.txt'))
        settings = [args[i+1] for i, arg in enumerate(args) if arg == '-c']
        self.assertFalse(any(s.startswith('model_providers.openai.') for s in settings))
        import tomllib
        provider_setting = next(s for s in settings if s.startswith('model_providers.'))
        provider = tomllib.loads(provider_setting)['model_providers']['research_chatgpt']
        self.assertTrue(provider['requires_openai_auth'])
        self.assertEqual(provider['wire_api'], 'responses')
        self.assertEqual(provider['request_max_retries'], 0)
        self.assertEqual(provider['stream_max_retries'], 0)

    def test_diagnostics_never_echo_process_text(self):
        for raw in [
            'Error: model_providers contains reserved built-in provider IDs: openai SECRET task-text',
            'connection failed https://user:SECRET@example.com task-text',
            'unrecognized error SECRET task-text',
        ]:
            with self.assertLogs('backend.agents.research_agent', level='WARNING') as logs:
                log_failure(17, raw)
            message = ''.join(logs.output)
            self.assertIn('exitkode=17', message)
            self.assertNotIn('SECRET', message)
            self.assertNotIn('task-text', message)
            self.assertNotIn('example.com', message)

    def test_missing_codex(self):
        with patch('backend.agents.research_agent.subprocess.Popen', side_effect=FileNotFoundError):
            with self.assertRaises(AgentError) as error:
                self.agent.run('hej')
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn('ikke fundet', str(error.exception))

    def test_cli_errors_no_retry_or_log_leak(self):
        for log, status in [('401 unauthorized SECRET', 503), ('usage_limit_reached SECRET', 429), ('unknown SECRET', 502), ('model_providers contains reserved built-in provider IDs: openai SECRET', 503)]:
            with self.subTest(log=log):
                # Each simulation needs a fresh template.
                self.setUp()
                with self.simulate('error', log):
                    with self.assertRaises(AgentError) as error:
                        self.agent.run('hej')
                self.assertEqual(error.exception.status_code, status)
                self.assertNotIn('SECRET', str(error.exception))
                self.assertEqual(len(self.calls), 1)

    def test_timeout_kills_and_reaps_and_releases_lock(self):
        self.agent.timeout_seconds = 0.1
        processes = []
        with self.simulate('timeout'):
            spawn = subprocess.Popen
            def tracked(*args, **kwargs):
                process = spawn(*args, **kwargs)
                processes.append(process)
                return process
            with patch('backend.agents.research_agent.subprocess.Popen', side_effect=tracked):
                with self.assertRaises(AgentError) as error:
                    self.agent.run('hej')
        self.assertEqual(error.exception.status_code, 504)
        self.assertEqual(processes[0].poll(), -9)
        self.assertFalse(Path(self.calls[0][1]['cwd']).exists())
        with patch.object(self.agent, '_run', return_value={'ok': True}):
            self.assertEqual(self.agent.run('igen'), {'ok': True})

    def test_concurrent_run_rejected(self):
        entered, release = threading.Event(), threading.Event()
        def running(task):
            entered.set()
            release.wait(3)
        with patch.object(self.agent, '_run', side_effect=running):
            thread = threading.Thread(target=self.agent.run, args=('first',))
            thread.start()
            try:
                self.assertTrue(entered.wait(2))
                with self.assertRaises(AgentError) as error:
                    ResearchAgent().run('second')
                self.assertEqual(error.exception.status_code, 409)
            finally:
                release.set()
                thread.join(3)

    def test_empty_output(self):
        with self.simulate('empty'):
            with self.assertRaises(AgentError) as error:
                self.agent.run('hej')
        self.assertEqual(error.exception.status_code, 502)


async def request(method, path, body=None):
    payload = json.dumps(body).encode() if body is not None else b''
    messages = []
    async def receive():
        return {'type': 'http.request', 'body': payload, 'more_body': False}
    async def send(message):
        messages.append(message)
    await app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
               'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
               'query_string': b'', 'headers': [(b'content-type', b'application/json')],
               'client': ('127.0.0.1', 1), 'server': ('127.0.0.1', 8000)}, receive, send)
    return messages[0]['status'], json.loads(b''.join(m.get('body', b'') for m in messages[1:]))


class EndpointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = patch('backend.history.DATABASE_PATH', Path(temporary.name) / 'data' / 'history.sqlite3')
        database.start()
        self.addCleanup(database.stop)
        runner = patch('backend.main.research_agent.run', side_effect=AssertionError('Real Codex forbidden in endpoint tests'))
        runner.start()
        self.addCleanup(runner.stop)

    def test_validation_and_get_removed(self):
        with patch('backend.main.research_agent.run') as run:
            for body in [{}, {'task': ''}, {'task': '   '}, {'task': 1}, {'task': 'x'*10001}, {'task': 'ok', 'extra': True}]:
                self.assertEqual(asyncio.run(request('POST', '/agents/research/run', body))[0], 422)
            self.assertEqual(asyncio.run(request('GET', '/agents/research/run'))[0], 405)
            run.assert_not_called()

    def test_valid_post_and_error_mapping(self):
        with patch('backend.main.research_agent.run', return_value={'response': 'hej'}) as run:
            self.assertEqual(asyncio.run(request('POST', '/agents/research/run', {'task': ' hej '})), (200, {'response': 'hej'}))
            run.assert_called_once_with('hej')
        with patch('backend.main.research_agent.run', side_effect=AgentError('Vent venligst', 409)):
            self.assertEqual(asyncio.run(request('POST', '/agents/research/run', {'task': 'hej'})), (409, {'detail': 'Vent venligst'}))

    def test_health(self):
        status, body = asyncio.run(request('GET', '/health'))
        self.assertEqual(status, 200)
        self.assertEqual(body['status'], 'online')


if __name__ == '__main__':
    unittest.main()
