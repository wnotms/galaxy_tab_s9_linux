import socketserver,http.server,threading,subprocess,json,tempfile,os
requests=[]
with tempfile.TemporaryDirectory(prefix='test254-api-probe-',dir='/tmp') as d:
    path=d+'/docker.sock'
    class Server(socketserver.UnixStreamServer):allow_reuse_address=True
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_HEAD(self):self.do_GET()
        def do_GET(self):
            body=b'OK' if self.path.endswith('_ping') else json.dumps(dict(ApiVersion='1.45',Version='26.1.5',Os='linux',Arch='arm64')).encode()
            self.send_response(200);self.send_header('API-Version','1.45');self.send_header('Docker-Experimental','false');self.send_header('OSType','linux');self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers()
            if self.command!='HEAD':self.wfile.write(body)
        def do_POST(self):
            data=self.rfile.read(int(self.headers.get('Content-Length','0')));requests.append(dict(path=self.path,body=json.loads(data)))
            body=json.dumps(dict(Id='0'*64,Warnings=[])).encode();self.send_response(201);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=Server(path,Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    cmd=['docker','-H','unix://'+path,'create','--pull=never','--device-read-bps','/dev/mmcblk1:1mb','--device-write-bps','/dev/mmcblk1:1mb','debian:trixie-slim','true']
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=10);server.shutdown();server.server_close()
    print(json.dumps(dict(fake_endpoint=True,real_docker_daemon_contacted=False,real_container_created=False,exit_status=result.returncode,stdout=result.stdout,stderr=result.stderr,requests=requests),indent=2));assert result.returncode==0
