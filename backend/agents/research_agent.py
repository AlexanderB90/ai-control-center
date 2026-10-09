"""Local text-only Codex runner; credentials are handled only by Codex."""
import fcntl
import logging
import os
from pathlib import Path
import signal
import subprocess
import tempfile

NOTICE = 'Denne første version henter ikke aktuelle oplysninger fra internettet.'
DISABLED_FEATURES = (
    'shell_tool', 'unified_exec', 'shell_snapshot', 'apps', 'plugins',
    'remote_plugin', 'browser_use', 'browser_use_external', 'computer_use',
    'image_generation', 'view_image', 'multi_agent', 'multi_agent_v2',
    'code_mode', 'code_mode_host', 'goals', 'hooks', 'memories',
    'skill_search', 'skill_mcp_dependency_install', 'sleep_tool', 'tool_suggest',
    'unbounded_connection_retries',
)

class AgentError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def process_environment():
    # Allowlist prevents API keys and inherited agent/session flags from leaking.
    allowed = ('HOME', 'PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'CODEX_HOME',
               'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME')
    return {key: os.environ[key] for key in allowed if key in os.environ}


def command(output: Path):
    args = ['codex', 'exec', '--ignore-user-config', '--ignore-rules',
            '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only',
            '--color', 'never', '--output-last-message', str(output)]
    for feature in DISABLED_FEATURES:
        args.extend(['--disable', feature])
    for setting in (
        'approval_policy="never"', 'web_search="disabled"',
        'forced_login_method="chatgpt"', 'model_provider="research_chatgpt"',
        'mcp_servers={}', 'project_doc_max_bytes=0',
        # 0.160.0 rejects overrides of the reserved built-in `openai` ID.
        'model_providers.research_chatgpt={name="Research ChatGPT", wire_api="responses", requires_openai_auth=true, request_max_retries=0, stream_max_retries=0}',
    ):
        args.extend(['-c', setting])
    return args + ['-']


def log_failure(exit_code: int, stderr: str):
    # Never log raw CLI text: it can contain credentials, prompts or responses.
    # Emit only fixed descriptions recognized from local diagnostics.
    lower = stderr.lower()
    if 'reserved built-in provider' in lower:
        reason = 'Konfigurationsfejl: reserveret provider-ID kan ikke overskrives.'
    elif 'failed to load' in lower and 'configuration' in lower:
        reason = 'Codex kunne ikke indlæse konfigurationen.'
    elif 'unexpected argument' in lower or 'unknown feature' in lower:
        reason = 'CLI afviste et argument eller feature-flag.'
    elif 'connection' in lower or 'connect' in lower or 'dns' in lower:
        reason = 'Codex rapporterede en forbindelsesfejl.'
    else:
        reason = str(failure_message(stderr))
    logging.getLogger(__name__).warning(
        'Codex-fejl: exitkode=%s; %s', exit_code, reason,
    )


def failure_message(log: str):
    log = log.lower()
    if 'reserved built-in provider' in log or ('failed to load' in log and 'configuration' in log):
        return AgentError('Codex afviste backendens konfiguration. Se den sikre diagnostik i backend-terminalen.', 503)
    if any(word in log for word in ('usage limit', 'rate limit', 'quota',
           'too many requests', '429', 'usage_limit', 'rate_limit', 'credits', 'limit reached')):
        return AgentError('Forbrugsgrænsen for Codex/ChatGPT er nået. Prøv igen senere.', 429)
    if any(word in log for word in ('login', 'log in', 'unauthorized',
           'authentication', '401', 'token', 'not authenticated', 'sign in')):
        return AgentError('Codex-login mangler eller er udløbet. Kør codex login med ChatGPT på denne maskine.', 503)
    return AgentError('Codex kunne ikke gennemføre opgaven. Kontrollér din lokale Codex-installation og forbindelse.')


class ResearchAgent:
    name = 'Research Agent'
    version = '0.2.0'
    timeout_seconds = 120

    def run(self, task: str):
        # File lock also serializes multiple local backend workers.
        lock_path = Path(__file__).resolve().parents[1] / '.research-agent.lock'
        with lock_path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise AgentError('Research Agent kører allerede en opgave. Vent til den er færdig.', 409)
            try:
                return self._run(task)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _run(self, task: str):
        with tempfile.TemporaryDirectory(prefix='research-agent-') as directory:
            output = Path(directory) / 'answer.txt'
            prompt = (
                'Du er Research Agent. Svar på dansk i ren tekst. '
                'Besvar opgaven ud fra din eksisterende viden og brugerens tekst. '
                'Brug ingen værktøjer. Angiv usikkerhed og opfind ikke kilder. '
                'En fast besked om manglende internetadgang tilføjes automatisk foran dit svar. '
                'Gentag ikke denne besked i dit svar.\n\n'
                f'Brugerens opgave:\n{task}'
            )
            try:
                with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                    process = subprocess.Popen(
                        command(output), stdin=subprocess.PIPE, stdout=stdout,
                        stderr=stderr, cwd=directory, env=process_environment(),
                        start_new_session=True, shell=False,
                    )
                    try:
                        process.communicate(prompt.encode('utf-8'), timeout=self.timeout_seconds)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.communicate()
                        raise AgentError('Opgaven tog for lang tid og blev stoppet efter 120 sekunder.', 504)
                    if process.returncode:
                        stderr.seek(0)
                        error_text = stderr.read().decode('utf-8', errors='replace')
                        log_failure(process.returncode, error_text)
                        raise failure_message(error_text)
            except FileNotFoundError:
                raise AgentError('Codex CLI blev ikke fundet. Installér Codex og sørg for, at codex findes i backendens PATH.', 503)
            except OSError:
                raise AgentError('Codex-processen kunne ikke startes på denne maskine.', 503)
            if not output.is_file():
                raise AgentError('Codex afsluttede uden et agentsvar.')
            answer = output.read_text(encoding='utf-8').strip()
            if not answer:
                raise AgentError('Codex afsluttede uden et agentsvar.')
            return {'agent': self.name, 'version': self.version, 'status': 'success',
                    'task': task, 'response': f'{NOTICE}\n\n{answer}'}


research_agent = ResearchAgent()
