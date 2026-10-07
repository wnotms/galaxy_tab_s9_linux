import base64,concurrent.futures,datetime,hashlib,json,re,subprocess,time
from pathlib import Path
R=Path('/home/ms/Samsung/galaxy_tab_s9_linux');OUT=Path('/tmp/gts9-test345-api-push-result.json');REPO='repos/wnotms/galaxy_tab_s9_linux'
record={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'device_operations':[],'force':False,'blobs':[],'commits':[],'reference_updated':False}
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
def api(path,method='GET',data=None):
 cmd=['gh','api',REPO+'/'+path,'--method',method]
 raw=None
 if data is not None:cmd+=['--input','-'];raw=json.dumps(data).encode()
 p=subprocess.run(cmd,input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
 if p.returncode:raise RuntimeError('API '+method+' '+path+': '+p.stderr.decode()[-300:])
 return json.loads(p.stdout)
def ref():return api('git/ref/heads/test')['object']['sha']
def identity(raw):
 m=re.fullmatch(rb'(.*?) <([^>]*)> (\d+) ([+-]\d{4})',raw);assert m,'invalid Git identity'
 name,email,epoch,zone=m.groups();z=zone.decode();offset=(int(z[1:3])*60+int(z[3:]))*(1 if z[0]=='+' else -1)
 date=datetime.datetime.fromtimestamp(int(epoch),datetime.timezone(datetime.timedelta(minutes=offset))).isoformat()
 return {'name':name.decode(),'email':email.decode(),'date':date}
def blob(sha):
 raw=git('cat-file','blob',sha);d=api('git/blobs','POST',{'content':base64.b64encode(raw).decode(),'encoding':'base64'})
 if d['sha']!=sha:raise RuntimeError('blob SHA mismatch')
 return {'sha':sha,'bytes':len(raw)}
try:
 if git('status','--porcelain').strip():raise RuntimeError('worktree must be clean')
 old=git('rev-parse','origin/test').decode().strip();head=git('rev-parse','HEAD').decode().strip();record.update(old=old,head=head)
 if ref()!=old:raise RuntimeError('remote ref changed; do not overwrite')
 git('merge-base','--is-ancestor',old,head)
 commits=git('rev-list','--reverse',old+'..'+head).decode().splitlines()
 known={x.split()[0] for x in git('rev-list','--objects',old).decode().splitlines()}
 uploaded=set();parent=old
 for sha in commits:
  raw=git('cat-file','commit',sha);header,message=raw.split(b'\n\n',1);headers={}
  for line in header.splitlines():
   key,value=line.split(b' ',1);headers.setdefault(key,[]).append(value)
  if set(headers)!={b'tree',b'parent',b'author',b'committer'} or headers[b'parent']!=[parent.encode()]:raise RuntimeError('nonlinear/signed/unsupported commit; abort')
  expected_tree=headers[b'tree'][0].decode();base_tree=git('rev-parse',parent+'^{tree}').decode().strip()
  assert api('git/commits/'+parent)['tree']['sha']==base_tree
  diff=git('diff-tree','-r','--no-commit-id','--no-abbrev','--no-renames','--raw','-z',parent,sha).split(b'\0')
  tree=[];needed=set();i=0
  while i<len(diff) and diff[i]:
   meta=diff[i].decode().split();path=diff[i+1].decode();i+=2
   assert len(meta)==5 and meta[0].startswith(':')
   mode,newsha,status=meta[1],meta[3],meta[4]
   if status=='D':tree.append({'path':path,'mode':meta[0][1:],'type':'blob','sha':None});continue
   if mode not in ('100644','100755','120000'):raise RuntimeError('unsupported tree mode')
   tree.append({'path':path,'mode':mode,'type':'blob','sha':newsha})
   if newsha not in known|uploaded:needed.add(newsha)
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
   for result in pool.map(blob,sorted(needed)):
    uploaded.add(result['sha']);record['blobs'].append(result)
  newtree=api('git/trees','POST',{'base_tree':base_tree,'tree':tree})
  if newtree['sha']!=expected_tree:raise RuntimeError('tree SHA mismatch; do not publish')
  payload={'message':message.decode(),'tree':expected_tree,'parents':[parent],'author':identity(headers[b'author'][0]),'committer':identity(headers[b'committer'][0])}
  created=api('git/commits','POST',payload)
  if created['sha']!=sha:raise RuntimeError('commit SHA mismatch; do not publish: '+created['sha'])
  record['commits'].append({'sha':sha,'tree':expected_tree,'parent':parent,'new_blobs':len(needed)})
  print(json.dumps(record['commits'][-1]),flush=True);parent=sha
 if parent!=head or ref()!=old:raise RuntimeError('head/remote changed before update; abort')
 updated=api('git/refs/heads/test','PATCH',{'sha':head,'force':False})
 if updated['object']['sha']!=head or ref()!=head:raise RuntimeError('reference update not confirmed')
 record.update(reference_updated=True,verdict='EXACT_OBJECTS_FAST_FORWARD_PASS')
 subprocess.run(['git','-C',str(R),'fetch','origin','test'],check=True,timeout=25)
 if git('rev-parse','origin/test').decode().strip()!=head:raise RuntimeError('local tracking ref not synchronized')
 print(json.dumps({'verdict':record['verdict'],'head':head,'uploaded_blobs':len(uploaded),'commits':len(commits)}),flush=True)
except Exception as e:
 record.update(verdict='API_FALLBACK_ABORTED',error=repr(e));raise
finally:
 record['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();OUT.write_text(json.dumps(record,indent=2)+'\n')
