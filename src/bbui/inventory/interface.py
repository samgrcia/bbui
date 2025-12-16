from yaml import dump
class Interface():
    def __init__(self,
                 interface : str,
                 addr_gen_mode6 : str | None = None,
                 ageingtime : str | None = None,
                 arp_interval : str | None = None,
                 arp_ip_target : str | None = None,
                 autoconnect : str | None = None,
                 dhcp_client_id : str | None = None,
                 dns4 : str | None = None,
                 dns4_ignore_auto : str | None = None,
                 dns4_search : str | None = None,
                 dns6 : str | None = None,
                 dns6_ignore_auto : str | None = None,
                 dns6_search : str | None = None,
                 downdelay : str | None = None,
                 egress : str | None = None,
                 flags : str | None = None,
                 forwarddelay : str | None = None,
                 gsm : str | None = None,
                 gw4 : str | None = None,
                 gw4_ignore_auto : str | None = None,
                 gw6 : str | None = None,
                 gw6_ignore_auto : str | None = None,
                 hairpin : str | None = None,
                 hellotime : str | None = None,
                 ignore_unsupported_suboptions : str | None = None,
                 ingress : str | None = None,
                 infiniband_mac : str | None = None,
                 ip4 : str | None = None,
                 ip6 : str | None = None,
                 ip_privacy6 : str | None = None,
                 ip_tunnel_dev : str | None = None,
                 ip_tunnel_input_key : str | None = None,
                 ip_tunnel_local : str | None = None,
                 ip_tunnel_output_key : str | None = None,
                 ip_tunnel_remote : str | None = None,
                 master : str | None = None,
                 maxage : str | None = None,
                 may_fail4 : str | None = None,
                 method4 : str | None = None,
                 method6 : str | None = None,
                 miimon : str | None = None,
                 mode : str | None = None,
                 mtu : str | None = None,
                 network : str | None = None,
                 never_default4 : str | None = None,
                 path_cost : str | None = None,
                 physical_device : str | None = None,
                 primary : str | None = None,
                 priority : str | None = None,
                 route_metric4 : str | None = None,
                 route_metric6 : str | None = None,
                 routes4 : str | None = None,
                 routes4_extended : str | None = None,
                 routes6 : str | None = None,
                 routes6_extended : str | None = None,
                 routing_rules4 : str | None = None,
                 runner : str | None = None,
                 runner_fast_rate : str | None = None,
                 runner_hwaddr_policy : str | None = None,
                 skip : str | None = None,
                 slave_type : str | None = None,
                 slavepriority : str | None = None,
                 ssid : str | None = None,
                 state : str | None = None,
                 stp : str | None = None,
                 transport_mode : str | None = None,
                 type : str = "ethernet",
                 updelay : str | None = None,
                 vlandev : str | None = None,
                 vlanid : str | None = None,
                 vpn : str | None = None,
                 vxlan_id : str | None = None,
                 vxlan_local : str | None = None,
                 vxlan_remote : str | None = None,
                 wifi : str | None = None,
                 wifi_sec : str | None = None,
                 wireguard : str | None = None,
                 xmit_hash_policy : str | None = None,
                 zone : str | None = None,
                 ) -> None:
        
        # Init
        self.attributes = {}
        self.interface = interface
        self.attributes['addr_gen_mode6'] = addr_gen_mode6
        self.attributes['ageingtime'] = ageingtime
        self.attributes['arp_interval'] = arp_interval
        self.attributes['arp_ip_target'] = arp_ip_target
        self.attributes['autoconnect'] = autoconnect
        self.attributes['dhcp_client_id'] = dhcp_client_id
        self.attributes['dns4'] = dns4
        self.attributes['dns4_ignore_auto'] = dns4_ignore_auto
        self.attributes['dns4_search'] = dns4_search
        self.attributes['dns6'] = dns6
        self.attributes['dns6_ignore_auto'] = dns6_ignore_auto
        self.attributes['dns6_search'] = dns6_search
        self.attributes['downdelay'] = downdelay
        self.attributes['egress'] = egress
        self.attributes['flags'] = flags
        self.attributes['forwarddelay'] = forwarddelay
        self.attributes['gsm'] = gsm
        self.attributes['gw4'] = gw4
        self.attributes['gw4_ignore_auto'] = gw4_ignore_auto
        self.attributes['gw6'] = gw6
        self.attributes['gw6_ignore_auto'] = gw6_ignore_auto
        self.attributes['hairpin'] = hairpin
        self.attributes['hellotime'] = hellotime
        self.attributes['ignore_unsupported_suboptions'] = ignore_unsupported_suboptions
        self.attributes['ingress'] = ingress
        self.attributes['infiniband_mac'] = infiniband_mac
        self.attributes['ip4'] = ip4
        self.attributes['ip6'] = ip6
        self.attributes['ip_privacy6'] = ip_privacy6
        self.attributes['ip_tunnel_dev'] = ip_tunnel_dev
        self.attributes['ip_tunnel_input_key'] = ip_tunnel_input_key
        self.attributes['ip_tunnel_local'] = ip_tunnel_local
        self.attributes['ip_tunnel_output_key'] = ip_tunnel_output_key
        self.attributes['ip_tunnel_remote'] = ip_tunnel_remote
        self.attributes['master'] = master
        self.attributes['maxage'] = maxage
        self.attributes['may_fail4'] = may_fail4
        self.attributes['method4'] = method4
        self.attributes['method6'] = method6
        self.attributes['miimon'] = miimon
        self.attributes['mode'] = mode
        self.attributes['mtu'] = mtu
        self.attributes['network'] = network
        self.attributes['never_default4'] = never_default4
        self.attributes['path_cost'] = path_cost
        self.attributes['physical_device'] = physical_device
        self.attributes['primary'] = primary
        self.attributes['priority'] = priority
        self.attributes['route_metric4'] = route_metric4
        self.attributes['route_metric6'] = route_metric6
        self.attributes['routes4'] = routes4
        self.attributes['routes4_extended'] = routes4_extended
        self.attributes['routes6'] = routes6
        self.attributes['routes6_extended'] = routes6_extended
        self.attributes['routing_rules4'] = routing_rules4
        self.attributes['runner'] = runner
        self.attributes['runner_fast_rate'] = runner_fast_rate
        self.attributes['runner_hwaddr_policy'] = runner_hwaddr_policy
        self.attributes['skip'] = skip
        self.attributes['slave_type'] = slave_type
        self.attributes['slavepriority'] = slavepriority
        self.attributes['ssid'] = ssid
        self.attributes['state'] = state
        self.attributes['stp'] = stp
        self.attributes['transport_mode'] = transport_mode
        self.attributes['type'] = type
        self.attributes['updelay'] = updelay
        self.attributes['vlandev'] = vlandev
        self.attributes['vlanid'] = vlanid
        self.attributes['vpn'] = vpn
        self.attributes['vxlan_id'] = vxlan_id
        self.attributes['vxlan_local'] = vxlan_local
        self.attributes['vxlan_remote'] = vxlan_remote
        self.attributes['wifi'] = wifi
        self.attributes['wifi_sec'] = wifi_sec
        self.attributes['wireguard'] = wireguard
        self.attributes['xmit_hash_policy'] = xmit_hash_policy
        self.attributes['zone'] = zone

    def __str__(self) -> str:
        return dump(self.to_dict())
    
    def to_dict(self) -> dict:
        out = {}
        out['interface'] = self.interface

        l = [k for k, v in self.attributes.items() if v is not None]
        for k in l:
            out[k] = self.attributes[k]
        return out

        # Case Ethernet
        
        # Case Infiniband

        # Case Bond

        # Case Ethernet Bond Slave

        # Case Infiniband Bond Slave 

