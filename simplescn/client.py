#! /usr/bin/env python3
#license: bsd3, see LICENSE.txt

import sys, os

from simplescn import sharedir

import socket
from http import client
import ssl
import threading
import json
import logging


from simplescn.client_admin import client_admin
from simplescn.client_safe import client_safe
from simplescn.client_config import client_config
from simplescn.dialogs import client_dialogs


from simplescn import check_certs, generate_certs, init_config_folder, default_configdir, default_sslcont, dhash, VALNameError, VALHashError, isself, check_name, commonscn, scnparse_url, AddressFail, rw_socket, check_args, safe_mdecode, generate_error, max_serverrequest_size, gen_result, check_result, check_argsdeco, scnauth_server, http_server, generate_error_deco, VALError, client_port, default_priority, default_timeout, check_hash, scnauth_client, traverser_helper, create_certhashheader, classify_noplugin, classify_local, classify_access, commonscnhandler, default_loglevel, loglevel_converter, connect_timeout

from simplescn.common import certhash_db
#VALMITMError



reference_header = \
{
"User-Agent": "simplescn/0.5 (client)",
"Authorization": 'scn {}',
"Connection": 'keep-alive' # keep-alive is set by server (and client?)
}
class client_client(client_admin, client_safe, client_config, client_dialogs):
    name = None
    cert_hash = None
    sslcont = None
    hashdb = None
    links = None
    redirect_addr = ""
    redirect_hash = ""
    scntraverse_helper = None
    brokencerts = []
    
    validactions = {"cmd_plugin", "remember_auth" }
    
    def __init__(self, _name, _pub_cert_hash, _certdbpath, certfpath, _links):
        client_dialogs.__init__(self)
        client_admin.__init__(self)
        client_safe.__init__(self)
        client_config.__init__(self)
        self.links = _links
        self.name = _name
        self.cert_hash = _pub_cert_hash
        self.hashdb = certhash_db(_certdbpath)
        self.sslcont = self.links["hserver"].sslcont
        
        if "hserver" in self.links:
            self.udpsrcsock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            self.udpsrcsock.settimeout(None)
            self.udpsrcsock.bind(self.links["hserver"].socket.getsockname())
            self.scntraverse_helper = traverser_helper(connectsock=self.links["hserver"].socket, srcsock=self.udpsrcsock)
        
        for elem in os.listdir(os.path.join(self.links["config_root"], "broken")):
            _splitted = elem.rsplit(".", 1)
            if _splitted[1] != "reason":
                continue
            _hash = _splitted[0]
            with open(os.path.join(self.links["config_root"], "broken", elem), "r") as reado:
                _reason = reado.read().strip().rstrip()
            if check_hash(_hash) and (_hash, _reason) not in self.brokencerts:
                self.brokencerts.append((_hash, _reason))
                
        #self.sslcont.load_cert_chain(certfpath+".pub", certfpath+".priv")
        # update self.validactions
        self.validactions.update(client_dialogs.validactions_dialogs)
        self.validactions.update(client_admin.validactions_admin)
        self.validactions.update(client_safe.validactions_safe)
        self.validactions.update(client_config.validactions_config)
        self._cache_help = self.cmdhelp()
    

    def do_request(self, _addr_or_con, _path, body={}, headers=None, forceport=False, forcehash=None, forcetraverse=False, sendclientcert=False, _reauthcount=0, _certtupel=None):
        """ func: use this method to communicate with clients/servers """
        if headers is None:
            headers = body.pop("headers", {})
        elif "headers" in body:
            del body["headers"]
        
        sendheaders = reference_header.copy()
        for key,value in headers.items():
            if key in ["Connection", "Host", "Accept-Encoding", "Content-Type", "Content-Length", "User-Agent", "X-certrewrap"]:
                continue
            sendheaders[key] = value
        sendheaders["Content-Type"] = "application/json; charset=utf-8"
        if sendclientcert:
            sendheaders["X-certrewrap"], _random = create_certhashheader(self.cert_hash)
        
        if isinstance(_addr_or_con, client.HTTPSConnection) == False:
            _addr = scnparse_url(_addr_or_con,force_port=forceport)
            con = client.HTTPSConnection(_addr[0], _addr[1], context=self.sslcont, timeout=self.links["config"].get("connect_timeout"))
            try:
                con.connect()
            except ConnectionRefusedError:
                forcetraverse = True
            
            if forcetraverse:
                if "traverseserveraddr" not in body:
                    return False, "connection refused and no traversalserver specified", isself, self.cert_hash
                _tsaddr = scnparse_url(body.get("traverseserveraddr"))
                contrav = client.HTTPSConnection(_tsaddr[0], _tsaddr[1], context=self.sslcont, timeout=self.links["config"].get("connect_timeout"))
                contrav.connect()
                _sport = contrav.sock.getsockname()[1]
                retserv = self.do_request(contrav, "/server/open_traversal")
                contrav.close()
                if retserv[0]:
                    con.sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    con.sock.bind(('', _sport)) #retserv.get("traverse_address"))
                    for count in range(0,3):
                        try:
                            con.sock.connect((_addr[0], _addr[1]))
                            break
                        except Exception:
                            pass
                    con.sock = self.sslcont.wrap_socket(con.sock)
                    con.timeout = self.links["config"].get("timeout")
                    con.sock.settimeout(self.links["config"].get("timeout"))
        else:
            con = _addr_or_con
            if con.sock is None:
                con.timeout = self.links["config"].get("connect_timeout")
                try:
                    con.connect()
                except ConnectionRefusedError:
                    pass
            con.timeout = self.links["config"].get("timeout")
            con.sock.settimeout(self.links["config"].get("timeout"))
            #if headers.get("Connection", "") != "keep-alive":
            #    con.connect()
        
        if _certtupel is None:
            pcert = ssl.DER_cert_to_PEM_cert(con.sock.getpeercert(True)).strip().rstrip()
            hashpcert = dhash(pcert)
            if forcehash is not None:
                if forcehash != hashpcert:
                    raise(VALHashError)
            elif body.get("forcehash") is not None:
                if body.get("forcehash") != hashpcert:
                    raise(VALHashError)
            if hashpcert == self.cert_hash:
                validated_name = isself
            else:
                hashob = self.hashdb.get(hashpcert)
                if hashob:
                    validated_name = (hashob[0], hashob[3]) #name, security
                    if validated_name[0] == isself:
                        raise(VALNameError)
                else:
                    validated_name = None
            _certtupel = (validated_name, hashpcert)
        else:
            validated_name, hashpcert = _certtupel
        #start connection
        con.putrequest("POST", _path)
        for key, value in sendheaders.items():
            #if key != "Proxy-Authorization":
            con.putheader(key, value)
        pwcallm = body.get("pwcall_method")
        if "pwcall_method" in body:
            del body["pwcall_method"]

        ob = bytes(json.dumps(body), "utf-8")
        
        con.putheader("Content-Length", str(len(ob)))
        con.endheaders()
        if sendclientcert:
            con.sock = con.sock.unwrap()
            con.sock = self.sslcont.wrap_socket(con.sock, server_side=True)
        con.send(ob)
        
        response = con.getresponse()
        servertype = response.headers.get("Server", "")
        logging.debug("Servertype: {}".format(servertype))
        if response.status == 401:
            body["pwcall_method"] = pwcallm
            auth_parsed = json.loads(sendheaders.get("Authorization", "scn {}").split(" ", 1)[1])
            if response.headers.get("Content-Length", "").strip().rstrip().isdigit() == False:
                con.close()
                return False, "no content length", _certtupel[0], _certtupel[1]
            readob = response.read(int(response.headers.get("Content-Length")))
            reqob = safe_mdecode(readob, response.headers.get("Content-Type","application/json; charset=utf-8"))
            if reqob is None:
                con.close()
                return False, "Invalid Authorization request object", _certtupel[0], _certtupel[1]
            
            realm = reqob.get("realm")
            if callable(pwcallm) == True:
                authob = pwcallm(hashpcert, reqob, _reauthcount)
            else:
                return False, "no way to input passphrase for authorization", _certtupel[0], _certtupel[1]
            

            if authob is None:
                con.close()
                return False, "Authorization failed", _certtupel[0], _certtupel[1]
            _reauthcount += 1
            auth_parsed[realm] = authob
            sendheaders["Authorization"] = "scn {}".format(json.dumps(auth_parsed).replace("\n",  ""))
            return self.do_request(con, _path, body=body, forcehash=forcehash, headers=sendheaders, forceport=forceport, _certtupel=_certtupel, forcetraverse=forcetraverse, sendclientcert=sendclientcert, _reauthcount=_reauthcount)
        else:
            if response.getheader("Content-Length", "").strip().rstrip().isdigit() == False:
                con.close()
                return False, "No content length", _certtupel[0], _certtupel[1]
            readob = response.read(int(response.getheader("Content-Length")))
            # kill keep-alive connection when finished, or transport connnection
            #if isinstance(_addr_or_con, client.HTTPSConnection) == False:
            con.close()
            if response.status == 200:
                status = True
                if sendclientcert:
                    if _random != response.getheader("X-certrewrap", ""):
                        return False, "rewrapped cert secret does not match", _certtupel[0], _certtupel[1]
        
            else:
                status = False
            
            if response.getheader("Content-Type").split(";")[0].strip().rstrip() in ["text/plain","text/html"]:
                obdict = gen_result(str(readob, "utf-8"), status)
            else:
                obdict = safe_mdecode(readob, response.getheader("Content-Type", "application/json"))
            if check_result(obdict, status) == False:
                return False, "error parsing request\n{}".format(readob), _certtupel[0], _certtupel[1]
            
            if status == True:
                return status, obdict["result"], _certtupel[0], _certtupel[1]
            else:
                return status, obdict["error"], _certtupel[0], _certtupel[1]



    def use_plugin(self, address, plugin, paction, forcehash=None, originalcert=None, forceport=False, requester="", traverseserveraddr=None):
        """ use this method to communicate with plugins """
        _addr = scnparse_url(address, force_port=forceport)
        con = client.HTTPSConnection(_addr[0], _addr[1], context=self.sslcont, timeout=self.links["config"].get("connect_timeout"))
        
        try:
            con.connect()
        except ConnectionRefusedError:
            if traverseserveraddr is not None:
                _tsaddr = scnparse_url(traverseserveraddr)
                contrav = client.HTTPSConnection(_tsaddr[0], _tsaddr[1], context=self.sslcont)
                contrav.connect()
                _sport = contrav.sock.getsockname()[1]
                retserv = self.do_request(contrav, "/server/open_traversal")
                contrav.close()
                if retserv[0]:
                    con.sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    con.sock.bind(('', _sport))#retserv.get("traverse_address"))
                    con.sock.settimeout(self.links["config"].get("connect_timeout"))
                    for count in range(0,3):
                        try:
                            con.sock.connect((_addr[0], _addr[1]))
                            break
                        except Exception:
                            pass
                    con.sock = self.sslcont.wrap_socket(con.sock)
            else:
                logging.error("connection failed and no traverse address")
                return None, None, None
        cert = ssl.DER_cert_to_PEM_cert(con.sock.getpeercert(True)).strip().rstrip()
        _hash = dhash(cert)
        con.putrequest("POST", "/plugin/{}/{}".format(plugin, paction))
        _certheader, _random = create_certhashheader(self.cert_hash)
        con.putheader("X-certrewrap", _certheader)
        con.putheader("User-Agent", "simplescn/0.5 (client-plugin)")
        if originalcert:
            con.putheader("X-original_cert", originalcert)
        con.endheaders()
        con.sock = con.sock.unwrap()
        con.sock = self.sslcont.wrap_socket(con.sock, server_side=True)
        
        sock = con.sock
        try:
            # terminates connection, even keep-alive is set
            #resp = con.getresponse()
            # so do it manually
            resp = client.HTTPResponse(con.sock, con.debuglevel, method=con._method)
            resp.begin()
        except socket.timeout:
            logging.error("timeout connection")
            return None, None, None
        # set to None before connection can destroy socket
        con.sock = None
        if resp.status != 200:
            logging.error("requesting plugin failed: {}, action: {}, status: {}, reason: {}".format(plugin, paction, resp.status, resp.reason))
            return None, None, None
        if _hash != forcehash:
            con.close()
            return None, cert, _hash
        if _random != resp.getheader("X-certrewrap", ""):
            logging.error("rewrapped cert secret does not match")
            con.close()
            return None, cert, _hash
        return sock, cert, _hash
        
    
    @check_argsdeco({"plugin": str, "paction": str})
    @classify_noplugin
    def cmd_plugin(self, obdict):
        """ func: trigger commandline action of plugin
            return: answer of plugin
            plugin: name of plugin
            paction: cmdaction of plugin """
        plugins = self.links["client_server"].pluginmanager.plugins
        if plugins is None:
            return False, "no plugins loaded"
        if obdict["plugin"] not in plugins:
            return False, "Error: plugin does not exist"
        plugin = plugins[obdict["plugin"]]
        if hasattr(plugin, "cmd_node_actions") == False:
            return False,  "Error: plugin does not support commandline"
                
        action = obdict["paction"]
        if hasattr(plugin, "cmd_node_localized_actions") and \
                action in plugin.cmd_node_localized_actions:
                action = plugin.cmd_node_localized_actions[action]
        try:
            resp = plugin.cmd_node_actions[action][0](obdict)
            return True, resp
        except Exception as e:
            False, generate_error(e)
    
    # auth is special variable see safe_mdecode in common
    
    @check_argsdeco({"auth": dict, "hash": str, "address": str})
    @classify_local
    def remember_auth(self, obdict):
        """ func: Remember authentication info for as long the program runs
            return: True, when success
            auth: authdict
            hash: hash to remember
            address: address of server/client for which the pw should be saved
        """
        if obdict.get("hash") is None:
            _hashob = self.gethash(obdict)
            if _hashob[0] == False:
                return False, "invalid address for retrieving hash"
            _hash = _hashob[1]["hash"]
        else:
            _hash = obdict.get("hash")
        for realm, pw in obdict.get("auth"):
            self.links["auth_client"].saveauth(pw, _hash, realm)
        return True
        
    
    
    # NEVER include in validactions
    # headers=headers
    # client_address=client_address
    @classify_access
    def access_core(self, action, obdict):
        """ internal method to access functions """
        
        if action in self.validactions:
            if "access" in getattr(getattr(self, action), "classify", set()):
                return False, "actions: 'classified access not allowed in access_core", isself, self.cert_hash
            if "insecure" in getattr(getattr(self, action), "classify", set()):
                return False, "method call not allowed this way (insecure)", isself, self.cert_hash
            if "experimental" in getattr(getattr(self, action), "classify", set()):
                logging.warning("action: \"{}\" is experimental".format(action))
            #with self.client_lock: # not needed, use sqlite's intern locking mechanic
            try:
                return getattr(self, action)(obdict)
            except Exception as e:
                return False, e #.with_traceback(sys.last_traceback)
        else:
            return False, "not in validactions", isself, self.cert_hash
    
    # command wrapper for cmd interfaces
    @generate_error_deco
    @classify_noplugin
    def command(self, inp, callpw_auth=False):
        # use safe_mdecode for x-www-form-urlencoded compatibility with auth extension
        obdict = safe_mdecode(inp, "application/x-www-form-urlencoded")
        if obdict is None:
            return False, "decoding failed"
        error=[]
        if check_args(obdict, {"action": str},error=error) == False:
            return False, "{}:{}".format(*error)
            #return False, "no action given", isself, self.cert_hash
        if obdict["action"] not in self.validactions:
            return False, "action: \"{}\" not in validactions".format(obdict["action"])
        if obdict["action"] == "command"  or "access" in getattr(getattr(self, obdict["action"]), "classify", set()):
            return False, "action: 'classified as access, command' not allowed in command"
        action = obdict["action"]
        del obdict["action"]
        
        def pw_auth_command(pwcerthash, authreqob, reauthcount):
            if callpw_auth == False:
                authob = self.links["auth_client"].asauth(obdict.get("auth", {}).get(authreqob.get("realm")), authreqob)
            else:
                authob = self.pw_auth(pwcerthash, authreqob, reauthcount)
            return authob
        obdict["pwcall_method"] = pw_auth_command
        try:
            return self.access_core(action, obdict)
        except Exception as e:
            return False, e
        
    # NEVER include in validactions
    # for plugins, e.g. untrusted
    # requester = "", invalid requester don't allow asking
    # headers=headers
    # client_address=client_address
    @generate_error_deco
    @classify_access
    def access_safe(self, action, requester="", **obdict):
        if "access" in getattr(getattr(self, action), "classify", set()):
            return False, "actions: 'access methods not allowed in access_safe"
        def pw_auth_plugin(pwcerthash, authreqob, reauthcount):
            authob = self.links["auth_client"].asauth(obdict.get("auth", {}).get(authreqob.get("realm")), authreqob)
            return authob
        obdict["pwcall_method"] = pw_auth_plugin
        obdict["requester"] = requester
        if action in self.validactions:
            if "noplugin" in getattr(getattr(self, action), "classify", set()):
                return False, "{} tried to use noplugin protected methods".format(requester)
            if "admin" in getattr(getattr(self, action), "classify", set()):
                # use_notify returns in error case None or False both evaluated as False (when not checking with ==)
                if requester == "" or self.use_notify('"{}" wants admin permissions\nAllow?'.format(requester)):
                    return False, "no permission"
            return self.access_core(action, obdict)
        else:
            return False, "not in validactions"
    
    
    # NEVER include in validactions
    # for user interactions
    # headers=headers
    # client_address=client_address
    @generate_error_deco
    @classify_access
    def access_main(self, action, **obdict):
        obdict["pwcall_method"] = self.pw_auth
        try:
            return self.access_core(action, obdict)
        except Exception as e:
            return False, e

    # help section
    def cmdhelp(self):
        out="""# commands
"""
        for funcname in sorted(self.validactions):
            func = getattr(self, funcname)
            if getattr(func, "__doc__", None) is not None:
                out+="{doc}\n".format(doc=func.__doc__)
            else:
                logging.info("Missing __doc__: {}".format(funcname))
        return out


