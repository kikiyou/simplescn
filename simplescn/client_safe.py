
"""
safe stuff (harm is limited, so useable for plugins) (client)
license: MIT, see LICENSE.txt
"""

import ssl
import socket
import logging
import abc


from simplescn.config import isself
from simplescn import EnforcedPortFail
from simplescn.tools import dhash, check_argsdeco, check_args, scnparse_url, check_updated_certs, classify_local, default_sslcont, check_local

class client_safe(object, metaclass=abc.ABCMeta):
    validactions_safe = {"get", "gethash", "help", "show", "register", "getlocal", "listhashes", "listnodenametypes", "listnames", "listnodenames", "listnodeall", "getservice", "registerservice", "listservices", "info", "check", "check_direct", "prioty_direct", "prioty", "ask", "getreferences", "cap", "findbyref", "delservice"}

    @property
    @abc.abstractmethod
    def hashdb(self):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def links(self):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def cert_hash(self):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def _cache_help(self):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def sslcont(self):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def name(self):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def brokencerts(self):
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def scntraverse_helper(self):
        raise NotImplementedError

    @abc.abstractmethod
    def do_request(self, _addr_or_con, _path, body=None, headers=None, forceport=False, forcehash=None, forcetraverse=False, sendclientcert=False):
        raise NotImplementedError

    @check_argsdeco()
    def help(self, obdict: dict):
        """ func: return help
            return: help """
        return True, {"help": self._cache_help}

    @check_argsdeco({"server": str})
    def register(self, obdict: dict):
        """ func: register client
            return: success or error
            server: address of server """
        _srvaddr = None
        if "hserver" in self.links:
            serversock = self.links["hserver"].socket
        else:
            return False, "cannot register without servercomponent"
        _srvaddr = scnparse_url(obdict.get("server"))
        if _srvaddr:
            self.scntraverse_helper.add_desttupel(_srvaddr)
        ret = self.do_request(obdict.get("server"), "/server/register", body={"name": self.name, "port": serversock.getsockname()[1], "update": self.brokencerts}, headers=obdict.get("headers"), sendclientcert=True, forcehash=obdict.get("forcehash"))

        if _srvaddr and (not ret[0] or ret[1].get("traverse", False)):
            self.scntraverse_helper.del_desttupel(_srvaddr)
        return ret

    @check_argsdeco()
    @classify_local
    def show(self, obdict: dict):
        """ func: show client stats
            return: client stats; port==0 means unixsockets """
        
        return True, {"name": self.name,
        "hash": self.cert_hash,
        "listen": self.links["hserver"].server_address,
        "port": self.links["hserver"].server_port}

    @check_argsdeco({"name": str, "port": int}, optional={"client": str})
    #@classify_local
    def registerservice(self, obdict: dict):
        """ func: register service (second way)
            return: success or error
            name: service name
            port: port number
            invisibleport: port is not shown (but can wrap)
            post: send http post request with certificate in header to service
            client: LOCAL client url (default: own client) """
        if obdict.get("client") is not None:
            return self.do_request(obdict.get("client", "::1-{}".format(self.links["hserver"].server_port)), "/server/registerservice", obdict, forcehash=self.cert_hash)
        else:
            return False, "no servercomponent/client available"

    @check_argsdeco({"name": str}, optional={"client": str})
    #@classify_local
    def delservice(self, obdict: dict):
        """ func: delete service (second way)
            return: success or error
            name: service name
            client: LOCAL client url (default: own client) """
        if obdict.get("client") is not None:
            return self.do_request(obdict.get("client", "::1-{}".format(self.links["hserver"].server_port)), "/server/delservice", obdict, forcehash=self.cert_hash)
        else:
            return False, "no servercomponent/client available"

    @check_argsdeco({"name": str}, optional={"client": str})
    def getservice(self, obdict: dict):
        """ func: get port of a service
            return: port of service
            name: service name
            client: client url (default: own client) """
        if obdict.get("client") is not None:
            client_addr = obdict["client"]
            del obdict["client"]
            _forcehash = obdict.get("forcehash")
        else:
            _forcehash = self.cert_hash
            client_addr = "::1-{}".format(self.links["server"].server_port)
        return self.do_request(client_addr, "/server/getservice", body={}, headers=obdict.get("headers"), forcehash=_forcehash)

    @check_argsdeco(optional={"client": str})
    def listservices(self, obdict: dict):
        """ func: list services with ports
            return port, service pairs
            client: client url (default: own client) """
        if obdict.get("client") is not None:
            client_addr = obdict["client"]
            _forcehash = obdict.get("forcehash")
            del obdict["client"]
        else:
            _forcehash = self.cert_hash
            client_addr = "::1-{}".format(self.links["hserver"].server_port)
        _tservices = self.do_request(client_addr, "/server/dumpservices", body={}, headers=obdict.get("headers"), forceport=True, forcehash=_forcehash)
        if not _tservices[0]:
            return _tservices
        out = sorted(_tservices[1].items(), key=lambda t: t[0])
        return _tservices[0], {"items": out, "map": ["name", "port"]}, _tservices[2], _tservices[3]

    @check_argsdeco({"server": str, "name": str, "hash": str})
    def get(self, obdict: dict):
        """ func: fetch client address from server
            return: address, port, name, security, hash, traverse_needed, traverse_address
            server: server url
            name: client name
            hash: client hash """
        _getret = self.do_request(obdict["server"], "/server/get", body={"hash": obdict.get("hash"), "name": obdict.get("name")}, headers=obdict.get("headers"), forcehash=obdict.get("forcehash"))
        if not _getret[0] or not check_args(_getret[1], {"address": str, "port": int}):
            return _getret
        if _getret[1].get("port", 0) < 1:
            return False, "port < 1: {}".format(_getret[1]["port"])
        # case: client runs on server
        if check_local(_getret[1]["address"]):
            # use serveraddress instead
            addr, port = scnparse_url(obdict["server"])
            _getret[1]["address"] = addr
        return _getret

    @check_argsdeco({"address": str})
    def gethash(self, obdict: dict):
        """ func: fetch hash from address
            return: hash, certificate (stripped = scn compatible)
            address: node url """
        if obdict["address"] in ["", " ", None]:
            return False, "address is empty"
        try:
            cont = default_sslcont()
            _addr = scnparse_url(obdict["address"], force_port=False)
            sock = socket.create_connection(_addr)
            sock = cont.wrap_socket(sock, server_side=False)
            pcert = ssl.DER_cert_to_PEM_cert(sock.getpeercert(True)).strip().rstrip()
            return True, {"hash": dhash(pcert), "cert": pcert}
        except ssl.SSLError:
            return False, "server speaks no tls 1.2"
        except ConnectionRefusedError:
            return False, "server does not exist"
        except EnforcedPortFail as exc:
            return False, exc.msg
        except Exception as exc:
            logging.error(exc)
            return False, exc

    @check_argsdeco({"address": str})
    def ask(self, obdict: dict):
        """ func: retrieve localname of a address/None if not available
            return: local information about remote url
            address: node url """
        _ha = self.gethash(obdict)
        if not _ha[0]:
            return _ha
        _hadict = _ha[1][dict]
        if _hadict.get("hash") == self.cert_hash:
            return True, {"localname": isself, "hash": self.cert_hash, "cert": _hadict["cert"]}
        hasho = self.hashdb.get(_hadict["hash"])
        if hasho:
            return True, {"localname": hasho[0], "security": hasho[3], "hash": _hadict["hash"], "cert": _hadict["cert"]}
        else:
            return True, {"hash": _hadict["hash"], "cert": _hadict["cert"]}

    @check_argsdeco({"server": str})
    def listnames(self, obdict: dict):
        """ func: sort and list names from server
            return: sorted list of client names with additional informations
            server: server url """
        _tnames = self.do_request(obdict["server"], "/server/dumpnames", body={}, headers=obdict.get("headers"), forcehash=obdict.get("forcehash"))
        if not _tnames[0]:
            return _tnames
        out = []
        for name, _hash, _security in sorted(_tnames[1], key=lambda t: t[0]):
            if _hash == self.cert_hash:
                out.append((name, _hash, _security, isself))
            else:
                out.append((name, _hash, _security, self.hashdb.certhash_as_name(_hash)))
        return _tnames[0], {"items": out, "map":["name", "hash", "security", "localname"]}, _tnames[2], _tnames[3]

    @check_argsdeco(optional={"address": str})
    def info(self, obdict: dict):
        """ func: retrieve info of node
            return: info section
            address: remote node url (default: own client) """
        if obdict.get("address") is not None:
            _addr = obdict["address"]
            _forcehash = obdict.get("forcehash")
            del obdict["address"]
        else:
            _forcehash = self.cert_hash
            _addr = "::1-{}".format(self.links["hserver"].server_port)
        ret = self.do_request(_addr, "/server/info", body={}, headers=obdict.get("headers"), forceport=True, forcehash=_forcehash)
        return ret

    @check_argsdeco(optional={"address": str})
    def cap(self, obdict: dict):
        """ func: retrieve capabilities of node
            return: info section
            address: remote node url (default: own client) """
        if obdict.get("address") is not None:
            _addr = obdict["address"]
            _forcehash = obdict.get("forcehash")
            del obdict["address"]
        else:
            _addr = "::1-{}".format(self.links["hserver"].server_port)
            _forcehash = self.cert_hash
        return self.do_request(_addr, "/server/cap", body={}, headers=obdict.get("headers"), forceport=True, forcehash=_forcehash)

    @check_argsdeco(optional={"address": str})
    def prioty_direct(self, obdict: dict):
        """ func: retrieve priority of node
            return: info section
            address: remote node url (default: own client) """
        if obdict.get("address") is not None:
            _addr = obdict["address"]
            del obdict["address"]
            _forcehash = obdict.get("forcehash")
        else:
            _forcehash = self.cert_hash
            _addr = "::1-{}".format(self.links["hserver"].server_port)
        return self.do_request(_addr, "/server/prioty", body={}, headers=obdict.get("headers"), forcehash=_forcehash, forceport=True)

    @check_argsdeco({"server": str, "name": str, "hash": str})
    def prioty(self, obdict: dict):
        """ func: retrieve priority and type of a client on a server
            return: priority and type
            server: server url
            name: client name
            hash: client hash """
        temp = self.get(obdict)
        if not temp[0]:
            return temp
        temp[1]["forcehash"] = obdict.get("hash")
        return self.prioty_direct({"address":"{address}-{port}".format(**temp[1])})

    @check_argsdeco({"address": str, "hash": str}, optional={"security": str})
    def check_direct(self, obdict: dict):
        """ func: check if a address is reachable; update local information when reachable
            return: priority, type, certificate security; return [3] == new hash of client
            address: node url
            hash: node certificate hash
            security: set/verify security """
        # force hash if hash is from client itself
        if obdict["hash"] == self.cert_hash:
            obdict["forcehash"] = self.cert_hash
            if obdict.get("security", "valid") != "valid":
                return False, "Error: own client is marked not valid"
        # only use forcehash if requested elsewise handle hash mismatch later
        prioty_ret = self.prioty_direct({"address": obdict["address"], "forcehash": obdict.get("forcehash")})
        if not prioty_ret[0]:
            return prioty_ret
        # don't query if hash is from client itself
        if obdict["hash"] == self.cert_hash:
            hashdbo = None
        else:
            hashdbo = self.hashdb.get(obdict["hash"])
        # handle hash mismatch
        if prioty_ret[3] != obdict["hash"] or obdict.get("security", "valid") != "valid":
            address, port = scnparse_url(obdict.get("address"), False)
            check_ret = check_updated_certs(address, port, [(obdict.get("hash"), "insecure"), ], newhash=prioty_ret[3])
            if check_ret in [None, []] and obdict.get("security", "valid") == "valid":
                return False, "MITM attack?, Certmismatch"
            elif check_ret in [None, []]:
                return False, "MITM?, Wrong Server information?, Certmismatch and security!=valid"
            if obdict.get("security", "valid") == "valid":
                obdict["security"] = "insecure"
            # is in db and was valid before
            if hashdbo and hashdbo[3] == "valid":
                # invalidate old
                self.hashdb.changesecurity(obdict["hash"], obdict.get("security", "insecure"))
                # create unverified new, if former state was valid and is not in db
                newhashdbo = self.hashdb.get(prioty_ret[3])
                if not newhashdbo:
                    self.hashdb.addhash(hashdbo[0], prioty_ret[3], hashdbo[1], hashdbo[2], "unverified")
                    newhashdbo = self.hashdb.get(prioty_ret[3])
                # copy references
                self.hashdb.copyreferences(hashdbo[4], newhashdbo[4])
                # replace hashdbo by newhashdbo
                hashdbo = newhashdbo
        # add security field, init as unverified
        prioty_ret[1]["security"] = "unverified"
        if hashdbo:
            # is hashdbo/newhashdbo in db
            self.hashdb.changepriority(prioty_ret[3], prioty_ret[1]["priority"])
            self.hashdb.changetype(prioty_ret[3], prioty_ret[1]["type"])
            # return security of current hash
            prioty_ret[1]["security"] = hashdbo[3]
        elif obdict["hash"] == self.cert_hash:
            # is client itself
            # valid because (hashdbo=None)
            prioty_ret[1]["security"] = "valid"
        return prioty_ret

    # reason for beeing seperate from get: to detect if a minor or a bigger error happened
    @check_argsdeco({"server": str, "name": str, "hash": str})
    def check(self, obdict: dict):
        """ func: check if client is reachable; update local information when reachable
            return: priority, type, certificate security, (new-)hash (client)
            server: server url
            name: client name
            hash: client certificate hash """
        get_ret = self.get(obdict)
        if not get_ret[0]:
            return get_ret
        # request forcehash if not valid
        if get_ret[1].get("security", "valid") != "valid":
            _forcehash = get_ret[1].get("hash")
        else:
            _forcehash = None
        newaddress = "{address}-{port}".format(**get_ret[1])
        direct_ret = self.check_direct({"address": newaddress, "hash": obdict["hash"], "forcehash":_forcehash, "security": get_ret[1].get("security", "valid")})
        # return new hash in hash field
        if direct_ret[0]:
            direct_ret[1]["hash"] = direct_ret[3]
        return direct_ret[0], direct_ret[1], get_ret[2], get_ret[3]
    ### local management ###

    @check_argsdeco({"hash": str})
    @classify_local
    def getlocal(self, obdict: dict):
        """ func: retrieve local information about hash (hashdb)
            return: local information about certificate hash
            hash: node certificate hash """
        out = self.hashdb.get(obdict["hash"])
        if out is None:
            return False, "Not in db"
        ret = \
        {
            "name": out[0],
            "type": out[1],
            "priority": out[2],
            "security": out[3],
            "certreferenceid": out[4]
        }
        return True, ret

    @check_argsdeco({"name": str}, optional={"filter": str})
    @classify_local
    def listhashes(self, obdict: dict):
        """ func: list hashes in hashdb
            return: list with local informations
            name: entity name
            filter: filter nodetype (server/client) (default: all) """
        _name = obdict.get("name")
        temp = self.hashdb.listhashes(_name, obdict.get("filter", None))
        if temp is None:
            return False
        else:
            return True, {"items":temp, "map": ["hash", "type", "priority", "security", "certreferenceid"]}

    @check_argsdeco()
    @classify_local
    def listnodenametypes(self, obdict: dict):
        """ func: list entity names with type
            return: name, type list """
        temp = self.hashdb.listnodenametypes()
        if temp is None:
            return False
        else:
            return True, {"items":temp, "map": ["name", "type"]}

    @check_argsdeco(optional={"filter": str})
    @classify_local
    def listnodenames(self, obdict: dict):
        """ func: list entity names
            return: list entity names
            filter: filter nodetype (server/client) (default: all) """
        temp = self.hashdb.listnodenames(obdict.get("filter", None))
        if temp is None:
            return False
        else:
            return True, {"items":temp, "map": ["name"]}

    @check_argsdeco(optional={"filter": str})
    @classify_local
    def listnodeall(self, obdict: dict):
        """ func: list nodes with all informations
            return: list with nodes with all information
            filter: filter nodetype (server/client) (default: all) """
        temp = self.hashdb.listnodeall(obdict.get("filter", None))
        if temp is None:
            return False
        else:
            return True, {"items":temp, "map": ["name", "hash", "type", "priority", "security", "certreferenceid"]}

    @check_argsdeco(optional={"filter": str, "hash": str, "certreferenceid": int})
    @classify_local
    def getreferences(self, obdict: dict):
        """ func: get references of a node certificate hash
            return: reference, referencetype list for hash/referenceid
            hash: local hash (or use certreferenceid)
            certreferenceid: reference id of certificate hash (or use hash)
            filter: filter reference type """
        if obdict.get("certreferenceid") is None:
            _hash = obdict.get("hash")
            _tref = self.hashdb.get(_hash)
            if _tref is None:
                return False, "certhash does not exist: {}".format(_hash)
            _tref = _tref[4]
        else:
            _tref = obdict.get("certreferenceid")
        temp = self.hashdb.getreferences(_tref, obdict.get("filter", None))
        if temp is None:
            return False
        return True, {"items": temp, "map": ["reference", "type"]}

    @check_argsdeco({"reference": str})
    @classify_local
    def findbyref(self, obdict: dict):
        """ func:find nodes in hashdb by reference
            return: certhash with additional informations
            reference: reference """
        temp = self.hashdb.findbyref(obdict["reference"])
        if temp is None:
            return False, "reference does not exist: {}".format(obdict["reference"])
        return True, {"items":temp, "map": ["name", "hash", "type", "priority", "security", "certreferenceid"]}

