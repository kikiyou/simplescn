#! /usr/bin/env python3

from http.server  import BaseHTTPRequestHandler,HTTPServer
import time
#import socket
import logging
import sys,signal,threading
import socketserver #,socket
import traceback
import os
from os import path


from common import success,error,server_port,check_certs,generate_certs,init_config_folder,default_configdir, default_sslcont,check_name,dhash_salt,gen_passwd_hash


class server(object):
    nhipmap=None
    nhlist_cache=""
    refreshthread=None
    isactive=True
    #name=None
    info=None
    
    def __init__(self,_name,_message):
        self.nhipmap={}
        self.nhlist_cond=threading.Event()
        self.change_sem=threading.Semaphore(1)
        self.refreshthread=threading.Thread(target=self.refresh_nhlist)
        self.refreshthread.daemon=True
        self.refreshthread.start()
        #self.name=_name
        self.info="{}{}/{}".format(success,_name,_message)

    def __del__(self):
        self.isactive=False
        self.nhlist_cond.set()
        try:
            self.refreshthread.join(4)
        except Exception as e:
            logging.error(e)

    def refresh_nhlist(self):
        while self.isactive:
            self.change_sem.acquire()
            tnhlist=""
            for _name in self.nhipmap:
                for _hash in self.nhipmap[_name]:
                    tnhlist="{}\n{}/{}".format(tnhlist,_name,_hash)
            self.nhlist_cache=tnhlist[1:]
            self.change_sem.release()
            self.nhlist_cond.clear()
            time.sleep(1)
            self.nhlist_cond.wait()
  

    def register(self,_name,_hash,_port,_addr):
        if check_name(_name)==False:
            return "{}invalid name".format(error)
        self.change_sem.acquire(False)
        self.nhipmap[_name]={_hash: (_addr[0],_port)}
        self.change_sem.release()
        self.nhlist_cond.set()
        return "{}registered".format(success)
    
    
    def get(self,_name,_hash,_addr):
        if _name not in self.nhipmap:
            return "{}name".format(error)
        if _hash not in self.nhipmap[_name]:
            return "{}certhash".format(error)
        return "{}{}:{}".format(success,*self.nhipmap[_name][_hash])
    
    def listnames(self,_addr):
        if len(self.nhlist_cache)==0:
            return "{}empty".format(success)
        return "{}{}".format(success,self.nhlist_cache)
    
    def info(self,_addr):
        return self.info 
    
    
class server_handler(BaseHTTPRequestHandler):
    #linkback=None
    validactions=["register","connect","get","listnames","info"]
    links=None
    spwhash=None
    tpwhash=None
    salt=None
    icon=b""
        
    def index(self):
        self.send_response(200)
        self.send_header('Content-type',"text/html")
        self.end_headers()
        self.wfile.write(b"TODO")

    #check server password
    def check_spw(self):
        if self.spwhash is None:
            return True
        if "spwhash" in self.headers:
            if dhash_salt(self.headers["spwhash"],self.salt)==self.spwhash:
                return True
        return False

    #check server password
    def check_tpw(self):
        if self.tpwhash is None:
            return True
        if "tpwhash" in self.headers:
            if dhash_salt(self.headers["tpwhash"],self.salt)==self.tpwhash:
                return True
        return False

    
    def do_GET(self):
        if self.path=="/favicon.ico":
            self.wfile.write(self.icon)
            return
        
        if self.check_spw()==False:
            self.send_error(401,"insufficient permissions")            
            return
        
        _path=self.path[1:].split("/")
        if _path[0]=="":
            self.index()
            return
        action=_path[0]
        if action=="index":
            self.index()
            return
        _path=_path+[self.client_address,]
        if action not in self.validactions:
            self.send_error(400,"invalid actions")
            return
        try:
            func=type(self.links["server_server"]).__dict__[action]
            response=func(self.links["server_server"],*_path[1:])
        except Exception as e:
            if self.client_address[0] in ["localhost","127.0.0.1","::1"]:
                #helps against ssl failing about empty string (EOF)
                st=str(e)+"\n\n"+str(traceback.format_tb(e))
                if len(st)>0:
                    self.send_error(500,st)
                else:
                    self.send_error(500,"unknown")
            return
        respparse=response.split("/",1)
        if respparse[0]=="error":
            #helps against ssl failing about empty string (EOF)
            if len(respparse[1])>0:
                self.send_error(400,respparse[1])
            else:
                self.send_error(400,"unknown")
        else:
            self.send_response(200)
            self.send_header('Content-type',"text")
            self.end_headers()
            #helps against ssl failing about empty string (EOF)
            if len(respparse[1])>0:
                self.wfile.write(bytes(respparse[1],"utf8"))
            else:
                self.wfile.write(bytes("success","utf8"))
        
        
