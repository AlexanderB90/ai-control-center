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

Early development - v0.4

## Start med én kommando (Ubuntu/WSL)

Stop først eventuelle manuelt startede backend- og frontendservere med Ctrl+C
i deres respektive terminaler. Start derefter fra projektmappen:

```bash
cd /home/alex/ai-control-center
python3 dev.py
```

Begge servere starter i samme terminal og lytter kun på 127.0.0.1.
Vent på Uvicorns opstart og Next.js' Ready-melding, og åbn
http://localhost:3000. Lad terminalen være åben; Ctrl+C stopper begge.
Hvis én server afslutter, stopper startfilen også den anden.
Startfilen ændrer ikke agenten, login eller historikdatabasen.

Kræver den eksisterende .venv med backendpakker, frontend/node_modules,
Node.js, npm og Codex i Ubuntu-terminalens PATH. Startfilen installerer
ikke pakker og kontrollerer ikke Codex-login. Ved manglende miljø kan det
oprettes fra projektmappen med python3 -m venv .venv, hvorefter backendpakker
installeres med .venv/bin/python -m pip install -r backend/requirements.txt.
Frontendpakker installeres med npm ci i frontend-mappen.

Kontrollér kun opsætning og ledige porte, uden at starte serverne:

```bash
python3 dev.py --check
```

Hvis port 3000 eller 8000 er optaget, afslutter startfilen med en dansk
besked. Den stopper ikke andre processer og vælger ikke en anden port.
Loglinjer fra begge servere vises i terminalen.
Dette er lokal udviklingsstart, ikke en permanent serverinstallation.
Afslut helst en igangværende agentopgave, før du stopper serverne.

Manuel kontrol af startfilen:
1. Med de gamle servere kørende: --check skal afvise de optagede porte.
2. Stop dem, kør --check igen, og start med python3 dev.py.
3. Kontrollér dashboard, /health og at eksisterende historik kan åbnes.
4. Tryk Ctrl+C, og kør --check igen: begge porte skal være ledige.

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

## Options Agent — platform v0.4

Options Agent v0.1 beregner covered calls og cash-secured puts med manuelt
indtastede oplysninger. Ingen Saxo-forbindelse eller ordreafgivelse.
Kun ujusterede, fysisk leverede aktieoptioner understøttes; ingen indeksoptioner,
spreads eller 0DTE. Alle beløb skal være i samme valuta.

Dashboardet har to handlinger:
- **Beregn**: deterministiske Decimal-beregninger i Python, uden AI eller lagring.
- **Beregn + AI-vurdering**: samme beregninger plus en dansk vurdering via det
  eksisterende Codex/ChatGPT-login. Handelsoplysninger og beregninger sendes til
  AI-modellen. Input, beregninger og svar gemmes lokalt i klartekst i den eksisterende
  Git-udelukkede SQLite-database. Research- og optionshistorik vises hver for sig.

AI-vurderingen tager højde for målet (præmieindtægt, beholde, sælge eller købe
aktier), men verificerer ikke de indtastede data. Kurser, nyheder, regnskab,
ex-udbytte, likviditet, spread, IV og Greeks hentes ikke. Brugeren træffer beslutningen.
Begge agenter bruger samme proceslås, timeout og begrænsede runner.
Ved AI-fejl bevares beregningen; ved lagringsfejl vises en særskilt advarsel.
Ingen automatisk gentagelse af AI-kald.

### Input og beregninger

Præmien indtastes **pr. aktie**, ikke pr. kontrakt. Kontraktstørrelsen skal
kontrolleres. Gebyrer er et fast samlet skøn for hele handlen, inklusive eventuel
tildeling. Kurstidspunkt og datakilde gemmes med vurderingen; data over 24 timer
gamle markeres. Fiktive eksempeldata skal vælges eksplicit.

Lad N = kontrakter × aktier pr. kontrakt og P = præmie × N − samlede gebyrer.
Ved udløbskurs S og strike K:
- Covered call, resultat fra dagens kurs S0:
  (S − S0) × N + P − max(S − K, 0) × N.
