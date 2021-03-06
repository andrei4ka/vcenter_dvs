#!/usr/bin/env python
import sys
import atexit
import argparse
import urllib3
import yaml
import time
from pyVim import connect

#import ssl

#ssl._create_default_https_context = ssl._create_unverified_context

urllib3.disable_warnings()

# $ virtual_machine_device_info.py -s vcsa -u my_user -i 172.16.254.101


class VrouterMap(object):
    _options = None
    _search_index = None
    _data = None

    @property
    def options(self):
        if self._options:
            return self._options

        parser = argparse.ArgumentParser()

        parser.add_argument('-s', '--host',
                            required = True,
                            action = 'store',
                            help = 'Remote host to connect to')

        parser.add_argument('-u', '--user',
                            required = True,
                            action = 'store',
                            help = 'User name to use when connecting to host')

        parser.add_argument('-p', '--password',
                            required = False,
                            action = 'store',
                            help = 'Password to use when connecting to host')

        parser.add_argument('-i', '--ip',
                            required = True,
                            action = 'store',
                            nargs = '+',
                            help = 'IP address of the VM to search for')

        parser.add_argument('-y', '--yaml',
                            required = False,
                            action='store_true',
                            default = False,
                            help ='Yaml format output')
        parser.set_defaults(yaml = False)

        self._options = parser.parse_args()
        return self._options

    @property
    def search_index(self):
        if self._search_index:
            return self._search_index

        # form a connection...
        si = connect.SmartConnect(
            host=self.options.host,
            user=self.options.user,
            pwd=self.options.password,
            port=443,
        )

        # Note: from daemons use a shutdown hook to do this, not the atexit
        atexit.register(connect.Disconnect, si)

        # http://pubs.vmware.com/vsphere-55/topic/com.vmware.wssdk.apiref.doc/vim.SearchIndex.html
        self._search_index = si.content.searchIndex
        return self._search_index

    def esxi_ip_get(self, vrouter_private_ip=None):
        try:
            esxi_object = self.search_index.FindByIp(None, vrouter_private_ip, True)
            if not esxi_object:
                return None
            esxi_host_name = esxi_object.runtime.host.name
            if not esxi_host_name:
                return None
            return esxi_host_name
        except TypeError:
            return None

    def retrieve_esxi_ip(self, vrouter_private_ip=None):
        for retry in xrange(10):
            esxi_ip = self.esxi_ip_get(vrouter_private_ip)
            if esxi_ip is not None:
                return esxi_ip
            self.debug("Can not get ip will try one more time")
            time.sleep(5)
        self.debug("Could not get association for that ip: ", vrouter_private_ip)
        return None

    @property
    def data(self):
        """
        :return: Mappings of the vcenter ips to the esxi ips
        :rtype: dict
        """
        if self._data:
            return self._data
        self._data = {}
        for vrouter_ip in self.options.ip:
            esxi_ip = self.retrieve_esxi_ip(vrouter_ip)
            if esxi_ip is None:
                continue
            self._data[vrouter_ip] = esxi_ip
        return self._data

    def output_yaml(self):
        print(yaml.dump(
            {'esxi_mapping': self.data},
            explicit_start=True,
            default_flow_style=False,
        ))

    def output_text(self):
        map_mask = '{vcenter}:{vrouter}'
        for vrouter_ip in self.data:
            print(map_mask.format(vcenter=self.data[vrouter_ip], vrouter=vrouter_ip))

    def debug(self, *args):
        sys.stderr.write(' '.join(args) + "\n")

    def main(self):
        if self.options.yaml:
            self.output_yaml()
        else:
            self.output_text()


if __name__ == '__main__':
    vm = VrouterMap()
    vm.main()
