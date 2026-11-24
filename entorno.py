import shutil
from pathlib import Path

from ui import blanco, gris, msg_aviso, panel, rojo, verde

BASE_DIR = Path(__file__).resolve().parent
CARPETA_DICCIONARIOS = BASE_DIR / "diccionarios"

# (comando, descripción, imprescindible)
HERRAMIENTAS = [
    ("nmap", "Reconocimiento de red y puertos", True),
    ("hydra", "Pruebas de credenciales", True),
    ("ssh", "Conexión SSH", False),
    ("lftp", "Conexión FTP con autologin", False),
    ("crunch", "Generar diccionarios", False),
    ("cupp", "Diccionarios personalizados", False),
    ("cameradar", "Fuerza bruta RTSP de cámaras", False),
    ("ffplay", "Ver vídeo RTSP en directo", False),
]


def _estado(ok: bool) -> str:
    return verde("✓") if ok else rojo("✗")


def _rockyou_disponible() -> bool:
    return (
        (CARPETA_DICCIONARIOS / "rockyou.txt").exists()
        or Path("/usr/share/wordlists/rockyou.txt.gz").exists()
    )


def chequear_entorno() -> None:
    """Muestra un panel con el estado de las herramientas externas del sistema."""
    filas = []
    faltan_criticas = False

    for comando, descripcion, critico in HERRAMIENTAS:
        disponible = shutil.which(comando) is not None
        if critico and not disponible:
            faltan_criticas = True
        nombre = blanco(comando.ljust(8)) if disponible else gris(comando.ljust(8))
        filas.append(f"{_estado(disponible)}  {nombre} {gris(descripcion)}")

    rockyou = _rockyou_disponible()
    filas.append(f"{_estado(rockyou)}  {blanco('rockyou'.ljust(8))} {gris('Diccionario de contraseñas')}")

    print()
    panel("Estado del Entorno", filas, subtitulo="Herramientas detectadas en el sistema")

    if faltan_criticas:
        print()
        msg_aviso("Faltan herramientas imprescindibles (nmap/hydra). Instálalas con: sudo apt install nmap hydra")
