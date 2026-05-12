# Análisis Funcional Detallado del Sistema de Gestión Presupuestaria (SGP)

Este documento describe de manera exhaustiva el funcionamiento del módulo SGP dentro del sistema de gestión, con el objetivo de facilitar el análisis para futuras modificaciones, mejoras o correcciones.

---

## 1. Visión General
El SGP es una herramienta diseñada para el seguimiento integral del presupuesto preventivo y ejecutado. Permite registrar desde la asignación inicial de fondos hasta el pago final, pasando por la distribución interna a unidades descentralizadas.

Sigue un modelo de ejecución secuencial basado en tres etapas contables estándar: **Compromiso**, **Devengado** y **Pago**.

---

## 2. Estructura de Datos (Nomenclatura y Modelos)

El sistema se apoya en una estructura jerárquica de "catálogos" o nomencladores que definen el origen y destino del gasto.

### A. Nomencladores Presupuestarios
Son las piezas básicas que componen la "partida" presupuestaria:
*   **Fuente de Financiamiento (FF):** Origen de los fondos (ej. Tesoro Nacional, Recursos Propios).
*   **Subprograma:** Nivel programático del presupuesto.
*   **Actividad:** La tarea o proyecto específico al que se asignan fondos.
*   **Incisos (INC):** Clasificación por objeto del gasto (ej. Inciso 2: Bienes de Consumo, Inciso 3: Servicios No Personales).
*   **PPAI (Objeto de Gasto):** El nivel más detallado de clasificación del gasto.
*   **Otros niveles técnicos:** `PPP-INC`, `PP-INC`, `Pre-inc`, `Incisos Agrupados`. Estos se usan para compatibilidad con sistemas superiores (como SLU/SIDIF).

### B. Entidades Principales
1.  **Ejercicio Económico (`BudgetFiscalYear`):** Define el año fiscal (ej. 2024). Puede estar **Abierto** o **Cerrado**.
2.  **Crédito Presupuestario (`BudgetCredit`):** Es la "bolsa" total de dinero asignada a una partida específica para un ejercicio. Se divide en cuatro cuatrimestres (`q1` a `q4`).
3.  **Distribución de Crédito (`BudgetAllocation`):** También llamado "Techo". Es la porción de un Crédito Presupuestario que se le asigna a una **Unidad** específica (ej. Escuadrilla Aeronaval).
4.  **Ejecución Presupuestaria (`BudgetExecution`):** Es el registro del gasto real. Cada registro de ejecución pertenece a una Distribución y sigue el flujo:
    *   **Compromiso:** Reserva del crédito.
    *   **Devengado:** Reconocimiento de la obligación de pago (recepción de factura/servicio).
    *   **Pago:** Cancelación de la deuda.

---

## 3. Flujo de Trabajo Funcional

### Paso 1: Apertura y Configuración
*   Se crea el **Ejercicio Económico**.
*   Se cargan o actualizan los códigos en los **Nomencladores** (FF, Actividad, etc.).

### Paso 2: Carga de AA.PP. (Anexo de Asignaciones)
*   Administración/Logística carga los **Créditos Presupuestarios**. 
*   *Regla:* La suma de los cuatrimestres define el `Monto Total` de la partida.

### Paso 3: Distribución a UU.CC. (Unidades Centralizadoras)
*   Se realiza la **Distribución (Techo)**.
*   *Validación Crítica:* No se puede distribuir más dinero del que existe en el Crédito Presupuestario original.

### Paso 4: Ciclo de Ejecución (Gasto Real)
1.  **Registro de Compromiso:** La unidad registra un número de expediente y un monto.
    *   *Validación:* El monto no puede superar el "Techo" (Distribución) disponible para esa unidad y partida.
2.  **Registro de Devengado:** Cuando llega la factura o se recibe el bien, se carga el monto devengado.
    *   *Validación:* No puede superar el monto previamente comprometido.
3.  **Registro de Pago:** Cuando el dinero sale de tesorería.
    *   *Validación:* No puede superar el monto devengado.

---

## 4. Roles y Permisos (RBAC)

El sistema diferencia el acceso según el perfil del usuario:

*   **Administradores / Logística:**
    *   Visibilidad total de todas las unidades.
    *   Capacidad de crear/editar Ejercicios y Créditos.
    *   Gestión de Nomencladores.
    *   Cierre del Ejercicio.
*   **Usuarios de Unidad (UU.CC.):**
    *   Solo ven sus propias "Distribuciones" (Techos).
    *   Pueden registrar Compromisos, Devengados y Pagos solo sobre sus techos asignados.
    *   No pueden modificar la estructura presupuestaria global.

---

## 5. Reportes y Análisis

El sistema genera un reporte de ejecución por unidad en el Dashboard que incluye:
*   **Asignado (Techo):** Lo que la unidad tiene para gastar.
*   **Comprometido:** Lo que ya reservó.
*   **Devengado:** Lo que ya "gastó" legalmente.
*   **Pagado:** Lo que efectivamente salió de caja.
*   **Disponible:** Lo que queda para nuevos compromisos (`Asignado - Comprometido`).
*   **Residuos Pasivos:** `Comprometido - Devengado` (Gastos contratados pero no concretados/facturados).
*   **Deuda Flotante:** `Devengado - Pago` (Facturas recibidas pero no pagadas).

---

## 6. Puntos de Análisis para Modificaciones

Basado en la revisión del código actual, aquí hay áreas propuestas para evaluación del equipo:

### A. Mejoras de Funcionalidad
*   **Reprogramaciones:** Existe lógica interna de reprogramación (`services.py`), pero falta una interfaz fluida para que Logística mueva saldos entre ejercicios o unidades masivamente.
*   **Soporte Documental:** Evaluar la inclusión de un campo para cargar PDFs de expedientes o facturas asociados a cada etapa de la ejecución.
*   **Validación de Fechas Cronológicas:** Implementar validaciones que impidan que un pago tenga fecha anterior al devengado, o un devengado fecha anterior al compromiso.

### B. Usabilidad y Configuración
*   **Simplificación de Nomencladores:** El sistema tiene 9 niveles de nomenclatura (`FF`, `Subprog`, `Actividad`, `PPP-INC`, `PP-INC`, `Pre-inc`, `Inc. Agrupado`, `INC`, `PPAI`). Se recomienda analizar si todos son operativos para la gestión diaria o si algunos pueden simplificarse/automatizarse.
*   **Dashboard Visual:** Podría beneficiarse de gráficos de barras o tortas para ver el porcentaje de ejecución de cada unidad a simple vista.

### C. Proceso de Cierre
*   Actualmente el cierre es manual y bloquea el año. Podría agregarse un proceso de "Cierre y Apertura" que migre automáticamente los Compromisos no alcanzados por el Devengado (Residuos) al ejercicio siguiente como "Compromisos Reprogramados".

---
> Documento generado para el análisis del sistema SGP.
