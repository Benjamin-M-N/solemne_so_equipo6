"""
concurrente.py
Analizador de ventas - version CONCURRENTE.

Arquitectura productor / consumidores:
  - La cola se llena con las rutas de los CSV antes de levantar los hilos.
  - N hilos trabajadores consumen la cola y procesan un archivo cada uno.
  - queue.Queue: cola sincronizada (thread-safe por diseno).
  - Dos threading.Lock: uno protege el archivo de errores, otro los
    acumuladores globales.
  - Centinelas (None): una por trabajador, para un termino ordenado.

Produce exactamente los mismos archivos y las mismas metricas que
secuencial.py; solo debe variar el tiempo de ejecucion.

Uso:  python3 src/concurrente.py
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "entrada"
SALIDA = RAIZ / "salida"
ERRORES = RAIZ / "errores"

VERSION = "concurrente"
TRABAJADORES = 4
CENTINELA = None

CATEGORIAS_VALIDAS = {"ALIMENTOS", "TECNOLOGIA", "HOGAR", "VESTUARIO"}
MEDIOS_PAGO_VALIDOS = {"EFECTIVO", "TARJETA", "TRANSFERENCIA"}

# --------------------------------------------------------------------------
# Recursos COMPARTIDOS entre hilos
# --------------------------------------------------------------------------
cola_archivos = Queue()
bloqueo_errores = threading.Lock()
bloqueo_totales = threading.Lock()

totales = {"archivos": 0, "leidos": 0, "validos": 0, "invalidos": 0,
           "unidades": 0, "monto": 0, "fallidos": 0}
cat_global = {}
pago_global = {}

archivo_errores = None  # se abre una sola vez en main()


def validar_registro(linea, ids_vistos):
    """Identica a la de secuencial.py.

    La version original comprobaba la fecha con len(fecha.split("-")) != 3,
    que acepta "02-09-2026" como valida. secuencial.py usaba strptime, que la
    rechaza. Esa diferencia hacia que las dos versiones pudieran contar
    distinto numero de registros invalidos sobre el mismo conjunto de datos.
    """
    campos = linea.strip().split(";")
    if len(campos) != 7:
        return False, "Numero incorrecto de campos"

    id_venta, fecha, cod, cat, cant, precio, pago = campos

    if not id_venta:
        return False, "ID de venta vacio"
    if id_venta in ids_vistos:
        return False, "ID de venta duplicado"

    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        return False, "Formato de fecha incorrecto"

    if not cod:
        return False, "Codigo de producto vacio"
    if cat not in CATEGORIAS_VALIDAS:
        return False, f"Categoria invalida ({cat})"

    try:
        cant = int(cant)
    except ValueError:
        return False, "Cantidad no es un entero"
    if cant <= 0:
        return False, "Cantidad debe ser mayor a 0"

    try:
        precio = int(precio)
    except ValueError:
        return False, "Precio no es un entero"
    if precio <= 0:
        return False, "Precio debe ser mayor a 0"

    if pago not in MEDIOS_PAGO_VALIDOS:
        return False, f"Medio de pago invalido ({pago})"

    ids_vistos.add(id_venta)
    return True, (id_venta, fecha, cod, cat, cant, precio, pago)


def clave_top(acumulador):
    """Misma regla de desempate que secuencial.py."""
    if not acumulador:
        return "N/A"
    return sorted(acumulador.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def registrar_error(nombre_archivo, num_linea, motivo, contenido):
    """Seccion critica 1: escritura en el archivo de errores compartido."""
    with bloqueo_errores:
        archivo_errores.write(f"{nombre_archivo};{num_linea};{motivo};{contenido}\n")


def procesar_archivo(ruta):
    """Procesa un CSV. Solo toca estructuras locales al hilo."""
    sucursal = ruta.name.replace("ventas_sucursal_", "").replace(".csv", "")
    ids_vistos = set()

    leidos = validos = invalidos = unidades = monto = 0
    cat_monto, pago_uso, prod_unidades = {}, {}, {}

    with open(ruta, "r", encoding="utf-8") as f:
        f.readline()  # descartar cabecera
        for num_linea, linea in enumerate(f, start=2):
            if not linea.strip():
                continue
            leidos += 1

            es_valido, resultado = validar_registro(linea, ids_vistos)
            if not es_valido:
                invalidos += 1
                registrar_error(ruta.name, num_linea, resultado, linea.strip())
                continue

            validos += 1
            _, _, cod, cat, cant, precio, pago = resultado
            subtotal = cant * precio

            unidades += cant
            monto += subtotal
            cat_monto[cat] = cat_monto.get(cat, 0) + subtotal
            pago_uso[pago] = pago_uso.get(pago, 0) + 1
            prod_unidades[cod] = prod_unidades.get(cod, 0) + cant

    # El nombre debe ser reporte_ventas_sucursal_NNN.txt tal como lo exige el
    # enunciado. La version original insertaba la palabra "concurrente" en el
    # nombre, con lo que el gestor de cierre no habria detectado estos
    # reportes y salida/ habria quedado con dos juegos de archivos distintos.
    ruta_reporte = SALIDA / f"reporte_ventas_sucursal_{sucursal}.txt"
    with open(ruta_reporte, "w", encoding="utf-8") as f:
        f.write("REPORTE DE VENTAS POR SUCURSAL\n")
        f.write(f"Archivo procesado: {ruta.name}\n")
        f.write(f"Sucursal: {sucursal}\n")
        f.write(f"Registros leidos: {leidos}\n")
        f.write(f"Registros validos: {validos}\n")
        f.write(f"Registros invalidos: {invalidos}\n")
        f.write(f"Unidades vendidas: {unidades}\n")
        f.write(f"Monto total vendido: ${monto:,}\n")
        f.write(f"Categoria con mayor venta: {clave_top(cat_monto)}\n")
        f.write(f"Medio de pago mas utilizado: {clave_top(pago_uso)}\n")
        f.write(f"Producto mas vendido: {clave_top(prod_unidades)}\n")

    return {"leidos": leidos, "validos": validos, "invalidos": invalidos,
            "unidades": unidades, "monto": monto,
            "cat_monto": cat_monto, "pago_uso": pago_uso}


def trabajador(numero):
    """Consume rutas de la cola hasta recibir el centinela."""
    while True:
        ruta = cola_archivos.get()

        if ruta is CENTINELA:
            cola_archivos.task_done()
            break

        try:
            m = procesar_archivo(ruta)
        except (OSError, UnicodeDecodeError) as error:
            # Error controlado: el hilo no muere, se registra y sigue.
            with bloqueo_totales:
                totales["fallidos"] += 1
            registrar_error(ruta.name, 0, f"No se pudo procesar: {error}", "")
        else:
            # Seccion critica 2: acumuladores globales.
            with bloqueo_totales:
                totales["archivos"] += 1
                totales["leidos"] += m["leidos"]
                totales["validos"] += m["validos"]
                totales["invalidos"] += m["invalidos"]
                totales["unidades"] += m["unidades"]
                totales["monto"] += m["monto"]
                for k, v in m["cat_monto"].items():
                    cat_global[k] = cat_global.get(k, 0) + v
                for k, v in m["pago_uso"].items():
                    pago_global[k] = pago_global.get(k, 0) + v
        finally:
            # En la version original task_done() estaba fuera de un finally.
            # Si procesar_archivo lanzaba una excepcion, la tarea nunca se
            # marcaba como terminada y cola.join() se quedaba colgado para
            # siempre.
            cola_archivos.task_done()


def main():
    global archivo_errores

    SALIDA.mkdir(parents=True, exist_ok=True)
    ERRORES.mkdir(parents=True, exist_ok=True)

    if not ENTRADA.is_dir():
        print(f"ERROR: no existe la carpeta {ENTRADA}. Ejecute primero generador.py")
        return

    archivo_errores = open(ERRORES / "registros_invalidos.txt", "w", encoding="utf-8")

    rutas = sorted(ENTRADA.glob("ventas_sucursal_*.csv"))
    for ruta in rutas:
        cola_archivos.put(ruta)

    inicio = time.perf_counter()

    hilos = [
        threading.Thread(target=trabajador, args=(n + 1,), name=f"trabajador-{n + 1}")
        for n in range(TRABAJADORES)
    ]
    for h in hilos:
        h.start()

    # Una centinela por trabajador: se encolan detras de los archivos, asi que
    # cada hilo solo la vera cuando ya no queden CSV por procesar.
    for _ in hilos:
        cola_archivos.put(CENTINELA)

    cola_archivos.join()
    for h in hilos:
        h.join()

    duracion = time.perf_counter() - inicio
    archivo_errores.close()

    with open(SALIDA / "consolidado_ventas.txt", "w", encoding="utf-8") as f:
        f.write("REPORTE CONSOLIDADO DE VENTAS\n")
        f.write(f"Version ejecutada: {VERSION}\n")
        f.write(f"Archivos procesados: {totales['archivos']}\n")
        f.write(f"Registros leidos: {totales['leidos']}\n")
        f.write(f"Registros validos: {totales['validos']}\n")
        f.write(f"Registros invalidos: {totales['invalidos']}\n")
        f.write(f"Unidades vendidas: {totales['unidades']}\n")
        f.write(f"Monto total vendido: ${totales['monto']:,}\n")
        f.write(f"Categoria con mayor monto acumulado: {clave_top(cat_global)}\n")
        f.write(f"Medio de pago mas utilizado: {clave_top(pago_global)}\n")
        f.write(f"Tiempo total de ejecucion: {duracion:.4f} segundos\n")
        f.write(f"Cantidad de trabajadores: {TRABAJADORES}\n")

    print(f"[{VERSION}] hilos trabajadores: {TRABAJADORES}")
    print(f"[{VERSION}] archivos procesados: {totales['archivos']} | fallidos: {totales['fallidos']}")
    print(f"[{VERSION}] registros validos: {totales['validos']} | invalidos: {totales['invalidos']}")
    print(f"[{VERSION}] unidades vendidas: {totales['unidades']}")
    print(f"[{VERSION}] monto total vendido: ${totales['monto']:,}")
    print(f"[{VERSION}] tiempo total: {duracion:.4f} s")


if __name__ == "__main__":
    main()
