"""Raccordement d'un téléphone : adresses du PC sur le réseau local et QR code.

Rien ici n'émet de paquet vers Internet : les adresses viennent de la liste des interfaces
réseau (psutil) ou de la résolution du nom du PC, et le QR est dessiné en local (segno).
"""

from __future__ import annotations

import ipaddress
import socket

try:
    import psutil
except ImportError:  # facultatif : on se rabat sur la résolution du nom d'hôte
    psutil = None
try:
    import segno
except ImportError:  # facultatif : le panneau s'affiche sans QR code
    segno = None

# Adaptateurs qui ne mènent pas au Wi-Fi/Ethernet du téléphone (machines virtuelles, VPN…).
VIRTUAL_HINTS = ("vethernet", "virtualbox", "vbox", "vmware", "hyper-v", "wsl", "docker",
                 "loopback", "bluetooth", "tap-", "tun", "vpn", "tailscale", "zerotier",
                 "hamachi", "npcap", "pseudo", "teredo", "isatap", "host-only")
WIFI_HINTS = ("wi-fi", "wifi", "wlan", "wireless", "sans fil")
ETHERNET_HINTS = ("ethernet", "local area", "réseau local", "reseau local", "lan")
# Adresse privée servant seulement à demander au système quelle interface sort par défaut :
# un socket UDP « connecté » ne transmet rien tant qu'on n'écrit pas dedans.
ROUTE_PROBE = ("10.255.255.255", 9)
# Sous-réseaux par défaut d'adaptateurs virtuels dont le nom ne le dit pas (VirtualBox host-only…).
VIRTUAL_NETS = (ipaddress.ip_network("192.168.56.0/24"), ipaddress.ip_network("192.168.99.0/24"))


def _main_route_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(ROUTE_PROBE)
            return probe.getsockname()[0]
    except OSError:
        return None


def _interface_addresses() -> list[tuple[str, str]]:
    """Couples (nom de l'interface, adresse IPv4) des interfaces actives."""
    found: list[tuple[str, str]] = []
    if psutil is not None:
        try:
            stats = psutil.net_if_stats()
            for name, addrs in psutil.net_if_addrs().items():
                if name in stats and not stats[name].isup:
                    continue
                found += [(name, a.address) for a in addrs if a.family == socket.AF_INET]
        except OSError:
            found = []
    if not found:
        try:
            found = [("", info[4][0]) for info in
                     socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
        except socket.gaierror:
            pass
    return found


def lan_addresses() -> list[str]:
    """Toutes les adresses IPv4 de ce PC hors boucle locale : sert aux noms d'hôte acceptés par le
    serveur et à ceux du certificat (donc volontairement large, adaptateurs virtuels compris)."""
    return sorted({ip for _, ip in _interface_addresses() if not ip.startswith("127.")})


def lan_candidates() -> list[dict]:
    """Adresses privées du PC, la plus probable d'abord (Wi-Fi/Ethernet réels, route par défaut)."""
    main_route = _main_route_ip()
    candidates, seen = [], set()
    for name, ip in _interface_addresses():
        try:
            addr = ipaddress.IPv4Address(ip)
        except ValueError:
            continue
        if not addr.is_private or addr.is_loopback or addr.is_link_local or ip in seen:
            continue
        seen.add(ip)
        lowered = name.lower()
        virtual = any(hint in lowered for hint in VIRTUAL_HINTS) or any(addr in n for n in VIRTUAL_NETS)
        kind = ("virtuel" if virtual else "Wi-Fi" if any(h in lowered for h in WIFI_HINTS)
                else "Ethernet" if any(h in lowered for h in ETHERNET_HINTS) else "autre")
        candidates.append({"ip": ip, "interface": name, "kind": kind, "virtual": virtual,
                           "main_route": ip == main_route})
    rank = {"Wi-Fi": 0, "Ethernet": 1, "autre": 2, "virtuel": 3}
    candidates.sort(key=lambda c: (c["virtual"], not c["main_route"], rank[c["kind"]], c["ip"]))
    for i, candidate in enumerate(candidates):
        candidate["recommended"] = i == 0 and not candidate["virtual"]
    return candidates


def qr_data_uri(text: str) -> str | None:
    """QR code (SVG en URI de données) ; None si la bibliothèque n'est pas installée."""
    if segno is None:
        return None
    return segno.make_qr(text, error="m").svg_data_uri(scale=6, border=2, xmldecl=False)
