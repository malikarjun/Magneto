#!/usr/bin/python

"""
Taken from examples/tree1024.py
Create a 64-host network on legacy switch, and run the CLI on it.
"""

from mininet.net import Mininet
from mininet.cli import CLI
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import OVSSwitch, Host, Node
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info
from mininet.link import TCLink
from math import ceil
import os,sys,argparse,re,time,json,pdb, threading, random,  csv



range1 = lambda start, end: range(start, end+1)

def back(topo):
    topo_back = {}
    for k in topo:
        for i in range1(*topo[k]):
            topo_back[i] = k
    return topo_back


topo_core = {1: [6, 9], 2: [10, 13], 3: [14, 17], 4: [18, 21], 5: [22, 25]}
topo_distro = {6: [26, 27], 7: [28, 29], 8: [30, 31], 9: [32, 33],
               10: [34, 35], 11: [36, 37], 12: [38, 39], 13: [40, 41],
               14: [42, 43], 15: [44, 45], 16: [46, 47], 17: [48, 49],
               18: [50, 51], 19: [52, 53], 20: [54, 55], 21: [56, 57],
               22: [58, 59], 23: [60, 61], 24: [62, 63], 25: [64, 65]}
topo_access = {26: [1, 2], 27: [3, 4], 28: [5, 6], 29: [7, 8], 30: [9, 10], 31:
    [11, 12], 32: [13, 14], 33: [15, 16], 34: [17, 18], 35: [19, 20], 36:
                   [21, 22], 37: [23, 24], 38: [25, 26], 39: [27, 28], 40: [29, 30], 41:
                   [31, 32], 42: [33, 34], 43: [35, 36], 44: [37, 38], 45: [39, 40], 46:
                   [41, 42], 47: [43, 44], 48: [45, 46], 49: [47, 48], 50: [49, 50], 51:
                   [51, 52], 52: [53, 54], 53: [55, 56], 54: [57, 58], 55: [59, 60], 56:
                   [61, 62], 57: [63, 64], 58: [65, 66], 59: [67, 68], 60: [69, 70], 61:
                   [71, 72], 62: [73, 74], 63: [75, 76], 64: [77, 78], 65: [79, 80]}
topo_subnet = {1: [[1, 4], [17, 20], [33, 36], [49, 52], [65, 68]],
               2: [[5, 8], [21, 24], [37, 40], [53, 56], [69, 72]],
               3: [[9, 12], [25, 28], [41, 44], [57, 60], [73, 76]],
               4: [[13, 16], [29, 32], [45, 48], [61, 64], [77, 80]]}

# Parent pointers are initialized using back function
topo_core_back = back(topo_core)
topo_distro_back = back(topo_distro)
topo_access_back = back(topo_access)
topo_subnet_back = {}

for k in topo_subnet:
    for l in topo_subnet[k]:
        for i in range1(*l):
            topo_subnet_back[i] = k