class InterfaceEthernet(Interface):
    def __init__(self, 
                 interface: str,
                 ip4: str,
                 network: str,
                 mac: str | None = "",
                 addr_gen_mode6: str | None = None,
                 ageingtime: str | None = None,
                 arp_interval: str | None = None,
                 arp_ip_target: str | None = None,
                 autoconnect: str | None = None,
                 dhcp_client_id: str | None = None,
                 dns4: str | None = None,
                 dns4_ignore_auto: str | None = None,
                 dns4_search: str | None = None,
                 dns6: str | None = None,
                 dns6_ignore_auto: str | None = None,
                 dns6_search: str | None = None,
                 downdelay: str | None = None,
                 egress: str | None = None,
                 flags: str | None = None,
                 forwarddelay: str | None = None,
                 gsm: str | None = None,
                 gw4: str | None = None,
                 gw4_ignore_auto: str | None = None,
                 gw6: str | None = None,
                 gw6_ignore_auto: str | None = None,
                 hairpin: str | None = None,
                 hellotime: str | None = None,
                 ignore_unsupported_suboptions: str | None = None,
                 ingress: str | None = None,
                 infiniband_mac : str | None = None,
                 ip6: str | None = None,
                 ip_privacy6: str | None = None,
                 ip_tunnel_dev: str | None = None,
                 ip_tunnel_input_key: str | None = None,
                 ip_tunnel_local: str | None = None,
                 ip_tunnel_output_key: str | None = None,
                 ip_tunnel_remote: str | None = None,
                 master: str | None = None,
                 maxage: str | None = None,
                 may_fail4: str | None = None,
                 method4: str | None = None,
                 method6: str | None = None,
                 miimon: str | None = None,
                 mode: str | None = None,
                 mtu: str | None = None,
                 never_default4: str | None = None,
                 path_cost: str | None = None,
                 physical_device: str | None = None,
                 primary: str | None = None,
                 priority: str | None = None,
                 route_metric4: str | None = None,
                 route_metric6: str | None = None,
                 routes4: str | None = None,
                 routes4_extended: str | None = None,
                 routes6: str | None = None,
                 routes6_extended: str | None = None,
                 routing_rules4: str | None = None,
                 runner: str | None = None,
                 runner_fast_rate: str | None = None,
                 runner_hwaddr_policy: str | None = None,
                 skip: str | None = None,
                 slave_type: str | None = None,
                 slavepriority: str | None = None,
                 ssid: str | None = None,
                 state: str | None = None,
                 stp: str | None = None,
                 transport_mode: str | None = None,
                 updelay: str | None = None,
                 vlandev: str | None = None,
                 vlanid: str | None = None,
                 vpn: str | None = None,
                 vxlan_id: str | None = None,
                 vxlan_local: str | None = None,
                 vxlan_remote: str | None = None,
                 wifi: str | None = None,
                 wifi_sec: str | None = None,
                 wireguard: str | None = None,
                 xmit_hash_policy: str | None = None,
                 zone: str | None = None) -> None:
        type = "ethernet"
        super().__init__(interface, addr_gen_mode6, ageingtime, arp_interval, 
                         arp_ip_target, autoconnect, dhcp_client_id, dns4, dns4_ignore_auto, 
                         dns4_search, dns6, dns6_ignore_auto, dns6_search, downdelay, egress, 
                         flags, forwarddelay, gsm, gw4, gw4_ignore_auto, gw6, gw6_ignore_auto, 
                         hairpin, hellotime, ignore_unsupported_suboptions, 
                         ingress, infiniband_mac, ip4, ip6, ip_privacy6, ip_tunnel_dev, ip_tunnel_input_key, 
                         ip_tunnel_local, ip_tunnel_output_key, ip_tunnel_remote, master, 
                         maxage, may_fail4, method4, method6, miimon, mode, mtu, network, 
                         never_default4, path_cost, physical_device, primary, priority, 
                         route_metric4, route_metric6, routes4, routes4_extended, routes6, 
                         routes6_extended, routing_rules4, runner, runner_fast_rate, 
                         runner_hwaddr_policy, skip, slave_type, slavepriority, ssid, 
                         state, stp, transport_mode, type, updelay, vlandev, vlanid, 
                         vpn, vxlan_id, vxlan_local, vxlan_remote, wifi, wifi_sec, 
                         wireguard, xmit_hash_policy, zone)
        