### receiverpart of client ###

class client_server(commonscn):
    capabilities = ["basic",]
    scn_type = "client"
    spmap = {}
    validactions = {"info", "getservice", "dumpservices", "cap", "prioty", "registerservice", "delservice"}
    local_client_service_control = False
    wlock = None
    def __init__(self, dcserver):
        commonscn.__init__(self)
        self.wlock = threading.Lock()
        if dcserver["name"] is None or len(dcserver["name"]) == 0:
            logging.info("Name empty")
            dcserver["name"] = "<noname>"

        if dcserver["message"] is None or len(dcserver["message"]) == 0:
            logging.info("Message empty")
            dcserver["message"] = "<empty>"
            
        self.name = dcserver["name"]
        self.message = dcserver["message"]
        self.priority = dcserver["priority"]
        self.cert_hash = dcserver["certhash"]
        self.cache["dumpservices"] = json.dumps(gen_result({}, True))
        self.update_cache()
    ### the primary way to add or remove a service
    ### can be called by every application on same client
    ### don't annote list with "map" dict structure on serverside (overhead)
    
    @check_argsdeco({"name": str, "port": int})
    @classify_local
    def registerservice(self, obdict):
        """ func: register a service = (map port to name)
            return: success or error
            name: service name
            port: port number """
        if obdict.get("clientaddress") is None:
            False, "bug: clientaddress is None"
        if obdict.get("clientaddress")[0] in ["127.0.0.1", "::1"]:
            self.wlock.acquire()
            self.spmap[obdict.get("name")] = obdict.get("port")
            self.cache["dumpservices"] = json.dumps(gen_result(self.spmap, True))
            #self.cache["listservices"] = json.dumps(gen_result(sorted(self.spmap.items(), key=lambda t: t[0]), True))
            self.wlock.release()
            return True
        return False, "no permission"
    
    ### don't annote list with "map" dict structure on serverside (overhead)
    
    @check_argsdeco({"name": str})
    @classify_local
    def delservice(self, obdict):
        """ func: delete a service
            return: success or error
            name: service name """
        if obdict.get("clientaddress") is None:
            False, "bug: clientaddress is None"
        if obdict.get("clientaddress")[0] in ["127.0.0.1", "::1"]:
            self.wlock.acquire()
            if obdict["name"] in self.spmap:
                del self.spmap[obdict["name"]]
                self.cache["dumpservices"] = json.dumps(gen_result(self.spmap, True)) #sorted(self.spmap.items(), key=lambda t: t[0]), True))
            self.wlock.release()
            return  True
        return False, "no permission"
        
    ### management section - end ###
    
    @check_argsdeco({"name": str})
    @classify_local
    def getservice(self, obdict):
        """ func: get the port of a service
            return: portnumber
            name: servicename """
        if obdict["name"] not in self.spmap:
            return False
        return True, self.spmap[obdict["name"]]
    
    
