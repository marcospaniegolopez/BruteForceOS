import os
import re
import sys

# ---------------------------------------------------------------------------
# Inicialización de terminal
# En Windows 10+ habilitamos el procesamiento de secuencias ANSI (VT) y
# forzamos UTF-8 para que los marcos y glifos se rendericen correctamente.
# ---------------------------------------------------------------------------
if os.name == "nt":
    os.system("")  # activa el soporte de colores ANSI en la consola de Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

# Desactiva colores si la salida no es una TTY interactiva
COLOR_ACTIVO = sys.stdout.isatty()

# Ancho del marco de la interfaz
ANCHO = 64
_INNER = ANCHO - 2

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _c(codigo: str, texto: str) -> str:
    if not COLOR_ACTIVO:
        return texto
    return f"\033[{codigo}m{texto}\033[0m"


def _vis_len(texto: str) -> int:
    """Longitud visible de una cadena, ignorando los códigos de color ANSI."""
    return len(_ANSI_RE.sub("", texto))


# ---------------------------------------------------------------------------
# Paleta de colores
# ---------------------------------------------------------------------------
def cyan(texto: str) -> str:
    return _c("1;36", texto)


def verde(texto: str) -> str:
    return _c("1;32", texto)


def amarillo(texto: str) -> str:
    return _c("1;33", texto)


def rojo(texto: str) -> str:
    return _c("1;31", texto)


def azul(texto: str) -> str:
    return _c("1;34", texto)


def gris(texto: str) -> str:
    return _c("0;90", texto)


def blanco(texto: str) -> str:
    return _c("1;37", texto)


# ---------------------------------------------------------------------------
# Utilidades de terminal
# ---------------------------------------------------------------------------
def limpiar() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pausar(mensaje: str = "Pulsa ENTER para continuar") -> None:
    input(gris(f"\n   ↵  {mensaje}... "))


def prompt(texto: str) -> str:
    """Prompt de entrada con un marcador consistente."""
    return input(verde("  ›  ") + texto + gris(": "))


# ---------------------------------------------------------------------------
# Mensajes de estado (glifos alineados a 2 espacios de sangría)
# ---------------------------------------------------------------------------
def msg_ok(texto: str) -> None:
    print(verde("  ✓  ") + blanco(texto))


def msg_info(texto: str) -> None:
    print(cyan("  »  ") + texto)


def msg_nota(texto: str) -> None:
    print(azul("  •  ") + gris(texto))


def msg_aviso(texto: str) -> None:
    print(amarillo("  !  " + texto))


def msg_error(texto: str) -> None:
    print(rojo("  ✗  " + texto))


# ---------------------------------------------------------------------------
# Componentes de interfaz
# ---------------------------------------------------------------------------
def cabecera_seccion(titulo: str, subtitulo: str | None = None) -> None:
    """Cabecera de sección como un marco cerrado y centrado."""
    print(cyan("  ╭" + "─" * _INNER + "╮"))
    print(cyan("  │") + blanco(titulo.upper().center(_INNER)) + cyan("│"))
    if subtitulo:
        print(cyan("  │") + gris(subtitulo.center(_INNER)) + cyan("│"))
    print(cyan("  ╰" + "─" * _INNER + "╯"))


def barra_sesion(objetivo_ip: str | None, diccionario: str | None) -> None:
    """Barra de estado de la sesión activa."""
    ip_txt = verde(objetivo_ip) if objetivo_ip else gris("ninguno")
    if diccionario:
        dic_txt = verde(os.path.basename(diccionario))
    else:
        dic_txt = gris("ninguno")

    contenido = f"  {gris('OBJETIVO')} {ip_txt}    {gris('·')}    {gris('DICCIONARIO')} {dic_txt}"
    relleno = max(0, _INNER - _vis_len(contenido))
    print(cyan("  ╭" + "─" * _INNER + "╮"))
    print(cyan("  │") + contenido + " " * relleno + cyan("│"))
    print(cyan("  ╰" + "─" * _INNER + "╯"))


def _borde_superior(titulo: str) -> str:
    """Borde superior con el título incrustado (`╭─ TÍTULO ───╮`)."""
    etiqueta = f"╭─ {titulo.upper()} "
    guiones = max(0, ANCHO - _vis_len(etiqueta) - 1)
    return "  " + cyan("╭─ ") + blanco(titulo.upper()) + cyan(" " + "─" * guiones + "╮")


def panel(titulo: str, filas: list[str], subtitulo: str | None = None) -> None:
    """Panel enmarcado con filas ya formateadas (bordes laterales y relleno)."""
    print(_borde_superior(titulo))
    if subtitulo:
        print(cyan("  │") + gris(f" {subtitulo}".ljust(_INNER)) + cyan("│"))
        print(cyan("  ├" + "─" * _INNER + "┤"))
    for fila in filas:
        relleno = max(0, _INNER - 1 - _vis_len(fila))
        print(cyan("  │ ") + fila + " " * relleno + cyan("│"))
    print(cyan("  ╰" + "─" * _INNER + "╯"))


def imprimir_menu(titulo: str, opciones: list[tuple[str, str]], subtitulo: str | None = None) -> None:
    """Menú enmarcado con el título incrustado en el borde superior."""
    print(_borde_superior(titulo))

    if subtitulo:
        texto_sub = f" {subtitulo}".ljust(_INNER)
        print(cyan("  │") + gris(texto_sub) + cyan("│"))
        print(cyan("  ├" + "─" * _INNER + "┤"))

    for clave, desc in opciones:
        if clave == "0":
            badge = rojo(f"[{clave}]")
        else:
            badge = cyan(f"[{clave}]")
        print(f"     {badge}  {desc}")

    print(cyan("  ╰" + "─" * _INNER + "╯"))
