service network-manager stop
ifconfig enp0s31f6 192.168.2.107 netmask 255.255.255.0
route add default gw 192.168.2.39
echo "nameserver 192.168.2.39" >> /etc/resolv.conf
