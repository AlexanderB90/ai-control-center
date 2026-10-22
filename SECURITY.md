# Cyberagent / AI Control Center – sikkerhedsregler

## Dataadskillelse

Dette GitHub-repository er til **kode, konfigurationseksempler uden credentials og generiske Skills**. Det er **ikke** et dokumentarkiv.

- Ingen personoplysninger fra arbejdet, regionale sagsakter, ikke-offentlige politikker, revisionsarbejdspapirer, ISO-/ISAE-kursusfiler, kundedata, nøgler eller tokens må tilføjes til Git – heller ikke til private branches, PR'er, issues eller logs.
- Alle egentlige dokumenter og output placeres i en lokal vidensbase **uden for** repoets rod og arbejdsmapper. Brug kun kilder, som du lovligt og med den nødvendige organisatoriske godkendelse må behandle.
- Brug syntetiske data i tests og eksempler. Redigér aldrig en ægte hemmelighed ind i en committed fil, heller ikke midlertidigt.
- `.gitignore` er kun en ekstra barriere. Git sporer fortsat filer, som allerede er committed. Kør `git status` og den sikkerhedskontrol, der er beskrevet nedenfor, før push.
- Hvis materiale allerede er offentliggjort: stop deling, tilbagekald berørte adgangsoplysninger, kontakt ansvarlige for sikkerhed/databeskyttelse, og vurder oprydning i Git-historik. Sletning af en fil i et nyt commit sletter ikke dens historie.

## Lokalt dokumentlager

Anbefalet WSL-layout (stien er et **forslag**, ikke en oprettet mappe):

```text
/home/alex/ai-control-center/          # Kun projektkode i Git
/home/alex/cyberagent-vault/           # Lokal viden, uden for Git
  sources/
  evidence/
  assessments/
```

Opret mappen med restriktive rettigheder, opbevar den på et godkendt og krypteret drev, og begræns adgangen. Lav backups efter gældende sikkerhedskrav. Ingen del af dette repository opretter, synkroniserer eller læser automatisk denne mappe.

Hvis arbejdet vedrører Region Nordjyllands **interne** oplysninger, er en privat hjemme-pc ikke automatisk godkendt til behandling. Brug kun regionens godkendte miljø og dataoverførsler.

## Eksterne AI-kald

- **Default-deny:** Backendens eksisterende `/agents/research/run` og `/agents/options/run` afviser eksterne AI-kald, medmindre administrator har sat `AIC_EXTERNAL_AI_ENABLED=1` i backendprocessens miljø.
- **Godkendelse per kald:** Desuden kræves `X-External-AI-Approved: true` for hver AI-kørsel. Dashboardet beder om aktivt samtykke og nulstiller afkrydsningen efter hver kørsel.
- Dette er **en lokal opt-in-mekanisme, ikke organisatorisk tilladelse eller automatisk klassifikation**. Selve kontrollen kan ikke identificere fortrolige oplysninger i indsat tekst, og headeren kan sættes af enhver klient med API-adgang.
- Brug **ikke** fortrolige/organisationsinterne dokumenter, persondata fra arbejdet, adgangsoplysninger eller andet beskyttet indhold med de eksisterende Codex/ChatGPT-kørsler, selv hvis opt-in er aktiveret. Fremtidig behandling af klassificeret materiale kræver separat godkendt arkitektur, databeskyttelsesvurdering, adgangsstyring og tekniske DLP-kontroller.
- Lokale og deterministiske beregninger som `/agents/options/calculate` fungerer uden godkendelse, fordi de ikke anvender den eksterne AI.
- Research Agent har ingen direkte filadgang i sin Codex-kørsel, men **tekst som indtastes i prompten sendes ud**. Historik lagres i lokal SQLite i klartekst, beskyttet alene af hostens filrettigheder.

## Kontrol før commits

Repoet indeholder en begrænset filtype-/tokenkontrol, **ikke** en fuldstændig secrets-scanner:

```bash
python3 scripts/security_scan.py            # kontrollér Git-tracked filer
mkdir -p .git/hooks\ncp .githooks/pre-commit .git/hooks/pre-commit\nchmod +x .git/hooks/pre-commit        # aktiver lokal pre-commit-kontrol
```

GitHub Actions gentager kontrollen på push og PR. Brug også GitHub secret scanning/push protection, hvis tilgængeligt, og en professionel secret-scanner inden indførelse af følsomt udviklingsarbejde. En CI-kontrol kører først **efter** et push og kan derfor ikke alene forhindre eksponering.

**Før aktivering af ekstern AI:** verificér provider, kontrakt, databehandling, logs, tilladelser og at data ikke er fortrolige. Start backend som f.eks. `AIC_EXTERNAL_AI_ENABLED=1 python3 dev.py` **kun efter** denne kontrol. Uden variablen er AI-kald låst.

## Afgrænsning

Disse regler gælder det her repository og dets FastAPI/Next.js-applikation. De konfigurerer **ikke** automatisk Paperclip, separate Codex-kørsler, andre agentprocesser, tilsluttede apps eller din ChatGPT-samtale. Disse integrationer skal kontrolleres særskilt før de får dataadgang.
