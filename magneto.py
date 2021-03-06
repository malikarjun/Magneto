# Copyright 2011-2012 James McCauley
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
An L2 learning switch.

It is derived from one written live for an SDN crash course.
It is somwhat similar to NOX's pyswitch in that it installs
exact-match rules for each flow.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str, str_to_dpid
from pox.lib.util import str_to_bool
from pox.lib.packet import ethernet, arp
from pox.lib.addresses import IPAddr, EthAddr
import time

log = core.getLogger()

class LearningSwitch (object):
  """
  The learning switch "brain" associated with a single OpenFlow switch.

  When we see a packet, we'd like to output it on a port which will
  eventually lead to the destination.  To accomplish this, we build a
  table that maps addresses to ports.

  We populate the table by observing traffic.  When we see a packet
  from some source coming from some port, we know that source is out
  that port.

  When we want to forward traffic, we look up the desintation in our
  table.  If we don't know the port, we simply send the message out
  all ports except the one it came in on.  (In the presence of loops,
  this is bad!).

  In short, our algorithm looks like this:

  For each packet from the switch:
  1) Use source address and switch port to update address/port table
  2) Is transparent = False and either Ethertype is LLDP or the packet's
     destination address is a Bridge Filtered address?
     Yes:
        2a) Drop packet -- don't forward link-local traffic (LLDP, 802.1x)
            DONE
  3) Is destination multicast?
     Yes:
        3a) Flood the packet
            DONE
  4) Port for destination address in our address/port table?
     No:
        4a) Flood the packet
            DONE
  5) Is output port the same as input port?
     Yes:
        5a) Drop packet and similar ones for a while
  6) Install flow table entry in the switch so that this
     flow goes out the appopriate port
     6a) Send the packet out appropriate port
  """
  def __init__ (self, connection):
    # Switch we'll be adding L2 learning switch capabilities to
    self.connection = connection

    # Our table
    self.macToPort = {}

    # We want to hear PacketIn messages, so we listen
    # to the connection
    connection.addListeners(self)
    magnetmac = '00:ff:00:00:ff:00'

    while(1):
      print('Sending seed ARP packets')

      for i in range(1,81):
        r = arp()
        r.hwtype = r.HW_TYPE_ETHERNET
        r.prototype = r.PROTO_TYPE_IP
        r.hwlen = 6
        r.protolen = r.protolen
        r.opcode = r.REPLY
        r.hwdst = EthAddr('00:00:00:00:00:00')
        r.protodst = IPAddr('10.0.0.{0}'.format(i))
        r.hwsrc = EthAddr(magnetmac)
        r.protosrc = IPAddr('10.0.0.{0}'.format(i))
        e = ethernet(type=ethernet.ARP_TYPE, src=EthAddr(magnetmac), dst=EthAddr('ff:ff:ff:ff:ff:ff')) # The dst should be unicast according to the paper
        # In case of unicast use this -> dst=EthAddr('00:00:00:00:00:' + hex(int(str(i)))[2:].zfill(2)))
        e.set_payload(r)
        log.debug("\nARPing for %s" % (str(r.protodst)))
        msg = of.ofp_packet_out()
        msg.data = e.pack()
        msg.actions.append(of.ofp_action_output(port=of.OFPP_ALL))
        connection.send(msg)

      time.sleep(5)



  def resend_packet (self, packet_in, out_port):
    """
    Instructs the switch to resend a packet that it had sent to us.
    "packet_in" is the ofp_packet_in object the switch had sent to the
    controller due to a table-miss.
    """
    msg = of.ofp_packet_out()
    msg.data = packet_in

    # Add an action to send to the specified port
    action = of.ofp_action_output(port = out_port)
    msg.actions.append(action)

    # Send message to switch
    self.connection.send(msg)

  def _handle_PacketIn (self, event):
    """
    Handle packet in messages from the switch to implement above algorithm.
    """

    packet = event.parsed

    self.macToPort[packet.src] = event.port # 1

    if packet.dst not in self.macToPort: # 4
      self.resend_packet(event.ofp, of.OFPP_ALL) # 4a
    else:
      port = self.macToPort[packet.dst]
      # 6
      log.debug("installing flow for %s.%i -> %s.%i" %
                (packet.src, event.port, packet.dst, port))
      msg = of.ofp_flow_mod()
      msg.match = of.ofp_match.from_packet(packet, event.port)
      msg.idle_timeout = 10
      msg.hard_timeout = 30
      msg.actions.append(of.ofp_action_output(port = port))
      msg.data = event.ofp # 6a
      self.connection.send(msg)


class magneto (object):
  """
  Waits for OpenFlow switches to connect and makes them learning switches.
  """
  def __init__ (self):
    """
    Initialize

    See LearningSwitch for meaning of 'transparent'
    'ignore' is an optional list/set of DPIDs to ignore
    """
    core.openflow.addListeners(self)

  def _handle_ConnectionUp (self, event):
    log.debug("Connection %s" % (event.connection,))
    LearningSwitch(event.connection)


def launch ():
  """
  Starts an L2 learning switch.
  """
  core.registerNew(magneto)
