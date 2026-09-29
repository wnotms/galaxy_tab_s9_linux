from pathlib import Path
import subprocess,time,json,hashlib,tarfile,urllib.request,urllib.parse,gzip
A=Path('reference/boot-tests/test-254-debian-container-kernel/attempt-03/host-images');A.mkdir(exist_ok=True)
out=Path('out/test254-oci-images');out.mkdir(exist_ok=True)
images=['hello-world:latest','debian:trixie-slim','nginx:alpine','alpine:latest']
for image in images:
    name=image.replace(':','-');argv=['docker','pull','--platform','linux/arm64',image];start=time.monotonic()
    with (A/(name+'-pull.log')).open('wb') as f:
        result=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,timeout=180)
    (A/(name+'-pull.json')).write_text(json.dumps(dict(argv=argv,exit_status=result.returncode,elapsed_seconds=time.monotonic()-start),indent=2)+'\n');assert result.returncode==0,image
    path=out/(name+'.tar');argv=['docker','image','save','--platform','linux/arm64','-o',str(path),image]
    result=subprocess.run(argv,capture_output=True,timeout=90);assert result.returncode==0,result.stderr
    with tarfile.open(path) as t:
        manifests=json.load(t.extractfile('manifest.json'));assert len(manifests)==1
        cfg=json.load(t.extractfile(manifests[0]['Config']));assert cfg['architecture']=='arm64' and cfg['os']=='linux'
        content=t.extractfile(manifests[0]['Config']).read();image_id='sha256:'+hashlib.sha256(content).hexdigest()
        assert set(manifests[0]['RepoTags'])=={image},manifests
    inspect=json.loads(subprocess.check_output(['docker','image','inspect','--platform','linux/arm64',image]))[0]
    repo='library/'+image.split(':')[0]
    digest=inspect['RepoDigests'][0].rsplit('@',1)[1]
    token_url='https://auth.docker.io/token?'+urllib.parse.urlencode(dict(service='registry.docker.io',scope='repository:'+repo+':pull'))
    token=json.load(urllib.request.urlopen(token_url,timeout=20))['token']
    def manifest(digest):
        request=urllib.request.Request('https://registry-1.docker.io/v2/'+repo+'/manifests/'+digest,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'})
        response=urllib.request.urlopen(request,timeout=25);raw=response.read();assert 'sha256:'+hashlib.sha256(raw).hexdigest()==digest;return raw
    index_raw=manifest(digest);index=json.loads(index_raw);(A/(name+'-registry-index.json')).write_bytes(index_raw)
    arm=[x for x in index['manifests'] if x.get('platform',{}).get('os')=='linux' and x.get('platform',{}).get('architecture')=='arm64'];assert len(arm)==1
    platform_digest=arm[0]['digest'];platform_raw=manifest(platform_digest);platform=json.loads(platform_raw);(A/(name+'-registry-arm64-manifest.json')).write_bytes(platform_raw)
    assert platform['config']['digest']==image_id,(platform['config']['digest'],image_id)
    with tarfile.open(path) as t:
        for layer,diffid in zip(manifests[0]['Layers'],cfg['rootfs']['diff_ids'],strict=True):
            stream=t.extractfile(layer);magic=stream.read(2);stream.seek(0);content=gzip.GzipFile(fileobj=stream) if magic==b'\x1f\x8b' else stream
            hashed=hashlib.sha256()
            while chunk:=content.read(1024*1024):hashed.update(chunk)
            assert 'sha256:'+hashed.hexdigest()==diffid,layer
    (A/(name+'-metadata.json')).write_text(json.dumps(dict(image=image,platform='linux/arm64',image_id=image_id,host_engine_image_id=inspect['Id'],arm64_manifest_digest=platform_digest,config_digest_verified_against_official_registry=True,all_diff_ids_verified=True,repo_digests=inspect['RepoDigests'],archive=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),save_argv=argv,source='docker.io/library official image; host pull then platform-specific save',device_pull_proven=False),indent=2)+'\n')
    print('HOST IMAGE VERIFIED',image,image_id,flush=True)
