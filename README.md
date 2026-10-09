# AI Control Center

Private self-hosted AI agent platform.

## Vision

AI Control Center is a modular platform for running and managing specialized AI agents from a central dashboard.

## Planned modules

- AI agent orchestration
- Research agents
- Financial market analysis
- Stock and options analysis
- Portfolio and risk analysis
- Trading journal
- Knowledge management
- Local and cloud AI models
- Secure remote access

## Status

Early development - v0.3

## Opgavehistorik i v0.3

Gennemførte Research Agent-opgaver gemmes automatisk med UUID, UTC-tidspunkt,
agentnavn og runner-version i `backend/data/history.sqlite3`. Stien er relativ
til backendens placering og afhænger ikke af terminalens arbejdsmappe.
Database og tabel oprettes ved første brug. Opgaver og fulde svar gemmes lokalt
i **klartekst**. Databasefolderen er ignoreret i Git og følger ikke med til GitHub.

Dashboardets historik under agentkortene viser de seneste 50 opgaver, nyeste
først. Åbn en gemt opgave for at se fuld opgave og svar uden at ændre den
aktive opgave. Historikken hentes ved åbning og efter et vellykket AI-kald.
Hvis lagring fejler, vises agentsvaret stadig med en særskilt advarsel;
AI-kaldet genkøres aldrig automatisk.

`POST /agents/research/run` bevarer svarfelterne og tilføjer kun
`history_warning`, hvis lagring fejler. `GET /agents/research/history` returnerer
metadata og opgaveuddrag (højst 160 tegn), og
`GET /agents/research/history/{id}` returnerer fuld opgave og svar.
Ukendte IDer giver 404; databasefejl ved læsning giver 503 med en fast dansk besked.
Platformversionen er 0.3.0; Research Agent er fortsat 0.2.0, da runneren er uændret.

## Research Agent v0.2 (lokal)

Bruger `codex exec` med eksisterende ChatGPT-login, uden API-nøgle.
Kræver Codex CLI 0.160.0 i backendens PATH. Agenten svarer på dansk og
henter ikke aktuelle oplysninger fra internettet.

Kørsler bruger en tom midlertidig arbejdsmappe, read-only sandbox,
deaktiverede shell-, browser-, app-, plugin- og agentværktøjer og ingen
bruger-konfiguration eller projektinstruktioner. Codex håndterer selv login;
applikationen læser hverken loginfiler eller `.env`. Kun udvalgte miljøvariabler
videresendes. Websøgning og provider-retries er slået fra.
Feature-flags er kontrolleret med `codex exec --help` og `codex features list`.
Konfiguration: https://developers.openai.com/codex/config-reference

Der tillades én kørsel ad gangen via en lokal fillås. Ekstra kald får HTTP 409.
Timeout er 120 sekunder; hele procesgruppen stoppes og processen høstes.
Kun sidste agentsvar vises, aldrig CLI-logs. Input er POST JSON med `task`
(1–10.000 tegn); blanke opgaver og ekstra felter afvises.

Start fra to terminaler (kun loopback):

```bash
cd /home/alex/ai-control-center
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```bash
cd /home/alex/ai-control-center/frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Åbn http://localhost:3000. Ved loginfejl: kør `codex login` i en terminal
som samme bruger som backend, og vælg ChatGPT-login.

Tests bruger midlertidige databaser og en simuleret eller mocket Codex-proces
uden rigtige AI-kald og uden at skrive i brugerens historik:

```bash
cd /home/alex/ai-control-center
.venv/bin/python -m unittest discover -s backend/tests -v
cd frontend
npm run lint
npx tsc --noEmit
```

Codex 0.160.0 afviser overrides af det reserverede provider-ID `openai`.
Backend bruger derfor en særskilt Responses-provider `research_chatgpt` med
OpenAI-login påkrævet, ChatGPT-login tvunget og begge retry-grænser sat til nul.
Ubegrænsede forbindelses-retries er også slået fra. Fejl logges lokalt med
exitkode og faste danske fejlbeskrivelser; rå stdout/stderr, opgaver og
credentials logges aldrig. Slutsvaret læses kun fra `--output-last-message`.
