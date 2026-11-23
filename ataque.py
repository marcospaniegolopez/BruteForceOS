import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CARPETA_DICCIONARIOS = BASE_DIR / "diccionarios"
CARPETA_RESULTADOS = BASE_DIR / "resultados"
CARPETA_ESCANEO = CARPETA_RESULTADOS / "escaneos"
ARCHIVO_DISPOSITIVOS = CARPETA_RESULTADOS / "dispositivos_accedidos.json"

SERVICIOS_SOPORTADOS = {"ssh", "ftp", "telnet"}
HILOS_POR_DEFECTO = 4


def _cargar_json(ruta: Path, defecto):
    if not ruta.exists():
        return defecto
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return defecto


def _guardar_json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)


def _normalizar_servicio(servicio: str, puerto: int) -> str | None:
    s = (servicio or "").lower()
    if "ssh" in s or puerto == 22:
        return "ssh"
    if "ftp" in s or puerto == 21:
        return "ftp"
    if "telnet" in s or puerto == 23:
        return "telnet"
    return None


def _elegir_diccionario_usuarios(diccionario_passwords: str) -> str | None:
    archivos = sorted([p for p in CARPETA_DICCIONARIOS.iterdir() if p.is_file()]) if CARPETA_DICCIONARIOS.exists() else []
    print("\n--- DICCIONARIO DE USUARIOS ---")
    print(f"1) Usar el mismo diccionario ({Path(diccionario_passwords).name})")
    print("2) Elegir otro diccionario de la carpeta diccionarios/")
    print("3) Escribir una ruta manual")

    sel = input("Elige opción [1]: ").strip() or "1"
    if sel == "1":
        return diccionario_passwords
    if sel == "2":
        if not archivos:
            print("[!] No hay diccionarios en la carpeta diccionarios/.")
            return None
        for idx, a in enumerate(archivos, start=1):
            print(f"  {idx}) {a.name}")
        num = input("Número de diccionario de usuarios: ").strip()
        if num.isdigit() and 1 <= int(num) <= len(archivos):
            return str(archivos[int(num) - 1])
        print("[!] Selección no válida.")
        return None
    if sel == "3":
        ruta = input("Ruta del archivo de usuarios: ").strip()
        if ruta and Path(ruta).exists():
            return ruta
        print("[!] La ruta indicada no existe.")
        return None

    print("[!] Opción no válida.")
    return None


def registrar_acceso_exitoso(ip: str, servicio: str, puerto: int, usuario: str, password: str, so_dispositivo: str = "No detectado") -> None:
    ruta_escaneo = CARPETA_ESCANEO / f"{ip}.json"
    datos_ip = _cargar_json(ruta_escaneo, {
        "ip": ip,
        "actualizado": datetime.now().isoformat(timespec="seconds"),
        "so_dispositivo": so_dispositivo,
        "puertos": [],
        "credenciales": [],
    })

    if so_dispositivo != "No detectado":
        datos_ip["so_dispositivo"] = so_dispositivo

    cred = {
        "servicio": servicio,
        "puerto": int(puerto),
        "usuario": usuario,
        "password": password,
        "fecha": datetime.now().isoformat(timespec="seconds"),
    }

    creds_existentes = datos_ip.get("credenciales", [])
    duplicado = any(
        c.get("servicio") == servicio
        and int(c.get("puerto", 0)) == int(puerto)
        and c.get("usuario") == usuario
        and c.get("password") == password
        for c in creds_existentes
    )
    if not duplicado:
        creds_existentes.append(cred)
    datos_ip["credenciales"] = creds_existentes
    datos_ip["actualizado"] = datetime.now().isoformat(timespec="seconds")
    _guardar_json(ruta_escaneo, datos_ip)

    dispositivos = _cargar_json(ARCHIVO_DISPOSITIVOS, [])
    so_final = datos_ip.get("so_dispositivo", so_dispositivo)
    idx_existente = next(
        (i for i, d in enumerate(dispositivos) if d.get("ip") == ip and d.get("servicio") == servicio and int(d.get("puerto", 0)) == int(puerto)),
        None,
    )
    registro_disp = {
        "ip": ip,
        "servicio": servicio,
        "puerto": int(puerto),
        "usuario": usuario,
        "password": password,
        "so_dispositivo": so_final,
        "actualizado": datetime.now().isoformat(timespec="seconds"),
    }
    if idx_existente is not None:
        dispositivos[idx_existente] = registro_disp
    else:
        dispositivos.append(registro_disp)
    _guardar_json(ARCHIVO_DISPOSITIVOS, dispositivos)


def _extraer_credenciales_hydra(salida: str) -> list[tuple[str, str]]:
    hallazgos = []
    for linea in salida.splitlines():
        # Soporta tanto formato estándar como líneas con 'misc: ...'
        m = re.search(r"\[\d+\]\[\S+\]\s+host:\s+\S+.*?\blogin:\s+(\S+)\s+password:\s+(.*)$", linea)
        if m:
            usuario = m.group(1).strip()
            password = m.group(2).strip()
            if (usuario, password) not in hallazgos:
                hallazgos.append((usuario, password))
    return hallazgos


