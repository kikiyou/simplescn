
import ssl
#import abc
from common import logger, success, error, isself, check_hash, server_port, dhash
from http import client
import json

class client_safe(object): #abc.ABC):
    
    validactions_safe={"get", "gethash", "help", "show", "register", "getlocal","listhashes","listnodenametypes", "searchhash","listnames", "listnodenames", "listnodeall", "getservice", "registerservice", "listservices", "info", "check", "check_direct", "prioty_direct", "prioty", "ask", "getreferences", "cap", "findbyref"}

    hashdb = None
    links = None
    cert_hash = None
    _cache_help = None
    validactions = None
    name = None
    sslcont = None
    
    
    def help(self): 
        return (True, self._cache_help, isself, self.cert_hash)
    
    def register(self,server_addr,dheader):
        return self.do_request(server_addr,"/register/{}/{}/{}".format(self.name, self.cert_hash, self.show()[1][2]), dheader, context = self.links["server"].sslcont)
    
    #returns name,certhash,own socket
    def show(self):
        return (True,(self.name,self.cert_hash,
                str(self.links["server"].socket.getsockname()[1])),isself,self.cert_hash)
    
    #### second way to add a service ####
    def registerservice(self,_servicename,_port):
        self.links["client_server"].spmap[_servicename]=_port
        return (True,"service registered",isself,self.cert_hash)
    
    #### second way to delete a service ####
    def delservice(self,_servicename):
        if _servicename in self.links["client_server"].spmap:
            del self.links["client_server"].spmap[_servicename]
        return (True,"service deleted",isself,self.cert_hash)
        
    def get(self, server_addr, _name, _hash, dheader):
        temp=self.do_request(server_addr,"/get/{}/{}".format(_name,_hash),dheader)
        if temp[0]==False:
            return temp
        try:
            address,port=json.loads(temp[1])
        except Exception as e:
            return (False, "splitting failed: {}".format(e), isself, self.cert_hash)
        try:
            temp2=(temp[0],(address,int(port)),temp[2],temp[3])
        except ValueError:
            return (False,"port not a number:\n{}".format(temp[1]),isself,self.cert_hash)
        if temp2[1][1]<1:
            return (False,"port <1:\n{}".format(temp[1][1]),isself,self.cert_hash)
        return temp2
        
    
    def gethash(self,_addr):
        _addr = _addr.split(":")
        if len(_addr) == 1:
            _addr = (_addr[0],server_port)
        try:
            con = client.HTTPSConnection(_addr[0], _addr[1], context=self.sslcont)
            con.connect()
            pcert = ssl.DER_cert_to_PEM_cert(con.sock.getpeercert(True))
            con.close()
            return (True, (dhash(pcert), pcert), isself, self.cert_hash)
        except ssl.SSLError:
            return (False, "server speaks no tls 1.2", isself, self.cert_hash)
        except ConnectionRefusedError:
            return (False, "server does not exist", isself, self.cert_hash)
        except Exception as e:
            return (False, "Other error: {}".format(e), isself, self.cert_hash)

    def ask(self,_address):
        _ha = self.gethash(_address)
        if _ha[0] == False:
            return _ha
        if _ha[1][0] == self.cert_hash:
            return (True, (isself, self.cert_hash), isself, self.cert_hash)
        temp = self.hashdb.certhash_as_name(_ha[1][0])
        return (True, (temp, _ha[1][0]), isself, self.cert_hash)

    def listnames(self,server_addr, dheader):
        temp = self.do_request(server_addr, "/listnames", dheader)
        if temp[0] == False:
            return temp
        out = []
        try:
            temp2 = json.loads(temp[1])
            for name in sorted(temp2):
                if name == isself:
                    logging.debug("Scamming attempt: SKIP")
                    continue
                    
                for _hash in sorted(temp2[name]):
                    if _hash == self.cert_hash:
                        out.append((name, _hash, isself))
                    else:
                        certname = self.hashdb.certhash_as_name(_hash)
                        out.append((name, _hash, certname))
                        
        except Exception as e:
            return False, "{}: {}".format(type(e).__name__, e),isself,self.cert_hash
        return (temp[0],out,temp[2],temp[3])
    
    def getservice(self, *args):
        if len(args)==1:
            dheader=args[0]
            client_addr="localhost:{}".format(self.links["server"].socket.getsockname()[1])
        elif len(args)==2:
            client_addr,dheader=args
        else:
            return (False,("wrong amount arguments (getservice): {}".format(args)),isself,self.cert_hash)
        return self.do_request(client_addr, "/getservice/{}".format(_service),dheader)
    
    def listservices(self,*args):
        if len(args)==1:
            dheader=args[0]
            client_addr="localhost:{}".format(self.links["server"].socket.getsockname()[1])
        elif len(args)==2:
            client_addr,dheader=args
        else:
            return (False,("wrong amount arguments (listservices): {}".format(args)),isself,self.cert_hash)
        temp=self.do_request(client_addr, "/listservices",dheader,forceport=True)
        if temp[0]==False:
            return temp
        temp2={}
        try:
            temp2 = json.loads(temp[1])
        except Exception as e:
            return False, "{}: {}".format(type(e).__name__, e)
        temp3=[]
        for elem in sorted(temp2.keys()):
            temp3.append((elem,temp2[elem]))
        return temp[0],temp3,temp[2],temp[3]
    
    def info(self,*args):
        if len(args) == 1:
            dheader=args[0]
            _addr="localhost:{}".format(self.links["server"].socket.getsockname()[1])
        elif len(args)==2:
            _addr,dheader=args
        else:
            return (False,("wrong amount arguments (info): {}".format(args)),isself,self.cert_hash)
        
        _tinfo=self.do_request(_addr, "/info", dheader, forceport=True)
        if _tinfo[0]==False:
            return _tinfo
        temp2={}
        try:
            temp2 = json.loads(_tinfo[1])
        except Exception as e:
            return False, "{}: {}".format(type(e).__name__, e)
        return True, temp2, _tinfo[2], _tinfo[3]

    def cap(self,*args):
        if len(args)==1:
            dheader=args[0]
            _addr="localhost:{}".format(self.links["server"].socket.getsockname()[1])
        elif len(args)==2:
            _addr,dheader=args
        else:
            return (False,("wrong amount arguments (cap): {}".format(args)),isself,self.cert_hash)
            
        temp=self.do_request(_addr, "/cap",dheader,forceport=True)
        if temp[0]==False:
            return temp
        
        temp2={}
        try:
            temp2 = json.loads(_tinfo[1])
        except Exception as e:
            return False, "{}: {}".format(type(e).__name__, e),isself,self.cert_hash
        return True, temp2, temp[2], temp[3]
        
    def prioty_direct(self,*args):
        if len(args)==1:
            dheader=args[0]
            _addr="localhost:{}".format(self.links["server"].socket.getsockname()[1])
        elif len(args)==2:
            _addr,dheader=args
        else:
            return (False,("wrong amount arguments (priority_direct): {}".format(args)),isself,self.cert_hash)
        
        _tprioty = self.do_request(_addr,  "/prioty",dheader,forceport=True)
        temp2={}
        try:
            temp2 = json.loads(_tprioty[1])
        except Exception as e:
            return False, "{}: {}".format(type(e).__name__, e),isself,self.cert_hash
        return True, temp2, _tprioty[2], _tprioty[3]

    def prioty(self,server_addr,_name,_hash,dheader):
        temp=self.get(server_addr,_name,_hash,dheader)
        if temp[0]==False:
            return temp
        return self.prioty_direct(temp[1])

    #check if _addr is reachable and update priority
    def check_direct(self,_addr,_namelocal,_hash,dheader):
        dheader["certhash"]=_hash #ensure this
        
        temp=self.prioty_direct(_addr,dheader)
        if temp[0]==False:
            return temp
        
        if self.hashdb.exist(_namelocal,_hash)==True:
            self.hashdb.changepriority(_namelocal,_hash,temp[1][0])
            self.hashdb.changetype(_namelocal,_hash,temp[1][1])
        return temp
    
    #check if node is reachable and update priority
    def check(self,server_addr,_name,_namelocal,_hash,dheader):
        temp=self.get(server_addr,_name,_hash,dheader)
        if temp[0]==False:
            return temp
        return self.check_direct(temp[1],_namelocal,_hash,dheader)
    #local management

    #search
    def searchhash(self,_certhash):
        temp=self.hashdb.certhash_as_name(_certhash)
        if temp is None:
            return(False, error,isself,self.cert_hash)
        else:
            return (True,temp,isself,self.cert_hash)
            
    def getlocal(self,_name,_certhash):
        temp=self.hashdb.get(_name,_certhash)
        if temp is None:
            return(False, error,isself,self.cert_hash)
        else:
            return (True,temp,isself,self.cert_hash)
    
    def listhashes(self, *args):
        if len(args) == 2:
            _name, _nodetypefilter = args
        elif len(args) == 1:
            _name=args[0]
            _nodetypefilter = None
        else:
            return (False,("wrong amount arguments (listhashes): {}".format(args)))
        temp=self.hashdb.listhashes(_name,_nodetypefilter)
        if temp is None:
            return(False, error,isself,self.cert_hash)
        else:
            return (True,temp,isself,self.cert_hash)
    
    def listnodenametypes(self):
        temp=self.hashdb.listnodenametypes()
        if temp is None:
            return(False, error,isself,self.cert_hash)
        else:
            return (True,temp,isself,self.cert_hash)
    
    def listnodenames(self,*args):
        if len(args)==1:
            _nodetypefilter=args[0]
        elif len(args)==0:
            _nodetypefilter=None
        else:
            return (False,("wrong amount arguments (listnodenames): {}".format(args)))
        temp=self.hashdb.listnodenames(_nodetypefilter)
        if temp is None:
            return(False, error,isself,self.cert_hash)
        else:
            return (True,temp,isself,self.cert_hash)

    def listnodeall(self, *args):
        if len(args)==1:
            _nodetypefilter=args[0]
        elif len(args)==0:
            _nodetypefilter=None
        else:
            return (False,"wrong amount arguments (listnodeall): {}".format(args),isself,self.cert_hash)
        temp=self.hashdb.listnodeall(_nodetypefilter)
        if temp is None:
            return (False, error,isself,self.cert_hash)
        else:
            return (True,temp,isself,self.cert_hash)
    
        
    def getreferences(self,*args):
        if len(args) == 2:
            _certhash,_reftypefilter=args
        elif len(args) == 1:
            _certhash=args[0]
            _reftypefilter=None
        else:
            return (False,"wrong amount arguments (getreferences): {}".format(args),isself,self.cert_hash)
        if check_hash(_certhash)==True:
            _localname=self.hashdb.certhash_as_name(_certhash) #can return None to sort out invalid hashes
        else:
            _localname=None
        if _localname is None:
            return (False, "certhash does not exist: {}".format(_certhash),isself,self.cert_hash)
        _tref=self.hashdb.get(_localname, _certhash)
        if _tref is None:
            return (False,"error in hashdb",isself,self.cert_hash)
        temp=self.hashdb.getreferences(_tref[2], _reftypefilter)
        if temp is None:
            return (False,error,isself,self.cert_hash)
        return (True,temp,isself,self.cert_hash)
        
    def findbyref(self,_reference):
        temp=self.hashdb.findbyref(_reference)
        if temp is None:
            return (False,error,isself,self.cert_hash)
        return (True,temp,isself,self.cert_hash)

