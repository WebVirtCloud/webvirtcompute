#
# libvrt - libvirt wrapper class
#

import re
import libvirt
from . import util
from xml.etree import ElementTree


class wvmConnect(object):

    def __init__(self):
        self.wvm = libvirt.open('qemu:///system')

    def get_cap_xml(self):
        return self.wvm.getCapabilities()

    def is_kvm_supported(self):
        return util.is_kvm_available(self.get_cap_xml())

    def get_host_info(self):
        nodeinfo = self.wvm.getInfo()
        processor = util.get_xml_data(self.wvm.getSysinfo(0), 'processor/entry[6]')
        return {
            'hostname': self.wvm.getHostname(),
            'arch': nodeinfo[0],
            'memory': nodeinfo[1] * (1024 ** 2),
            'cpus': nodeinfo[2],
            'processor': processor if processor else 'Unknown',
            'connection': self.wvm.getURI()
        }

    def get_host_type(self):
        return util.get_xml_data(self.get_cap_xml(), 'guest/arch/domain', 'type')

    def get_host_mem_usage(self):
        hostemem = self.wvm.getInfo()[1] * (1024**2)
        freemem = self.wvm.getMemoryStats(-1, 0)
        if isinstance(freemem, dict):
            mem = list(freemem.values())
            free = (mem[1] + mem[2] + mem[3]) * 1024
            percent = (100 - ((free * 100) / hostmem))
            usage = (hostmem - free)
            return {'size': hostmem, 'usage': usage, 'percent': round(percent)}
        return {'size': 0, 'usage': 0, 'percent': 0}

    def get_host_cpu_usage(self):
        prev_idle = prev_total = diff_usage = 0
        cpu = self.wvm.getCPUStats(-1, 0)
        if isinstance(cpu, dict):
            for num in range(2):
                idle = self.wvm.getCPUStats(-1, 0)['idle']
                total = sum(self.wvm.getCPUStats(-1, 0).values())
                diff_idle = idle - prev_idle
                diff_total = total - prev_total
                diff_usage = (1000 * (diff_total - diff_idle) / diff_total + 5) / 10
                prev_total = total
                prev_idle = idle
                if num == 0:
                    time.sleep(1)
                if diff_usage < 0:
                    diff_usage = 0
        return {'usage': round(diff_usage)}

    def get_storages(self):
        storages = []
        for pool in self.wvm.listStoragePools():
            storages.append(pool)
        for pool in self.wvm.listDefinedStoragePools():
            storages.append(pool)
        return storages

    def get_storage(self, name):
        return self.wvm.storagePoolLookupByName(name)

    def get_storage_usage(self, name):
        pool = self.get_storage(name)
        pool.refresh()
        if pool.isActive():
            size = pool.info()[1]
            free = pool.info()[3]
            used = size - free
            percent = (used * 100) / size
            return {'size': size, 'used': used, 'percent': percent}
        return {'size': 0, 'used': 0, 'percent': 0}

    def get_networks(self):
        virtnet = []
        for net in self.wvm.listNetworks():
            virtnet.append(net)
        for net in self.wvm.listDefinedNetworks():
            virtnet.append(net)
        return virtnet

    def refresh_storages(self):
        for pool in self.wvm.listStoragePools():
            stg = self.wvm.storagePoolLookupByName(pool)
            stg.refresh()

    def get_ifaces(self):
        interface = []
        for inface in self.wvm.listInterfaces():
            interface.append(inface)
        for inface in self.wvm.listDefinedInterfaces():
            interface.append(inface)
        return interface

    def get_iface(self, name):
        return self.wvm.interfaceLookupByName(name)

    def get_secrets(self):
        return self.wvm.listSecrets()

    def get_secret(self, uuid):
        return self.wvm.secretLookupByUUIDString(uuid)

    def get_volume_by_path(self, path):
        return self.wvm.storageVolLookupByPath(path)

    def get_network(self, net):
        return self.wvm.networkLookupByName(net)

    def get_instance(self, name):
        return self.wvm.lookupByName(name)

    def get_instance_status(self, name):
        dom = self.wvm.lookupByName(name)
        return dom.info()[0]

    def get_instances(self):
        instances = []
        for inst_id in self.wvm.listDomainsID():
            dom = self.wvm.lookupByID(int(inst_id))
            instances.append(dom.name())
        for name in self.wvm.listDefinedDomains():
            instances.append(name)
        return instances

    def get_snapshots(self):
        instance = []
        for snap_id in self.wvm.listDomainsID():
            dom = self.wvm.lookupByID(int(snap_id))
            if dom.snapshotNum(0) != 0:
                instance.append(dom.name())
        for name in self.wvm.listDefinedDomains():
            dom = self.wvm.lookupByName(name)
            if dom.snapshotNum(0) != 0:
                instance.append(dom.name())
        return instance

    def get_net_device(self):
        netdevice = []
        for dev in self.wvm.listAllDevices(0):
            xml = dev.XMLDesc(0)
            if util.get_xml_data(xml, 'capability', 'type') == 'net':
                netdevice.append(util.get_xml_data(xml, 'capability/interface'))
        return netdevice

    def get_host_instances(self):
        vname = []
        for name in self.get_instances():
            dom = self.get_instance(name)
            mem = util.get_xml_data(dom.XMLDesc(0), 'currentMemory')
            mem = round(int(mem) / 1024)
            cur_vcpu = util.get_xml_data(dom.XMLDesc(0), 'vcpu', 'current')
            if cur_vcpu:
                vcpu = cur_vcpu
            else:
                vcpu = util.get_xml_data(dom.XMLDesc(0), 'vcpu')
            vname.append({'name': dom.name(), 'status': dom.info()[0], 'uuid': dom.UUIDString(), 'vcpu': vcpu, 'memory': mem})
        return vname

    def close(self):
        self.wvm.close()


