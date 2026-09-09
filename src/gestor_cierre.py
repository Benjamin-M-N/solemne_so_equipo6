"""
gestor_cierre.py
Modulo de cierre comercial (Parte 2 / Parte 3 del enunciado).

Toma los reportes generados por la Parte 1 y:
  1. Detecta los archivos reporte_ventas_sucursal_NNN.txt en salida/.
  2. Lee el valor "Registros invalidos" de cada reporte.
  3. Mueve a cierre_comercial/aprobados/ los que tienen cero invalidos.
  4. Mueve a cierre_comercial/observados/ los que tienen uno o mas.
  5. Valida que el origen exista, sea archivo regular y que el destino sea seguro.
  6. Evita sobrescritura aplicando sufijo correlativo _1, _2, ...
  7. Copia salida/consolidado_ventas.txt a cierre_comercial/respaldos/ sin
     modificar el original.
  8. Crea cierre_comercial/inventario_cierre.csv.
  9. Registra todas las operaciones y errores en logs/cierre_comercial.log.
 10. Maneja errores controlados sin terminar abruptamente.

Uso:  python3 src/gestor_cierre.py
"""

import csv
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "salida"
ERRORES = RAIZ / "errores"
CIERRE = RAIZ / "cierre_comercial"
APROBADOS = CIERRE / "aprobados"
OBSERVADOS = CIERRE / "observados"
RESPALDOS = CIERRE / "respaldos"
LOGS = RAIZ / "logs"

RUTA_LOG = LOGS / "cierre_comercial.log"
RUTA_INVENTARIO = CIERRE / "inventario_cierre.csv"

PATRON_REPORTE = "reporte_ventas_sucursal_*.txt"
CABECERA_INVENTARIO = [
    "nombre_archivo", "tipo_reporte", "sucursal", "estado",
    "tamano_bytes", "fecha_modificacion", "ruta_final",
]

# Contadores para el resumen final.
resumen = {"aprobados": 0, "observados": 0, "respaldos": 0,
           "colisiones": 0, "errores": 0}


# ---------------------------------------------------------------------------
# Bitacora
# ---------------------------------------------------------------------------
def escribir_log(nivel, mensaje):
    """Bitacora persistente: se abre en modo append para no perder las
    ejecuciones anteriores."""
    marca = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{marca}] [{nivel}] {mensaje}"
    try:
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError as error:
        # Si ni siquiera se puede escribir la bitacora, al menos se avisa por
        # consola. El programa no se detiene por esto.
        print(f"No se pudo escribir en la bitacora: {error}", file=sys.stderr)
    print(linea)


def log_info(mensaje):
    escribir_log("INFO", mensaje)


def log_error(mensaje):
    resumen["errores"] += 1
    escribir_log("ERROR", mensaje)


