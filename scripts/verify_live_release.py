"""Bounded live acceptance using only invented facts and an isolated SQLite database.
Uses the already configured provider; never copies user documents or changes provider settings.
"""
import os,sys,sqlite3,json,subprocess,time,secrets
from pathlib import Path
from uuid import uuid4
from dotenv import dotenv_values
from cryptography.fernet import Fernet
import httpx
ROOT=Path(__file__).resolve().parents[1]

def main():
    local=dotenv_values(ROOT/'traceform/.env')
    storage=ROOT/'traceform'/local.get('OBJECT_STORAGE_PATH','storage_data')
    c=sqlite3.connect(ROOT/'traceform/traceform.db');c.row_factory=sqlite3.Row
    row=c.execute('select p.* from provider_configurations p join active_provider a on a.configuration_id=p.id where a.id=1').fetchone();c.close()
    if not row or not row['encrypted_key']:raise ValueError('Configure a provider before live acceptance.')
    original_master=local.get('TRACEFORM_MASTER_KEY') or (storage/'.provider-master-key').read_text().strip()
    credential=Fernet(original_master.encode()).decrypt(row['encrypted_key'].encode()).decode()
    folder=ROOT/'.runtime'/('phase8-live-'+uuid4().hex[:10]);folder.mkdir()
    master=Fernet.generate_key().decode();api_key=secrets.token_hex(24)
    env={**os.environ,**{k:v for k,v in local.items() if v is not None},'APP_ENV':'test',
      'DATABASE_URL':'sqlite+aiosqlite:///'+str(folder/'live.db'),'OBJECT_STORAGE_PATH':str(folder/'storage'),
      'API_KEYS':api_key+':release:admin','TRACEFORM_MASTER_KEY':master,'TRACEFORM_AUTO_MIGRATE':'true',
      'GEMINI_API_KEY':credential if row['provider']=='gemini' else '',
      'ANTHROPIC_API_KEY':credential if row['provider']=='anthropic' else '',
      'GEMINI_MODEL':row['model'],'ANTHROPIC_MODEL':row['model']}
    processes=[];streams=[]
    report={'data_mode':'live_provider_synthetic_acceptance','provider':row['provider'],'model':row['model'],
      'budget_ceiling_usd':.15,'isolated_database':True,'passed':False}
    try:
      for name,args in [('api',['-m','uvicorn','api.main:app','--host','127.0.0.1','--port','8009']),('worker',['-m','orchestrator.worker'])]:
        stream=(folder/(name+'.log')).open('w');streams.append(stream)
        processes.append(subprocess.Popen([sys.executable,*args],cwd=ROOT/'traceform',env=env,stdout=stream,stderr=stream,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
        if name=='api':
          for _ in range(50):
            try:
              if httpx.get('http://127.0.0.1:8009/api/v1/healthz',timeout=2,trust_env=False).status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.3)
          else:raise RuntimeError('Isolated API did not start.')
      with httpx.Client(base_url='http://127.0.0.1:8009',headers={'X-API-Key':api_key},timeout=100,trust_env=False) as client:
        source=client.post('/api/v1/sources/',files={'file':('Synthetic_Cedar.txt',b'Cedar Garden is fictional. It has 12 raised beds and 18 volunteers. No budget or purchasing deadline has been approved.','text/plain')},data={'sensitivity':'public'})
        source.raise_for_status();sid=source.json()['id']
        response=client.post('/api/v1/generations/',headers={'Idempotency-Key':str(uuid4())},json={'source_id':sid,'output_types':['executive_summary'],'budget_type':'cost_usd','budget_ceiling':.15,'params':{'tone':'plain and neutral','audience':'garden volunteers','detail_level':'low','objective':'Summarize only the source facts. Label any proposed action as a recommendation.'}})
        report['admission_http_status']=response.status_code
        if response.status_code!=202:
          report['status']='admission_failed';report['message']=response.json().get('detail');return report
        gid=response.json()['id'];report['generation_id']=gid
        deadline=time.monotonic()+300
        while True:
          result=client.get('/api/v1/generations/'+gid);result.raise_for_status();result=result.json()
          if result['status'] not in {'queued','pending','running'}:break
          if time.monotonic()>deadline:
            client.post('/api/v1/generations/'+gid+'/cancel');report['status']='acceptance_deadline';return report
          time.sleep(1)
        report.update(status=result['status'],total_tokens=result['total_tokens'],estimated_cost_usd=result['total_cost_usd'],artifacts=[{'id':a['id'],'review_status':a['review_status'],'assurance_status':a['assurance_status'],'anchors_matched':a['evidence']['anchors_matched'],'anchors_total':a['evidence']['anchors_total']} for a in result['artifacts']])
        report['passed']=result['status']=='completed' and bool(result['artifacts']) and all(a['assurance_status']=='verified' for a in result['artifacts'])
        requests=client.get('/api/v1/operations/requests').json();report['requests']=requests
        return report
    finally:
      for process in processes:
        process.terminate()
      for process in processes:
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill()
      for stream in streams:stream.close()
      (folder/'report.json').write_text(json.dumps(report,indent=2))
      (ROOT/'.runtime/phase8-live-report.json').write_text(json.dumps(report,indent=2))
      print(json.dumps(report,indent=2))

if __name__=='__main__':
    outcome=main();sys.exit(0 if outcome['passed'] else 1)
