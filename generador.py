"""
generador.py
Genera los archivos de entrada ventas_sucursal_NNN.csv para la Parte 1.

Cambio respecto de la version original: antes TODOS los archivos incluian un
registro invalido, por lo que el gestor de cierre nunca podia clasificar
ningun reporte como aprobado. Ahora la mitad de las sucursales se generan
limpias (0 invalidos -> aprobados/) y el resto con uno o mas registros
invalidos (-> observados/).

Uso:  python3 generador.py     (ejecutar desde la raiz del proyecto)
"""

import os
import random
from datetime import datetime, timedelta
from pathlib import Path

# La carpeta entrada/ se crea siempre junto a este archivo, sin importar
# desde que directorio se invoque python3 generador.py. Antes usaba la ruta
# relativa "entrada", que dependia del directorio de trabajo: si se ejecutaba
# desde src/ el script creaba src/entrada/ por error.
RAIZ = Path(__file__).resolve().parent
ENTRADA = RAIZ / "entrada"

# Semilla fija: la entrega debe ser reproducible (README con pasos repetibles).
SEMILLA = 20260909
random.seed(SEMILLA)

CANTIDAD_SUCURSALES = 20
REGISTROS_VALIDOS_POR_ARCHIVO = 10

# Sucursales que llevaran registros invalidos. El resto queda limpia.
# Se declaran explicitamente para poder justificar en el informe cuantos
# reportes deben terminar en aprobados/ y cuantos en observados/.
SUCURSALES_CON_ERRORES = {3, 7, 11, 14, 18, 20}

CATEGORIAS_VALIDAS = ["ALIMENTOS", "TECNOLOGIA", "HOGAR", "VESTUARIO"]
MEDIOS_PAGO_VALIDOS = ["EFECTIVO", "TARJETA", "TRANSFERENCIA"]
CABECERA = "id_venta;fecha;codigo_producto;categoria;cantidad;precio_unitario;medio_pago\n"

FECHA_BASE = datetime(2026, 9, 2)


def construir_registros_validos():
    """Devuelve 10 lineas validas cumpliendo los minimos de la Parte 1:
    al menos 2 categorias distintas, 2 medios de pago distintos y 1 producto
    repetido."""
    cat1, cat2 = random.sample(CATEGORIAS_VALIDAS, 2)
    pago1, pago2 = random.sample(MEDIOS_PAGO_VALIDOS, 2)
    producto_repetido = f"P{random.randint(1000, 2000)}"

    lineas = []
    fecha = FECHA_BASE.strftime("%Y-%m-%d")

    # Dos ventas del mismo producto con distinta categoria y medio de pago.
    lineas.append(
        f"V001;{fecha};{producto_repetido};{cat1};"
        f"{random.randint(1, 5)};{random.randint(1000, 50000)};{pago1}\n"
    )
    lineas.append(
        f"V002;{fecha};{producto_repetido};{cat2};"
        f"{random.randint(1, 5)};{random.randint(1000, 50000)};{pago2}\n"
    )

    for j in range(3, REGISTROS_VALIDOS_POR_ARCHIVO + 1):
        fecha_venta = (FECHA_BASE + timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d")
        lineas.append(
            f"V{j:03d};{fecha_venta};P{random.randint(3000, 9999)};"
            f"{random.choice(CATEGORIAS_VALIDAS)};{random.randint(1, 10)};"
            f"{random.randint(1500, 200000)};{random.choice(MEDIOS_PAGO_VALIDOS)}\n"
        )

    return lineas


def construir_registros_invalidos(indice_inicial):
    """Devuelve entre 1 y 3 lineas invalidas, cada una violando una regla
    distinta. Sirve para demostrar que la validacion detecta varios motivos."""
    plantillas = [
        # Formato de fecha incorrecto (debe ser AAAA-MM-DD).
        lambda n: f"V{n:03d};02-09-2026;P9999;ALIMENTOS;3;1000;EFECTIVO\n",
        # Categoria fuera de las cuatro permitidas.
        lambda n: f"V{n:03d};2026-09-03;P9998;JUGUETES;2;1500;TARJETA\n",
        # Cantidad negativa.
        lambda n: f"V{n:03d};2026-09-03;P9997;HOGAR;-5;2500;EFECTIVO\n",
        # Medio de pago invalido.
        lambda n: f"V{n:03d};2026-09-04;P9996;VESTUARIO;1;3000;CHEQUE\n",
        # Numero incorrecto de campos (faltan dos).
        lambda n: f"V{n:03d};2026-09-04;P9995;HOGAR;2\n",
        # Precio no numerico.
        lambda n: f"V{n:03d};2026-09-05;P9994;TECNOLOGIA;1;abc;TARJETA\n",
    ]

    cantidad = random.randint(1, 3)
    elegidas = random.sample(plantillas, cantidad)
    return [plantilla(indice_inicial + i) for i, plantilla in enumerate(elegidas)]


def main():
    ENTRADA.mkdir(parents=True, exist_ok=True)

    limpias = 0
    con_errores = 0

    for i in range(1, CANTIDAD_SUCURSALES + 1):
        ruta = ENTRADA / f"ventas_sucursal_{i:03d}.csv"
        lineas = construir_registros_validos()

        if i in SUCURSALES_CON_ERRORES:
            lineas.extend(construir_registros_invalidos(REGISTROS_VALIDOS_POR_ARCHIVO + 1))
            con_errores += 1
        else:
            limpias += 1

        with open(ruta, "w", encoding="utf-8") as f:
            f.write(CABECERA)
            f.writelines(lineas)

    print(f"Archivos generados en entrada/: {CANTIDAD_SUCURSALES}")
    print(f"  Sin registros invalidos (iran a aprobados/):  {limpias}")
    print(f"  Con registros invalidos (iran a observados/): {con_errores}")
    print(f"  Sucursales con errores: {sorted(SUCURSALES_CON_ERRORES)}")
    print(f"  Semilla utilizada: {SEMILLA}")


if __name__ == "__main__":
    main()