class client_handler(commonscnhandler):
    server_version = 'simplescn/1.0 (client)'
    
    handle_local = False
    handle_remote = False
    webgui = False
    
    
    def handle_client(self, action):
        if action not in self.links["client"].validactions:
            self.send_error(400, "invalid action - client")
            return
        # redirect overrides handle_local, handle_remote
        if self.handle_remote == False and \
        "redirect" not in getattr(getattr(self.links["client"], action), "classify", set()) and \
        (self.handle_local == False or self.client_address2[0] not in ["127.0.0.1", "::1"]):
            self.send_error(403, "no permission - client")
            return
        if "admin" in getattr(getattr(self.links["client"], action), "classify", set()):
            #if self.client_cert is None:
            #    self.send_error(403, "no permission (no certrewrap) - admin")
            #    return
            if "admin" in self.links["auth_server"].realms:
                realm = "admin"
            else:
                realm = "client"
        else:
            realm = "client"
        # if redirect bypass
        if "redirect" not in getattr(getattr(self.links["client"], action), "classify", set()) and self.links["auth_server"].verify(realm, self.auth_info) == False:
            authreq = self.links["auth_server"].request_auth(realm)
            #self.cleanup_stale_data(max_serverrequest_size)
            ob = bytes(json.dumps(authreq), "utf-8")
            self.scn_send_answer(401, body=ob, docache=False)
            return
        
        
        obdict = self.parse_body()
        if obdict is None:
            return
        response = self.links["client"].access_main(action, **obdict)

        if response[0] == False:
            error = response[1]
            generror = generate_error(error)
            
            if isinstance(error, (str, AddressFail, VALError)):
                if isinstance(error, str) == False:
                    del generror["stacktrace"]
                jsonnized = json.dumps(gen_result(generror, False))
            else:
                if self.client_address2[0] not in ["127.0.0.1", "::1"]:
                    generror = generate_error("unknown")
                ob = bytes(json.dumps(gen_result(generror, False)), "utf-8")
                self.scn_send_answer(500, body=ob, mime="application/json", docache=False)
                return
        else:
            jsonnized = json.dumps(gen_result(response[1],response[0]))
        
        ob = bytes(jsonnized, "utf-8")
        if response[0] == False:
            self.scn_send_answer(400, body=ob, docache=False)
        else:
            self.scn_send_answer(200, body=ob, docache=False)

    def handle_server(self, action):
        if action not in self.links["client_server"].validactions:
            self.scn_send_answer(400, message="invalid action - server", docache=False)
            return
        
        if self.links["auth_server"].verify("server", self.auth_info) == False:
            authreq = self.links["auth_server"].request_auth("server")
            ob = bytes(json.dumps(authreq), "utf-8")
            self.cleanup_stale_data(max_serverrequest_size)
            self.scn_send_answer(401, body=ob, docache=False)
            return
        
        if action in self.links["client_server"].cache:
            # cleanup {} or smaller, protect against big transmissions
            self.cleanup_stale_data(2)
            
            ob = bytes(self.links["client_server"].cache[action], "utf-8")
            self.scn_send_answer(200, body=ob, docache=False)
            return
        
        obdict = self.parse_body(max_serverrequest_size)
        if obdict is None:
            return None
        try:
            func = getattr(self.links["client_server"], action)
            response = func(obdict)
            jsonnized = json.dumps(gen_result(response[1],response[0]))
        except Exception as e:
            error = generate_error("unknown")
            if self.client_address2[0] in ["127.0.0.1", "::1"]:
                error = generate_error(e)
            ob = bytes(json.dumps(gen_result(error, False)), "utf-8")
            self.scn_send_answer(500, body=ob, mime="application/json")
            return
        
        
        if jsonnized is None:
            jsonnized = json.dumps(gen_result(generate_error("jsonized None"), False))
            response[0] = False
        ob = bytes(jsonnized, "utf-8")
        if response[0] == False:
            self.scn_send_answer(400, body=ob, mime="application/json", docache=False)
        else:
            self.scn_send_answer(200, body=ob, mime="application/json", docache=False)
        
    def do_GET(self):
        if self.init_scn_stuff() == False:
            return
        if self.path == "/favicon.ico":
            if "favicon.ico" in self.statics:
                self.scn_send_answer(200, self.statics["favicon.ico"], docache=True)
            else:
                self.scn_send_answer(404, docache=True)
            return
        
        if self.webgui == False:
            self.scn_send_answer(404, message="no webgui enabled", docache=True)
        
        _path=self.path[1:].split("/")
        if _path[0] in ("","client","html","index"):
            self.html("client.html")
            return
        elif  _path[0]=="static" and len(_path)>=2:
            if _path[1] in self.statics:
                self.scn_send_answer(200, body=self.statics[_path[1]], docache=True)
                return
        elif len(_path)==2:
            self.handle_server(_path[0])
            return
        self.scn_send_answer(404, message="resource not found (GET)", docache=True)
    
    
    def do_POST(self):
        if self.init_scn_stuff() == False:
            return
        splitted = self.path[1:].split("/", 1)
        if len(splitted) == 1:
            resource = splitted[0]
            sub = ""
        else:
            resource = splitted[0]
            sub = splitted[1]
        
        if resource == "plugin":
            pluginm = self.links["client_server"].pluginmanager
            split2 = sub.split("/", 1)
            if len(split2) != 2:
                #self.cleanup_stale_data()
                self.scn_send_answer(400, message="no plugin/action specified")
                return
            plugin, action = split2
            
            if plugin not in pluginm.plugins:
                #self.cleanup_stale_data()
                self.scn_send_answer(404, message="plugin not available")
                return
            
            #pluginpw = "plugin:{}".format(plugin)
            #if self.links["auth_server"].verify(pluginpw, self.auth_info) == False and action not in pluginm.plugins[plugin].whitelist:
            #    authreq = self.links["auth_server"].request_auth(pluginpw)
            #    ob = bytes(json.dumps(authreq), "utf-8")
            #    self.scn_send_answer(401, ob)
            #    return
            # gui receive
            if hasattr(pluginm.plugins[plugin], "receive") == True:
                # not supported yet
                # don't forget redirect_hash
                if self.links["client"].redirect_addr != "":
                    # needs to implement http handshake and stop or don't analyze content
                    if hasattr(pluginm.plugins[plugin], "rreceive") == True:
                        ret = self.handle_plugin(pluginm.plugins[plugin].rreceive, action)
                    else:
                        ret = True
                    if ret == False:
                        return
                    self.send_response(200)
                    self.send_header("Connection", "keep-alive")
                    self.send_header("Cache-Control", "no-cache")
                    if self.headers.get("X-certrewrap") is not None:
                        self.send_header("X-certrewrap", self.headers.get("X-certrewrap").split(";")[1])
                    self.end_headers()
                    # send if not sent already
                    self.wfile.flush()
                    sockd = self.links["client"].use_plugin(self.links["client"].redirect_addr, \
                                        plugin, action, forcehash=self.links["client"].redirect_hash, originalcert=self.client_cert)
                    redout = threading.Thread(target=rw_socket, args=(self.connection, sockd), daemon=True)
                    redout.run()
                    rw_socket(sockd, self.connection)
                    return
                else:
                    self.handle_plugin(pluginm.plugins[plugin].receive, action)
        # for invalidating and updating, don't use connection afterwards 
        elif resource == "usebroken":
            self.handle_usebroken(sub)
        elif resource == "server":
            self.handle_server(sub)
        elif resource == "client":
            self.handle_client(sub)
        else:
            self.scn_send_answer(404, message="resource not found (POST)", docache=True)