# ---------------------------------------------------------------------------
# Validaciones y utilidades
# ---------------------------------------------------------------------------
def normalizar(texto):
    """Quita tildes y pasa a minusculas. Necesario porque los reportes pueden
    venir con 'Registros invalidos' o 'Registros invalidos' segun quien haya
    generado la Parte 1."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_tildes.lower()


def preparar_carpetas():
    for carpeta in (CIERRE, APROBADOS, OBSERVADOS, RESPALDOS, LOGS):
        carpeta.mkdir(parents=True, exist_ok=True)


def origen_valido(ruta):
    """Requisito 5: el origen debe existir y ser un archivo regular.
    Un directorio o un enlace roto se rechazan."""
    if not ruta.exists():
        log_error(f"El origen no existe: {ruta}")
        return False
    if not ruta.is_file():
        log_error(f"El origen no es un archivo regular: {ruta}")
        return False
    return True


def destino_seguro(destino, base_permitida):
    """Requisito 5: el destino debe quedar dentro de cierre_comercial/.
    Evita que un nombre manipulado (por ejemplo con ../) escriba fuera del
    arbol del proyecto."""
    try:
        destino_abs = destino.resolve()
        base_abs = base_permitida.resolve()
    except OSError as error:
        log_error(f"No se pudo resolver la ruta de destino {destino}: {error}")
        return False

    if not destino_abs.is_relative_to(base_abs):
        log_error(f"Destino fuera del area permitida: {destino_abs}")
        return False
    if not base_abs.is_dir():
        log_error(f"La carpeta de destino no existe: {base_abs}")
        return False
    return True


def ruta_sin_colision(destino):
    """Requisito 6: si el nombre ya existe en el destino, agrega un sufijo
    correlativo _1, _2, ... antes de la extension.

    Ejemplo: reporte_ventas_sucursal_001.txt ya existe
             -> reporte_ventas_sucursal_001_1.txt
    """
    if not destino.exists():
        return destino

    base = destino.stem
    extension = destino.suffix
    contador = 1
    while True:
        candidato = destino.with_name(f"{base}_{contador}{extension}")
        if not candidato.exists():
            resumen["colisiones"] += 1
            log_info(
                f"Colision detectada para {destino.name}. "
                f"Se usara el nombre {candidato.name} para no sobrescribir."
            )
            return candidato
        contador += 1


def leer_registros_invalidos(ruta):
    """Requisito 2: extrae el entero de la linea 'Registros invalidos: N'.
    Lanza ValueError si el reporte no tiene esa linea, para que el llamador
    decida que hacer sin que el programa caiga."""
    patron = re.compile(r"registros\s+invalidos\s*:\s*(\d+)")
    with open(ruta, "r", encoding="utf-8", errors="replace") as f:
        for linea in f:
            coincidencia = patron.search(normalizar(linea))
            if coincidencia:
                return int(coincidencia.group(1))
    raise ValueError("el reporte no contiene la linea 'Registros invalidos'")


def extraer_sucursal(nombre):
    coincidencia = re.search(r"sucursal_(\d+)", nombre)
    return coincidencia.group(1) if coincidencia else "SIN_ID"


def fila_inventario(ruta_final, nombre_original, tipo, sucursal, estado):
    info = ruta_final.stat()
    return {
        "nombre_archivo": ruta_final.name,
        "tipo_reporte": tipo,
        "sucursal": sucursal,
        "estado": estado,
        "tamano_bytes": info.st_size,
        "fecha_modificacion": datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "ruta_final": str(ruta_final.relative_to(RAIZ)),
    }


# ---------------------------------------------------------------------------
# Operaciones principales
# ---------------------------------------------------------------------------
def clasificar_reportes():
    """Requisitos 1, 3, 4: detecta, clasifica y MUEVE los reportes individuales."""
    filas = []
    rutas = sorted(SALIDA.glob(PATRON_REPORTE))

    if not rutas:
        log_error(
            f"No se encontraron archivos {PATRON_REPORTE} en {SALIDA}. "
            "Verifique que la Parte 1 se haya ejecutado."
        )
        return filas

    log_info(f"Reportes individuales detectados: {len(rutas)}")

    for ruta in rutas:
        if not origen_valido(ruta):
            continue

        sucursal = extraer_sucursal(ruta.name)

        try:
            invalidos = leer_registros_invalidos(ruta)
        except (OSError, ValueError) as error:
            # Error controlado: ante un reporte ilegible o mal formado se
            # asume el caso conservador (observado) en vez de descartarlo.
            log_error(f"{ruta.name}: {error}. Se clasifica como observado por precaucion.")
            invalidos = -1

        if invalidos == 0:
            carpeta, estado = APROBADOS, "aprobado"
        else:
            carpeta, estado = OBSERVADOS, "observado"

        destino = carpeta / ruta.name
        if not destino_seguro(destino, CIERRE):
            continue

        destino = ruta_sin_colision(destino)

        try:
            # move: el reporte individual cambia de ubicacion, no se duplica.
            shutil.move(str(ruta), str(destino))
        except (OSError, shutil.Error) as error:
            log_error(f"No se pudo mover {ruta.name} a {destino}: {error}")
            continue

        resumen[estado + "s"] += 1
        log_info(
            f"MOVER {ruta.name} -> {destino.relative_to(RAIZ)} "
            f"(registros invalidos: {invalidos if invalidos >= 0 else 'indeterminado'})"
        )
        filas.append(fila_inventario(destino, ruta.name, "individual", sucursal, estado))

    return filas


def respaldar_consolidado():
    """Requisito 7: COPIA el consolidado, dejando el original en salida/."""
    filas = []
    origen = SALIDA / "consolidado_ventas.txt"

    if not origen_valido(origen):
        log_error("No se genero el respaldo porque falta salida/consolidado_ventas.txt")
        return filas

    destino = RESPALDOS / origen.name
    if not destino_seguro(destino, CIERRE):
        return filas

    destino = ruta_sin_colision(destino)

    try:
        # copy2 preserva la fecha de modificacion del original.
        shutil.copy2(str(origen), str(destino))
    except (OSError, shutil.Error) as error:
        log_error(f"No se pudo respaldar {origen.name}: {error}")
        return filas

    if not origen.exists():
        log_error("El consolidado desaparecio de salida/ tras la copia.")
    else:
        log_info(f"COPIAR {origen.name} -> {destino.relative_to(RAIZ)} (original intacto en salida/)")

    resumen["respaldos"] += 1
    filas.append(fila_inventario(destino, origen.name, "consolidado", "GLOBAL", "respaldo"))
    return filas


def escribir_inventario(filas):
    """Requisito 8."""
    try:
        with open(RUTA_INVENTARIO, "w", encoding="utf-8", newline="") as f:
            # lineterminator="\n": por defecto el modulo csv escribe CRLF,
            # que en GNU/Linux queda como ^M al final de cada linea.
            escritor = csv.DictWriter(
                f, fieldnames=CABECERA_INVENTARIO, delimiter=";", lineterminator="\n"
            )
            escritor.writeheader()
            for fila in filas:
                escritor.writerow(fila)
    except OSError as error:
        log_error(f"No se pudo escribir el inventario: {error}")
        return
    log_info(f"Inventario generado con {len(filas)} registros en {RUTA_INVENTARIO.relative_to(RAIZ)}")


def demostrar_error_controlado():
    """Requisito 10: provoca deliberadamente un error de archivo inexistente
    para dejar constancia en la bitacora de que el programa lo captura y
    continua su ejecucion normal."""
    log_info("Prueba de manejo de error controlado: se intentara leer un archivo inexistente.")
    inexistente = SALIDA / "reporte_ventas_sucursal_999.txt"
    try:
        leer_registros_invalidos(inexistente)
    except FileNotFoundError:
        escribir_log(
            "ERROR",
            f"Error controlado capturado: no existe {inexistente.name}. "
            "El gestor continua sin interrumpirse."
        )
    except (OSError, ValueError) as error:
        escribir_log("ERROR", f"Error controlado capturado: {error}")


def main():
    preparar_carpetas()
    log_info("=== Inicio del cierre comercial ===")

    demostrar_error_controlado()

    filas = clasificar_reportes()
    filas.extend(respaldar_consolidado())
    escribir_inventario(filas)

    ruta_invalidos = ERRORES / "registros_invalidos.txt"
    if ruta_invalidos.is_file():
        log_info(f"Archivo de registros invalidos presente: {ruta_invalidos.relative_to(RAIZ)}")
    else:
        log_error("No se encontro errores/registros_invalidos.txt")

    log_info(
        f"Resumen: aprobados={resumen['aprobados']}, observados={resumen['observados']}, "
        f"respaldos={resumen['respaldos']}, colisiones={resumen['colisiones']}, "
        f"errores registrados={resumen['errores']}"
    )
    log_info("=== Fin del cierre comercial ===")


if __name__ == "__main__":
    main()
