import os
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CARPETA_DICCIONARIOS = BASE_DIR / "diccionarios"


def asegurar_carpeta() -> Path:
    CARPETA_DICCIONARIOS.mkdir(parents=True, exist_ok=True)
    return CARPETA_DICCIONARIOS


def listar_diccionarios() -> list[Path]:
    carpeta = asegurar_carpeta()
    return sorted([p for p in carpeta.iterdir() if p.is_file()])


def mostrar_estado_diccionarios() -> list[Path]:
    archivos = listar_diccionarios()
    print(f"\n=== GESTIÓN DE DICCIONARIOS ===")
    print(f"Carpeta: {CARPETA_DICCIONARIOS}")

    if not archivos:
        print("Estado: Carpeta vacía")
        print(f"-> Para añadir diccionarios, mételos en: {CARPETA_DICCIONARIOS}")
    else:
        print("Diccionarios disponibles:")
        for idx, archivo in enumerate(archivos, start=1):
            print(f"  {idx}) {archivo.name}")
        print(f"-> Para añadir más diccionarios, mételos en: {CARPETA_DICCIONARIOS}")

    return archivos


def _ejecutar(cmd: list[str]) -> None:
    print(f"\n[+] Ejecutando: {' '.join(cmd)}\n" + "-" * 45)
    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print(f"[!] Herramienta no encontrada: '{cmd[0]}'")


def _menu_crear_diccionario() -> Path | None:
    carpeta = asegurar_carpeta()
    while True:
        print("\n--- CREAR / PREPARAR DICCIONARIO ---")
        print("1) Generar con Crunch (en carpeta diccionarios/)")
        print("2) Generar con CUPP interactivo")
        print("3) Unir dos diccionarios sin duplicados (sort -u)")
        print("4) Descomprimir rockyou.txt.gz")
        print("0) Volver")

        op = input("Elige opción: ").strip()

        if op == "1":
            min_len = input("Longitud mínima: ").strip()
            max_len = input("Longitud máxima: ").strip()
            charset = input("Conjunto de caracteres (o deja vacío si usas patrón -t): ").strip()
            patron = input("Patrón -t (opcional, ej. @@%%): ").strip()
            nombre = input("Nombre del archivo de salida [crunch_dict.txt]: ").strip() or "crunch_dict.txt"
            salida = carpeta / nombre

            cmd = ["crunch", min_len, max_len]
            if charset:
                cmd.append(charset)
            if patron:
                cmd.extend(["-t", patron])
            cmd.extend(["-o", str(salida)])
            _ejecutar(cmd)

            if salida.exists():
                print(f"[+] Diccionario creado en: {salida}")
                return salida
        elif op == "2":
            if shutil.which("cupp"):
                _ejecutar(["cupp", "-i"])
            elif os.path.exists(BASE_DIR / "cupp.py"):
                _ejecutar(["python3", str(BASE_DIR / "cupp.py"), "-i"])
            else:
                print("[!] CUPP no está instalado. Instálalo con: sudo apt install cupp")
        elif op == "3":
            archivos = listar_diccionarios()
            if len(archivos) < 2:
                print(f"[!] Necesitas al menos 2 diccionarios en {carpeta} para unirlos.")
                continue
            for idx, a in enumerate(archivos, start=1):
                print(f"  {idx}) {a.name}")
            i1 = input("Número del primer diccionario: ").strip()
            i2 = input("Número del segundo diccionario: ").strip()
            if i1.isdigit() and i2.isdigit() and 1 <= int(i1) <= len(archivos) and 1 <= int(i2) <= len(archivos):
                f1 = archivos[int(i1) - 1]
                f2 = archivos[int(i2) - 1]
                nombre = input("Nombre del archivo final [combinado.txt]: ").strip() or "combinado.txt"
                salida = carpeta / nombre
                _ejecutar(["bash", "-c", f"cat '{f1}' '{f2}' | sort -u > '{salida}'"])
                if salida.exists():
                    print(f"[+] Diccionario combinado guardado en: {salida}")
                    return salida
            else:
                print("[!] Selección no válida.")
        elif op == "4":
            origen = input("Ruta del .gz [/usr/share/wordlists/rockyou.txt.gz]: ").strip() or "/usr/share/wordlists/rockyou.txt.gz"
            destino = carpeta / "rockyou.txt"
            if os.path.exists(origen):
                _ejecutar(["bash", "-c", f"gzip -dk -c '{origen}' > '{destino}'"])
                if destino.exists():
                    print(f"[+] Descomprimido en: {destino}")
                    return destino
            else:
                print(f"[!] No existe el archivo: {origen}")
        elif op == "0":
            return None
        else:
            print("[!] Opción no válida.")


def menu_diccionarios(diccionario_actual: str | None = None) -> str | None:
    while True:
        archivos = mostrar_estado_diccionarios()
        if diccionario_actual:
            print(f"Diccionario activo en sesión: {diccionario_actual}")

        print("\nOpciones:")
        print("1) Utilizar un diccionario de la carpeta")
        print("2) Crear o preparar un diccionario nuevo")
        print("0) Volver al menú principal")

        op = input("Elige una opción: ").strip()

        if op == "1":
            if not archivos:
                print(f"[!] No hay diccionarios disponibles. Mételos en: {CARPETA_DICCIONARIOS}")
                continue
            sel = input("Elige el número de diccionario: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(archivos):
                elegido = archivos[int(sel) - 1]
                print(f"[+] Diccionario seleccionado: {elegido.name}")
                return str(elegido)
            print("[!] Número no válido.")
        elif op == "2":
            creado = _menu_crear_diccionario()
            if creado and creado.exists():
                usar = input(f"¿Usar '{creado.name}' como diccionario activo ahora? (s/n): ").strip().lower()
                if usar == "s":
                    return str(creado)
        elif op == "0":
            return diccionario_actual
        else:
            print("[!] Opción no válida.")