class client_init(object):
    config_root = None
    plugins_config = None
    links = None
    run = True # necessary for some runmethods
    
    def __init__(self, confm, pluginm):
        logging.root.setLevel(confm.get("loglevel"))
        self.links = {"trusted_certhash": ""}
        self.links["config"] = confm
        self.links["config_root"] = confm.get("config")
        
        _cpath=os.path.join(self.links["config_root"],"client")
        init_config_folder(self.links["config_root"],"client")
        
        
        if check_certs(_cpath+"_cert") == False:
            logging.info("Certificate(s) not found. Generate new...")
            generate_certs(_cpath+"_cert")
            logging.info("Certificate generation complete")
        with open(_cpath+"_cert.pub", 'rb') as readinpubkey:
            pub_cert = readinpubkey.read().strip().rstrip() #why fail
        
        self.links["auth_client"] = scnauth_client()
        self.links["auth_server"] = scnauth_server(dhash(pub_cert))
        
        if confm.getb("webgui")!=False:
            logging.debug("webgui enabled")
            client_handler.webgui=True
            #load static files
            for elem in os.listdir(os.path.join(sharedir, "static")):
                with open(os.path.join(sharedir,"static",elem), 'rb') as _staticr:
                    client_handler.statics[elem]=_staticr.read()
        else:
            client_handler.webgui=False
        if confm.getb("cpwhash") == True:
            client_handler.handle_local = True
            # ensure that password is set when allowing remote access
            if confm.getb("remote") == True:
                client_handler.handle_remote = True
            self.links["auth_server"].init_realm("client", confm.get("cpwhash"))
        elif confm.getb("cpw") == True:
            client_handler.handle_local = True
            # ensure that password is set when allowing remote access
            if confm.getb("remote") == True:
                client_handler.handle_remote = True
            self.links["auth_server"].init_realm("client", dhash(confm.get("cpw")))
        
        if confm.getb("apwhash") == True:
            self.links["auth_server"].init_realm("admin", confm.get("apwhash"))
        elif confm.getb("apw") == True:
            self.links["auth_server"].init_realm("admin", dhash(confm.get("apw")))
            
        if confm.getb("spwhash") == True:
            self.links["auth_server"].init_realm("server", confm.get("spwhash"))
        elif confm.getb("spw") == True:
            self.links["auth_server"].init_realm("server", dhash(confm.get("spw")))
        

        with open(_cpath+"_name.txt", 'r') as readclient:
            _name = readclient.readline().strip().rstrip() # remove \n
            
        with open(_cpath+"_message.txt", 'r') as readinmes:
            _message = readinmes.read()
        #report missing file
        if None in [pub_cert, _name, _message]:
            raise(Exception("missing"))
        
        _name = _name.split("/")
        if len(_name)>2 or check_name(_name[0]) == False:
            logging.error("Configuration error in {}\nshould be: <name>/<port>\nor name contains some restricted characters".format(_cpath+"_name"))
            sys.exit(1)

        if confm.get("port") > -1:
            pass
        elif len(_name) >= 2:
            confm.set("port", _name[1])
        else: # fallback, configmanager autoconverts into string
            confm.set("port", client_port)
        port = confm.get("port")
        
        clientserverdict={"name": _name[0], "certhash": dhash(pub_cert),
                "priority": confm.get("priority"), "message": _message}
        
        self.links["client_server"] = client_server(clientserverdict)
        self.links["client_server"].pluginmanager = pluginm
        self.links["configmanager"] = confm
        

        client_handler.links = self.links
        
        # use timeout argument of BaseServer
        http_server.timeout = confm.get("timeout")
        if confm.getb("noserver") == False:
            self.links["hserver"] = http_server(("", port), _cpath+"_cert", client_handler, "Enter client certificate pw")
        self.links["client"] = client_client(_name[0], dhash(pub_cert), os.path.join(self.links["config_root"], "certdb.sqlite"), _cpath+"_cert", self.links)
        
        
    def serve_forever_block(self):
        self.links["hserver"].serve_forever()
        
    def serve_forever_nonblock(self):
        sthread = threading.Thread(target=self.serve_forever_block, daemon=True)
        sthread.start()


