"""
secuencial.py
Analizador de ventas - version SECUENCIAL (un solo hilo, un archivo a la vez).

Lee entrada/ventas_sucursal_NNN.csv, valida cada registro, genera un reporte
individual por sucursal en salida/, un consolidado en salida/ y el detalle de
los registros rechazados en errores/.

Uso:  python3 src/secuencial.py     (desde la raiz del proyecto o desde donde sea)
"""

import time
from datetime import datetime
from pathlib import Path

# La raiz del proyecto se calcula a partir de la ubicacion de este archivo
# (src/ esta un nivel bajo la raiz). Asi el script funciona sin importar
# desde que directorio se invoque.
RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "entrada"
SALIDA = RAIZ / "salida"
ERRORES = RAIZ / "errores"

VERSION = "secuencial"
TRABAJADORES = 1

CATEGORIAS_VALIDAS = {"ALIMENTOS", "TECNOLOGIA", "HOGAR", "VESTUARIO"}
MEDIOS_PAGO_VALIDOS = {"EFECTIVO", "TARJETA", "TRANSFERENCIA"}


def validar_registro(linea, ids_vistos):
    """Valida una linea del CSV.

    IMPORTANTE: esta funcion debe ser identica a la de concurrente.py. Si las
    dos versiones validan distinto, las metricas no coinciden y la comparacion
    exigida por el enunciado deja de tener sentido.

    Devuelve (True, tupla_de_campos) o (False, motivo).
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
    """Devuelve la clave con mayor valor. Ante empate gana la clave menor en
    orden alfabetico, para que secuencial y concurrente entreguen el mismo
    resultado en vez de depender del orden de recorrido."""
    if not acumulador:
        return "N/A"
    return sorted(acumulador.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def procesar_archivo(ruta, manejador_errores):
    """Procesa un CSV y devuelve el diccionario de metricas de esa sucursal."""
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
                manejador_errores(ruta.name, num_linea, resultado, linea.strip())
                continue

            validos += 1
            _, _, cod, cat, cant, precio, pago = resultado
            subtotal = cant * precio

            unidades += cant
            monto += subtotal
            cat_monto[cat] = cat_monto.get(cat, 0) + subtotal
            pago_uso[pago] = pago_uso.get(pago, 0) + 1
            prod_unidades[cod] = prod_unidades.get(cod, 0) + cant

    return {
        "sucursal": sucursal,
        "archivo": ruta.name,
        "leidos": leidos,
        "validos": validos,
        "invalidos": invalidos,
        "unidades": unidades,
        "monto": monto,
        "cat_monto": cat_monto,
        "pago_uso": pago_uso,
        "prod_unidades": prod_unidades,
    }


def escribir_reporte_individual(m):
    ruta = SALIDA / f"reporte_ventas_sucursal_{m['sucursal']}.txt"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("REPORTE DE VENTAS POR SUCURSAL\n")
        f.write(f"Archivo procesado: {m['archivo']}\n")
        f.write(f"Sucursal: {m['sucursal']}\n")
        f.write(f"Registros leidos: {m['leidos']}\n")
        f.write(f"Registros validos: {m['validos']}\n")
        f.write(f"Registros invalidos: {m['invalidos']}\n")
        f.write(f"Unidades vendidas: {m['unidades']}\n")
        f.write(f"Monto total vendido: ${m['monto']:,}\n")
        f.write(f"Categoria con mayor venta: {clave_top(m['cat_monto'])}\n")
        f.write(f"Medio de pago mas utilizado: {clave_top(m['pago_uso'])}\n")
        f.write(f"Producto mas vendido: {clave_top(m['prod_unidades'])}\n")
    return ruta


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    ERRORES.mkdir(parents=True, exist_ok=True)

    if not ENTRADA.is_dir():
        print(f"ERROR: no existe la carpeta {ENTRADA}. Ejecute primero generador.py")
        return

    ruta_errores = ERRORES / "registros_invalidos.txt"
    archivo_errores = open(ruta_errores, "w", encoding="utf-8")

    def registrar_error(archivo, num_linea, motivo, contenido):
        archivo_errores.write(f"{archivo};{num_linea};{motivo};{contenido}\n")

    # sorted() garantiza un orden estable de procesamiento.
    rutas = sorted(ENTRADA.glob("ventas_sucursal_*.csv"))

    g = {"archivos": 0, "leidos": 0, "validos": 0, "invalidos": 0, "unidades": 0, "monto": 0}
    g_cat, g_pago = {}, {}

    inicio = time.perf_counter()

    for ruta in rutas:
        try:
            m = procesar_archivo(ruta, registrar_error)
        except OSError as error:
            # Error controlado: si un archivo no se puede leer se registra y
            # el proceso continua con el resto.
            registrar_error(ruta.name, 0, f"No se pudo procesar: {error}", "")
            continue

        escribir_reporte_individual(m)

        g["archivos"] += 1
        g["leidos"] += m["leidos"]
        g["validos"] += m["validos"]
        g["invalidos"] += m["invalidos"]
        g["unidades"] += m["unidades"]
        g["monto"] += m["monto"]
        for k, v in m["cat_monto"].items():
            g_cat[k] = g_cat.get(k, 0) + v
        for k, v in m["pago_uso"].items():
            g_pago[k] = g_pago.get(k, 0) + v

    duracion = time.perf_counter() - inicio
    archivo_errores.close()

    with open(SALIDA / "consolidado_ventas.txt", "w", encoding="utf-8") as f:
        f.write("REPORTE CONSOLIDADO DE VENTAS\n")
        f.write(f"Version ejecutada: {VERSION}\n")
        f.write(f"Archivos procesados: {g['archivos']}\n")
        f.write(f"Registros leidos: {g['leidos']}\n")
        f.write(f"Registros validos: {g['validos']}\n")
        f.write(f"Registros invalidos: {g['invalidos']}\n")
        f.write(f"Unidades vendidas: {g['unidades']}\n")
        f.write(f"Monto total vendido: ${g['monto']:,}\n")
        f.write(f"Categoria con mayor monto acumulado: {clave_top(g_cat)}\n")
        f.write(f"Medio de pago mas utilizado: {clave_top(g_pago)}\n")
        f.write(f"Tiempo total de ejecucion: {duracion:.4f} segundos\n")
        f.write(f"Cantidad de trabajadores: {TRABAJADORES}\n")

    print(f"[{VERSION}] archivos procesados: {g['archivos']}")
    print(f"[{VERSION}] registros validos: {g['validos']} | invalidos: {g['invalidos']}")
    print(f"[{VERSION}] unidades vendidas: {g['unidades']}")
    print(f"[{VERSION}] monto total vendido: ${g['monto']:,}")
    print(f"[{VERSION}] tiempo total: {duracion:.4f} s")


if __name__ == "__main__":
    main()
