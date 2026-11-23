import os
import sys

# Desactiva colores si la salida no es una TTY interactiva
COLOR_ACTIVO = sys.stdout.isatty()


def _c(codigo: str, texto: str) -> str:
    if not COLOR_ACTIVO:
        return texto
    return f"\033[{codigo}m{texto}\033[0m"


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


def limpiar() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pausar(mensaje: str = "Pulsa ENTER para continuar...") -> None:
    input(gris(f"\n{mensaje}"))


def msg_ok(texto: str) -> None:
    print(verde(f"[OK] {texto}"))


def msg_info(texto: str) -> None:
    print(cyan(f"[+] {texto}"))


def msg_nota(texto: str) -> None:
    print(azul(f"[i] {texto}"))


def msg_aviso(texto: str) -> None:
    print(amarillo(f"[!] {texto}"))


def msg_error(texto: str) -> None:
    print(rojo(f"[X] {texto}"))


def cabecera_seccion(titulo: str, subtitulo: str | None = None) -> None:
    ancho = 62
    borde = "=" * ancho
    print(cyan(borde))
    print(cyan(f"  {titulo.upper().center(ancho - 4)}"))
    if subtitulo:
        print(gris(f"  {subtitulo.center(ancho - 4)}"))
    print(cyan(borde))


def barra_sesion(objetivo_ip: str | None, diccionario: str | None) -> None:
    ip_txt = verde(objetivo_ip) if objetivo_ip else gris("Ninguna")
    if diccionario:
        nombre_dic = os.path.basename(diccionario)
        dic_txt = verde(nombre_dic)
    else:
        dic_txt = gris("Ninguno")

    print(gris("-" * 62))
    print(f"  Objetivo: {ip_txt}   |   Diccionario: {dic_txt}")
    print(gris("-" * 62))


def imprimir_menu(titulo: str, opciones: list[tuple[str, str]], subtitulo: str | None = None) -> None:
    cabecera_seccion(titulo, subtitulo)
    for clave, desc in opciones:
        if clave == "0":
            print(f"  {rojo(f'[{clave}]')} {desc}")
        else:
            print(f"  {cyan(f'[{clave}]')} {desc}")
    print(gris("-" * 62))