class InterfaceInfiniband(Interface):
    def __init__(self, 
                 interface: str,
                 ip4: str,
                 network: str,
                 infiniband_mac: str,
                 addr_gen_mode6: str | None = None,
                 ageingtime: str | None = None,
                 arp_interval: str | None = None,
                 arp_ip_target: str | None = None,
                 autoconnect: str | None = None,
                 dhcp_client_id: str | None = None,
                 dns4: str | None = None,
                 dns4_ignore_auto: str | None = None,
                 dns4_search: str | None = None,
                 dns6: str | None = None,
                 dns6_ignore_auto: str | None = None,
                 dns6_search: str | None = None,
                 downdelay: str | None = None,
                 egress: str | None = None,
                 flags: str | None = None,
                 forwarddelay: str | None = None,
                 gsm: str | None = None,
                 gw4: str | None = None,
                 gw4_ignore_auto: str | None = None,
                 gw6: str | None = None,
                 gw6_ignore_auto: str | None = None,
                 hairpin: str | None = None,
                 hellotime: str | None = None,
                 ignore_unsupported_suboptions: str | None = None,
                 ingress: str | None = None,
                 ip6: str | None = None,
                 ip_privacy6: str | None = None,
                 ip_tunnel_dev: str | None = None,
                 ip_tunnel_input_key: str | None = None,
                 ip_tunnel_local: str | None = None,
                 ip_tunnel_output_key: str | None = None,
                 ip_tunnel_remote: str | None = None,
                 master: str | None = None,
                 maxage: str | None = None,
                 may_fail4: str | None = None,
                 method4: str | None = None,
                 method6: str | None = None,
                 miimon: str | None = None,
                 mode: str | None = None,
                 mtu: str | None = None,
                 never_default4: str | None = None,
                 path_cost: str | None = None,
                 physical_device: str | None = None,
                 primary: str | None = None,
                 priority: str | None = None,
                 route_metric4: str | None = None,
                 route_metric6: str | None = None,
                 routes4: str | None = None,
                 routes4_extended: str | None = None,
                 routes6: str | None = None,
                 routes6_extended: str | None = None,
                 routing_rules4: str | None = None,
                 runner: str | None = None,
                 runner_fast_rate: str | None = None,
                 runner_hwaddr_policy: str | None = None,
                 skip: str | None = None,
                 slave_type: str | None = None,
                 slavepriority: str | None = None,
                 ssid: str | None = None,
                 state: str | None = None,
                 stp: str | None = None,
                 transport_mode: str | None = None,
                 updelay: str | None = None,
                 vlandev: str | None = None,
                 vlanid: str | None = None,
                 vpn: str | None = None,
                 vxlan_id: str | None = None,
                 vxlan_local: str | None = None,
                 vxlan_remote: str | None = None,
                 wifi: str | None = None,
                 wifi_sec: str | None = None,
                 wireguard: str | None = None,
                 xmit_hash_policy: str | None = None,
                 zone: str | None = None) -> None:
        type = "infiniband"
        super().__init__(interface, addr_gen_mode6, ageingtime, arp_interval, 
                         arp_ip_target, autoconnect, dhcp_client_id, dns4, dns4_ignore_auto, 
                         dns4_search, dns6, dns6_ignore_auto, dns6_search, downdelay, egress, 
                         flags, forwarddelay, gsm, gw4, gw4_ignore_auto, gw6, gw6_ignore_auto, 
                         hairpin, hellotime, ignore_unsupported_suboptions, 
                         ingress, infiniband_mac, ip4, ip6, ip_privacy6, ip_tunnel_dev, ip_tunnel_input_key, 
                         ip_tunnel_local, ip_tunnel_output_key, ip_tunnel_remote, master, 
                         maxage, may_fail4, method4, method6, miimon, mode, mtu, network, 
                         never_default4, path_cost, physical_device, primary, priority, 
                         route_metric4, route_metric6, routes4, routes4_extended, routes6, 
                         routes6_extended, routing_rules4, runner, runner_fast_rate, 
                         runner_hwaddr_policy, skip, slave_type, slavepriority, ssid, 
                         state, stp, transport_mode, type, updelay, vlandev, vlanid, 
                         vpn, vxlan_id, vxlan_local, vxlan_remote, wifi, wifi_sec, 
                         wireguard, xmit_hash_policy, zone)
        

if __name__ == "__main__":
    ilist = [
        InterfaceEthernet("eno1", "10.0.10.1", "admin1"),
        InterfaceInfiniband("ib0", "10.0.30.1", "admin1", infiniband_mac="00:00:00:00:00:00:00:00:00:00")
    ]
    
    for i in ilist:
        print(f'{i}')