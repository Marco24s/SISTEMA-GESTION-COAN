## 📌 SOFTWARE SPECIFICATION

**Sistema de Gestión de Materias Grasas Aeronáuticas**

---

### 1. Project Overview

Design and develop a **network-based software system** for the management, planning, and control of **aeronautical lubricating greases** used by the **Comando de la Aviación Naval**.

The system must support:

* Operational planning based on flight hours
* Stock control by grease type and batch
* Shelf-life and expiration management
* Forecasting of procurement needs
* Logistic and budgetary decision support

The application is intended for **institutional use**, with multiple concurrent users on an internal network.

---

### 2. Technical Requirements

* Application type: **Web-based, multi-user**
* Backend language: **Python**
* Backend framework: **Django**
* Database: **PostgreSQL**
* Frontend: Standard web technologies (HTML, CSS, Bootstrap, minimal JavaScript)
* Client access: Web browser (no local installation required)

The system must be **modular, scalable, maintainable**, and suitable for long-term institutional use.

---

### 3. Functional Modules

---

#### 3.1 Aircraft Management

Each aircraft model must include:

* Aircraft model
* Unit / Squadron
* Number of aircraft
* Operational status (active / inactive)

---

#### 3.2 Grease Management

Each grease record must include:

* Technical designation
* Specification or standard (MIL, NATO, OEM, etc.)
* Packaging / presentation (kg, cartridge, can, etc.)
* Total shelf life (months)
* Flag indicating whether **re-certification / reconditioning** is allowed

---

#### 3.3 Aircraft–Grease Association

An aircraft model may use **multiple grease types**.

For each association, store:

* Aircraft model
* Grease type
* Hourly consumption rate (e.g., kg/hour, g/hour, kg/100h)
* Optional notes (e.g., application point)

---

#### 3.4 Flight Planning

For each aircraft model:

* Time period (monthly / quarterly / yearly)
* Planned flight hours

The system must automatically calculate:

* Total grease consumption per period
* Consumption broken down by grease type

---

#### 3.5 Stock and Batch Management

Stock must be tracked **by batch (lot)**, including:

* Grease type
* Batch number
* Manufacturing date
* Expiration date
* Initial quantity
* Available quantity
* Storage location (warehouse / unit)
* Status:

  * Serviceable
  * Near expiration
  * Expired
  * Pending re-certification

---

#### 3.6 Expiration and Shelf-Life Logic

The system must:

* Generate configurable alerts before expiration (e.g., 6 months)
* Identify greases that will expire before planned consumption
* Prioritize consumption of batches closest to expiration

---

#### 3.7 Procurement Forecasting

The system must calculate and display:

* Current available stock
* Projected consumption based on flight planning
* Shortfall or surplus by grease type
* Recommended purchase quantities per planning period

---

#### 3.8 Reports

Generate exportable reports (Excel and/or PDF):

* Consumption by aircraft model
* Consumption by grease type
* Current stock levels
* Greases nearing expiration
* Procurement requirements

---

### 4. Users and Access Control

Implement role-based access control:

* Administrator
* Logistics user
* Read-only user

Permissions must restrict data modification according to role.

---

### 5. Business Rules

* Expired grease must not be allowed for operational use
* Stock movements affecting quantities must not be deleted (only auditable adjustments allowed)
* Full traceability by batch is mandatory
* All calculations must be automatic, reproducible, and auditable

---

### 6. Expected Deliverables

* Database schema / data model
* Implemented business logic
* Functional user interfaces and forms
* Administrative interface
* Core calculation engine
* Clean, simple, institutional-oriented UI

---

### 7. Development Priority

Deliver first a **Minimum Viable Product (MVP)** including:

* Aircraft management
* Grease management
* Aircraft–grease consumption logic
* Flight planning
* Stock control
* Procurement calculation

The system must be designed to allow future extensions without rework.
