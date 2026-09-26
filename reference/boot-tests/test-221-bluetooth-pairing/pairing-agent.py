#!/usr/bin/env python3
"""TEST SCAFFOLDING - NOT PART OF THE PROJECT.

Kept only as evidence for test 221: this is the agent that completed the SSP
handshake far enough to prove the tablet's controller and BlueZ agent path work.
Nothing in the repository installs or depends on it, and it is not deployed.

Minimal BlueZ pairing agent for the X710 bring-up test (test 221).

NoInputNoOutput = SSP "Just Works": it accepts confirmations and answers a
passkey request. It needs python3-dbus and python3-gi, neither of which the
shipped rootfs installs.

Three bugs were found while getting this to run, and they are why the file is
kept rather than described:
  * BlueZ's Agent1.Cancel takes NO arguments; declaring in_signature="o" makes
    dbus-python refuse to build the class at all.
  * dbus.mainloop.NativeMainLoop is abstract and cannot be instantiated; without
    python3-gi there is no runnable loop, so the package is required.
  * bluetoothctl cannot register an agent over ssh (it wants a session bus), so
    the agent must be built against the SYSTEM bus directly.
"""
import select
import sys

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()


class Agent(dbus.service.Object):
    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Release(self):
        print("AGENT Release", flush=True)

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        print("AGENT RequestAuthorization -> accept", flush=True)

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        print("AGENT AuthorizeService -> accept", flush=True)

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        print("AGENT RequestPinCode -> 0000", flush=True)
        return "0000"

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        print("AGENT RequestPasskey -> 0", flush=True)
        return dbus.UInt32(0)

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        print("AGENT DisplayPasskey %06d entered=%d" % (passkey, entered), flush=True)

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def DisplayPinCode(self, device, pincode):
        print("AGENT DisplayPinCode %s" % pincode, flush=True)

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        print("AGENT RequestConfirmation %06d -> accept" % passkey, flush=True)

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        print("AGENT Cancel", flush=True)


Agent(bus, "/gts9/agent")
mgr = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"),
                     "org.bluez.AgentManager1")
mgr.RegisterAgent("/gts9/agent", "NoInputNoOutput")
mgr.RequestDefaultAgent("/gts9/agent")
print("AGENT REGISTERED", flush=True)

from gi.repository import GLib
GLib.MainLoop().run()
