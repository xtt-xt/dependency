# -*- coding: utf-8 -*-

from mod.common.mod import Mod
import mod.client.extraClientApi as clientApi


@Mod.Binding(name="Script_NeteaseMod9sPMlz0K", version="0.0.1")
class Script_NeteaseMod9sPMlz0K(object):

    def __init__(self):
        pass

    @Mod.InitServer()
    def Script_NeteaseMod9sPMlz0KServerInit(self):
        import mod.server.extraServerApi as serverApi
        serverApi.RegisterSystem("Script_NeteaseMod9sPMlz0K", "server", "Script_NeteaseMod9sPMlz0K.Server.MyServerSystem")

    @Mod.DestroyServer()
    def Script_NeteaseMod9sPMlz0KServerDestroy(self):
        pass

    @Mod.InitClient()
    def Script_NeteaseMod9sPMlz0KClientInit(self):
        clientApi.RegisterSystem("Script_NeteaseMod9sPMlz0K", "client", "Script_NeteaseMod9sPMlz0K.Client.MyClientSystem")
    

    @Mod.DestroyClient()
    def Script_NeteaseMod9sPMlz0KClientDestroy(self):
        pass
