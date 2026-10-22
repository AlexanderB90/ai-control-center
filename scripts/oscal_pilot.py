"""Offline, synthetic OSCAL pilot for Cyberagent; no external AI or documents.

The candidate is deliberately imperfect, to test scoring. It is NOT an
AI-generated mapping and benchmark results are NOT measurements of agent quality.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import NAMESPACE_URL, uuid5

PROJECT = Path(__file__).resolve().parents[1]
STAMP = '2026-10-22T00:00:00Z'
DATA = {
    'nis2': [
        ('nis2-04','Leverandør- og forsyningskædesikkerhed','Syntetisk kontrolmål: styr direkte leverandørrisici og følg op på leverandører.'),
        ('nis2-06','Evaluering af sikkerhedsforanstaltninger','Syntetisk kontrolmål: test om sikkerhedskontroller er effektive.'),
        ('nis2-09','Personalesikkerhed og adgangsstyring','Syntetisk kontrolmål: styr identiteter og autoriserede adgangsrettigheder.'),
    ],
    'iso27002': [
        ('iso-5-19','Supplier relationships','Syntetisk beskrivelse af sikkerhed i leverandørrelationer.'),
        ('iso-5-20','Supplier agreements','Syntetisk beskrivelse af sikkerhedskrav i aftaler.'),
        ('iso-5-21','ICT supply chain','Syntetisk beskrivelse af sikkerhed i IKT-forsyningskæden.'),
        ('iso-5-22','Supplier monitoring','Syntetisk beskrivelse af opfølgning på leverandørers tjenester.'),
        ('iso-5-23','Cloud services','Syntetisk beskrivelse af sikkerhed ved cloudtjenester.'),
        ('iso-5-35','Independent review','Syntetisk beskrivelse af uafhængig evaluering af sikkerhed.'),
        ('iso-5-36','Compliance review','Syntetisk beskrivelse af gennemgang af efterlevelse.'),
        ('iso-5-15','Access control','Syntetisk beskrivelse af adgangskontrol.'),
        ('iso-5-18','Access rights','Syntetisk beskrivelse af håndtering af adgangsrettigheder.'),
        ('iso-8-5','Secure authentication','Syntetisk beskrivelse af sikker autentifikation.'),
    ],
}
# Separate, hand-curated benchmark; NOT a legal mapping or automated result.
GOLD = {
 ('nis2-04','iso-5-19'),('nis2-04','iso-5-20'),('nis2-04','iso-5-21'),
 ('nis2-04','iso-5-22'),('nis2-04','iso-5-23'),('nis2-06','iso-5-35'),
 ('nis2-06','iso-5-36'),('nis2-09','iso-5-15'),('nis2-09','iso-5-18'),
 ('nis2-09','iso-8-5'),
}
# Intentionally contains 1 false positive and misses 1 true relationship.
DEMO = (GOLD - {('nis2-04','iso-5-20')}) | {('nis2-06','iso-5-23')}

def stable_uuid(text):
    return str(uuid5(NAMESPACE_URL, 'cyberagent-synthetic-oscal-pilot/'+text))

def catalog(kind, controls):
    return {'catalog': {
        'uuid': stable_uuid(kind),
        'metadata': {'title': f'SYNTHETIC {kind} control sample',
                     'last-modified': STAMP, 'version': '0.1.0', 'oscal-version': '1.2.1'},
        'controls': [
            {'id': id_, 'title': title,
             'parts': [{'id': id_+'-smt', 'name': 'statement', 'prose': prose}],
             'props': [{'name': 'source-type', 'value': 'synthetic-example'}]}
            for id_,title,prose in controls],
    }}

def mapping(pairs):
    return {'mapping-collection': {
        'uuid': stable_uuid('mapping'),
        'metadata': {'title': 'SYNTHETIC NIS2 to ISO27002 candidate',
                     'last-modified': STAMP, 'version':'0.1.0', 'oscal-version':'1.2.1'},
        'provenance': {'method':'automation', 'matching-rationale':'semantic',
                       'status':'incomplete',
                       'mapping-description':'Synthetic candidate to test quality reporting only.'},
        'mappings':[{
            'uuid':stable_uuid('entry'),
            'source-resource':{'type':'catalog','href':'../../catalogs/nis2/catalog.json',
                               'props':[{'name':'catalog_uuid','value':stable_uuid('nis2'),
                                         'ns':'https://example.org/cyberagent/oscal'}]},
            'target-resource':{'type':'catalog','href':'../../catalogs/iso27002/catalog.json',
                               'props':[{'name':'catalog_uuid','value':stable_uuid('iso27002'),
                                         'ns':'https://example.org/cyberagent/oscal'}]},
            'maps':[{'uuid':stable_uuid(f'{s}--{t}'), 'relationship':'intersects-with',
                      'sources':[{'type':'control','id-ref':s}],
                      'targets':[{'type':'control','id-ref':t}],
                      'confidence-score':{'percentage':0.5},
                      'coverage':{'target-coverage':0.5}}
                      for s,t in sorted(pairs)]
        }]
    }}

def assert_external_folder(folder):
    resolved = folder.resolve()
    if resolved == PROJECT or PROJECT in resolved.parents:
        raise ValueError('Afvist: OSCAL-data skal ligge uden for Git-repository.')

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def generate(out):
    assert_external_folder(out)
    for label, entries in DATA.items():
        write_json(out/'catalogs'/label/'catalog.json',catalog(label,entries))
    write_json(out/'mapping-collections'/'candidate'/'mapping-collection.json',mapping(DEMO))
    write_json(out/'benchmark-gold.json',{'provenance':'synthetic human-curated test fixture, not legal advice',
                                         'pairs':[list(p) for p in sorted(GOLD)]})
    return out/'mapping-collections'/'candidate'/'mapping-collection.json'

def pairs_from_doc(doc):
    collection = doc['mapping-collection']
    pairs = []
    for group in collection['mappings']:
        for record in group['maps']:
            for source in record['sources']:
                for target in record['targets']:
                    pairs.append((source['id-ref'],target['id-ref']))
    if len(pairs) != len(set(pairs)):
        raise ValueError('Duplicate mapped pairs')
    return set(pairs)

def score(path):
    doc = json.loads(path.read_text(encoding='utf-8'))
    predicted = pairs_from_doc(doc)
    known_source = {x[0] for x in DATA['nis2']}
    known_target = {x[0] for x in DATA['iso27002']}
    unknown = [(s,t) for s,t in sorted(predicted) if s not in known_source or t not in known_target]
    if unknown:
        raise ValueError('Mapping references unknown control IDs: '+repr(unknown))
    tp=len(predicted&GOLD)
    precision = tp/len(predicted) if predicted else 0.0
    recall = tp/len(GOLD) if GOLD else 0.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    return {'test_data':'synthetic', 'reference_pairs':len(GOLD),'candidate_pairs':len(predicted),
            'true_positives':tp,'false_positives':len(predicted-GOLD),
            'false_negatives':len(GOLD-predicted),
            'precision':round(precision,4),'recall':round(recall,4),'f1':round(f1,4),
            'extra_pairs':[list(p) for p in sorted(predicted-GOLD)],
            'missing_pairs':[list(p) for p in sorted(GOLD-predicted)]}

def trestle_validate(out):
    """Requires installed compliance-trestle; exits nonzero if missing or invalid."""
    import shutil
    if not shutil.which('trestle'):
        raise RuntimeError('Trestle is not installed; pip install compliance-trestle in a dedicated venv.')
    with tempfile.TemporaryDirectory(prefix='cyberagent-trestle-') as tmp:
        root=Path(tmp)
        subprocess.run(['trestle','init','-tr',str(root)],check=True,timeout=90,
                       capture_output=True,text=True)
        for key, source in [('nis2',out/'catalogs'/'nis2'/'catalog.json'),
                             ('iso27002',out/'catalogs'/'iso27002'/'catalog.json')]:
            target=root/'catalogs'/key/'catalog.json'
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            subprocess.run(['trestle','validate','-tr',str(root),'-f',str(target)],
                           check=True,timeout=90,capture_output=True,text=True)
        target=root/'mapping-collections'/'candidate'/'mapping-collection.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(out/'mapping-collections'/'candidate'/'mapping-collection.json',target)
        subprocess.run(['trestle','validate','-tr',str(root),'-f',str(target)],
                       check=True,timeout=90,capture_output=True,text=True)
    return True

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path,help='External path outside repository')
    parser.add_argument('--trestle-validate',action='store_true')
    parser.add_argument('--candidate',type=Path,help='Optional OSCAL Compass mapping collection to score (no AI calls)')
    args=parser.parse_args(argv)
    try:
        result=generate(args.out)
        metrics=score(args.candidate or result)
        print(json.dumps(metrics,ensure_ascii=False,indent=2))
        if args.trestle_validate:
            trestle_validate(args.out)
            print('Compliance Trestle schema validation passed.')
        return 0
    except (ValueError,OSError,RuntimeError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        print(f'Pilot failed: {exc}',file=sys.stderr)
        return 1
if __name__=='__main__': raise SystemExit(main())