#specified seperately because of chicken egg problem
#"config":default_configdir
default_client_args = {
            "noplugins": ["False", bool, "<bool>: deactivate plugins"],
            "cpwhash": ["", str, "<hash>: sha256 hash of pw, higher preference than cpw (needed for remote control)"],
            "cpw": ["", str, "<pw>: password (cleartext) (needed for remote control)"],
            "apwhash": ["", str, "<hash>: sha256 hash of pw, higher preference than apw"],
            "apw": ["", str, "<pw>: password (cleartext)"],
            "spwhash": ["", str, "<hash>: sha256 hash of pw, higher preference than spw"],
            "spw": ["", str, "<pw>: password (cleartext)"],
            "noserver": ["False", bool, "<bool>: deactivate server component (deactivate also remote pw, notify support)"],
            "remote" : ["False", bool, "<bool>: remote reachable (not localhost) (needs cpwhash/file)"],
            "priority": [str(default_priority), int, "<int>: set priority"],
            "connect_timeout": [str(connect_timeout), int, "<int>: set timeout for connecting"],
            "timeout": [str(default_timeout), int, "<int>: set default timeout"],
            "webgui": ["False", bool, "<bool>: enables webgui"],
            "loglevel": [str(default_loglevel), loglevel_converter, "<int/str>: loglevel"],
            "nocmd": ["False", bool, "<bool>: use no cmd"],
            "port": [str(-1), int, "<int>: port of server component, -1: use port in \"client_name.txt\""]}
             
