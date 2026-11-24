import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from ui import (
    cabecera_seccion,
    gris,
    imprimir_menu,
    limpiar,
    msg_aviso,
    msg_error,
    msg_info,
    msg_nota,
    msg_ok,
    pausar,
    verde,
)
from validacion import es_ip_valida, es_rango_valido

BASE_DIR = Path(__file__).resolve().parent
CARPETA_ESCANEO = BASE_DIR / "resultados" / "escaneos"


def asegurar_carpeta_escaneos() -> Path:
    CARPETA_ESCANEO.mkdir(parents=True, exist_ok=True)
    return CARPETA_ESCANEO


def hacer_ping(ip: str, pausar_al_final: bool = False) -> bool:
    msg_info(f"Enviando ping (-c 1) a {ip}...")
    try:
        res = subprocess.run(
            ["ping", "-c", "1", ip],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            msg_ok(f"El paquete ha llegado a {ip} (host activo).")
            if pausar_al_final:
                pausar()
            return True
        msg_error(f"No ha respondido el paquete a {ip}.")
        if pausar_al_final:
            pausar()
        return False
    except FileNotFoundError:
        msg_error("El comando 'ping' no está disponible en este sistema.")
        if pausar_al_final:
            pausar()
        return False


def _ejecutar_nmap(args: list[str], usar_sudo: bool = False) -> str:
    if not shutil.which("nmap"):
        msg_error("'nmap' no está instalado. Instálalo con: sudo apt install nmap")
        return ""
    cmd = ["sudo", "nmap"] + args if usar_sudo else ["nmap"] + args
    msg_info(f"Ejecutando: {' '.join(cmd)}")
    print(gris("-" * 62))
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        salida = (res.stdout or "") + (res.stderr or "")
        print(salida)
        return res.stdout or ""
    except FileNotFoundError:
        msg_error("No se pudo ejecutar nmap.")
        return ""


def escanear_red(rango: str) -> list[dict]:
    salida = _ejecutar_nmap(["-sn", rango])
    hosts = []
    ip_actual = None
    hostname_actual = "Desconocido"

    for linea in salida.splitlines():
        m_host = re.search(r"Nmap scan report for (.+)", linea)
        if m_host:
            if ip_actual:
                hosts.append({"ip": ip_actual, "dispositivo": hostname_actual})
            raw = m_host.group(1).strip()
            m_par = re.match(r"^(.+?)\s+\(([\d.]+)\)$", raw)
            if m_par:
                hostname_actual = m_par.group(1).strip()
                ip_actual = m_par.group(2).strip()
            else:
                ip_actual = raw
                hostname_actual = "Desconocido"
        m_mac = re.search(r"MAC Address:\s+[\dA-F:]+\s+\((.+)\)", linea, re.I)
        if m_mac and ip_actual:
            hostname_actual = m_mac.group(1).strip()

    if ip_actual:
        hosts.append({"ip": ip_actual, "dispositivo": hostname_actual})

    print()
    cabecera_seccion("Hosts Detectados", rango)
    if not hosts:
        msg_aviso("No se detectaron hosts activos en el rango indicado.")
    else:
        for idx, h in enumerate(hosts, start=1):
            print(f"  [{idx}] IP: {verde(h['ip'])}  |  Dispositivo/Host: {h['dispositivo']}")
    return hosts


def _parsear_puertos_y_so(salida_nmap: str) -> tuple[list[dict], str]:
    puertos = []
    so_estimado = "No detectado"

    for linea in salida_nmap.splitlines():
        m_puerto = re.match(r"^(\d+)/(tcp|udp)\s+open\s+(\S+)(?:\s+(.*))?$", linea.strip())
        if m_puerto:
            puertos.append({
                "puerto": int(m_puerto.group(1)),
                "protocolo": m_puerto.group(2),
                "servicio": m_puerto.group(3).lower(),
                "version": (m_puerto.group(4) or "").strip(),
            })

        m_os = re.search(r"(?:OS details|Aggressive OS guesses|Running):\s*(.+)", linea)
        if m_os and so_estimado == "No detectado":
            so_estimado = m_os.group(1).strip()

    return puertos, so_estimado


def guardar_resultado_ip(ip: str, datos: dict) -> Path:
    carpeta = asegurar_carpeta_escaneos()
    archivo = carpeta / f"{ip}.json"
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    return archivo


def cargar_resultado_ip(ip: str) -> dict | None:
    archivo = asegurar_carpeta_escaneos() / f"{ip}.json"
    if not archivo.exists():
        return None
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def analizar_objetivo(ip: str, modo: str = "rapido") -> dict:
    hacer_ping(ip, pausar_al_final=False)

    if modo == "completo":
        salida = _ejecutar_nmap(["-p-", "--open", "-sV", "-O", ip], usar_sudo=True)
    elif modo == "agresivo":
        salida = _ejecutar_nmap(["-p-", "--open", "-A", ip], usar_sudo=True)
    else:
        salida = _ejecutar_nmap(["--open", "-sV", ip], usar_sudo=False)

    puertos, so_estimado = _parsear_puertos_y_so(salida)
    previo = cargar_resultado_ip(ip) or {}

    registro = {
        "ip": ip,
        "actualizado": datetime.now().isoformat(timespec="seconds"),
        "so_dispositivo": so_estimado if so_estimado != "No detectado" else previo.get("so_dispositivo", "No detectado"),
        "puertos": puertos if puertos else previo.get("puertos", []),
        "credenciales": previo.get("credenciales", []),
    }

    ruta = guardar_resultado_ip(ip, registro)
    print()
    cabecera_seccion("Resumen de Análisis", ip)
    msg_ok(f"Guardado en: resultados/escaneos/{ruta.name}")
    msg_info(f"SO / Dispositivo estimado: {registro['so_dispositivo']}")
    if registro["puertos"]:
        for p in registro["puertos"]:
            ver = f" ({p['version']})" if p["version"] else ""
            print(f"  • Puerto {verde(str(p['puerto']))}/{p['protocolo']} -> {p['servicio']}{ver}")
    else:
        msg_nota("No se detectaron puertos abiertos en este escaneo.")

    pausar()
    return registro


def menu_reconocimiento(objetivo_actual: str | None = None) -> str | None:
    while True:
        limpiar()
        imprimir_menu(
            "Reconocimiento y Análisis",
            [
                ("1", "Escanear red para ver IPs activas y dispositivos (-sn)"),
                ("2", "Hacer ping rápido a una IP (-c 1)"),
                ("3", "Analizar una IP (puertos, servicios y SO/dispositivo)"),
                ("0", "Volver al menú principal"),
            ],
            subtitulo=f"Objetivo activo: {objetivo_actual or 'Ninguno'}",
        )

        op = input(verde("Elige una opción: ")).strip()

        if op == "1":
            rango = input(verde("Introduce el rango de red (ej. 192.168.68.0/24): ")).strip()
            if rango and not es_rango_valido(rango):
                msg_error(f"'{rango}' no es una IP o rango CIDR válido (ej. 192.168.1.0/24).")
                pausar()
                continue
            if rango:
                hosts = escanear_red(rango)
                if hosts:
                    elegir = input(verde("\n¿Fijar alguna IP como objetivo actual? (número o Enter para omitir): ")).strip()
                    if elegir.isdigit() and 1 <= int(elegir) <= len(hosts):
                        ip_sel = hosts[int(elegir) - 1]["ip"]
                        msg_ok(f"Objetivo fijado en: {ip_sel}")
                        pausar()
                        return ip_sel
                pausar()
        elif op == "2":
            ip = input(verde(f"IP destino [{objetivo_actual or ''}]: ")).strip() or (objetivo_actual or "")
            if ip and not es_ip_valida(ip):
                msg_error(f"'{ip}' no es una dirección IP válida.")
                pausar()
                continue
            if ip:
                hacer_ping(ip, pausar_al_final=True)
        elif op == "3":
            ip = input(verde(f"IP a analizar [{objetivo_actual or ''}]: ")).strip() or (objetivo_actual or "")
            if not ip:
                msg_aviso("Debes indicar una IP.")
                pausar()
                continue
            if not es_ip_valida(ip):
                msg_error(f"'{ip}' no es una dirección IP válida.")
                pausar()
                continue
            imprimir_menu(
                "Tipo de Análisis",
                [
                    ("1", "Puertos comunes y servicios (-sV)"),
                    ("2", "Todos los puertos + servicios + SO (-p- --open -sV -O con sudo)"),
                    ("3", "Análisis agresivo completo (-p- --open -A con sudo)"),
                ],
            )
            tipo = input(verde("Elige [1]: ")).strip() or "1"
            modo_map = {"1": "rapido", "2": "completo", "3": "agresivo"}
            analizar_objetivo(ip, modo_map.get(tipo, "rapido"))
            return ip
        elif op == "0":
            return objetivo_actual
        else:
            msg_aviso("Opción no válida.")
            pausar()