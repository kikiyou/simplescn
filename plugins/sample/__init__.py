

###### created by pluginmanager ######
# specifies the interfaces
# interfaces

# configmanager (see common)
# config

# resources which can be accessed
# resources

# plugin path
# path


###### created by pluginmanager end ######



# defaults for config (needed)
defaults={}

# initialises plugin. Returns False or Exception for not loading  (needed)
def init():
    #global gtk_node_iface
    #global gtk_server_iface
    print("Hello World")
    return True


def sampleaction(url, dheader):
    print("Hello actions: "+url)
    return "Hello actions, return: "+url


def sampleaction_cmd():
    print("Hello actions world")
    return "Hello actions world"
    
# dict, just shows up in cmd, do localisation in plugin 
# please don't localise dict keys
cmd_node_actions={"foo-action": (sampleaction_cmd, "localized description")}

# do it this way
cmd_node_localized_actions={"Aktion": "foo-action"}

# iterable, for node actions, just shows up in gui, do localization in plugin
gui_node_actions=[{"text":"foo-actionname","action":sampleaction, "icon":"optionalfoo-iconlocation"}, ]

# iterable, for server actions, just shows up in gui, do localization in plugin
gui_server_actions=[{"text":"foo-actionname","action":sampleaction, "icon":"optionalfoo-iconlocation"}, ]




#def gui_server_iface(gui, _name, _hash, _address):
#    pass
#    return widget

#def gui_node_iface(gui, _name, _hash, _address):
#    pass
#    return widget

### uncomment for being accessable by internet
### client:
# def receive(action, _socket, _cert, certhash):
#     pass
## executed when redirected, return False, when redirect should not be executed
# def rreceive(action, _socket, _cert, certhash):
#     pass
### server:
# def sreceive(action, _socket, _cert, certhash):
#     pass