class wvmStorages(wvmConnect):

    def get_storages_info(self):
        storages = []
        for storage in self.get_storages():
            stg = self.get_storage(storage)
            active = bool(stg.isActive())
            s_type = util.get_xml_data(stg.XMLDesc(0), element='type')
            if active is True:
                for volume in  stg.listVolumes():
                    volumes = []
                    vol = stg.storageVolLookupByName(volume)
                    volumes.append({
                        'name': volume,
                        'type': util.get_xml_data(vol.XMLDesc(0), 'target/format', 'type'),
                        'size': vol.info()[1]
                    })
            storages.append({
                'name': storage,
                'active': active,
                'type': s_type,
                'volumes': volumes,
                'size': {
                    'total': stg.info()[1],
                    'used': stg.info()[2],
                    'free': stg.info()[3]
                },
                'autostart': bool(stg.autostart())
            })
        return storages

    def define_storage(self, xml, flag=0):
        self.wvm.storagePoolDefineXML(xml, flag)

    def create_storage_dir(self, name, target):
        xml = f"""
                <pool type='dir'>
                <name>{name}</name>
                <target>
                    <path>{target}</path>
                </target>
                </pool>"""
        self.define_storage(xml, 0)
        stg = self.get_storage(name)
        stg.create(0)
        stg.setAutostart(1)

    def create_storage_logic(self, name, source):
        xml = f"""
                <pool type='logical'>
                <name>{name}</name>
                  <source>
                    <device path='{source}'/>
                    <name>{name}</name>
                    <format type='lvm2'/>
                  </source>            
                  <target>
                       <path>/dev/{name}</path>
                  </target>
                </pool>"""
        self.define_storage(xml, 0)
        stg = self.get_storage(name)
        stg.build(0)
        stg.create(0)
        stg.setAutostart(1)

    def create_storage_ceph(self, name, pool, user, secret, host, host2=None, host3=None):
        xml = f"""
                <pool type='rbd'>
                <name>{name}</name>
                <source>
                    <name>{pool}</name>
                    <host name='{host}' port='6789'/>"""
        if host2:
            xml += f"""<host name='{host2}' port='6789'/>"""
        if host3:
            xml += f"""<host name='{host3}' port='6789'/>"""

        xml += f"""<auth username='{user}' type='ceph'>
                        <secret uuid='{secret}'/>
                    </auth>
                </source>
                </pool>"""
        self.define_storage(xml, 0)
        stg = self.get_storage(name)
        stg.create(0)
        stg.setAutostart(1)

    def create_storage_netfs(self, name, host, source, format, target):
        xml = f"""
                <pool type='nfs'>
                <name>{name}</name>
                <source>
                    <host name='{host}'/>
                    <dir path='{source}'/>
                    <format type='{format}'/>
                </source>
                <target>
                    <path>{target}</path>
                </target>
                </pool>"""
        self.define_storage(xml, 0)
        stg = self.get_storage(name)
        stg.create(0)
        stg.setAutostart(1)


