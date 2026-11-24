"""Módulo de cámaras IP / RTSP para BruteForceOS.

Cubre el flujo típico de auditoría de cámaras en un laboratorio autorizado:
  1. Descubrir cámaras y sus puertos característicos (web, RTSP, ONVIF).
  2. Probar credenciales del panel web (hydra) o del stream RTSP (cameradar).
  3. Ver el vídeo en directo con ffplay / vlc una vez se conoce la URL.

Todo se apoya en los helpers de interfaz de ui.py para mantener el estilo.
"""

import shutil
import subprocess
from pathlib import Path

from ataque import PUERTOS_SERVICIO, ejecutar_hydra
from conexion import _asegurar_herramienta
from ui import (
    cabecera_seccion,
    ejecutar_con_spinner,
    gris,
    imprimir_menu,
    limpiar,
    magenta,
    msg_aviso,
    msg_error,
    msg_info,
    msg_nota,
    msg_ok,
    pausar,
    verde,
)
from validacion import es_ip_valida, es_rango_valido

# Puertos que delatan una cámara IP / NVR / DVR
PUERTOS_CAMARA = [80, 81, 443, 554, 8000, 8080, 8443, 8554, 8899, 9000, 34567, 37777]

# Rutas RTSP habituales por fabricante (para probar el stream a mano)
RUTAS_RTSP_COMUNES = [
    ("Hikvision", "/Streaming/Channels/101"),
    ("Dahua", "/cam/realmonitor?channel=1&subtype=0"),
    ("Axis", "/axis-media/media.amp"),
    ("Genérica 1", "/live"),
    ("Genérica 2", "/live.sdp"),
    ("Genérica 3", "/h264"),
    ("Genérica 4", "/stream1"),
    ("Genérica 5", "/onvif1"),
    ("Genérica 6", "/video1"),
    ("Genérica 7", "/11"),
]


# ---------------------------------------------------------------------------
# Descubrimiento de cámaras
# ---------------------------------------------------------------------------
def _escanear_puertos_camara(objetivo: str) -> None:
    if not shutil.which("nmap") and not _asegurar_herramienta("nmap", "nmap"):
        pausar()
        return

    puertos = ",".join(str(p) for p in PUERTOS_CAMARA)
    cmd = ["nmap", "-p", puertos, "--open", "-sV", objetivo]
    msg_info(f"Buscando puertos de cámara en {objetivo}...")
    print(gris("-" * 62))
    try:
        res = ejecutar_con_spinner(cmd, texto="Rastreando puertos de cámara", timeout=300)
        print((res.stdout or "") + (res.stderr or ""))
    except FileNotFoundError:
        msg_error("No se pudo ejecutar nmap.")
        pausar()
        return

    msg_nota("Puertos 554/8554 = RTSP (vídeo) · 80/8080/443 = panel web · 37777/34567 = DVR propietario")
    pausar()


# ---------------------------------------------------------------------------
# RTSP con cameradar
# ---------------------------------------------------------------------------
def _asegurar_cameradar() -> list[str] | None:
    """Prepara cameradar y devuelve el prefijo de invocación.

    cameradar NO está en apt, así que se intenta, por orden:
      1. Binario ya instalado en el PATH  -> ["cameradar"]
      2. Docker (imagen oficial)          -> ["sudo","docker","run","--rm","--net=host","ullaakut/cameradar"]
      3. go install                       -> ["cameradar"]
    Devuelve None si no se pudo preparar.
    """
    if shutil.which("cameradar"):
        return ["cameradar"]

    msg_aviso("'cameradar' no está instalado (no viene en los repositorios apt).")

    # Opción 1: Docker (la más fiable)
    if shutil.which("docker"):
        resp = input(verde("¿Preparar cameradar con Docker ahora? [S/n]: ")).strip().lower()
        if resp in ("", "s", "si", "sí", "y", "yes"):
            msg_info("Descargando imagen 'ullaakut/cameradar' con Docker (puede pedir sudo)...")
            res = subprocess.run(["sudo", "docker", "pull", "ullaakut/cameradar"], check=False)
            if res.returncode == 0:
                msg_ok("Imagen de cameradar lista en Docker.")
                return ["sudo", "docker", "run", "--rm", "--net=host", "ullaakut/cameradar"]
            msg_error("No se pudo descargar la imagen de Docker.")

    # Opción 2: go install
    if shutil.which("go"):
        resp = input(verde("¿Instalar cameradar con 'go install' ahora? [S/n]: ")).strip().lower()
        if resp in ("", "s", "si", "sí", "y", "yes"):
            msg_info("Instalando cameradar con go install (puede tardar)...")
            res = subprocess.run(
                ["go", "install", "github.com/Ullaakut/cameradar/v5/cmd/cameradar@latest"],
                check=False,
            )
            if res.returncode == 0 and shutil.which("cameradar"):
                msg_ok("cameradar instalado correctamente.")
                return ["cameradar"]
            msg_error("go install terminó pero 'cameradar' no está en el PATH (revisa $GOPATH/bin o ~/go/bin).")

    msg_error("No se pudo preparar cameradar automáticamente.")
    msg_nota("Instala Docker (sudo apt install docker.io) o Go (sudo apt install golang) y vuelve a intentarlo.")
    return None