- Cash-secured put: P − max(K − S, 0) × N.
- Covered call viser også resultat fra den oplyste købspris samt aktier uden call.
- Break-even vises kun, hvis den kan nås på payoff-kurven.
- Fra beregningsversion 0.1.1 afrundes scenariekurser til to decimaler før
  resultatberegning, så resultatet svarer til den viste kurs. Break-even er
  fortsat afrundet og kan derfor give et lille plus/minus ved den viste kurs.
  Eksisterende historik er uændrede snapshots; rettelsen gælder nye beregninger.
- Cash-secured puts kræver frie kontanter på mindst K × N + gebyrer;
  den forventede præmie tælles ikke som forhåndsdækning.
- Kun de kontraktdækkede aktier medregnes. Maksimalt tab inkluderer kursfald til nul.
- Nettopræmieprocent er ikke forventet samlet afkast og annualiseres ikke.
- Skat, valutaændringer, udbytte, renter og tidligere præmier er udeladt.
  Førtidig tildeling og faktisk udførelsespris kan ændre forløbet.

Fiktiv kontrol: 100 aktier, kurs 100, købspris 95, call-strike 105,
præmie 2 pr. aktie og gebyrer 5 giver nettopræmie 195.
Bedste udløbsresultat fra dagens kurs er 695; fra købsprisen 1.195.
Break-even fra dagens kurs er 98,05, og maksimalt tab er 9.805.