class wvmStorage(wvmConnect):
    def __init__(self, pool):
        wvmConnect.__init__(self)
        self.pool = self.get_storage(pool)

    def get_name(self):
        return self.pool.name()

    def get_active(self):
        return bool(self.pool.isActive())

    def get_status(self):
        status = ['Not running', 'Initializing pool, not available', 'Running normally', 'Running degraded']
        try:
            return status[self.pool.info()[0]]
        except ValueError:
            return 'Unknown'

    def get_total_size(self):
        return self.pool.info()[1]

    def get_used_size(self):
        return self.pool.info()[3]

    def get_free_size(self):
        return self.pool.info()[3]

    def XMLDesc(self, flags):
        return self.pool.XMLDesc(flags)

    def createXML(self, xml, flags):
        self.pool.createXML(xml, flags)

    def createXMLFrom(self, xml, vol, flags):
        self.pool.createXMLFrom(xml, vol, flags)

    def define(self, xml):
        return self.wvm.storagePoolDefineXML(xml, 0)

    def is_active(self):
        return bool(self.pool.isActive())

    def get_uuid(self):
        return self.pool.UUIDString()

    def start(self):
        self.pool.create(0)

    def stop(self):
        self.pool.destroy()

    def delete(self):
        self.pool.undefine()

    def refresh(self):
        self.pool.refresh(0)

    def get_autostart(self):
        return bool(self.pool.autostart())

    def set_autostart(self, value):
        self.pool.setAutostart(value)

    def get_type(self):
        return util.get_xml_data(self.XMLDesc(0), element='type')

    def get_target_path(self):
        return util.get_xml_data(self.XMLDesc(0), 'target/path')

    def get_allocation(self):
        return int(util.get_xml_data(self.XMLDesc(0), 'allocation'))

    def get_available(self):
        return int(util.get_xml_data(self.XMLDesc(0), 'available'))

    def get_capacity(self):
        return int(util.get_xml_data(self.XMLDesc(0), 'capacity'))

    def get_pretty_allocation(self):
        return util.pretty_bytes(self.get_allocation())

    def get_pretty_available(self):
        return util.pretty_bytes(self.get_available())

    def get_pretty_capacity(self):
        return util.pretty_bytes(self.get_capacity())

    def get_volumes(self):
        try:
            self.refresh()
        except Exception:
            pass
        if self.get_active() is True:
            return self.pool.listVolumes()
        return []

    def get_volume(self, name):
        return self.pool.storageVolLookupByName(name)

    def get_volume_size(self, name):
        vol = self.get_volume(name)
        return vol.info()[1]

    def _vol_XMLDesc(self, name):
        vol = self.get_volume(name)
        return vol.XMLDesc(0)

    def del_volume(self, name):
        vol = self.pool.storageVolLookupByName(name)
        vol.delete(0)

    def get_volume_type(self, name):
        return util.get_xml_data(self._vol_XMLDesc(name), 'target/format', 'type')

    def get_volume_info(self, volname):
        return {
            'name': volname,
            'size': self.get_volume_size(volname),
            'type': self.get_volume_type(volname)
        }

    def get_volumes_info(self):
        try:
            self.refresh()
        except Exception:
            pass
        vols = self.get_volumes()
        vol_list = []

        for volname in vols:
            vol_list.append({
                'name': volname,
                'size': self.get_volume_size(volname),
                'type': self.get_volume_type(volname)
            })
        return vol_list

    def resize_volume(self, name, size):
        vol = self.get_volume(name)
        vol.resize(size)

    def create_volume(self, name, size, fmt='qcow2', metadata=False):
        storage_type = self.get_type()
        alloc = size
        if fmt == 'unknown':
            fmt = 'raw'
        if storage_type == 'dir':
            name += '.img'
            alloc = 0
        xml = f"""
            <volume>
                <name>{name}</name>
                <capacity>{size}</capacity>
                <allocation>{alloc}</allocation>
                <target>
                    <format type='{fmt}'/>
                </target>
            </volume>"""
        self.createXML(xml, metadata)

    def clone_volume(self, name, clone, fmt=None, metadata=False):
        storage_type = self.get_type()
        if storage_type == 'dir':
            clone += '.img'
        vol = self.get_volume(name)
        if fmt is None:
            fmt = self.get_volume_type(name)
        xml = f"""
            <volume>
                <name>{clone}</name>
                <capacity>0</capacity>
                <allocation>0</allocation>
                <target>
                    <format type='{fmt}'/>
                </target>
            </volume>"""
        self.createXMLFrom(xml, vol, metadata)


