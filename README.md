# Solemne 1 - Parte Práctica 2 - Equipo 6

Sistemas Operativos NRC-14749 · Profesor René Galarce Godoy
Lenguaje: Python 3 · Sistema: Debian 13 "trixie" 64 bits sobre VirtualBox

Integrantes: Natalie Roa, Martin Pavie, Máximo Inostroza, Kevin Lener,
Benjamín Morales, Lucas Rivas.

## Instalación y configuración de la VM

| Recurso | Valor |
|---|---|
| Hipervisor | Oracle VirtualBox |
| Imagen | debian-13.6.0-amd64-netinst.iso (Debian 13 "trixie", 64 bits) |
| RAM | 4 GB |
| Procesadores virtuales | 2 vCPU |
| Disco virtual | 25 GB |
| Red | NAT con conectividad |

Verificación posterior a la instalación, ejecutada dentro de la VM:

```bash
cat /etc/os-release
lscpu
free -h
df -h
ip a
```

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

Copie el proyecto completo a `~/solemne_so_equipo6/` dentro de la VM antes de
continuar.

### 1. Generar los datos de entrada

```bash
python3 src/generador.py
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
python3 src/generador.py && python3 src/concurrente.py && python3 src/gestor_cierre.py
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

## Checklist de entrega final

- [x] VM Debian 13 instalada y accesible, con capturas de instalación
      (particionado, usuario, primer inicio) y de la configuración de recursos
      en el hipervisor (`evidencias/evidencias_instalacion_debian/`).
- [x] `python3 --version` y paquetes del punto "Requisitos" verificados en la
      VM (no en el equipo local de desarrollo).
- [x] `src/secuencial.py` y `src/concurrente.py` ejecutados en Debian; las 5
      métricas de negocio coinciden entre ambas versiones (solo varía el
      tiempo de ejecución, que puede ser mayor o menor en la concurrente
      dependiendo del volumen de datos y la sobrecarga de sincronización de
      los hilos).
- [x] `src/gestor_cierre.py` ejecutado en Debian, con 14 reportes en
      `aprobados/`, 6 en `observados/`, 1 respaldo y 21 filas + cabecera en
      `inventario_cierre.csv`.
- [x] Capturas de `ps -eo pid,ppid,stat,%cpu,%mem,rss,vsz,cmd`, `pstree -p`,
      `free -h`, `df -h`, `du -sh ~/solemne_so_equipo6`, `find`, `ls -lah` y
      `stat logs/cierre_comercial.log` tomadas durante o justo después de la
      ejecución concurrente (`evidencias/evidencias_procesos/`).
- [x] Informe final (Word/PDF, 12 páginas) con las capturas anteriores
      insertadas y el análisis técnico correspondiente. Se entrega por
      separado en la plataforma del curso, no está incluido en este
      repositorio.
- [x] Repositorio/carpeta de entrega con código, `entrada/`, reportes,
      consolidado, inventario, bitácora y este README.