Strategigrundlag: [OIC covered call](https://www.optionseducation.org/strategies/all-strategies/covered-call-buy-write)
og [OIC cash-secured put](https://www.optionseducation.org/strategies/all-strategies/cash-secured-put).

### Endpoints og kontrol

- POST /agents/options/calculate — beregning uden AI.
- POST /agents/options/run — beregning, vurdering og historik.
- GET /agents/options/history — seneste 50 vurderinger.
- GET /agents/options/history/{id} — gemt input, beregning og svar.

Kør fra projektets rod i Linux/WSL:

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
cd frontend
npm run lint
npx tsc --noEmit
```

Options-tests bruger midlertidige databaser og en simuleret AI. De kontrollerer
payoffs, dækning, enheder, ugyldige input, fejlhåndtering og adskilt historik.
De nye tests samt lint/TypeScript skal køres lokalt før sammenfletning.

Manuel kontrol: Indlæs det fiktive eksempel, kontrollér kontraktbekræftelsen og
tryk Beregn. Kontrollér tallene ovenfor. Prøv derefter AI-vurdering, genindlæs
siden og genåbn vurderingen fra optionshistorikken. En gemt vurdering kan åbnes
under en ny kørsel uden at ændre den aktive opgave.

## Valgfri websøgning i Options Agent v0.2

Vælg **Brug websøgning ved AI-vurdering**, og tryk **Beregn + AI-vurdering**.
Standardvalget er fortsat uden web. Beregn-knappen foretager ingen søgning.
Research Agent er fortsat uden web.

Webtilvalget bruger Codex med live-søgning, Code Mode og den medfølgende
code-mode-host. Konfigurationen er afprøvet i en lokal søgetest med Codex
0.162.1 på Ubuntu/WSL. Code Mode og standalone search er eksperimentelle.
Hjælpeprogrammets mappe findes ved at følge codex-binærens symlink.
Shell-, app-, plugin-, browser- og fleragentværktøjer er stadig deaktiveret;
read-only sandbox, fælles lås, 120 sekunders timeout og ingen provider-retries
bevares. Code Mode udvider værktøjsmiljøet i webtilvalget.

AI'en instrueres i at undersøge officielle selskabskilder og begivenheder
frem mod udløb, give URL'er og skelne mellem bekræftede oplysninger og estimater.
Den instrueres i kun at bruge selskab/ticker og relevante datoer i søgninger,
ikke private beholdnings- eller kontantbeløb. AI-modellen modtager fortsat
hele analysens input som ved den eksisterende vurdering.

Backend kræver mindst én afsluttet web_search-hændelse fra CLI'en.
Et svar eller en URL i modelteksten alene er ikke nok.
Ved manglende søgehændelser eller en fatal kørselsfejl vises beregningen
med advarsel, uden at et almindeligt AI-svar præsenteres som webresearch.
En afsluttet søgehændelse garanterer ikke, at alle påstande er korrekte.

Strukturerede kilde-URL'er fra søgeværktøjet vises som links, når CLI'en
leverer dem. Listen er søgeresultater og ikke nødvendigvis de kilder,
AI'en faktisk citerer. Hvis listen mangler, vises en advarsel og kilderne
må kontrolleres i svaret. Rå CLI-logs gemmes eller vises ikke.
Søgestatus, tidspunkt og kildeoversigt gemmes sammen med vurderingen.

Websøgning leverer ikke et verificeret markedsdatafeed og ændrer ikke
handelsinput eller beregnede beløb. pandas/yfinance og Saxo-integration
er ikke tilføjet. Gamle historikposter er uændrede.

Lokal kontrol efter opdatering:
1. Kør backendtests, frontend lint og TypeScript som ovenfor.
2. Start python3 dev.py, vælg webtilvalget og gennemfør en optionsvurdering.
3. Kontrollér webstatus, kilder og uændrede beregnede beløb.
4. Genindlæs og åbn historikken; webstatus og kilder skal være bevaret.
5. Fravælg web og kontrollér, at den almindelige vurdering stadig virker.

## Chatbaseret arbejdsrum

Forsiden bruger nu samtaler frem for agentkort og beregnerformularer.
Vælg Assistent, Research Agent eller Options Agent, skriv frit, og følg op
i samme samtale. Forslag på startsiden udfylder skrivefeltet, men sender ikke.
Enter sender; Shift+Enter giver ny linje. Menuen kan åbnes på mobil.
Websøgning er et eksplicit tilvalg for den næste besked.

POST /chat/run modtager agent, web_research og messages med user/assistant-roller.
Kun 1–20 beskeder med højst 10.000 tegn hver og samlet 40.000 tegn accepteres.
Frontend sender højst de seneste 19 beskeder inden for denne grænse.
Rollefølgen valideres, og systembeskeder fra klienten accepteres ikke.
Chat bruger den eksisterende begrænsede Codex-runner og fælles kørselslås.
Ingen automatisk genkørsel ved fejl; teksten gendannes i skrivefeltet.

Optionschatten er fri samtale og kalder ikke beregningsmotoren.
Den instrueres i ikke at præsentere modelberegninger som Python-verificerede.
Der er ingen automatisk delegation, stemmefunktion eller adgang til øvrige samtaler.
De eksisterende beregningsendpoints og tests er bevaret.

Samtaler gemmes i klartekst i browserens localStorage, nøgle
ai-control-center.chats.v1, højst 50 samtaler og de seneste 40 beskeder pr. samtale.
Lagringen er knyttet til browserprofil og origin (localhost og 127.0.0.1 er forskellige).
Det er ikke serverbaseret synkronisering eller en permanent vidensbase.
Fejl ved lagring giver en advarsel. Ufuldstændige svarforløb gemmes ikke som
afsluttede samtalebeskeder. Chattekst og det valgte samtaleudsnit sendes til
AI-modellen via Codex. Slet samtale fjerner kun den pågældende browserhistorik.

Tidligere analyser i SQLite kan åbnes fra sidepanelet. De ændres ikke.
Gamle optionsberegninger findes under Vis gemte beregningsdata i arkivet.
Chatten læser ikke automatisk arkivet som kontekst.

Kontrollér med backendtests, frontend lint og TypeScript. Manuel kontrol:
start en optionschat uden formular, stil et opfølgende spørgsmål, genindlæs,
og genåbn samtalen. Skift agent og opret en separat samtale. Prøv webtilvalget
og gamle analyser. Kontrollér mobilmenu og at fejl gendanner brugerens tekst.
