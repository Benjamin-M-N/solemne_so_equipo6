# Solemne 1 - Parte Práctica 2 - Equipo 6

Sistemas Operativos NRC-14749 · Profesor René Galarce Godoy
Lenguaje: Python 3 · Sistema: Debian 13 "trixie" 64 bits sobre VirtualBox

## Estructura

```
solemne_so_equipo6/
├── entrada/                     ventas_sucursal_NNN.csv (20 archivos)
├── salida/
│   ├── reporte_ventas_sucursal_NNN.txt
│   └── consolidado_ventas.txt
├── errores/
│   └── registros_invalidos.txt
├── cierre_comercial/
│   ├── aprobados/               reportes con 0 registros inválidos
│   ├── observados/              reportes con 1 o más registros inválidos
│   ├── respaldos/               copia de consolidado_ventas.txt
│   └── inventario_cierre.csv
├── logs/
│   └── cierre_comercial.log
├── src/
│   ├── secuencial.py
│   ├── concurrente.py
│   └── gestor_cierre.py
├── evidencias/
├── generador.py
└── README.md
```

## Requisitos

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip procps psmisc tree
python3 --version
```

No se usan dependencias externas: todo es biblioteca estándar de Python
(`csv`, `re`, `shutil`, `threading`, `queue`, `pathlib`, `datetime`).

## Ejecución reproducible

Todos los comandos se ejecutan desde la raíz del proyecto.

### 1. Generar los datos de entrada

```bash
python3 generador.py
```

Usa la semilla fija `20260909`, por lo que los 20 archivos son idénticos en
cada ejecución. Las sucursales 3, 7, 11, 14, 18 y 20 contienen registros
inválidos; las otras 14 quedan limpias. Esto garantiza que el gestor de cierre
tenga reportes para clasificar en **ambas** carpetas.

### 2. Ejecutar la versión secuencial

```bash
time python3 src/secuencial.py
```

### 3. Ejecutar la versión concurrente

```bash
time python3 src/concurrente.py
```

Las cinco métricas exigidas por el enunciado deben coincidir entre ambas
versiones: archivos procesados, registros válidos, registros inválidos,
unidades vendidas y monto total vendido. Solo debe variar el tiempo.

Verificación automática de la coincidencia:

```bash
python3 src/secuencial.py  && cp salida/consolidado_ventas.txt /tmp/sec.txt
python3 src/concurrente.py && cp salida/consolidado_ventas.txt /tmp/con.txt
diff /tmp/sec.txt /tmp/con.txt
```

El `diff` solo debe mostrar diferencias en las líneas "Versión ejecutada",
"Tiempo total de ejecución" y "Cantidad de trabajadores".

### 4. Ejecutar el gestor de cierre

```bash
python3 src/gestor_cierre.py
```

Importante: el gestor **mueve** los reportes individuales fuera de `salida/`.
Para repetir el ciclo completo hay que volver a ejecutar el paso 2 o 3 antes de
llamarlo de nuevo. Si se ejecuta dos veces sin regenerar, los reportes ya
existentes en destino provocan colisión y el gestor aplica el sufijo `_1`,
`_2`, etc. (comportamiento esperado y exigido por el enunciado).

Para partir de cero:

```bash
rm -rf cierre_comercial logs salida errores
python3 generador.py && python3 src/concurrente.py && python3 src/gestor_cierre.py
```

## Verificación del resultado

```bash
tree solemne_so_equipo6
ls -lah cierre_comercial/aprobados cierre_comercial/observados cierre_comercial/respaldos
cat cierre_comercial/inventario_cierre.csv
cat logs/cierre_comercial.log
stat logs/cierre_comercial.log
du -sh .
```

Resultado esperado con la semilla por defecto:

| Carpeta | Archivos |
|---|---|
| `cierre_comercial/aprobados/` | 14 |
| `cierre_comercial/observados/` | 6 |
| `cierre_comercial/respaldos/` | 1 |
| `cierre_comercial/inventario_cierre.csv` | 21 filas + cabecera |

## Mover vs copiar

Los reportes individuales se **mueven** (`shutil.move`) porque cada uno debe
quedar en exactamente un estado: aprobado u observado. Mantener una copia en
`salida/` dejaría el mismo reporte en dos estados a la vez.

El consolidado se **copia** (`shutil.copy2`) porque es el documento de
referencia del cierre: debe permanecer en `salida/` como salida de la Parte 1 y
además existir en `cierre_comercial/respaldos/` como respaldo del cierre.
`copy2` preserva la fecha de modificación del original.

## Integridad de archivos

Antes de escribir en el destino, `ruta_sin_colision()` comprueba si el nombre
ya existe. Si existe, inserta un sufijo correlativo antes de la extensión:

```
reporte_ventas_sucursal_001.txt   ya existe
reporte_ventas_sucursal_001_1.txt se usa este nombre
```

Así dos archivos distintos nunca quedan con el mismo nombre en la carpeta de
destino, y ninguna ejecución del gestor puede destruir el resultado de una
ejecución anterior.

## Error controlado

`gestor_cierre.py` captura y registra en la bitácora, sin interrumpirse:

- Archivo de origen inexistente (se fuerza deliberadamente al inicio, sobre
  `reporte_ventas_sucursal_999.txt`, para dejar constancia en el log).
- Origen que no es un archivo regular.
- Reporte sin la línea "Registros inválidos" (se clasifica como observado por
  precaución).
- Destino fuera del árbol `cierre_comercial/`.
- Fallos de E/S al mover, copiar o escribir el inventario.
