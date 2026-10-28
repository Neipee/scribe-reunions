"""Certificat HTTPS auto-signé, nécessaire pour que le navigateur d'un téléphone
autorise le micro (contexte sécurisé). Généré localement, sans OpenSSL système."""

from __future__ import annotations

import datetime as dt
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from . import CERTS_DIR


def lan_addresses() -> list[str]:
    """Adresses IPv4 de ce PC sur le réseau local (hors 127.x)."""
    addresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except socket.gaierror:
        pass
    return sorted(a for a in addresses if not a.startswith("127."))


def ensure_certificate(force: bool = False) -> tuple[Path, Path]:
    cert_path, key_path = CERTS_DIR / "cert.pem", CERTS_DIR / "key.pem"
    if cert_path.exists() and key_path.exists() and not force:
        return cert_path, key_path
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    names = [x509.DNSName("localhost"), x509.DNSName(socket.gethostname()),
             x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    names += [x509.IPAddress(ipaddress.ip_address(a)) for a in lan_addresses()]
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Scribe reunions (local)")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                           serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path
