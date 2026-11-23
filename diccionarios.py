import gzip
import shutil
import subprocess
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

BASE_DIR = Path(__file__).resolve().parent
CARPETA_DICCIONARIOS = BASE_DIR / "diccionarios"


def asegurar_carpeta_diccionarios() -> Path:
    CARPETA_DICCIONARIOS.mkdir(parents=True, exist_ok=True)
    return CARPETA_DICCIONARIOS


def listar_diccionarios() -> list[Path]:
    carpeta = asegurar_carpeta_diccionarios()
    return sorted([p for p in carpeta.iterdir() if p.is_file() and p.name != ".gitkeep"])


def _contar_lineas(ruta: Path) -> int:
    try:
        with open(ruta, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def mostrar_diccionarios() -> list[Path]:
    archivos = listar_diccionarios()
    cabecera_seccion("Diccionarios Disponibles", "Carpeta: diccionarios/")
    if not archivos:
        msg_aviso("La carpeta 'diccionarios/' está vacía.")
        msg_nota("Coloca ahí tus archivos .txt o usa las opciones para crear/preparar uno.")
        return []

    for idx, ruta in enumerate(archivos, start=1):
        tam_kb = ruta.stat().st_size / 1024
        lineas = _contar_lineas(ruta)
        print(f"  [{idx}] {verde(ruta.name)}  {gris(f'({lineas} líneas | {tam_kb:.1f} KB)')}")
    return archivos


def _descomprimir_rockyou() -> str | None:
    origen = Path("/usr/share/wordlists/rockyou.txt.gz")
    destino = asegurar_carpeta_diccionarios() / "rockyou.txt"

    if destino.exists():
        msg_ok(f"rockyou.txt ya está disponible en: {destino}")
        return str(destino)

    if not origen.exists():
        msg_error("No se encontró /usr/share/wordlists/rockyou.txt.gz en el sistema.")
        return None

    msg_info("Descomprimiendo rockyou.txt.gz hacia diccionarios/rockyou.txt...")
    try:
        with gzip.open(origen, "rb") as f_in, open(destino, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        msg_ok(f"Diccionario listo en: {destino}")
        return str(destino)
    except OSError as e:
        msg_error(f"Error al descomprimir rockyou: {e}")
        return None


def _crear_con_crunch() -> str | None:
    if not shutil.which("crunch"):
        msg_error("'crunch' no está instalado. Instálalo con: sudo apt install crunch")
        return None

    min_len = input(verde("Longitud mínima [4]: ")).strip() or "4"
    max_len = input(verde("Longitud máxima [6]: ")).strip() or "6"
    charset = input(verde("Caracteres [abcdefghijklmnopqrstuvwxyz0123456789]: ")).strip() or "abcdefghijklmnopqrstuvwxyz0123456789"
    nombre = input(verde("Nombre de salida (ej. generado.txt): ")).strip() or "generado.txt"
    if not nombre.endswith(".txt"):
        nombre += ".txt"

    salida = asegurar_carpeta_diccionarios() / nombre
    cmd = ["crunch", min_len, max_len, charset, "-o", str(salida)]
    msg_info(f"Ejecutando: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0 and salida.exists():
        msg_ok(f"Diccionario creado en: {salida}")
        return str(salida)

    msg_error("No se pudo generar el diccionario con crunch.")
    if res.stderr:
        print(res.stderr)
    return None


def _crear_con_cupp() -> str | None:
    if not shutil.which("cupp"):
        msg_error("'cupp' no está instalado. Instálalo con: sudo apt install cupp")
        return None

    msg_nota("Se iniciará CUPP en modo interactivo...")
    subprocess.run(["cupp", "-i"], check=False)

    for candidato in sorted(Path(".").glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
        mover = input(verde(f"¿Mover '{candidato.name}' a diccionarios/? [s/N]: ")).strip().lower()
        if mover == "s":
            destino = asegurar_carpeta_diccionarios() / candidato.name
            shutil.move(str(candidato), str(destino))
            msg_ok(f"Movido a: {destino}")
            return str(destino)
        break

    msg_nota("Si CUPP generó un archivo, puedes seleccionarlo o copiarlo a diccionarios/.")
    return None


def _unir_diccionarios() -> str | None:
    archivos = listar_diccionarios()
    if len(archivos) < 2:
        msg_aviso("Necesitas al menos 2 diccionarios en diccionarios/ para unirlos.")
        return None

    cabecera_seccion("Unir Diccionarios (sin repetidos)", "Usa sort -u")
    for idx, a in enumerate(archivos, start=1):
        print(f"  [{idx}] {a.name}")

    s1 = input(verde("Número del primer diccionario: ")).strip()
    s2 = input(verde("Número del segundo diccionario: ")).strip()
    if not (s1.isdigit() and s2.isdigit()):
        msg_aviso("Debes introducir números válidos.")
        return None

    i1, i2 = int(s1) - 1, int(s2) - 1
    if not (0 <= i1 < len(archivos) and 0 <= i2 < len(archivos)) or i1 == i2:
        msg_aviso("Selección inválida o duplicada.")
        return None

    nombre_out = input(verde("Nombre del diccionario unido [combinado.txt]: ")).strip() or "combinado.txt"
    if not nombre_out.endswith(".txt"):
        nombre_out += ".txt"

    salida = asegurar_carpeta_diccionarios() / nombre_out
    if shutil.which("sort"):
        cmd = f'sort -u "{archivos[i1]}" "{archivos[i2]}" > "{salida}"'
        res = subprocess.run(cmd, shell=True, check=False)
        if res.returncode == 0 and salida.exists():
            msg_ok(f"Diccionario combinado creado en: {salida}")
            return str(salida)

    lineas_unicas = set()
    for p in (archivos[i1], archivos[i2]):
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            for linea in f:
                limpia = linea.rstrip("\r\n")
                if limpia:
                    lineas_unicas.add(limpia)

    with open(salida, "w", encoding="utf-8") as f:
        for palabra in sorted(lineas_unicas):
            f.write(palabra + "\n")

    msg_ok(f"Diccionario combinado creado en: {salida}")
    return str(salida)


def menu_diccionarios(diccionario_actual: str | None = None) -> str | None:
    while True:
        limpiar()
        archivos = mostrar_diccionarios()
        print()
        imprimir_menu(
            "Gestión de Diccionarios",
            [
                ("1", "Seleccionar un diccionario de la lista"),
                ("2", "Descomprimir rockyou.txt.gz a diccionarios/"),
                ("3", "Crear diccionario con Crunch"),
                ("4", "Crear diccionario personalizado con CUPP"),
                ("5", "Unir dos diccionarios sin duplicados (sort -u)"),
                ("6", "Introducir ruta manual de otro diccionario"),
                ("0", "Volver al menú principal"),
            ],
            subtitulo=f"Diccionario activo: {Path(diccionario_actual).name if diccionario_actual else 'Ninguno'}",
        )

        op = input(verde("Elige una opción: ")).strip()

        if op == "1":
            if not archivos:
                msg_aviso("No hay diccionarios disponibles para seleccionar.")
                pausar()
                continue
            sel = input(verde("Número de diccionario a activar: ")).strip()
            if sel.isdigit() and 1 <= int(sel) <= len(archivos):
                elegido = str(archivos[int(sel) - 1])
                msg_ok(f"Diccionario activo: {Path(elegido).name}")
                pausar()
                return elegido
            msg_aviso("Número no válido.")
            pausar()
        elif op == "2":
            ruta = _descomprimir_rockyou()
            pausar()
            if ruta:
                return ruta
        elif op == "3":
            ruta = _crear_con_crunch()
            pausar()
            if ruta:
                return ruta
        elif op == "4":
            ruta = _crear_con_cupp()
            pausar()
            if ruta:
                return ruta
        elif op == "5":
            ruta = _unir_diccionarios()
            pausar()
            if ruta:
                return ruta
        elif op == "6":
            ruta = input(verde("Ruta completa del diccionario: ")).strip()
            if ruta and Path(ruta).exists():
                msg_ok(f"Diccionario activo: {ruta}")
                pausar()
                return ruta
            msg_error("La ruta no existe.")
            pausar()
        elif op == "0":
            return diccionario_actual
        else:
            msg_aviso("Opción no válida.")
            pausar()