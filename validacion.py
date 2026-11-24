import ipaddress


def es_ip_valida(valor: str) -> bool:
    """True si `valor` es una IPv4/IPv6 individual válida."""
    try:
        ipaddress.ip_address((valor or "").strip())
        return True
    except ValueError:
        return False


def es_rango_valido(valor: str) -> bool:
    """True si `valor` es una IP individual o un rango CIDR válido (ej. 192.168.1.0/24)."""
    try:
        ipaddress.ip_network((valor or "").strip(), strict=False)
        return True
    except ValueError:
        return False
