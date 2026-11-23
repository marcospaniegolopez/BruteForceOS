import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CARPETA_RESULTADOS = BASE_DIR / "resultados"
CARPETA_ESCANEO = CARPETA_RESULTADOS / "escaneos"
ARCHIVO_DISPOSITIVOS = CARPETA_RESULTADOS / "dispositivos_accedidos.json"

SERVICIOS_SOPORTADOS = {"ssh", "ftp", "telnet"}


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
        m = re.search(r"\[\d+\]\[\S+\]\s+host:\s+\S+\s+login:\s+(\S+)\s+password:\s+(.*)$", linea)
        if m:
            usuario = m.group(1).strip()
            password = m.group(2).strip()
            if (usuario, password) not in hallazgos:
                hallazgos.append((usuario, password))
    return hallazgos


def ejecutar_hydra(ip: str, servicio: str, puerto: int, diccionario: str, usuario: str | None = None, lista_usuarios: str | None = None, hilos: int = 4) -> list[tuple[str, str]]:
    if not shutil.which("hydra"):
        print("[!] 'hydra' no está instalado. Instálalo con: sudo apt install hydra")
        return []

    cmd = ["hydra", "-t", str(hilos), "-s", str(puerto)]
    if usuario:
        cmd.extend(["-l", usuario])
    elif lista_usuarios:
        cmd.extend(["-L", lista_usuarios])
    else:
        print("[!] Debes indicar un usuario (-l) o lista de usuarios (-L).")
        return []

    cmd.extend(["-P", diccionario, ip, servicio])
    print(f"\n[+] Lanzando Hydra: {' '.join(cmd)}\n" + "-" * 50)

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    salida = (res.stdout or "") + (res.stderr or "")
    print(salida)

    hallazgos = _extraer_credenciales_hydra(salida)
    datos_ip = _cargar_json(CARPETA_ESCANEO / f"{ip}.json", {})
    so_disp = datos_ip.get("so_dispositivo", "No detectado")

    for u, p in hallazgos:
        print(f"[+] Credencial encontrada en {ip}:{puerto} ({servicio}) -> {u} : {p}")
        registrar_acceso_exitoso(ip, servicio, puerto, u, p, so_disp)

    if not hallazgos:
        print("[-] No se encontraron credenciales válidas con este diccionario.")
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
            print(f"1) Automático según escaneo previo de {ip} ({', '.join(f'{s}:{pt}' for s, pt in objetivos_ataque)})")
        else:
            print("1) Automático según escaneo previo (sin puertos SSH/FTP/Telnet guardados aún)")
        print("2) Elegir servicio y puerto manualmente")
        print("0) Volver al menú principal")

        op = input("Elige opción: ").strip()
        if op == "0":
            return ip

        modo_user = input("¿Usar un usuario concreto (u) o una lista de usuarios (l)? [u]: ").strip().lower() or "u"
        usuario = None
        lista_usuarios = None
        if modo_user == "l":
            lista_usuarios = input("Ruta del archivo de usuarios: ").strip()
        else:
            usuario = input("Usuario objetivo [root]: ").strip() or "root"

        hilos_txt = input("Número de hilos (-t) [4]: ").strip() or "4"
        hilos = int(hilos_txt) if hilos_txt.isdigit() and int(hilos_txt) > 0 else 4

        if op == "1" and objetivos_ataque:
            for srv, pt in objetivos_ataque:
                ejecutar_hydra(ip, srv, pt, dic, usuario=usuario, lista_usuarios=lista_usuarios, hilos=hilos)
        else:
            srv = input("Servicio (ssh / ftp / telnet) [ssh]: ").strip().lower() or "ssh"
            puerto_def = {"ssh": 22, "ftp": 21, "telnet": 23}.get(srv, 22)
            pt_txt = input(f"Puerto [{puerto_def}]: ").strip() or str(puerto_def)
            puerto = int(pt_txt) if pt_txt.isdigit() else puerto_def
            ejecutar_hydra(ip, srv, puerto, dic, usuario=usuario, lista_usuarios=lista_usuarios, hilos=hilos)

        return ip