# OSCAL Compass + Compliance Trestle: sikker integrationspilot

Denne pilot bruger udelukkende syntetiske kontrolbeskrivelser. Den er **ikke** en fagligt valideret NIS2/ISO-mapping, indeholder ingen standardtekster og giver ikke en ISAE-konklusion.

## Hvad er verificeret

- OSCAL Compass Agentic Agile Authoring `compliance-mapping` forventer to OSCAL-kataloger og producerer en Mapping Collection. Skill bruger lokale embeddings og agent-subtasks til semantisk vurdering, og kalder Trestle til skemavalidering.
- Compliance Trestle tilbyder Python/CLI til OSCAL, herunder `trestle init` og `trestle validate`.
- Denne pilot producerer **3 syntetiske NIS2-kontroller, 10 syntetiske ISO-referencer og en bevidst fejlbehæftet mapping**; kvalitetsmåleren sammenligner den med 10 på forhånd fastsatte testrelationer.
- OSCAL Compass' fulde Skill og Trestles validering er **ikke kørt i CI** med denne ændring. Installer og kontroller versioner særskilt, inden senere end-to-end-test.

Kilder:
- https://github.com/oscal-compass/agentic-agile-authoring/tree/main/skills/compliance-mapping
- https://github.com/oscal-compass/compliance-trestle
- https://oscal-compass.github.io/compliance-trestle/latest/quick-start/

## Lokal test uden AI og uden følsomme data

Fra projektets rod i WSL:

```bash
.venv/bin/python -m unittest backend.tests.test_oscal_pilot -v
.venv/bin/python scripts/oscal_pilot.py --out /tmp/cyberagent-oscal-pilot
```

Resultat på den bevidst fejlbehæftede prøve: TP=9, FP=1, FN=1, precision=0,90, recall=0,90 og F1=0,90. Det er **ikke** en observeret nøjagtighed for en AI-model.

## Validering med Compliance Trestle (separat miljø)

Opret separat miljø uden for repository, efter kontrol af afhængigheder og licenser:

```bash
python3 -m venv /tmp/cyberagent-trestle-venv
/tmp/cyberagent-trestle-venv/bin/pip install compliance-trestle
PATH=/tmp/cyberagent-trestle-venv/bin:$PATH python3 scripts/oscal_pilot.py --out /tmp/cyberagent-oscal-pilot --trestle-validate
```

Trestles faktiske skemavalidering skal verificeres. En JSON-fil med OSCAL-lignende felter er ikke nødvendigvis et skemagyldigt OSCAL-dokument.

## Integration med OSCAL Compass

Brug **kun syntetiske kataloger** fra `/tmp/cyberagent-oscal-pilot/catalogs/`. Test `compliance-mapping` i en separat sandbox med dokumenteret, fastlåst upstream commit og uden private filer. Skill's Stage 4 bruger AI-subagenter, og skal godkendes særskilt; den er **ikke** indeholdt i denne pilot og er ikke automatisk omfattet af backendens eksterne AI-gate. En produceret `mapping_collection.json` kan senere scores via:

```bash
python3 scripts/oscal_pilot.py --out /tmp/cyberagent-oscal-pilot --candidate /tmp/oscal-compass-result/mapping_collection.json
```

## Acceptkriterier for næste fase

1. Trestle skemavaliderer begge kataloger og Mapping Collection uden fejl.
2. Output indeholder ikke ukendte kontrol-ID'er, dubletter eller usporbare relationer.
3. OSCAL Compass-kandidat sammenlignes med et uafhængigt, manuelt og kildebaseret benchmark.
4. Fejlmatch og manglende match kan forklares til en faglig reviewer.
5. Data placeres uden for Git-repository; ingen eksterne AI-kald med fortroligt materiale.
6. Ingen automatisk sammenblanding af NIS2-lovkrav, ISO-kontrolvalg og implementeringsstatus.
