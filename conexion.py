import json
import shutil
import subprocess
from pathlib import Path

from ui import (
    cabecera_seccion,
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

BASE_DIR = Path(__file__).resolve().parent
CARPETA_RESULTADOS = BASE_DIR / "resultados"
CARPETA_ESCANEO = CARPETA_RESULTADOS / "escaneos"
ARCHIVO_DISPOSITIVOS = CARPETA_RESULTADOS / "dispositivos_accedidos.json"


def _cargar_json(ruta: Path, defecto):
    if not ruta.exists():
        return defecto
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return defecto


def lanzar_conexion(credencial: dict) -> None:
    ip = credencial["ip"]
    servicio = credencial["servicio"].lower()
    puerto = int(credencial["puerto"])
    usuario = credencial["usuario"]
    password = credencial["password"]

    limpiar()
    cabecera_seccion("Conectado al Sistema", f"{ip}:{puerto} ({servicio.upper()})")
    msg_ok(f"Usuario: {usuario}  |  Contraseña: {password}")
    print()

    if servicio == "ssh":
        if not shutil.which("ssh"):
            msg_error("'ssh' no está instalado en este sistema.")
            pausar()
            return
        msg_nota("Escribe 'exit' para cerrar la sesión SSH y volver a BruteForceOS.\n")
        subprocess.run(["ssh", "-p", str(puerto), f"{usuario}@{ip}"], check=False)

    elif servicio == "ftp":
        if shutil.which("lftp"):
            msg_nota("Sesión FTP activa con lftp. Escribe 'exit' o 'quit' para salir.\n")
            subprocess.run(["lftp", "-u", f"{usuario},{password}", "-p", str(puerto), ip], check=False)
        elif shutil.which("ftp"):
            msg_nota("Cliente 'ftp' estándar detectado (sin autologin).")
            msg_info(f"Usuario: {usuario}  |  Contraseña: {password}\n")
            subprocess.run(["ftp", ip, str(puerto)], check=False)
        else:
            msg_error("No está instalado 'lftp' ni 'ftp'. Instálalo con: sudo apt install lftp")

    elif servicio == "telnet":
        if not shutil.which("telnet"):
            msg_error("'telnet' no está instalado en este sistema.")
            pausar()
            return
        msg_info(f"Usuario: {usuario}  |  Contraseña: {password}")
        msg_nota("Escribe 'exit' o 'logout' para cerrar la sesión.\n")
        subprocess.run(["telnet", ip, str(puerto)], check=False)

    else:
        msg_aviso(f"Servicio no soportado para conexión automática: {servicio}")

    print()
    msg_info("Sesión remota finalizada.")
    pausar()


def conectar_por_ip(ip: str) -> bool:
    datos_ip = _cargar_json(CARPETA_ESCANEO / f"{ip}.json", {})
    creds = datos_ip.get("credenciales", [])
    so_disp = datos_ip.get("so_dispositivo", "No detectado")

    if not creds:
        todos = _cargar_json(ARCHIVO_DISPOSITIVOS, [])
        creds = [d for d in todos if d.get("ip") == ip]

    if not creds:
        msg_aviso(f"No hay credenciales guardadas para la IP {ip}.")
        pausar()
        return False

    if len(creds) == 1:
        elegida = dict(creds[0])
        elegida.setdefault("ip", ip)
        elegida.setdefault("so_dispositivo", so_disp)
        lanzar_conexion(elegida)
        return True

    cabecera_seccion(f"Accesos para {ip}", f"SO / Dispositivo: {so_disp}")
    for idx, c in enumerate(creds, start=1):
        print(f"  [{idx}] {c['servicio'].upper()} puerto {c['puerto']} -> usuario '{c['usuario']}'")
    sel = input(verde("Elige cuál usar [1]: ")).strip() or "1"
    if sel.isdigit() and 1 <= int(sel) <= len(creds):
        elegida = dict(creds[int(sel) - 1])
        elegida.setdefault("ip", ip)
        lanzar_conexion(elegida)
        return True

    msg_aviso("Selección no válida.")
    pausar()
    return False


def menu_conexion(objetivo_actual: str | None = None) -> str | None:
    while True:
        limpiar()
        imprimir_menu(
            "Acceso y Dispositivos",
            [
                ("1", "Conectar indicando solo la IP"),
                ("2", "Conectarse a un dispositivo anterior guardado"),
                ("0", "Volver al menú principal"),
            ],
            subtitulo=f"Objetivo en sesión: {objetivo_actual or 'Ninguno'}",
        )

        op = input(verde("Elige opción: ")).strip()

        if op == "1":
            ip = input(verde(f"Introduce solo la IP [{objetivo_actual or ''}]: ")).strip() or (objetivo_actual or "")
            if ip:
                conectar_por_ip(ip)
                return ip
            msg_aviso("Debes indicar una IP.")
            pausar()
        elif op == "2":
            dispositivos = _cargar_json(ARCHIVO_DISPOSITIVOS, [])
            if not dispositivos:
                msg_aviso("Todavía no hay dispositivos anteriores guardados.")
                pausar()
                continue
            limpiar()
            cabecera_seccion("Dispositivos Anteriores", "Historial de accesos guardados")
            for idx, d in enumerate(dispositivos, start=1):
                print(
                    f"  [{idx}] {d['ip']} | {d['servicio'].upper()}:{d['puerto']} | "
                    f"User: {d['usuario']} | {d.get('so_dispositivo', 'No detectado')}"
                )
            sel = input(verde("\nElige el número de dispositivo (o Enter para cancelar): ")).strip()
            if sel.isdigit() and 1 <= int(sel) <= len(dispositivos):
                elegido = dispositivos[int(sel) - 1]
                lanzar_conexion(elegido)
                return elegido["ip"]
        elif op == "0":
            return objetivo_actual
        else:
            msg_aviso("Opción no válida.")
            pausar()