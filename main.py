import os
import sys
import time
from pathlib import Path

from ataque import menu_ataque
from conexion import menu_conexion
from diccionarios import menu_diccionarios
from reconocimiento import menu_reconocimiento

BASE_DIR = Path(__file__).resolve().parent
CARPETA_DICCIONARIOS = BASE_DIR / "diccionarios"
CARPETA_RESULTADOS = BASE_DIR / "resultados"
CARPETA_ESCANEO = CARPETA_RESULTADOS / "escaneos"


def inicializar_carpetas() -> None:
    CARPETA_DICCIONARIOS.mkdir(parents=True, exist_ok=True)
    CARPETA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    CARPETA_ESCANEO.mkdir(parents=True, exist_ok=True)


def animacion_inicio() -> None:
    os.system("cls" if os.name == "nt" else "clear")
    banner = [
        "=============================================================",
        "                  B R U T E F O R C E  O S                 ",
        "       Programa creado por: Marcos Paniego López            ",
        "   AVISO: Uso exclusivo en entornos de prueba autorizados   ",
        "=============================================================",
    ]
    for linea in banner:
        print(linea)
        time.sleep(0.08)


def mostrar_estado_sesion(sesion: dict) -> None:
    ip_actual = sesion.get("objetivo_ip") or "Ninguna"
    dic_actual = sesion.get("diccionario") or "Ninguno"
    print(f"\n[Sesión] Objetivo actual: {ip_actual} | Diccionario: {dic_actual}")


def resetear_sesion(sesion: dict) -> None:
    sesion["objetivo_ip"] = None
    sesion["diccionario"] = None
    print("\n[+] Sesión/objetivo actual reseteado (los resultados guardados se mantienen).")


def mostrar_menu() -> None:
    print("\n--- MENÚ PRINCIPAL ---")
    print("1) Reconocimiento y análisis de red / SO")
    print("2) Gestión y creación de diccionarios")
    print("3) Pruebas de acceso y credenciales")
    print("4) Acceso por IP / Dispositivos anteriores")
    print("5) Resetear objetivo de la sesión actual")
    print("0) Salir")


def main() -> None:
    inicializar_carpetas()
    animacion_inicio()

    sesion = {
        "objetivo_ip": None,
        "diccionario": None,
    }

    while True:
        mostrar_estado_sesion(sesion)
        mostrar_menu()
        opcion = input("\nElige una opción: ").strip()

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
            print("\nSaliendo de BruteForceOS...")
            sys.exit(0)
        else:
            print("\n[!] Opción no válida. Inténtalo de nuevo.")


if __name__ == "__main__":
    main()