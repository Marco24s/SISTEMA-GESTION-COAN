# Manual de Usuario: Sistema de Gestión de Materias Grasas Aeronáuticas

Bienvenido al manual del **Sistema de Gestión de Materias Grasas Aeronáuticas**. Este sistema está diseñado para facilitar el control de stock, la planificación del consumo y el pronóstico de abastecimiento de grasas y lubricantes para la aviación naval.

---

## 1. Introducción y Visión General

El sistema permite centralizar la información de los lubricantes disponibles, monitorear sus fechas de vencimiento y proyectar las necesidades futuras basadas en las horas de vuelo planificadas para cada modelo de aeronave.

---

## 2. Gestión de Datos Maestros

Esta sección cubre la configuración inicial necesaria para que el sistema opere correctamente.

### 2.1 Unidades y Escuadras
Las **Unidades** representan las dependencias físicas u operativas (ej: Escuadrilla Aeronaval, Almacén General). 
*   Para agregar una unidad, diríjase a **Unidades** y use el botón **Crear Unidad**.

### 2.2 Unidades de Medida
Antes de cargar grasas, asegúrese de tener configuradas las unidades de medida (Kg, Lts, Cartucho, etc.) en la sección de **Configuración**.

### 2.3 Aeronaves
Aquí se registran los modelos de aeronaves (ej: B-200, Turbo Tracker). Es fundamental asignar cada modelo a una **Unidad** responsable.

### 2.4 Biblioteca de Grasas (Tipos de Grasas)
En esta sección se catalogan todos los productos. Cada registro incluye:
*   **Nomenclatura**: Nombre comercial o técnico.
*   **Presentación y Unidad**: Ej: 5.00 Kg o 0.40 Kg (Cartucho).
*   **Normas MIL / NATO**: Especificaciones técnicas.
*   **Vida Útil**: Cantidad de meses que el producto es serviciable desde su fabricación.
*   **Stock Mínimo**: El sistema generará alertas automáticas cuando el stock total de este producto caiga por debajo de este valor.

---

## 3. Configuración Operativa

### 3.1 Asociación Aeronave-Grasa
Para que el sistema proyecte consumos, debe vincular cada modelo de aeronave con las grasas que utiliza.
*   Debe ingresar el **Consumo por Hora de Vuelo** para cada grasa asociada.
*   *Ejemplo*: Si un avión consume 0.05 Kg de una grasa por hora, el sistema usará este valor para calcular las necesidades según las horas voladas.

---

## 4. Gestión de Inventario (Stock)

### 4.1 Registro de "Casamatas" (Lotes)
El stock se gestiona mediante lotes numerados llamados "Casamatas".
*   Al ingresar una casamata, se debe indicar la **Fecha de Fabricación**. El sistema calculará automáticamente el vencimiento inicial.
*   Debe especificar la **Ubicación** (Almacén o Unidad).

### 4.2 Control de Estado y Vencimientos
El sistema clasifica los lotes en:
*   **Retesteable (Serviciable)**: Lotes aptos para el uso.
*   **Próximo a Vencer**: Alerta visual cuando faltan pocos meses para el vencimiento (Configurable).
*   **Vencido**: El stock ya no debe ser utilizado operativamente.

### 4.3 Re-ensayos (Retesteo)
Si una grasa permite re-certificación (configurado en el Tipo de Grasa), puede extender su vida útil:
1.  Marque el lote como **"Retesteando..."** (esto indica que se envió muestra al laboratorio).
2.  Una vez recibido el resultado, cargue los años de extensión otorgados. El sistema actualizará el vencimiento y devolverá el lote al estado **Serviciable**.

### 4.4 Registro de Consumo
Se utiliza para dar de baja stock del sistema por uso operativo o ajustes. El sistema priorizará automáticamente el consumo de los lotes **más próximos a vencer** (lógica FIFO adaptada a vencimientos).

---

## 5. Planificación y Pronóstico

### 5.1 Planes de Empleo
Cargue las horas de vuelo proyectadas para un período (mensual, trimestral o anual).

### 5.2 Pronóstico de Abastecimiento
Es la herramienta central de toma de decisiones. Compara:
*   Stock Disponible Actual.
*   Consumo Proyectado (basado en Planes de Empleo).
*   **Resultado**: Indica cuánta cantidad de cada grasa falta comprar para cubrir la operación programada.

### 5.3 Requerimientos de Compra
Desde el Pronóstico de Abastecimiento, puede generar **Solicitudes de Adquisición**. Estas solicitudes tienen estados (Pendiente, En Proceso, Recibido) para facilitar el seguimiento logístico.

---

## 6. Reportes y Herramientas

*   **Exportación**: Casi todas las tablas (Stock, Pronóstico, Requerimientos) cuentan con botones para descargar la información en **Excel (CSV)** o **PDF**.
*   **Calculadora de Horas**: Herramienta rápida para saber cuántas horas puede volar su flota con el stock actual antes de quedarse sin una grasa específica.

---

## 7. Roles y Niveles de Acceso

*   **Administrador / Logística**: Acceso total a configuración y gestión de stock.
*   **Usuario de Unidad**: Solo puede ver y registrar consumos de su propia aeronave/dependencia asignada.
