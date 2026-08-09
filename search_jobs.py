#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, html, json, re, sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable, Optional
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parent; CONFIG_PATH=ROOT/'config.json'; OUTPUT_DIR=ROOT/'output'; DATA_DIR=ROOT/'data'; SEEN_PATH=DATA_DIR/'seen_jobs.json'
UA='job-search-agent/1.0 (personal job search)'; TIMEOUT=25
@dataclass
class Job:
    source:str; title:str; company:str; location:str; remote:bool; url:str; description:str=''; published_at:str=''; score:int=0; verdict:str=''; reasons:str=''; first_seen:str=''
def clean_html(value):
    if not value:return ''
    return re.sub(r'\s+',' ',BeautifulSoup(html.unescape(value),'html.parser').get_text(' ',strip=True)).strip()
def norm(value): return re.sub(r'\s+',' ',(value or '').lower()).strip()
def stable_id(job): return hashlib.sha256(f'{norm(job.company)}|{norm(job.title)}|{job.url}'.encode()).hexdigest()[:20]
def parse_date(value):
    if not value:return None
    value=value.strip().replace('Z','+00:00')
    try:
        dt=datetime.fromisoformat(value); return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except ValueError:return None
def fetch_arbeitnow(max_pages=3):
    jobs=[]
    for page in range(1,max_pages+1):
        r=requests.get('https://www.arbeitnow.com/api/job-board-api',params={'page':page},timeout=TIMEOUT,headers={'User-Agent':UA}); r.raise_for_status(); rows=r.json().get('data',[])
        if not rows:break
        for x in rows: jobs.append(Job('Arbeitnow',x.get('title',''),x.get('company_name',''),x.get('location',''),bool(x.get('remote',False)),x.get('url',''),clean_html(x.get('description','')),x.get('created_at','') or ''))
    return jobs
def fetch_remotive():
    r=requests.get('https://remotive.com/api/remote-jobs',timeout=TIMEOUT,headers={'User-Agent':UA}); r.raise_for_status(); jobs=[]
    for x in r.json().get('jobs',[]): jobs.append(Job('Remotive',x.get('title',''),x.get('company_name',''),x.get('candidate_required_location','') or 'Remote',True,x.get('url',''),clean_html(x.get('description','')),x.get('publication_date','') or ''))
    return jobs
def contains_any(text,terms):
    t=norm(text); return [term for term in terms if norm(term) in t]
def evaluate(job,cfg):
    s=cfg['search']; title=norm(job.title); full=norm(' '.join([job.title,job.location,job.description])); score=0; reasons=[]
    title_hits=contains_any(job.title,s['title_keywords']); pos=contains_any(full,s['strong_positive_keywords']); neg=contains_any(full,s['negative_keywords']); coding=contains_any(full,s['coding_core_keywords'])
    if title_hits: score+=35+min(15,5*(len(title_hits)-1)); reasons.append('target title')
    elif any(k in title for k in ['manager','director','lead','head']): score+=10; reasons.append('management title')
    else: score-=25; reasons.append('weak title match')
    if pos: score+=min(35,5*len(pos)); reasons.append('profile keywords: '+', '.join(pos[:5]))
    if neg: score-=45; reasons.append('language risk: '+', '.join(neg[:3]))
    if coding: score-=60; reasons.append('hands-on coding risk: '+', '.join(coding[:3]))
    loc=norm(job.location+' '+job.description[:1200])
    if job.remote:
        if contains_any(loc,s['remote_location_keywords']): score+=10; reasons.append('remote geography plausible')
        elif any(x in loc for x in ['us only','usa only','canada only','latin america','apac only']): score-=50; reasons.append('remote geography likely incompatible')
        else: reasons.append('remote geography needs verification')
    elif contains_any(loc,s['onsite_location_keywords']): score+=20; reasons.append('Prague onsite/hybrid')
    else: score-=35; reasons.append('non-Prague onsite/hybrid')
    dt=parse_date(job.published_at)
    if dt:
        age=datetime.now(timezone.utc)-dt
        if age>timedelta(days=s['max_age_days']): score-=30; reasons.append('older posting')
        elif age<=timedelta(days=7): score+=10; reasons.append('recent')
    if job.description and sum(ch.isascii() for ch in job.description[:1500])/max(1,len(job.description[:1500]))>.92: score+=5; reasons.append('English-description heuristic')
    job.score=score; job.verdict='REVIEW' if (coding or neg) and score>=s['minimum_score'] else ('STRONG' if score>=70 else ('MATCH' if score>=s['minimum_score'] else 'LOW')); job.reasons='; '.join(reasons); return job
def load_seen():
    try:return json.loads(SEEN_PATH.read_text(encoding='utf-8')) if SEEN_PATH.exists() else {}
    except Exception:return {}
def save_seen(seen): DATA_DIR.mkdir(exist_ok=True); SEEN_PATH.write_text(json.dumps(seen,indent=2,ensure_ascii=False),encoding='utf-8')
def write_outputs(jobs,cfg):
    OUTPUT_DIR.mkdir(exist_ok=True); fields=list(Job.__dataclass_fields__.keys())
    with (OUTPUT_DIR/'jobs.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); [w.writerow(asdict(j)) for j in jobs]
    with (OUTPUT_DIR/'jobs.md').open('w',encoding='utf-8') as f:
        f.write('# IT PM Job Search Results\n\nGenerated: '+datetime.now(timezone.utc).isoformat()+'\n\n| Score | Verdict | Role | Company | Location | Source |\n|---:|---|---|---|---|---|\n')
        for j in jobs[:cfg['output']['top_n']]: f.write(f'| {j.score} | {j.verdict} | [{j.title.replace("|","/")}]({j.url}) | {j.company.replace("|","/")} | {j.location.replace("|","/")} | {j.source} |\n')
def main():
    cfg=json.loads(CONFIG_PATH.read_text(encoding='utf-8')); all_jobs=[]
    try:
        if cfg['sources']['arbeitnow']['enabled']: all_jobs+=fetch_arbeitnow(cfg['sources']['arbeitnow'].get('max_pages',3))
    except Exception as e: print(f'[WARN] Arbeitnow failed: {e}',file=sys.stderr)
    try:
        if cfg['sources']['remotive']['enabled']: all_jobs+=fetch_remotive()
    except Exception as e: print(f'[WARN] Remotive failed: {e}',file=sys.stderr)
    unique={stable_id(j):j for j in all_jobs}; seen=load_seen(); now=datetime.now(timezone.utc).isoformat(); matched=[]
    for jid,j in unique.items():
        if jid not in seen: seen[jid]={'first_seen':now,'url':j.url,'title':j.title,'company':j.company}
        j.first_seen=seen[jid]['first_seen']; evaluate(j,cfg)
        if j.score>=cfg['search']['minimum_score']: matched.append(j)
    matched.sort(key=lambda j:(j.score,j.published_at),reverse=True); matched=matched[:cfg['output']['top_n']]; save_seen(seen); write_outputs(matched,cfg); print(f'Fetched {len(all_jobs)} jobs; {len(unique)} unique; {len(matched)} matched.')
    for j in matched[:10]: print(f'{j.score:>3} {j.verdict:<6} {j.title} — {j.company} — {j.location}')
    return 0
if __name__=='__main__': raise SystemExit(main())