def _fuerza_rtsp_cameradar(objetivo: str) -> None:
    invocacion = _asegurar_cameradar()
    if not invocacion:
        pausar()
        return

    puertos = input(verde("Puertos RTSP a probar [554,8554]: ")).strip() or "554,8554"
    cmd = invocacion + ["-t", objetivo, "-p", puertos]
    msg_info(f"Lanzando cameradar contra {objetivo} (puertos {puertos})...")
    print(gris("-" * 62))
    try:
        res = ejecutar_con_spinner(cmd, texto="Descubriendo rutas y credenciales RTSP", timeout=900)
        salida = (res.stdout or "") + (res.stderr or "")
        print(salida)
        if "rtsp://" in salida.lower():
            msg_ok("Cameradar encontró stream(s) RTSP. Copia la URL para verla en la opción 'Ver vídeo'.")
        else:
            msg_aviso("No se confirmaron streams RTSP accesibles con los diccionarios por defecto.")
    except FileNotFoundError:
        msg_error("No se pudo ejecutar cameradar.")
    pausar()


# ---------------------------------------------------------------------------
# Visor del stream en directo
# ---------------------------------------------------------------------------
def _reproductor_disponible() -> str | None:
    for reproductor in ("ffplay", "cvlc", "vlc", "mpv"):
        if shutil.which(reproductor):
            return reproductor
    return None


def _asegurar_reproductor() -> str | None:
    """Devuelve un reproductor disponible; si no hay ninguno, ofrece instalar ffmpeg."""
    reproductor = _reproductor_disponible()
    if reproductor:
        return reproductor

    msg_aviso("No hay ningún reproductor de vídeo instalado (ffplay/vlc/mpv).")
    # ffplay viene en el paquete 'ffmpeg'
    if _asegurar_herramienta("ffplay", "ffmpeg"):
        return "ffplay"
    # Alternativa: VLC
    if _asegurar_herramienta("vlc", "vlc"):
        return "vlc"
    return None


def _lanzar_reproductor(url: str) -> None:
    reproductor = _asegurar_reproductor()
    if not reproductor:
        msg_error("No se pudo preparar ningún reproductor de vídeo.")
        pausar()
        return

    if reproductor == "ffplay":
        cmd = ["ffplay", "-rtsp_transport", "tcp", "-fflags", "nobuffer", url]
    elif reproductor in ("vlc", "cvlc"):
        cmd = [reproductor, url]
    else:  # mpv
        cmd = ["mpv", url]

    msg_ok(f"Abriendo vídeo con {reproductor}...")
    msg_nota("Cierra la ventana del reproductor (o Ctrl+C aquí) para volver a BruteForceOS.")
    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        msg_error(f"No se pudo ejecutar {reproductor}.")
    print()
    msg_info("Visor cerrado.")
    pausar()


def _ver_stream_rtsp(objetivo: str | None) -> None:
    limpiar()
    cabecera_seccion("Ver Vídeo RTSP en Directo", "Construye la URL del stream")

    ip = input(verde(f"IP de la cámara [{objetivo or ''}]: ")).strip() or (objetivo or "")
    if not ip:
        msg_aviso("Debes indicar la IP de la cámara.")
        pausar()
        return
    if not es_ip_valida(ip):
        msg_error(f"'{ip}' no es una IP válida.")
        pausar()
        return

    puerto = input(verde("Puerto RTSP [554]: ")).strip() or "554"
    usuario = input(verde("Usuario (Enter si no hace falta): ")).strip()
    password = input(verde("Contraseña (Enter si no hace falta): ")).strip()

    print()
    msg_info("Rutas RTSP habituales por fabricante:")
    for idx, (marca, ruta) in enumerate(RUTAS_RTSP_COMUNES, start=1):
        print(f"  [{idx}] {gris(marca.ljust(12))} {ruta}")
    print(f"  [m] Escribir una ruta manual")

    sel = input(verde("\nElige ruta [1]: ")).strip() or "1"
    if sel.lower() == "m":
        ruta = input(verde("Ruta (empezando por /): ")).strip() or "/"
    elif sel.isdigit() and 1 <= int(sel) <= len(RUTAS_RTSP_COMUNES):
        ruta = RUTAS_RTSP_COMUNES[int(sel) - 1][1]
    else:
        msg_aviso("Selección no válida, uso la primera ruta.")
        ruta = RUTAS_RTSP_COMUNES[0][1]

    if not ruta.startswith("/"):
        ruta = "/" + ruta

    credencial = f"{usuario}:{password}@" if usuario else ""
    url = f"rtsp://{credencial}{ip}:{puerto}{ruta}"

    print()
    cabecera_seccion("URL del Stream", "Lista para reproducir")
    print("  " + magenta(url))
    print()
    _lanzar_reproductor(url)