overwrite_client_args={
            "config": [default_configdir, str, "<dir>: path to config dir"]}


def client_paramhelp():
    t = "# parameters (permanent)\n"
    for _key, elem in sorted(default_client_args.items(), key=lambda x: x[0]):
        t += "  * key: {}, default: {}, doc: {}\n".format(_key, elem[0], elem[2])
    t += "# parameters (non-permanent)\n"
    for _key, elem in sorted(overwrite_client_args.items(), key=lambda x: x[0]):
        t += "  * key: {}, value: {}, doc: {}\n".format(_key, elem[0], elem[2])
    return t

def cmdloop(clientinitm):
    while True:
        inp = input('urlgetformat:\naction=<action>&arg1=<foo>\nuse action=saveauth&auth=<realm>:<pw>&auth=<realm2>:<pw2> to save pws. Enter:\n')
        if inp in ["exit", "close", "quit"]:
            break
        # help
        if inp == "help":
            inp = "action=help"
        ret = clientinitm.links["client"].command(inp, callpw_auth=True)
        if ret[1] is not None:
            if ret[0] == True:
                print("Success: ", end="")
            else:
                print("Error: ", end="")
            if ret[2] == isself:
                print("This client:")
            elif ret[2] == None:
                print("Unknown partner, hash: {}:".format(ret[3]))
            else:
                print("Known, name: {} ({}):".format(ret[2][0],ret[2][1]))
            if isinstance(ret[1], dict):
                for elem in ret[1].items():
                    if isinstance(elem[1], str):
                        print("{}:{}".format(elem[0], elem[1].replace("\\n", "\n")))
                    else:
                        print("{}:{}".format(elem[0], elem[1]))
            else:
                print("Print direct", ret[1])
                print(ret[1])


