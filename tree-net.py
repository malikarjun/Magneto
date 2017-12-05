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


    info('*** Add legacy switches\n')
    s1 = net.addSwitch('s1', cls=OVSSwitch, failMode='standalone')
    s2 = net.addSwitch('s2', cls=OVSSwitch, failMode='standalone')
    net.addLink(s1, s2)


    info('*** Add SDN switches\n')
    s3 = net.addSwitch('s3', cls=OVSSwitch, failMode='secure')
    net.addLink(s3, s1)
    net.addLink(s3, s2)

    info('*** Add Hosts\n')
    h1 = net.addHost('h1')
    net.addLink(h1, s1)
    h2 = net.addHost('h2')
    net.addLink(h2, s2)


    info('*** Starting network\n')
    net.build()

    info('*** Starting switches\n')
    # Start switches and connect the SDN enabled ones to the controller c0 before starting
    for switch in net.switches:
        if str(switch) in switches:
            info('*** switch connected to controller ',switch,'\n')
            switch.start([c0])
            # os.system('sudo ovs-vsctl set bridge \"'+str(switch)+'\" protocols=OpenFlow13')
        else:
            switch.start([])




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

    if args.cli:
        CLI(net)
        net.stop()
        exit(0)

    net.stop()
    exit(0)