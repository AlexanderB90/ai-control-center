"""Synthetic 10-area NIS2 / ISO 27002 OSCAL Compass embedding retrieval benchmark.
Scores assess candidate retrieval, NOT AI judge quality, legal mapping or compliance.
Descriptions are authored test summaries, never copyrighted ISO text.
"""
import argparse
import json
from pathlib import Path
import sys
from oscal_pilot import catalog, assert_external_folder, write_json
AREAS=json.loads(r'''[["nis2-01","Risk management and information security policies","Policies on security risk analysis, risk treatment, management responsibilities and regulatory requirements"],["nis2-02","Incident handling","Preparation detection response incident reporting, investigation evidence and lessons learned"],["nis2-03","Business continuity and crisis management","Business continuity backup restoration disaster recovery and ICT resilience during disruptive incidents"],["nis2-04","Supply chain security","Security in direct supplier relationships, third-party contracts, ICT supply chains and cloud services"],["nis2-05","Security acquisition development maintenance","Secure procurement software development, technical vulnerabilities, configuration and change management"],["nis2-06","Assess effectiveness of security risk management","Audit compliance review independent testing and monitoring effectiveness of security controls"],["nis2-07","Cyber hygiene and cybersecurity training","Workforce security awareness education malware protection secure devices and vulnerability remediation"],["nis2-08","Cryptography and encryption","Policies and procedures for use of encryption cryptographic controls and key management"],["nis2-09","Human resources access control and asset management","Personnel screening and offboarding, identities, permissions and information asset inventory"],["nis2-10","MFA and secure communications","Secure authentication with multiple factors, secure communication channels and emergency voice video text messaging"]]''')
ISO=json.loads(r'''[["5.1","Information security policies"],["5.2","Information security roles and responsibilities"],["5.7","Threat intelligence"],["5.8","Information security in project management"],["5.9","Inventory of information and other assets"],["5.14","Information transfer"],["5.15","Access control"],["5.16","Identity management"],["5.17","Authentication information"],["5.18","Access rights"],["5.19","Supplier relationships"],["5.20","Supplier agreements"],["5.21","ICT supply chain security"],["5.22","Monitoring supplier services"],["5.23","Security in cloud services"],["5.24","Incident management planning"],["5.25","Assessment of security events"],["5.26","Incident response"],["5.27","Learning from incidents"],["5.28","Collection of evidence"],["5.29","Security during disruption"],["5.30","ICT readiness for business continuity"],["5.31","Legal and regulatory requirements"],["5.35","Independent information security review"],["5.36","Compliance with security policies and standards"],["6.1","Personnel screening"],["6.3","Security awareness education training"],["6.5","Responsibilities after role change or termination"],["6.8","Reporting security events"],["8.1","User endpoint device security"],["8.2","Privileged access rights"],["8.3","Information access restriction"],["8.5","Secure authentication"],["8.7","Malware protection"],["8.8","Management of technical vulnerabilities"],["8.9","Configuration management"],["8.13","Information backup"],["8.14","System redundancy"],["8.15","Logging"],["8.16","Monitoring activities"],["8.20","Network security"],["8.21","Network services security"],["8.22","Network segregation"],["8.24","Use of cryptography"],["8.25","Secure development lifecycle"],["8.26","Application security requirements"],["8.27","Secure system architecture"],["8.28","Secure coding"],["8.29","Security testing"],["8.30","Outsourced development"],["8.31","Separation of environments"],["8.32","Change management"]]''')
GOLD=json.loads(r'''{"nis2-01":["5.1","5.2","5.7","5.9","5.31"],"nis2-02":["5.24","5.25","5.26","5.27","5.28","6.8","8.15","8.16"],"nis2-03":["5.29","5.30","8.13","8.14"],"nis2-04":["5.19","5.20","5.21","5.22","5.23"],"nis2-05":["5.8","8.8","8.9","8.25","8.26","8.27","8.28","8.29","8.30","8.31","8.32"],"nis2-06":["5.35","5.36","8.16","8.29"],"nis2-07":["6.3","8.1","8.7","8.8","8.9"],"nis2-08":["5.14","8.24"],"nis2-09":["5.9","5.15","5.16","5.17","5.18","6.1","6.5","8.2","8.3"],"nis2-10":["5.14","8.5","8.20","8.21","5.29","5.30"]}''')

def iso_id(number):
    return "iso-"+number.replace(".","-")

def generate(out):
    assert_external_folder(out)
    source=[(iso_id(number), name, "Control concerning "+name.lower()+".") for number,name in ISO]
    write_json(out/"catalogs"/"iso-expanded"/"catalog.json", catalog("iso-expanded",source))
    write_json(out/"catalogs"/"nis2-ten"/"catalog.json",catalog("nis2-ten",AREAS))
    write_json(out/"provisional-reference.json",{"note":"Reviewer-created test rubric, not an authoritative control mapping",
        "pairs":[[iso_id(number),area] for area,numbers in GOLD.items() for number in numbers]})
    return out

def score(candidate_file):
    data=json.loads(candidate_file.read_text(encoding="utf-8"))
    by_area={}
    known={iso_id(row[0]) for row in ISO}
    for group in data["pairs"]:
        area=group["target_id"]
        if area in by_area or area not in GOLD: raise ValueError("Duplicate or unexpected NIS2 target: "+area)
        hits=[x["source_id"] for x in group["candidates"]]
        if len(hits)!=len(set(hits)) or not set(hits)<=known: raise ValueError("Unknown or duplicate ISO IDs")
        by_area[area]=hits
    if set(by_area)!=set(GOLD): raise ValueError("NIS2 target coverage incomplete")
    reference={(iso_id(i),area) for area,ids in GOLD.items() for i in ids}
    scores={}
    for k in (3,5,10):
        predicted={(source,area) for area,ids in by_area.items() for source in ids[:k]}
        tp=len(predicted & reference)
        precision=tp/len(predicted) if predicted else 0
        recall=tp/len(reference) if reference else 0
        f1=2*precision*recall/(precision+recall) if precision+recall else 0
        scores[str(k)]={"hits":tp,"extra":len(predicted-reference),"missed":len(reference-predicted),
             "precision":round(precision,4),"recall":round(recall,4),"f1":round(f1,4)}
    return {"benchmark":"SYNTHETIC; provisional human-selected reference, not independently reviewed",
         "stage":"OSCAL Compass Stage 3 embedding candidate retrieval (NO LLM JUDGE)",
         "areas":len(AREAS),"iso_controls":len(ISO),"reference_pairs":len(reference),
         "model":"all-MiniLM-L6-v2","ann_backend":data.get("ann_backend"),"scores":scores,
         "per_area":{area:{"reference_count":len(GOLD[area]),
            "top5_hits":sum((source,area) in reference for source in hits[:5]),
            "top5_candidates":hits[:5],
            "not_found_in_top10":[iso_id(i) for i in GOLD[area] if iso_id(i) not in hits[:10]]}
             for area,hits in sorted(by_area.items())}}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",required=True,type=Path)
    parser.add_argument("--candidates",type=Path)
    args=parser.parse_args()
    try:
        generate(args.out)
        if args.candidates:
            metrics=score(args.candidates)
            write_json(args.out/"benchmark-results.json",metrics)
            print(json.dumps(metrics,indent=2,ensure_ascii=False))
        else:
            print("Catalogs generated; supply --candidates for real Compass retrieval score.")
        return 0
    except (OSError,ValueError,KeyError) as error:
        print("Benchmark failed: "+str(error),file=sys.stderr)
        return 1
if __name__=="__main__": raise SystemExit(main())
