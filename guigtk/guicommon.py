#! /usr/bin/env python3


import sys
import os


from gi.repository import Gtk,Gdk


run=True

open_addresses={}

class gtkclient_template(Gtk.Builder):
    #builder=None
    links=None
    win=None
    dparam=None
    address=None
    #autoclose=0 #closes window after a timeperiod
    
    def __init__(self,links,_address,dparam):
        Gtk.Builder.__init__(self)
        self.links=links
        self.dparam=dparam
        self.address=_address
        
    def init2(self, _file):
        classname=type(self).__name__
        if self.address not in open_addresses:
            open_addresses[self.address]=[classname, self]
        elif open_addresses[self.address]==classname:
            open_addresses[self.address][1].grab_focus()
            return False
        else:
            open_addresses[self.address][1].close()
            open_addresses[self.address]=[classname, self]
        
        self.set_application(self.links["gtkclient"])
        self.add_from_file(_file)
        return True
        
    def do_requestdo(self,action,*requeststrs,parse=-1):
        requeststrs+=(self.dparam,)
        return self.links["gtkclient"].do_requestdo(action,*requeststrs,parse=parse)
    
    def close(self,*args):
        self.win.destroy()
        self.links["gtkclient"].remove_window(self.win)
        del open_addresses[self.address]
        del self