def inputw():
    input("Please enter passphrase:\n")
    
class http_server_server(socketserver.ThreadingMixIn,HTTPServer):
    server_server=None
    sslcont=None
    #def __del__(self):
    #    self.crappyssl.close()
  
    def __init__(self, server_address,certfpath):
        socketserver.TCPServer.__init__(self, server_address, server_handler)
        #self.crappyssl=workaround_ssl(certs[1])

        self.sslcont=default_sslcont()
        self.sslcont.load_cert_chain(certfpath+".pub",certfpath+".priv")
        self.socket=self.sslcont.wrap_socket(self.socket)


class server_init(object):
    config_path=None
    links=None
    
    def __init__(self,**kwargs):
        self.config_path=path.expanduser(kwargs["config"])
        if self.config_path[-1]==os.sep:
            self.config_path=self.config_path[:-1]
        port=kwargs["port"]
        init_config_folder(self.config_path,"server")
        
        server_handler.salt=os.urandom(4)
        if kwargs["spwhash"] is not None:
            server_handler.spwhash=dhash_salt(kwargs["spwhash"],server_handler.salt)
        elif kwargs["spwfile"] is not None:
            op=open("r")
            server_handler.spwhash=gen_passwd_hash(op.readline())
            op.close()
        
        if kwargs["tpwhash"] is not None:
            server_handler.tpwhash=dhash_salt(kwargs["tpwhash"],server_handler.salt)
        elif kwargs["tpwfile"] is not None:
            op=open("r")
            server_handler.tpwhash=gen_passwd_hash(op.readline())
            op.close()
        
        
        with open("favicon.ico", 'rb') as faviconr:
            server_handler.icon=faviconr.read()
        
        self.links={}
        _cpath="{}{}{}".format(self.config_path,os.sep,"server")
        _message=None
        _name=None
        if check_certs(_cpath+"_cert")==False:
            logging.debug("Certificate(s) not found. Generate new...")
            generate_certs(self.config_path+"server_cert")
            logging.debug("Certificate generation complete")
        with open(_cpath+"_name", 'r') as readserver:
            _name=readserver.readline()
            
        with open(_cpath+"_message", 'r') as readservmessage:
            _message=readservmessage.read()
            if _message[-1] in "\n":
                _message=_message[:-1]
        if None in [_name,_message]:
            raise(Exception("missing"))

        
        _name=_name.split("/")
        if len(_name)>2 or check_name(_name[0])==False:
            print("Configuration error in {}".format(_cpath+"_name"))
            print("should be: <name>/<port>")
            print("Name has some restricted characters")
            

        
        
        if port is not None:
            port=int(port)
        elif len(_name)>=2:
            _port=int(_name[1])
        else:
            _port=server_port

        self.links["server_server"]=server(_name[0],_message)
        server_handler.links=self.links
        
        self.links["hserver"]=http_server_server(("0.0.0.0",_port),_cpath+"_cert")

    def serve_forever_block(self):
        self.links["hserver"].serve_forever()
    def serve_forever_nonblock(self):
        self.sthread = threading.Thread(target=self.serve_forever_block)
        self.sthread.daemon = True
        self.sthread.start()



def signal_handler(_signal, frame):
    sys.exit(0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    signal.signal(signal.SIGINT, signal_handler)
    d={"config":default_configdir,"port":None,"spwhash":None,"spwfile":None,"tpwhash":None,"tpwfile":None}

    if len(sys.argv)>1:
        tparam=()
        for elem in sys.argv:
            elem=elem.strip("-")
            if elem in ["help","h"]:
                #paramhelp()
                sys.exit(0)
            else:
                tparam=elem.split("=")
                if len(tparam)==1:
                    tparam=elem.split(":")
                if  len(tparam)==1:
                    continue
                d[tparam[0]]=tparam[1]
                
    cm=server_init(**d)
    logging.debug("server started. Enter mainloop")
    cm.serve_forever_block()