# ---------------------------------------------------------------------------
# Panel web de la cámara (atajo a hydra)
# ---------------------------------------------------------------------------
def _atacar_panel_web(objetivo: str | None, diccionario: str | None) -> None:
    limpiar()
    cabecera_seccion("Panel Web de la Cámara", "Fuerza bruta del login HTTP(S)")

    ip = input(verde(f"IP de la cámara [{objetivo or ''}]: ")).strip() or (objetivo or "")
    if not ip or not es_ip_valida(ip):
        msg_error("IP no válida.")
        pausar()
        return

    dic = input(verde(f"Diccionario de contraseñas [{diccionario or ''}]: ")).strip() or (diccionario or "")
    if not dic or not Path(dic).exists():
        msg_error("Debes indicar un diccionario válido.")
        pausar()
        return

    imprimir_menu(
        "Tipo de Login Web",
        [
            ("1", "HTTP con autenticación básica (http-get)"),
            ("2", "HTTPS con autenticación básica (https-get)"),
            ("3", "Formulario HTTP de login (http-form-post)"),
        ],
    )
    tipo = input(verde("Elige [1]: ")).strip() or "1"
    servicio = {"1": "http-get", "2": "https-get", "3": "http-form-post"}.get(tipo, "http-get")

    puerto_def = PUERTOS_SERVICIO.get(servicio, 80)
    pt = input(verde(f"Puerto [{puerto_def}]: ")).strip() or str(puerto_def)
    puerto = int(pt) if pt.isdigit() else puerto_def

    usuario = input(verde("Usuario [admin]: ")).strip() or "admin"

    if servicio in ("http-get", "https-get"):
        ruta = input(verde("Ruta protegida [/]: ")).strip() or "/"
        if not ruta.startswith("/"):
            ruta = "/" + ruta
        opcion = ruta
    else:
        msg_nota("Formato: /ruta:campo_user=^USER^&campo_pass=^PASS^:F=texto_de_error")
        msg_nota("Ejemplo: /login.cgi:user=^USER^&pwd=^PASS^:F=incorrect")
        opcion = input(verde("Cadena del formulario: ")).strip() or None

    ejecutar_hydra(ip, servicio, puerto, dic, usuario=usuario, opcion_modulo=opcion)


# ---------------------------------------------------------------------------
# Menú principal del módulo
# ---------------------------------------------------------------------------
def menu_camaras(objetivo_actual: str | None = None, diccionario_actual: str | None = None) -> str | None:
    while True:
        limpiar()
        print()
        print("  " + magenta("📷  CÁMARAS IP / RTSP") + gris("  ·  vídeo en directo y credenciales"))
        imprimir_menu(
            "Auditoría de Cámaras",
            [
                ("1", "Descubrir puertos de cámara en una IP/rango"),
                ("2", "Fuerza bruta de credenciales RTSP (cameradar)"),
                ("3", "Ver vídeo RTSP en directo (ffplay / vlc)"),
                ("4", "Fuerza bruta del panel web (HTTP/HTTPS)"),
                ("0", "Volver al menú principal"),
            ],
            subtitulo=f"Objetivo: {objetivo_actual or 'Ninguno'}",
        )

        op = input(verde("Elige una opción: ")).strip()

        if op == "1":
            objetivo = input(verde(f"IP o rango [{objetivo_actual or ''}]: ")).strip() or (objetivo_actual or "")
            if not objetivo:
                msg_aviso("Debes indicar una IP o rango.")
                pausar()
                continue
            if not es_rango_valido(objetivo):
                msg_error(f"'{objetivo}' no es una IP o rango válido.")
                pausar()
                continue
            _escanear_puertos_camara(objetivo)
            if es_ip_valida(objetivo):
                objetivo_actual = objetivo
        elif op == "2":
            objetivo = input(verde(f"IP o rango [{objetivo_actual or ''}]: ")).strip() or (objetivo_actual or "")
            if not objetivo or not es_rango_valido(objetivo):
                msg_error("IP o rango no válido.")
                pausar()
                continue
            _fuerza_rtsp_cameradar(objetivo)
            if es_ip_valida(objetivo):
                objetivo_actual = objetivo
        elif op == "3":
            _ver_stream_rtsp(objetivo_actual)
        elif op == "4":
            _atacar_panel_web(objetivo_actual, diccionario_actual)
        elif op == "0":
            return objetivo_actual
        else:
            msg_aviso("Opción no válida.")
            pausar()