def treeNet(net, switches):
    '''
    @param net
        The Mininetnet network reference
    @param switches
        A list of switches which should be SDN enabled. Default is standalone
    '''
    info( '*** Adding controller\n' )
    c0=net.addController(name='c0',
            controller=RemoteController,
            protocol='tcp',
            port=6633)


    info( '*** Add switches\n')

    hs100 = {'bw':100,'delay':'10ms'} #Mbit/s
    hs1000 = {'bw':1000,'delay':'10ms'} #Mbit/s

    info( '*** Add core and distribution\n')
    for sw in topo_core:
        s_core = net.addSwitch('s'+str(sw), cls=OVSSwitch, failMode='standalone')

        for i in range1(*topo_core[sw]):
            switchName = 's'+str(i)
            s = None
            try:
                s = net.get(switchName)
            except KeyError:
                s = net.addSwitch(switchName, cls=OVSSwitch,
                        failMode='secure' if switchName in switches else
                        'standalone')
            link = net.addLink(s, s_core, cls=TCLink, **hs1000)

    info( '*** Add access\n')
    for sw in topo_distro:
        for i in range1(*topo_distro[sw]):
            switchName = 's'+str(i)
            s = None
            try:
                s = net.get(switchName)
            except KeyError:
                s = net.addSwitch(switchName, cls=OVSSwitch,
                        failMode='standalone')
            link = net.addLink(s, net.get('s'+str(sw)), cls=TCLink, **hs1000)

    info( '*** Add hosts\n')
    for sw in topo_access:
        for i in range1(*topo_access[sw]):
            hostName = 'h'+str(i)
            h = None
            try:
                h = net.get(hostName)
            except KeyError:
                h = net.addHost(hostName, defaultRoute=None)
            link = net.addLink(h, net.get('s'+str(sw)), cls=TCLink, **hs100)

    core_switches = topo_core.keys()
    core_switches.sort()

    # Add links between core switches
    i = 0
    while i < len(core_switches)-1:
        net.addLink(net.get('s'+str(core_switches[i])), net.get('s'+str(core_switches[i+1])), cls=TCLink, **hs1000)
        i += 1

    info('*** Starting network\n')
    net.build()

    # Set IP Addresses to each of the hosts
    for host in net.hosts:
        print('For host {0}, ip is 10.0.0.{1}'.format(str(host), str(host)[1:]))
        host.setIP('10.0.0.{0}'.format(str(host)[1:]))



    # Set MAC Addresses to each of the host by converting the host number to hexadecimal notation
    # Ask
    for host in net.hosts:
        if 'mirror' in str(host) or 's1' in str(host):
            continue
        mac = '00:00:00:00:00:' + hex(int(str(host)[1:]))[2:].zfill(2)
        host.setMAC(mac)

    info('*** Starting switches\n')
    # Start switches and connect the SDN enabled ones to the controller c0 before starting
    for switch in net.switches:
        if str(switch) in switches:
            info('*** switch connected to controller ', switch, '\n')
            switch.start([c0])
            # os.system('sudo ovs-vsctl set bridge \"' + str(switch) + '\" protocols=OpenFlow13')
        else:
            switch.start([])

    info('*** Post configure switches and hosts\n')


    generateFlows(net, list(switches))
    #
    # os.system('sh vlan.sh')
    # os.system('bash clear.sh')
    #
    # if len(args.switches) != 0:
    #     os.system('bash conff')

def generateFlows(net, switches, magnet_mac='00:ff:00:00:ff:00'):

    rule = '\nip,priority=1,nw_dst=10.0.0.{0},actions=mod_dl_dst:{1},mod_dl_src:{2},output:{3}'
    rule_2 = '\nip,priority=2,nw_dst=10.0.0.{0},in_port={1},actions=mod_dl_dst:{2},mod_dl_src:{3},{4}'
    for sw in switches:
        file_name = 'flows_{}'.format(sw)
        flows = open(file_name, 'w')
        for host in net.hosts:
            host_num = int(str(host)[1:])
            host_mac = '00:00:00:00:00:' + hex(host_num)[2:].zfill(2)
            out_port = 1

            for idx, ac_sw in enumerate(topo_distro[int(sw[1:])]):
                for hh in topo_access[ac_sw]:
                    if hh == host_num:
                        out_port = (idx + 2)

            flows.write(rule.format(str(host)[1:], host_mac, magnet_mac, out_port))
            flows.write(rule_2.format(str(host)[1:], out_port, host_mac, magnet_mac, 'in_port'))
        flows.close()
        os.system('sudo ovs-ofctl add-flows {0} {1}'.format(sw, file_name))


if __name__ == '__main__':
    # os.system('sudo mn -c')
    TOPO_FILE = 'topo_tree_adj_list'

    parser = argparse.ArgumentParser(description='Run a mininet simulation for tree topology')
    parser.add_argument('-c', '--cli', help='Display CLI on given topology.', action='store_true')
    parser.add_argument('-s', '--switches', help='''Names of switches to have
                        SDN. Switches are numbered in level-order of a tree
                        starting from 1. Enter a space seperated list''',
                        nargs='*', default={}, type=str)
    args = parser.parse_args()

    if args.cli:
        setLogLevel( 'info' )

    net = Mininet( topo=None, build=False, ipBase='10.0.0.0/8', autoSetMacs=True)
    treeNet(net, set(args.switches))
    print(net.get('s6').ports)

    if args.cli:
        CLI(net)
        net.stop()
        exit(0)

    net.stop()
    exit(0)