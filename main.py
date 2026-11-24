import sys
import time
from pathlib import Path

from ataque import menu_ataque
from conexion import menu_conexion
from diccionarios import menu_diccionarios
from entorno import chequear_entorno
from reconocimiento import menu_reconocimiento
from ui import (
    barra_sesion,
    cyan,
    gris,
    imprimir_menu,
    limpiar,
    msg_aviso,
    msg_info,
    msg_nota,
    pausar,
    verde,
)

BASE_DIR = Path(__file__).resolve().parent
CARPETA_DICCIONARIOS = BASE_DIR / "diccionarios"
CARPETA_RESULTADOS = BASE_DIR / "resultados"
CARPETA_ESCANEO = CARPETA_RESULTADOS / "escaneos"


def inicializar_carpetas() -> None:
    CARPETA_DICCIONARIOS.mkdir(parents=True, exist_ok=True)
    CARPETA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    CARPETA_ESCANEO.mkdir(parents=True, exist_ok=True)


def animacion_inicio() -> None:
    limpiar()
    ancho = 62
    vacia = " " * ancho
    lineas = [
        cyan("  ╭" + "─" * ancho + "╮"),
        cyan("  │") + vacia + cyan("│"),
        cyan("  │") + verde("B R U T E F O R C E   O S".center(ancho)) + cyan("│"),
        cyan("  │") + vacia + cyan("│"),
        cyan("  │") + gris("Creado por  ·  Marcos Paniego López".center(ancho)) + cyan("│"),
        cyan("  │") + gris("Uso exclusivo en entornos de prueba autorizados".center(ancho)) + cyan("│"),
        cyan("  │") + vacia + cyan("│"),
        cyan("  ╰" + "─" * ancho + "╯"),
    ]
    for linea in lineas:
        print(linea)
        time.sleep(0.06)


def resetear_sesion(sesion: dict) -> None:
    sesion["objetivo_ip"] = None
    sesion["diccionario"] = None
    msg_info("Sesión reseteada. Los escaneos y dispositivos guardados se mantienen.")
    pausar()


def main() -> None:
    inicializar_carpetas()
    animacion_inicio()
    chequear_entorno()
    pausar()

    sesion = {
        "objetivo_ip": None,
        "diccionario": None,
    }

    opciones_menu = [
        ("1", "Reconocimiento y análisis de red / SO"),
        ("2", "Gestión y creación de diccionarios"),
        ("3", "Pruebas de acceso y credenciales"),
        ("4", "Acceso por IP / Dispositivos anteriores"),
        ("5", "Resetear objetivo de la sesión actual"),
        ("0", "Salir"),
    ]

    while True:
        limpiar()
        print(cyan("BRUTEFORCE OS") + gris("  |  Autor: Marcos Paniego López"))
        barra_sesion(sesion["objetivo_ip"], sesion["diccionario"])
        imprimir_menu("Menú Principal", opciones_menu)

        try:
            opcion = input(verde("Elige una opción: ")).strip()

            if opcion == "1":
                sesion["objetivo_ip"] = menu_reconocimiento(sesion["objetivo_ip"])
            elif opcion == "2":
                sesion["diccionario"] = menu_diccionarios(sesion["diccionario"])
            elif opcion == "3":
                sesion["objetivo_ip"] = menu_ataque(sesion["objetivo_ip"], sesion["diccionario"])
            elif opcion == "4":
                sesion["objetivo_ip"] = menu_conexion(sesion["objetivo_ip"])
            elif opcion == "5":
                resetear_sesion(sesion)
            elif opcion == "0":
                limpiar()
                msg_info("Saliendo de BruteForceOS. ¡Hasta la próxima prueba!")
                sys.exit(0)
            else:
                msg_aviso("Opción no válida. Revisa las opciones disponibles.")
                pausar()
        except KeyboardInterrupt:
            print()
            msg_nota("Operación cancelada. Volviendo al menú principal.")
            pausar()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        sys.exit(0)