def ejecutar_hydra(
    ip: str,
    servicio: str,
    puerto: int,
    diccionario_passwords: str,
    usuario: str | None = None,
    lista_usuarios: str | None = None,
    hilos: int = HILOS_POR_DEFECTO,
) -> list[tuple[str, str]]:
    if not shutil.which("hydra"):
        print("[!] 'hydra' no está instalado. Instálalo con: sudo apt install hydra")
        return []

    cmd = ["hydra", "-t", str(hilos), "-s", str(puerto)]
    if usuario:
        cmd.extend(["-l", usuario])
    elif lista_usuarios:
        cmd.extend(["-L", lista_usuarios])
    else:
        print("[!] Debes indicar un usuario (-l) o una lista de usuarios (-L).")
        return []

    cmd.extend(["-P", diccionario_passwords, ip, servicio])
    print(f"\n[+] Lanzando Hydra: {' '.join(cmd)}\n" + "-" * 50)

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    salida = (res.stdout or "") + (res.stderr or "")
    print(salida)

    hallazgos = _extraer_credenciales_hydra(salida)
    datos_ip = _cargar_json(CARPETA_ESCANEO / f"{ip}.json", {})
    so_disp = datos_ip.get("so_dispositivo", "No detectado")

    for u, p in hallazgos:
        print(f"[+] Acceso válido en {ip}:{puerto} ({servicio}) -> usuario: '{u}' | contraseña: '{p}'")
        registrar_acceso_exitoso(ip, servicio, puerto, u, p, so_disp)

    if not hallazgos:
        print("[-] No se encontraron credenciales válidas con los diccionarios indicados.")
    return hallazgos


def menu_ataque(objetivo_actual: str | None = None, diccionario_actual: str | None = None) -> str | None:
    while True:
        print("\n=== PRUEBAS DE ACCESO Y CREDENCIALES ===")
        ip = input(f"IP objetivo [{objetivo_actual or ''}]: ").strip() or (objetivo_actual or "")
        if not ip:
            print("[!] No hay IP objetivo definida.")
            return objetivo_actual

        dic = input(f"Ruta del diccionario [{diccionario_actual or ''}]: ").strip() or (diccionario_actual or "")
        if not dic or not Path(dic).exists():
            print("[!] Debes seleccionar o indicar un diccionario válido.")
            return objetivo_actual

        datos_ip = _cargar_json(CARPETA_ESCANEO / f"{ip}.json", {})
        puertos_detectados = datos_ip.get("puertos", [])
        objetivos_ataque = []

        for p in puertos_detectados:
            srv = _normalizar_servicio(p.get("servicio", ""), int(p.get("puerto", 0)))
            if srv in SERVICIOS_SOPORTADOS:
                objetivos_ataque.append((srv, int(p["puerto"])))

        print("\nModo de ataque:")
        if objetivos_ataque:
            print(f"1) Automático según escaneo previo ({', '.join(f'{s}:{pt}' for s, pt in objetivos_ataque)})")
        else:
            print("1) Automático según escaneo previo (sin puertos guardados aún; pasará a manual)")
        print("2) Elegir servicio y puerto manualmente")
        print("0) Volver al menú principal")

        op = input("Elige opción: ").strip()
        if op == "0":
            return ip

        print("\n¿Conoces el usuario?")
        print("1) Sí, indicar un usuario concreto")
        print("2) No, usar un diccionario de usuarios (mismo diccionario u otro)")
        modo_user = input("Elige opción [1]: ").strip() or "1"

        usuario = None
        lista_usuarios = None
        if modo_user == "2":
            lista_usuarios = _elegir_diccionario_usuarios(dic)
            if not lista_usuarios:
                continue
        else:
            usuario = input("Usuario objetivo [msfadmin]: ").strip() or "msfadmin"

        if op == "1" and objetivos_ataque:
            for srv, pt in objetivos_ataque:
                ejecutar_hydra(ip, srv, pt, dic, usuario=usuario, lista_usuarios=lista_usuarios)
        else:
            if op == "1" and not objetivos_ataque:
                print("[i] No había puertos guardados del escaneo; indícalo aquí:")
            srv = input("Servicio (ssh / ftp / telnet) [ssh]: ").strip().lower() or "ssh"
            puerto_def = {"ssh": 22, "ftp": 21, "telnet": 23}.get(srv, 22)
            pt_txt = input(f"Puerto [{puerto_def}]: ").strip() or str(puerto_def)
            puerto = int(pt_txt) if pt_txt.isdigit() else puerto_def
            ejecutar_hydra(ip, srv, puerto, dic, usuario=usuario, lista_usuarios=lista_usuarios)

        return ip