class wvmNetworks(wvmConnect):

    def get_networks_info(self):
        networks = []
        get_networks = self.get_networks()
        for network in get_networks:
            net = self.get_network(network)
            net_status = net.isActive()
            net_bridge = net.bridgeName()
            net_forwd = util.get_xml_data(net.XMLDesc(0), 'forward', 'mode')
            networks.append({
                'name': network,
                'status': net_status,
                'device': net_bridge,
                'forward': net_forwd
            })
        return networks

    def define_network(self, xml):
        self.wvm.networkDefineXML(xml)

    def create_network(self, name, forward, gateway, mask, dhcp, bridge, openvswitch, fixed=False):
        xml = """
            <network>
                <name>%s</name>""" % name
        if forward in ['nat', 'route', 'bridge']:
            xml += """<forward mode='%s'/>""" % forward
        xml += """<bridge """
        if forward in ['nat', 'route', 'none']:
            xml += """stp='on' delay='0'"""
        if forward == 'bridge':
            xml += """name='%s'""" % bridge
        xml += """/>"""
        if openvswitch is True:
            xml += """<virtualport type='openvswitch'/>"""
        if forward != 'bridge':
            xml += """
                        <ip address='%s' netmask='%s'>""" % (gateway, mask)
            if dhcp:
                xml += """<dhcp>
                            <range start='%s' end='%s' />""" % (dhcp[0], dhcp[1])
                if fixed:
                    fist_oct = int(dhcp[0].strip().split('.')[3])
                    last_oct = int(dhcp[1].strip().split('.')[3])
                    for ip in range(fist_oct, last_oct + 1):
                        xml += """<host mac='%s' ip='%s.%s' />""" % (util.randomMAC(), gateway[:-2], ip)
                xml += """</dhcp>"""

            xml += """</ip>"""
        xml += """</network>"""
        self.define_network(xml)
        net = self.get_network(name)
        net.create()
        net.setAutostart(1)


class wvmNetwork(wvmConnect):
    
    def __init__(self, net):
        wvmConnect.__init__(self)
        self.net = self.get_network(net)

    def get_name(self):
        return self.net.name()

    def XMLDesc(self, flags):
        return self.net.XMLDesc(flags)

    def define(self, xml):
        self.wvm.networkDefineXML(xml)

    def get_autostart(self):
        return bool(self.net.autostart())

    def set_autostart(self, value):
        self.net.setAutostart(value)

    def is_active(self):
        return bool(self.net.isActive())

    def get_uuid(self):
        return self.net.UUIDString()

    def get_bridge_device(self):
        try:
            return self.net.bridgeName()
        except Exception:
            return None

    def start(self):
        self.net.create()

    def stop(self):
        self.net.destroy()

    def delete(self):
        self.net.undefine()

    def get_ipv4_network(self):
        xml = self.XMLDesc(0)
        if not util.get_xml_data(xml, 'ip'):
            return None

        addrStr = util.get_xml_data(xml, 'ip', 'address')
        netmaskStr = util.get_xml_data(xml, 'ip', 'netmask')
        prefix = util.get_xml_data(xml, 'ip', 'prefix')

        if prefix:
            prefix = int(prefix)
            binstr = ((prefix * "1") + ((32 - prefix) * "0"))
            netmaskStr = str(IP(int(binstr, base=2)))

        if netmaskStr:
            netmask = IP(netmaskStr)
            gateway = IP(addrStr)
            network = IP(gateway.int() & netmask.int())
            ret = IP(str(network) + "/" + netmaskStr)
        else:
            ret = IP(str(addrStr))

        return ret

    def get_ipv4_forward(self):
        xml = self.XMLDesc(0)
        fw = util.get_xml_data(xml, 'forward', 'mode')
        forwardDev = util.get_xml_data(xml, 'forward', 'dev')
        return [fw, forwardDev]

    def get_ipv4_dhcp_range(self):
        xml = self.XMLDesc(0)
        dhcpstart = util.get_xml_data(xml, 'ip/dhcp/range[1]', 'start')
        dhcpend = util.get_xml_data(xml, 'ip/dhcp/range[1]', 'end')
        if not dhcpstart and not dhcpend:
            return None
        return [IP(dhcpstart), IP(dhcpend)]

    def get_ipv4_dhcp_range_start(self):
        dhcp = self.get_ipv4_dhcp_range()
        if not dhcp:
            return None
        return dhcp[0]

    def get_ipv4_dhcp_range_end(self):
        dhcp = self.get_ipv4_dhcp_range()
        if not dhcp:
            return None
        return dhcp[1]

    def can_pxe(self):
        xml = self.XMLDesc(0)
        forward = self.get_ipv4_forward()[0]
        if forward and forward != "nat":
            return True
        return bool(util.get_xml_data(xml, 'ip/dhcp/bootp', 'file'))

    def get_mac_ipaddr(self):
        fixed_mac = []
        xml = self.XMLDesc(0)
        tree = ElementTree.fromstring(xml)
        dhcp_list = tree.findall('ip/dhcp/host')
        for i in dhcp_list:
            fixed_mac.append({'host': i.get('ip'), 'mac': i.get('mac')})

        return fixed_mac
