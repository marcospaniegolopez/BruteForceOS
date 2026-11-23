import json
import shutil
import subprocess
from pathlib import Path

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

    print(f"\n[+] Conectando a {ip} por {servicio.upper()} en el puerto {puerto} como '{usuario}'...")
    print(f"[i] Contraseña guardada: {password}")

    if servicio == "ssh":
        if not shutil.which("ssh"):
            print("[!] 'ssh' no está disponible en este sistema.")
            return
        cmd = ["ssh", "-p", str(puerto), f"{usuario}@{ip}"]
        subprocess.run(cmd, check=False)

    elif servicio == "ftp":
        if shutil.which("lftp"):
            cmd = ["lftp", "-u", f"{usuario},{password}", "-p", str(puerto), ip]
            subprocess.run(cmd, check=False)
        elif shutil.which("ftp"):
            print(f"[i] Usa usuario '{usuario}' y contraseña '{password}' cuando lo solicite.")
            subprocess.run(["ftp", ip, str(puerto)], check=False)
        else:
            print("[!] No se encontró 'ftp' ni 'lftp'.")

    elif servicio == "telnet":
        if not shutil.which("telnet"):
            print("[!] 'telnet' no está disponible en este sistema.")
            return
        print(f"[i] Usuario guardado: '{usuario}' | Contraseña guardada: '{password}'")
        subprocess.run(["telnet", ip, str(puerto)], check=False)

    else:
        print(f"[!] Servicio no soportado para conexión automática: {servicio}")


def conectar_por_ip(ip: str) -> bool:
    datos_ip = _cargar_json(CARPETA_ESCANEO / f"{ip}.json", {})
    creds = datos_ip.get("credenciales", [])
    so_disp = datos_ip.get("so_dispositivo", "No detectado")

    if not creds:
        todos = _cargar_json(ARCHIVO_DISPOSITIVOS, [])
        creds = [d for d in todos if d.get("ip") == ip]

    if not creds:
        print(f"[!] No hay credenciales ni puertos guardados para la IP {ip}. Ejecuta primero el escaneo y el ataque.")
        return False

    if len(creds) == 1:
        elegida = dict(creds[0])
        elegida.setdefault("ip", ip)
        elegida.setdefault("so_dispositivo", so_disp)
        lanzar_conexion(elegida)
        return True

    print(f"\nAccesos guardados para {ip} ({so_disp}):")
    for idx, c in enumerate(creds, start=1):
        print(f"  {idx}) {c['servicio'].upper()} puerto {c['puerto']} -> usuario '{c['usuario']}'")
    sel = input("Elige cuál usar [1]: ").strip() or "1"
    if sel.isdigit() and 1 <= int(sel) <= len(creds):
        elegida = dict(creds[int(sel) - 1])
        elegida.setdefault("ip", ip)
        lanzar_conexion(elegida)
        return True

    print("[!] Selección no válida.")
    return False


def menu_conexion(objetivo_actual: str | None = None) -> str | None:
    while True:
        print("\n=== ACCESO AUTOMÁTICO Y DISPOSITIVOS ANTERIORES ===")
        print("1) Conectar indicando solo la IP (usa puerto y credenciales guardados)")
        print("2) Conectarse a un dispositivo anterior guardado")
        print("0) Volver al menú principal")

        op = input("Elige opción: ").strip()

        if op == "1":
            ip = input(f"Introduce solo la IP [{objetivo_actual or ''}]: ").strip() or (objetivo_actual or "")
            if ip:
                conectar_por_ip(ip)
                return ip
            print("[!] Debes indicar una IP.")
        elif op == "2":
            dispositivos = _cargar_json(ARCHIVO_DISPOSITIVOS, [])
            if not dispositivos:
                print("[!] Todavía no hay dispositivos anteriores guardados.")
                continue
            print("\n--- DISPOSITIVOS ANTERIORES ---")
            for idx, d in enumerate(dispositivos, start=1):
                print(
                    f"  {idx}) IP: {d['ip']} | {d['servicio'].upper()}:{d['puerto']} | "
                    f"User: {d['usuario']} | SO/Disp: {d.get('so_dispositivo', 'No detectado')}"
                )
            sel = input("Elige el número de dispositivo (o Enter para cancelar): ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(dispositivos):
                elegido = dispositivos[int(sel) - 1]
                lanzar_conexion(elegido)
                return elegido["ip"]
        elif op == "0":
            return objetivo_actual
        else:
            print("[!] Opción no válida.")