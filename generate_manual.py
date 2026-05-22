import os
import sys

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_elements(num_pages)
            super().showPage()
        super().save()

    def draw_page_elements(self, page_count):
        self.saveState()
        
        # Cover page doesn't get headers or footers (Page 1)
        if self._pageNumber > 1:
            # Header
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#1A365D")) # Navy
            self.drawString(54, 745, "SISTEMA DE GESTIÓN DE CRÉDITOS (SGC)")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#4A5568"))
            self.drawRightString(558, 745, "Manual de Usuario v2.1")
            
            # Header line
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(54, 737, 558, 737)
            
            # Footer line
            self.line(54, 52, 558, 52)
            
            # Footer text
            self.drawString(54, 40, "Armada Argentina — Comando de la Aviación Naval (COAN)")
            page_text = f"Página {self._pageNumber} de {page_count}"
            self.drawRightString(558, 40, page_text)
            
        else:
            # Draw beautiful Cover Page background elements
            # Elegant dark-navy accent block on the top
            self.setFillColor(colors.HexColor("#1A365D")) 
            self.rect(0, 500, 612, 292, fill=True, stroke=False)
            
            # Accent gold/amber stripe
            self.setFillColor(colors.HexColor("#D97706")) 
            self.rect(0, 485, 612, 15, fill=True, stroke=False)
            
            # Subdued very light slate-gray block on the bottom
            self.setFillColor(colors.HexColor("#F8FAFC"))
            self.rect(0, 0, 612, 485, fill=True, stroke=False)
            
            # Border decorative line for the lower area
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(1)
            self.line(54, 54, 558, 54)
            self.line(54, 54, 54, 450)
            self.line(558, 54, 558, 450)
            
        self.restoreState()

def build_pdf(filename, story_elements):
    # Setup document
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=80,
        bottomMargin=80
    )
    doc.build(story_elements, canvasmaker=NumberedCanvas)

def generate_manual():
    # Define cohesive and premium styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=26,
        leading=32,
        textColor=colors.white,
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#FCD34D"), # Light Amber/Gold
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1A365D"), # Navy
        spaceBefore=22,
        spaceAfter=10,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#2C5282"), # Slate Blue
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    
    h3_style = ParagraphStyle(
        'DocH3',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor("#4A5568"), # Slate Gray
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=8
    )
    
    body_bold_style = ParagraphStyle(
        'DocBodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    code_style = ParagraphStyle(
        'DocCode',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1A202C"),
        backColor=colors.HexColor("#EDF2F7"),
        borderPadding=6,
        spaceBefore=6,
        spaceAfter=6
    )
    
    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#2D3748"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )

    callout_style = ParagraphStyle(
        'DocCallout',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor("#2C5282"),
        backColor=colors.HexColor("#EBF8FF"),
        borderColor=colors.HexColor("#90CDF4"),
        borderWidth=0.5,
        borderPadding=8,
        spaceBefore=8,
        spaceAfter=8
    )

    story = []
    
    # ==================== PORTADA (PAGE 1) ====================
    story.append(Spacer(1, 40))
    story.append(Paragraph("SISTEMA DE GESTIÓN DE CRÉDITOS", title_style))
    story.append(Paragraph("SGC — Plataforma Unificada COAN", subtitle_style))
    
    # Large spacer to push items below the navy/gold banner (past y = 485)
    story.append(Spacer(1, 230))
    
    cover_meta_style_bold = ParagraphStyle(
        'CoverMetaBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=2
    )
    cover_meta_style_normal = ParagraphStyle(
        'CoverMetaNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=2
    )
    
    story.append(Paragraph("MANUAL COMPLETO DE USUARIO Y PROCEDIMIENTOS", cover_meta_style_bold))
    story.append(Paragraph("Manual de Operación de Crédito y Ejecución Presupuestaria", cover_meta_style_normal))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Organismo:</b> Armada Argentina — Comando de la Aviación Naval (COAN)", cover_meta_style_normal))
    story.append(Paragraph("<b>Entorno de Red:</b> Operación Híbrida / Desconectada de Alta Disponibilidad", cover_meta_style_normal))
    story.append(Paragraph("<b>Versión del Documento:</b> 2.1 (Concurrencia Atómica & Multi-Rol)", cover_meta_style_normal))
    story.append(Paragraph("<b>Fecha de Emisión:</b> Mayo de 2026", cover_meta_style_normal))
    story.append(Paragraph("<b>Autor de Seguridad:</b> Administración del Sistema SGC", cover_meta_style_normal))
    
    story.append(PageBreak())
    
    # ==================== INDICE / INTRODUCCION (PAGE 2) ====================
    story.append(Paragraph("Introducción y Arquitectura General", h1_style))
    
    story.append(Paragraph(
        "El <b>Sistema de Gestión de Créditos (SGC)</b> es una plataforma tecnológica avanzada e integral desarrollada específicamente "
        "para el Comando de la Aviación Naval (COAN) de la Armada Argentina. Su propósito primordial es administrar, controlar y trazar con "
        "absoluto rigor el ciclo de vida del gasto público militar de la fuerza, desde la asignación del crédito anual de las partidas hasta el "
        "pago final de las facturas de proveedores.",
        body_style
    ))
    
    story.append(Paragraph(
        "El SGC se distingue por implementar una robusta arquitectura con soporte para transacciones concurrentes, redundancia offline y "
        "un sistema dinámico de seguridad centrado en el usuario. Toda la lógica del sistema está orientada a mitigar errores humanos en la carga de "
        "expedientes y asegurar que las distintas dependencias navales no sobrepasen los techos de financiamiento asignados trimestralmente.",
        body_style
    ))
    
    story.append(Paragraph("Pilares de Seguridad y Control de Acceso Modulares", h2_style))
    story.append(Paragraph(
        "La plataforma opera con un sistema de seguridad granular. El acceso a cada subsistema principal "
        "(SGMG — Sistema de Gestión de Materias Grasas, SIGERA — Sistema de Gestión de Recursos del Aire, SGP — Sistema de Gestión del Personal) "
        "requiere la autorización explícita de un <b>PIN de Seguridad de 4 dígitos</b> único por usuario y módulo. Este mecanismo es gestionado centralmente "
        "por la administración del sistema mediante un middleware que intercepta cada consulta y bloquea los accesos no autorizados de forma preventiva.",
        body_style
    ))
    
    story.append(Paragraph("Trazabilidad y Visibilidad Restringida de Datos", h2_style))
    story.append(Paragraph(
        "Para garantizar la confidencialidad de la información presupuestaria sensible de la Armada, el SGC aplica filtros estrictos a nivel "
        "de base de datos según el perfil del usuario activo:",
        body_style
    ))
    
    story.append(Paragraph("&bull; <b>Usuarios Administradores (AA.PP. / Superusuarios):</b> Poseen control total y visibilidad absoluta de los créditos, distribuciones globales y auditorías completas.", bullet_style))
    story.append(Paragraph("&bull; <b>Usuarios Operativos (UU.CC. / Comandos de Unidad):</b> Visualizan <i>exclusivamente</i> la información presupuestaria, créditos trimestrales asignados y gastos cometidos correspondientes a su unidad autorizada. Tienen restringido el acceso a partidas globales de otras unidades.", bullet_style))
    
    story.append(Paragraph(
        "<i>Nota de Seguridad: Todos los intentos de acceso fallidos o intentos de transpasar los límites de visualización de créditos asignados son registrados de forma persistente en los registros de auditoría del sistema para control preventivo.</i>",
        callout_style
    ))
    
    story.append(PageBreak())
    
    # ==================== ESTRUCTURA Y CLASIFICADORES (PAGE 3) ====================
    story.append(Paragraph("Estructura Presupuestaria y Clasificadores", h1_style))
    story.append(Paragraph(
        "Para la correcta registración y formulación del gasto público militar, el sistema SGC modela la estructura presupuestaria de "
        "la República Argentina a través de clasificadores anidados y relacionales. Estos catálogos son el pilar sobre el cual se asienta "
        "toda la imputación del gasto. Ningún crédito o gasto puede existir en el sistema sin estar vinculado a esta red de clasificadores.",
        body_style
    ))
    
    story.append(Paragraph("Los Componentes Presupuestarios en el SGC", h2_style))
    story.append(Paragraph(
        "A continuación se detallan los nomencladores presupuestarios clave gestionados en el panel de configuración central:",
        body_style
    ))

    story.append(Paragraph("&bull; <b>Ejercicio / Año Fiscal:</b> Representa el período económico (ej: 2026). Los ejercicios pueden estar en estado <b>Abierto (OPEN)</b> o <b>Cerrado (CLOSED)</b>. Cuando un ejercicio se marca como cerrado, se bloquea atómicamente toda creación de nuevos créditos, modificaciones o compromisos de gasto para dicho año.", bullet_style))
    story.append(Paragraph("&bull; <b>Fuente de Financiamiento (FF):</b> Clasifica el origen de los fondos (ej: FF 11 - Tesoro Nacional, FF 13 - Recursos Propios, FF 99 - Crédito Externo/Otros). Su comportamiento define flujos y subcuentas automáticas.", bullet_style))
    story.append(Paragraph("&bull; <b>Programa (PROG) y Subprograma (SUBPROG):</b> Categorizan la finalidad de las operaciones. El programa cuenta con un código administrador de 3 dígitos (ej: 016 - Operaciones Aéreas).", bullet_style))
    story.append(Paragraph("&bull; <b>Inciso (INCISO):</b> El nivel general del gasto. Por ejemplo, Inciso 1 (Personal), Inciso 2 (Bienes de Consumo), Inciso 3 (Servicios No Personales), Inciso 4 (Bienes de Uso - Inversión/Obras) e Inciso 5 (Transferencias).", bullet_style))
    story.append(Paragraph("&bull; <b>Estructura Interna del Inciso:</b> Principal (PPAL), Parcial (PARCIAL) y Sub-Parcial (SUBPC) (ej: Subparcial 2510 para Lubricantes).", bullet_style))
    story.append(Paragraph("&bull; <b>Moneda (MONEDA):</b> Denominación presupuestaria técnica (ej: 1 - Pesos Argentinos, 2 - Dólares Estadounidenses, etc.).", bullet_style))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("Estructura de Imputación Base", h3_style))
    story.append(Paragraph(
        "Toda partida de crédito se identifica de forma única con una cadena estandarizada que vincula todos estos códigos. "
        "En la interfaz se representa con el formato:",
        body_style
    ))
    story.append(Paragraph("<b>[FF]-[PROG]-[SUBPROG]-[INCISO]-[PPAL]-[PARCIAL]-[SUBPC]-[MONEDA]</b>", code_style))
    
    # Nomencladores Table
    headers = [Paragraph("<b>Clasificador</b>", body_bold_style), Paragraph("<b>Código</b>", body_bold_style), Paragraph("<b>Descripción Ejemplo</b>", body_bold_style)]
    data = [
        headers,
        [Paragraph("FF", body_style), Paragraph("11 / 13 / 99", body_style), Paragraph("Tesoro / Recursos Propios / Crédito Externo", body_style)],
        [Paragraph("Programa", body_style), Paragraph("16 / 24", body_style), Paragraph("Sostén Operacional de la Aviación Naval", body_style)],
        [Paragraph("Inciso", body_style), Paragraph("2 / 3 / 4", body_style), Paragraph("Consumo / Servicios / Bienes de Uso (Obras)", body_style)],
        [Paragraph("Subparcial", body_style), Paragraph("2510 / 2520", body_style), Paragraph("Grasas y Lubricantes Aeronáuticos", body_style)],
    ]
    t = Table(data, colWidths=[120, 100, 284])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t)
    
    story.append(PageBreak())
    
    # ==================== MODULO 1: GESTION DE CREDITOS (PAGE 4) ====================
    story.append(Paragraph("Módulo 1: Gestión de Créditos Presupuestarios (AA.PP.)", h1_style))
    story.append(Paragraph(
        "El Módulo de Créditos Presupuestarios es el punto de inicio de la cadena del gasto. Es la herramienta exclusiva del rol de "
        "<b>Administración de Presupuesto (AA.PP.)</b> del COAN. A través de este panel, se ingresan las partidas presupuestarias globales "
        "autorizadas por el Estado Mayor de la Armada para el ejercicio fiscal activo.",
        body_style
    ))
    
    story.append(Paragraph("1. Registro y Alta de Créditos", h2_style))
    story.append(Paragraph(
        "Para dar de alta un crédito, el administrador accede a la sección <b>'Créditos (AA.PP.)'</b> y selecciona <b>'Nuevo Crédito Presupuestario'</b>. "
        "El sistema despliega un formulario unificado donde se debe seleccionar:",
        body_style
    ))
    story.append(Paragraph("&bull; El Ejercicio Económico activo.", bullet_style))
    story.append(Paragraph("&bull; Los clasificadores de catálogo (FF, Programa, SUBPROG, INCISO, PPAL, Parcial, SUBPC, Moneda).", bullet_style))
    story.append(Paragraph("&bull; Los importes correspondientes a cada trimestre del año: <b>Monto T1, Monto T2, Monto T3, Monto T4</b>.", bullet_style))
    story.append(Paragraph("&bull; Observaciones adicionales de la partida.", bullet_style))
    
    story.append(Paragraph(
        "El sistema calcula de forma instantánea el Monto Total de la partida (T1 + T2 + T3 + T4) y realiza validaciones "
        "para impedir registros duplicados de idéntica estructura clasificadora en el mismo ejercicio.",
        body_style
    ))
    
    story.append(Paragraph("2. Ajustes y Modificaciones de Crédito (Reajustes)", h2_style))
    story.append(Paragraph(
        "Los montos asignados a un crédito no son estáticos; pueden sufrir variaciones durante el año debido a refuerzos presupuestarios o "
        "recortes de partidas. Para modificar un crédito existente de forma segura, el sistema prohíbe la edición directa del registro. En su lugar, "
        "implementa un flujo de <b>Ajuste de Crédito</b>:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Auditoría Completa:</b> Al realizar un ajuste, el usuario debe ingresar los nuevos importes trimestrales y detallar obligatoriamente el <b>Motivo del Ajuste</b>.", bullet_style))
    story.append(Paragraph("&bull; <b>Historial de Cambios:</b> El SGC guarda un log permanente que almacena el monto anterior por trimestre, el nuevo monto ajustado, la diferencia resultante (deltas), el usuario responsable de la acción y la fecha exacta.", bullet_style))
    story.append(Paragraph("&bull; <b>Validación de Techo:</b> No se puede ajustar un crédito reduciendo sus importes trimestrales por debajo de las sumas que ya fueron distribuidas a las Unidades Destinatarias para ese mismo trimestre. De intentarlo, el sistema arrojará un error descriptivo indicando exactamente en qué trimestre y por qué monto se está superando el límite físico de reducción.", bullet_style))
    
    story.append(Paragraph("3. Gestión del Tipo de Crédito y Desasignaciones", h2_style))
    story.append(Paragraph(
        "Cada partida se categoriza bajo un <i>Tipo de Crédito</i>. El sistema permite realizar cambios de tipo o desasignaciones parciales "
        "de crédito de forma controlada. Cada desasignación de fondos de una partida registra logs específicos de auditoría detallando los motivos.",
        body_style
    ))
    
    story.append(PageBreak())
    
    # ==================== MODULO 2: DISTRIBUCION (PAGE 5) ====================
    story.append(Paragraph("Módulo 2: Distribución de Techos a Unidades Ejecutoras (UU.CC.)", h1_style))
    story.append(Paragraph(
        "Una vez que los Créditos Presupuestarios globales (AA.PP.) están cargados en el SGC, el administrador debe transferir o 'distribuir' "
        "esos fondos a las distintas <b>Unidades de Consumo / Unidades Ejecutoras (UU.CC.)</b> del COAN (ej: Escuadra Aeronaval Nº 1, "
        "Base Aeronaval Comandante Espora, etc.). Esta distribución crea un <b>Techo Presupuestario de Unidad</b>.",
        body_style
    ))
    
    story.append(Paragraph("1. Mecánica de Distribución y Asignación de Techos", h2_style))
    story.append(Paragraph(
        "Para realizar una distribución, el administrador ingresa a <b>'Distribución (UU.CC.)'</b> y selecciona <b>'Nueva Distribución de Crédito'</b>:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Crédito Origen:</b> Se selecciona la partida presupuestaria global cargada en el paso anterior. La interfaz muestra un indicador dinámico en tiempo real que detalla el <b>Saldo Disponible para Distribuir</b> del crédito seleccionado, evitando que el administrador haga cálculos manuales.", bullet_style))
    story.append(Paragraph("&bull; <b>Unidad Destino:</b> Se elige el comando o dependencia militar que recibirá los fondos.", bullet_style))
    story.append(Paragraph("&bull; <b>Montos Trimestrales (T1 a T4):</b> Se definen las cuotas trimestrales asignadas a la unidad. Al guardar, el total asignado se consolida atómicamente.", bullet_style))
    
    story.append(Paragraph("2. Vinculación con Proyectos / Planes de Gasto (Trazabilidad Extrema)", h2_style))
    story.append(Paragraph(
        "Con el objetivo de maximizar el control financiero, cada distribución de crédito puede asociarse a uno o más <b>Proyectos / Planes de Gasto</b> "
        "(anteriormente denominados 'Clasificaciones'). Estos proyectos son definidos por la comandancia para agrupar metas físicas de la fuerza "
        "(ej: 'Plan de Gasto para Mantenimiento de Aviones Super Etendard', 'Meta Adquisición de Grasas Especiales 2026').",
        body_style
    ))
    story.append(Paragraph(
        "Esta asociación permite obtener reportes consolidados cruzando las distribuciones con metas de gasto preestablecidas (target_amount), "
        "permitiendo verificar en cualquier momento si los fondos asignados se condicen con las metas estimadas.",
        body_style
    ))
    
    story.append(Paragraph("3. Monitoreo Activo de Saldos de Techo", h2_style))
    story.append(Paragraph(
        "El SGC calcula para cada registro de Distribución tres campos monetarios dinámicos fundamentales:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Monto Asignado (Techo Total):</b> La suma del presupuesto transferido a la unidad (T1 + T2 + T3 + T4).", bullet_style))
    story.append(Paragraph("&bull; <b>Monto Comprometido Acumulado (Spent Amount):</b> La sumatoria de todos los gastos reservados o ejecutados y registrados por la unidad contra ese techo.", bullet_style))
    story.append(Paragraph("&bull; <b>Saldo Disponible:</b> Calculado de forma estricta como <i>Monto Asignado menos Monto Comprometido</i>. Este es el saldo de control preventivo en tiempo real.", bullet_style))
    
    story.append(PageBreak())
    
    # ==================== MODULO 3: FLUJO DE EJECUCION (PAGE 6) ====================
    story.append(Paragraph("Módulo 3: Flujo de Ejecución del Gasto (Paso a Paso)", h1_style))
    story.append(Paragraph(
        "El corazón operativo de la plataforma SGC radica en el control del gasto público militar a través de un flujo secuencial, estricto "
        "y ordenado de tres pasos que corresponden a las etapas administrativas del Presupuesto Público Argentino: "
        "<b>1. Compromiso -> 2. Devengado -> 3. Pago</b>.",
        body_style
    ))
    
    story.append(Paragraph("Flujo de Operación Secuencial", h2_style))
    story.append(Paragraph(
        "El flujo de ejecución del gasto debe respetarse obligatoriamente de forma cronológica y cuantitativa:",
        body_style
    ))
    
    # Gasto Flow Table
    headers_gasto = [Paragraph("<b>Fase del Gasto</b>", body_bold_style), Paragraph("<b>Monto Límite</b>", body_bold_style), Paragraph("<b>Efecto Financiero</b>", body_bold_style)]
    data_gasto = [
        headers_gasto,
        [Paragraph("<b>1. Compromiso</b>", body_style), Paragraph("Hasta el Saldo Disponible del Techo", body_style), Paragraph("Reserva presupuesto del techo trimestral. Impide usar el dinero para otra compra.", body_style)],
        [Paragraph("<b>2. Devengado</b>", body_style), Paragraph("Hasta el Monto Comprometido", body_style), Paragraph("Registra la recepción conforme del bien/servicio o factura. Consolida el gasto.", body_style)],
        [Paragraph("<b>3. Pago</b>", body_style), Paragraph("Hasta el Monto Devengado", body_style), Paragraph("Registra la salida física del dinero o cancelación de la obligación al proveedor.", body_style)],
    ]
    tg = Table(data_gasto, colWidths=[120, 140, 244])
    tg.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(tg)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Fase 1: Registro del Compromiso", h2_style))
    story.append(Paragraph(
        "Cuando una Unidad Operativa requiere iniciar un proceso de compra o gasto, debe registrar un Compromiso contra su techo asignado. "
        "Para ello ingresa a <b>'Ejecución'</b>, selecciona <b>'Comprometer Gasto'</b> y completa el formulario con los siguientes campos clave:",
        body_style
    ))
    
    story.append(Paragraph("&bull; <b>Distribución / Techo:</b> Se selecciona el techo disponible asignado. El combo autocompleta el saldo disponible actualizado de forma visual para evitar errores de selección.", bullet_style))
    story.append(Paragraph("&bull; <b>Número de Expediente / Referencia:</b> Código oficial (ej: <i>'Exp. 14/2026'</i>) que avala el gasto administrativamente.", bullet_style))
    story.append(Paragraph("&bull; <b>ID de Control Único:</b> Código opcional externo para prevenir de forma absoluta la duplicación involuntaria de la carga (ej: número de factura de proveedor, ID externo, etc.).", bullet_style))
    story.append(Paragraph("&bull; <b>Monto a Comprometer:</b> Importe en pesos. Si se marca la casilla <i>'¿Comprometer el total disponible?'</i>, el sistema rellena automáticamente el campo con el saldo exacto remanente de la distribución, facilitando la liquidación final de partidas.", bullet_style))
    story.append(Paragraph("&bull; <b>Tipo de Gasto (TG):</b> Clasificador específico para los incisos de operación regular.", bullet_style))
    story.append(Paragraph("&bull; <b>Número de Obra:</b> Identificador de 5 dígitos requerido específicamente para inversiones e infraestructura (Inciso 4).", bullet_style))
    story.append(Paragraph("&bull; <b>Afecta PG 117:</b> Casilla de verificación para denotar si el gasto impacta las partidas especiales contempladas bajo el programa PG 117.", bullet_style))
    story.append(Paragraph("&bull; <b>Fecha de Compromiso:</b> Fecha oficial de reserva de los fondos.", bullet_style))
    
    story.append(PageBreak())
    
    # ==================== IMPUTACION VARIABLE (PAGE 7) ====================
    story.append(Paragraph("El Motor de Imputación Variable Automática", h1_style))
    story.append(Paragraph(
        "Uno de los desarrollos más complejos del SGC es el <b>Motor de Imputación Variable Automática</b>. Este sistema elimina "
        "por completo la necesidad de que los operadores de unidad conozcan y conformen manualmente las largas y complejas cadenas de imputación "
        "del nomenclador público argentino al comprometer un gasto.",
        body_style
    ))
    
    story.append(Paragraph("Reglas de Negocio para el Cálculo Automático", h2_style))
    story.append(Paragraph(
        "Al guardar un Compromiso, el sistema SGC computa de forma atómica e inteligente dos variables presupuestarias complejas según el "
        "clasificador origen, la fuente de financiamiento (FF) y los campos cargados:",
        body_style
    ))
    
    story.append(Paragraph("<b>1. Subcuenta Presupuestaria (SC) Automática:</b>", body_bold_style))
    story.append(Paragraph(
        "Si la Fuente de Financiamiento (FF) del crédito es <b>13 (Recursos Propios)</b> o <b>99 (Otros)</b>, el sistema asigna automáticamente la subcuenta <b>'99'</b>. "
        "Para cualquier otra fuente de financiamiento (ej: FF 11 - Tesoro Nacional), el sistema asigna de forma predeterminada la subcuenta <b>'51'</b>.",
        body_style
    ))
    
    story.append(Paragraph("<b>2. Subparcial Calculado de 5 Dígitos (SSSSS):</b>", body_bold_style))
    story.append(Paragraph(
        "El subparcial de 5 dígitos se computa de forma dinámica mediante las siguientes tres reglas exclusivas:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Regla A (Obras Especiales):</b> Si el Inciso del crédito es <b>4 (Bienes de Uso / Obras)</b> y la Fuente de Financiamiento (FF) es <b>13</b> o <b>99</b>, el subparcial toma de forma automática el valor fijo <b>'99999'</b>.", bullet_style))
    story.append(Paragraph("&bull; <b>Regla B (Obras Regulares):</b> Si el Inciso es <b>4</b> y la Fuente de Financiamiento (FF) es ordinaria (ej: FF 11), el subparcial se conforma obligatoriamente utilizando el <b>Número de Obra</b> de 5 dígitos ingresado por el operador (rellenado con ceros a la izquierda de ser necesario).", bullet_style))
    story.append(Paragraph("&bull; <b>Regla C (Operaciones Corrientes):</b> Para el resto de los Incisos (1 - Personal, 2 - Bienes de Consumo, 3 - Servicios, 5 - Transferencias), el subparcial de 5 dígitos se auto-conforma combinando: <i>[Nomenclador Base (2 dígitos)] + [Código Tipo de Gasto (1 dígito)] + [Código Afectación PG117 (2 dígitos: '17' si afecta, '00' si no afecta)]</i>.", bullet_style))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("La Cadena de Imputación Variable Generada", h2_style))
    story.append(Paragraph(
        "Al concluir los cálculos, el SGC genera una cadena única denominada <b>Imputación Variable</b>, la cual representa la "
        "identidad formal de la reserva del gasto público ante la Contaduría de la Armada. Su estructura es:",
        body_style
    ))
    story.append(Paragraph("<b>UUUUUU . I . P . p . SSSSS . M . OOO . CC</b>", code_style))
    
    # Imputacion Table
    headers_imp = [Paragraph("<b>Segmento</b>", body_bold_style), Paragraph("<b>Longitud</b>", body_bold_style), Paragraph("<b>Significado Presupuestario</b>", body_bold_style)]
    data_imp = [
        headers_imp,
        [Paragraph("<b>UUUUUU</b>", body_style), Paragraph("6 dígitos", body_style), Paragraph("Código único de Componente / Dependencia COAN", body_style)],
        [Paragraph("<b>I . P . p</b>", body_style), Paragraph("3 dígitos", body_style), Paragraph("Inciso, Principal y Parcial de la partida de origen", body_style)],
        [Paragraph("<b>SSSSS</b>", body_style), Paragraph("5 dígitos", body_style), Paragraph("Subparcial dinámico calculado (obras o regular)", body_style)],
        [Paragraph("<b>M</b>", body_style), Paragraph("1 dígito", body_style), Paragraph("Código identificador del tipo de Moneda de la partida", body_style)],
        [Paragraph("<b>OOO</b>", body_style), Paragraph("3 dígitos", body_style), Paragraph("Código OT (Orden de Trabajo) asignado a la Unidad Ejecutora", body_style)],
        [Paragraph("<b>CC</b>", body_style), Paragraph("2 dígitos", body_style), Paragraph("Subcuenta de financiamiento asignada (51 / 99)", body_style)],
    ]
    ti = Table(data_imp, colWidths=[90, 80, 334])
    ti.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(ti)
    
    story.append(PageBreak())
    
    # ==================== CONTROL CONCURRENCIA & PROCESOS POSTERIORES (PAGE 8) ====================
    story.append(Paragraph("Seguridad Transaccional y Procesos Posteriores", h1_style))
    story.append(Paragraph(
        "Debido a que el SGC opera en una red que puede experimentar sobrecargas o accesos concurrentes de múltiples dependencias, "
        "el motor interno implementa mecanismos avanzados de protección para evitar la sobre-ejecución del presupuesto asignado.",
        body_style
    ))
    
    story.append(Paragraph("1. Control Preventivo de Saldos y Bloqueo de Concurrencia", h2_style))
    story.append(Paragraph(
        "Cuando un operador presiona 'Guardar' en un compromiso, el sistema ejecuta de forma interna y atómica los siguientes pasos en la base de datos:",
        body_style
    ))
    story.append(Paragraph("<b>1. Bloqueo Preventivo de Fila:</b> Utiliza una instrucción <code>SELECT FOR UPDATE</code> para bloquear el registro de la Distribución (Techo de la unidad). Esto impide que otros operadores ejecuten transacciones simultáneas sobre el mismo techo hasta que la operación actual finalice.", bullet_style))
    story.append(Paragraph("<b>2. Validación de Saldo Real:</b> Verifica si el monto solicitado es menor o igual al disponible exacto. Si el saldo es insuficiente, aborta la transacción lanzando una excepción controlada (<code>InsufficientFundsError</code>).", bullet_style))
    story.append(Paragraph("<b>3. Idempotencia y Prevención de Duplicados:</b> Intenta crear el registro de ejecución. Si se detecta una colisión simultánea por el <code>external_id</code>, cancela la nueva carga y retorna el registro preexistente, garantizando que el dinero no se debite dos veces.", bullet_style))
    story.append(Paragraph("<b>4. Actualización Atómica:</b> Suma el importe comprometido al total de gasto acumulado (<code>spent_amount</code>) del techo de forma directa.", bullet_style))
    
    story.append(Paragraph("2. Fase de Devengado y Pago", h2_style))
    story.append(Paragraph(
        "Una vez que el Compromiso está asentado en firme, el operador puede registrar las fases subsiguientes a medida que se concreta la compra:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Fase 2 - Devengado:</b> Al recibirse la factura de compra o los bienes conformes, el usuario edita el registro del Compromiso en el listado y selecciona <b>'Devengar Gasto'</b>. Ingrese el monto devengado (el cual no puede superar bajo ninguna circunstancia el monto comprometido originalmente) y la fecha de devengo.", bullet_style))
    story.append(Paragraph("&bull; <b>Fase 3 - Pago:</b> Una vez librada la orden de pago bancaria o cheque, el usuario edita la ejecución devengada y selecciona <b>'Pagar Gasto'</b>. Ingrese el monto pagado (que no puede superar el monto devengado) y la fecha de pago efectiva.", bullet_style))
    
    story.append(Paragraph("3. Liberación de Sobrantes (Release Surplus)", h2_style))
    story.append(Paragraph(
        "Es común que un compromiso de gasto se reserve por un monto estimado (ej: $100.000) pero la compra final resulte inferior "
        "(ej: factura de devengado final por $85.000). En ese escenario, quedan $15.000 'bloqueados' en el sistema que la unidad ya no utilizará. "
        "Para resolver esto de forma segura:",
        body_style
    ))
    story.append(Paragraph(
        "El operador dispone del botón <b>'Liberar Sobrante'</b>. El SGC ajusta de forma atómica el monto comprometido original, "
        "igualándolo al monto devengado/pagado ($85.000) y reingresa automáticamente la diferencia sobrante ($15.000) de vuelta al "
        "saldo disponible del Techo Presupuestario de la unidad para que pueda ser utilizado en futuras compras.",
        body_style
    ))
    
    story.append(Paragraph("4. Eliminación de Registros de Ejecución", h2_style))
    story.append(Paragraph(
        "Para resguardar la consistencia y auditoría de la contabilidad presupuestaria, el sistema prohíbe de forma general la eliminación "
        "de registros de ejecución por parte de usuarios comunes. Únicamente los **superusuarios** o administradores del sistema tienen la facultad "
        "de realizar un borrado físico. Al eliminar una ejecución, el sistema devuelve automáticamente el monto comprometido al techo de la unidad.",
        body_style
    ))
    
    story.append(PageBreak())
    
    # ==================== COMPENSACIONES DE PARTIDAS (PAGE 9) ====================
    story.append(Paragraph("Módulo 4: Compensaciones de Partidas", h1_style))
    story.append(Paragraph(
        "Durante el ejercicio financiero, es recurrente que ciertas partidas presupuestarias globales (AA.PP.) cuenten con saldo excedente "
        "mientras que otras se encuentren deficitarias. Para solucionar esto sin alterar la asignación total de presupuesto autorizada por la Armada, "
        "el SGC provee el módulo de <b>Compensaciones de Partidas Presupuestarias</b>.",
        body_style
    ))
    
    story.append(Paragraph("1. Flujo y Reglas de Compensación", h2_style))
    story.append(Paragraph(
        "Las compensaciones se rigen por un estricto principio de partida doble y control administrativo:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Límite del Programa:</b> Para salvaguardar la normativa presupuestaria pública, la compensación solo se permite entre créditos pertenecientes al mismo <b>Programa Presupuestario</b>.", bullet_style))
    story.append(Paragraph("&bull; <b>Monto en Origen:</b> La solicitud de fondos a transferir desde el Crédito de Origen no puede superar en ningún trimestre al saldo de crédito disponible no distribuido de dicho trimestre.", bullet_style))
    
    story.append(Paragraph("2. Circuito Administrativo de Aprobación", h2_style))
    story.append(Paragraph(
        "El proceso de compensación consta de un circuito formal con segregación de funciones:",
        body_style
    ))
    story.append(Paragraph("<b>1. Solicitud:</b> Un operador o planificador crea una solicitud de compensación indicando el Crédito Origen, la Partida Destino (la cual puede crearse en el acto si no existía anteriormente en el catálogo), los montos a transferir por trimestre y las observaciones justificando el movimiento de fondos. El estado inicial de la solicitud queda como <b>Pendiente (PENDIENTE)</b> y los fondos de origen no se tocan aún.", bullet_style))
    story.append(Paragraph("<b>2. Autorización / Aprobación:</b> Un usuario con rol de Administrador o Comandante superior evalúa la solicitud. Tiene la facultad de <b>Aprobar (APROBADO)</b> o <b>Rechazar (RECHAZADO)</b> la solicitud.", bullet_style))
    story.append(Paragraph("<b>3. Ejecución Atómica:</b> Al aprobarse formalmente la solicitud, el SGC realiza el traspaso de fondos de forma atómica: resta los montos de cada trimestre en el crédito de origen y los suma al crédito de destino. Finalmente marca el estado de la compensación como <b>Ejecutado (EJECUTADO)</b> e imprime la firma digital del usuario que autorizó el movimiento.", bullet_style))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("Tabla de Estados del Circuito de Compensación", h3_style))
    
    headers_comp = [Paragraph("<b>Estado</b>", body_bold_style), Paragraph("<b>Significado Administrativo</b>", body_bold_style), Paragraph("<b>Efecto Presupuestario</b>", body_bold_style)]
    data_comp = [
        headers_comp,
        [Paragraph("PENDIENTE", body_style), Paragraph("Creada por el planificador, en espera de revisión.", body_style), Paragraph("Sin efecto. Los saldos no se modifican.", body_style)],
        [Paragraph("RECHAZADO", body_style), Paragraph("Evaluada y descartada por la comandancia por improcedente.", body_style), Paragraph("Sin efecto. La solicitud queda archivada.", body_style)],
        [Paragraph("EJECUTADO", body_style), Paragraph("Aprobada y aplicada formalmente a los saldos.", body_style), Paragraph("<b>Atómico:</b> Resta en Origen, Suma en Destino de forma irreversible.", body_style)],
    ]
    tc_c = Table(data_comp, colWidths=[90, 214, 200])
    tc_c.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(tc_c)
    
    story.append(PageBreak())
    
    # ==================== CONSULTAS Y REPORTES (PAGE 10) ====================
    story.append(Paragraph("Consultas, Reportes y Exportación de Datos", h1_style))
    story.append(Paragraph(
        "Para facilitar la toma de decisiones estratégicas por parte de la Comandancia de la Aviación Naval, el SGC ofrece "
        "diversas herramientas interactivas de análisis, visualización y exportación de datos contables.",
        body_style
    ))
    
    story.append(Paragraph("1. Estadísticas y Dashboard Presupuestario Interactivo", h2_style))
    story.append(Paragraph(
        "El Dashboard del SGC presenta una visualización consolidada y en tiempo real de la situación de los créditos:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Resumen Ejecutivo:</b> Gráficos de barras y dona que ilustran la relación entre el total asignado por partida y el nivel de compromiso y devengado.", bullet_style))
    story.append(Paragraph("&bull; <b>Detalle Desglosado:</b> Los montos correspondientes a 'Distribuido' en los tooltips del gráfico son **interactivos y clickeables**. Al pulsarlos, se despliega de forma instantánea un sub-modal con el desglose exacto de los importes transferidos a cada una de las unidades de consumo, permitiendo un análisis 'drill-down' de la información.", bullet_style))
    story.append(Paragraph("&bull; <b>Cálculo de Indicadores Críticos:</b> El sistema computa de forma automatizada indicadores clave como **Residuos Pasivos** (Compromiso no Devengado) y la **Deuda Flotante** (Devengado no Pagado) para evaluar el rezago de las compras.", bullet_style))
    
    story.append(Paragraph("2. Proyectos y Metas Presupuestarias (Clasificaciones)", h2_style))
    story.append(Paragraph(
        "A través de la vista de <b>'Proyectos / Planes de Gasto'</b>, la comandancia puede analizar el avance de ejecución de proyectos específicos "
        "vinculados a múltiples distribuciones de crédito. La vista detalla la meta de presupuesto del proyecto (target_amount), el monto real asignado "
        "y el porcentaje de ejecución respecto a la meta estimada, logrando trazabilidad gerencial absoluta.",
        body_style
    ))
    
    story.append(Paragraph("3. Exportación de Rendiciones", h2_style))
    story.append(Paragraph(
        "Para los entes de control externos de la Armada, el sistema provee una herramienta de exportación unificada de rendiciones a formato **CSV** compatible "
        "con planillas Excel. La exportación incluye la apertura detallada de cada compromiso, devengado y pago, la imputación variable autocalculada, "
        "el número de obra y expediente, facilitando la auditoría y rendición de cuentas reglamentaria.",
        body_style
    ))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("Procedimiento ante Contingencias u Operación Offline", h2_style))
    story.append(Paragraph(
        "El SGC está diseñado para poder operar en entornos aislados o en servidores de bases navales que sufran pérdida temporal de red con el comando central. "
        "En caso de operar de forma offline, los operadores de unidad pueden seguir registrando compromisos y devengados en sus terminales locales. Una vez restablecido "
        "el enlace de comunicaciones, el sistema sincroniza automáticamente las tablas de ejecución utilizando los ID de control único como salvaguarda ante colisiones.",
        body_style
    ))
    
    story.append(Paragraph(
        "<i>Fin del Manual. Para soporte presupuestario o técnico, contacte a la Jefatura de Presupuesto y Finanzas del Comando de la Aviación Naval.</i>",
        callout_style
    ))

    # Compile the PDF!
    print("Compiling PDF...")
    build_pdf("c:\\Materias-Grasas\\Manual_Usuario_SGC.pdf", story)
    print("PDF Compiled successfully!")

    # Now generate the Markdown version!
    print("Generating Markdown file...")
    md_content = """# Manual de Uso del Sistema de Gestión de Créditos (SGC)
**Plataforma Presupuestaria Unificada — Comando de la Aviación Naval (COAN)**

---

## Introducción y Arquitectura General

El **Sistema de Gestión de Créditos (SGC)** es una plataforma tecnológica avanzada e de alta disponibilidad desarrollada específicamente para el Comando de la Aviación Naval (COAN) de la Armada Argentina. Su propósito primordial es administrar, controlar y trazar con absoluto rigor el ciclo de vida del gasto público militar de la fuerza, desde la asignación del crédito anual de las partidas hasta el pago final de las facturas de proveedores.

El SGC se distingue por implementar una robusta arquitectura con soporte para transacciones concurrentes, redundancia offline y un sistema dinámico de seguridad centrado en el usuario. Toda la lógica del sistema está orientada a mitigar errores humanos en la carga de expedientes y asegurar que las distintas dependencias navales no sobrepasen los techos de financiamiento asignados trimestralmente.

### Pilares de Seguridad y Control de Acceso Modulares
La plataforma opera con un sistema de seguridad granular. El acceso a cada subsistema principal (SGMG — Sistema de Gestión de Materias Grasas, SIGERA — Sistema de Gestión de Recursos del Aire, SGP — Sistema de Gestión del Personal) requiere la autorización explícita de un **PIN de Seguridad de 4 dígitos** único por usuario y módulo. Este mecanismo es gestionado centralmente por la administración del sistema mediante un middleware que intercepta cada consulta y bloquea los accesos no autorizados de forma preventiva.

### Trazabilidad y Visibilidad Restringida de Datos
Para garantizar la confidencialidad de la información presupuestaria sensible de la Armada, el SGC aplica filtros estrictos a nivel de base de datos según el perfil del usuario activo:
* **Usuarios Administradores (AA.PP. / Superusuarios):** Poseen control total y visibilidad absoluta de los créditos, distribuciones globales y auditorías completas.
* **Usuarios Operativos (UU.CC. / Comandos de Unidad):** Visualizan *exclusivamente* la información presupuestaria, créditos trimestrales asignados y gastos cometidos correspondientes a su unidad autorizada. Tienen restringido el acceso a partidas globales de otras unidades.

> **Nota de Seguridad:** Todos los intentos de acceso fallidos o intentos de transpasar los límites de visualización de créditos asignados son registrados de forma persistente en los registros de auditoría del sistema para control preventivo.

---

## Estructura Presupuestaria y Clasificadores

Para la correcta registración y formulación del gasto público militar, el sistema SGC modela la estructura presupuestaria de la República Argentina a través de clasificadores anidados y relacionales. Estos catálogos son el pilar sobre el cual se asienta toda la imputación del gasto. Ningún crédito o gasto puede existir en el sistema sin estar vinculado a esta red de clasificadores.

### Los Componentes Presupuestarios en el SGC
A continuación se detallan los nomencladores presupuestarios clave gestionados en el panel de configuración central:
* **Ejercicio / Año Fiscal:** Representa el período económico (ej: 2026). Los ejercicios pueden estar en estado **Abierto (OPEN)** o **Cerrado (CLOSED)**. Cuando un ejercicio se marca como cerrado, se bloquea atómicamente toda creación de nuevos créditos, modificaciones o compromisos de gasto para dicho año.
* **Fuente de Financiamiento (FF):** Clasifica el origen de los fondos (ej: FF 11 - Tesoro Nacional, FF 13 - Recursos Propios, FF 99 - Crédito Externo/Otros). Su comportamiento define flujos y subcuentas automáticas.
* **Programa (PROG) y Subprograma (SUBPROG):** Categorizan la finalidad de las operaciones. El programa cuenta con un código administrador de 3 dígitos (ej: 016 - Operaciones Aéreas).
* **Inciso (INCISO):** El nivel general del gasto. Por ejemplo, Inciso 1 (Personal), Inciso 2 (Bienes de Consumo), Inciso 3 (Servicios No Personales), Inciso 4 (Bienes de Uso - Inversión/Obras) e Inciso 5 (Transferencias).
* **Estructura Interna del Inciso:** Principal (PPAL), Parcial (PARCIAL) y Sub-Parcial (SUBPC) (ej: Subparcial 2510 para Lubricantes).
* **Moneda (MONEDA):** Denominación presupuestaria técnica (ej: 1 - Pesos Argentinos, 2 - Dólares Estadounidenses, etc.).

### Estructura de Imputación Base
Toda partida de crédito se identifica de forma única con una cadena estandarizada que vincula todos estos códigos. En la interfaz se representa con el formato:

```
[FF]-[PROG]-[SUBPROG]-[INCISO]-[PPAL]-[PARCIAL]-[SUBPC]-[MONEDA]
```

| Clasificador | Código Ejemplo | Descripción Ejemplo |
| :--- | :--- | :--- |
| **FF** | 11 / 13 / 99 | Tesoro / Recursos Propios / Crédito Externo |
| **Programa** | 16 / 24 | Sostén Operacional de la Aviación Naval |
| **Inciso** | 2 / 3 / 4 | Consumo / Servicios / Bienes de Uso (Obras) |
| **Subparcial** | 2510 / 2520 | Grasas y Lubricantes Aeronáuticos |

---

## Módulo 1: Gestión de Créditos Presupuestarios (AA.PP.)

El Módulo de Créditos Presupuestarios es el punto de inicio de la cadena del gasto. Es la herramienta exclusiva del rol de **Administración de Presupuesto (AA.PP.)** del COAN. A través de este panel, se ingresan las partidas presupuestarias globales autorizadas por el Estado Mayor de la Armada para el ejercicio fiscal activo.

### 1. Registro y Alta de Créditos
Para dar de alta un crédito, el administrador accede a la sección **'Créditos (AA.PP.)'** y selecciona **'Nuevo Crédito Presupuestario'**. El sistema despliega un formulario unificado donde se debe seleccionar:
* El Ejercicio Económico activo.
* Los clasificadores de catálogo (FF, Programa, SUBPROG, INCISO, PPAL, Parcial, SUBPC, Moneda).
* Los importes correspondientes a cada trimestre del año: **Monto T1, Monto T2, Monto T3, Monto T4**.
* Observaciones adicionales de la partida.

El sistema calcula de forma instantánea el Monto Total de la partida (T1 + T2 + T3 + T4) y realiza validaciones para impedir registros duplicados de idéntica estructura clasificadora en el mismo ejercicio.

### 2. Ajustes y Modificaciones de Crédito (Reajustes)
Los montos asignados a un crédito no son estáticos; pueden sufrir variaciones durante el año debido a refuerzos presupuestarios o recortes de partidas. Para modificar un crédito existente de forma segura, el sistema prohíbe la edición directa del registro. En su lugar, implementa un flujo de **Ajuste de Crédito**:
* **Auditoría Completa:** Al realizar un ajuste, el usuario debe ingresar los nuevos importes trimestrales y detallar obligatoriamente el **Motivo del Ajuste**.
* **Historial de Cambios:** El SGC guarda un log permanente que almacena el monto anterior por trimestre, el nuevo monto ajustado, la diferencia resultante (deltas), el usuario responsable de la acción y la fecha exacta.
* **Validación de Techo:** No se puede ajustar un crédito reduciendo sus importes trimestrales por debajo de las sumas que ya fueron distribuidas a las Unidades Destinatarias para ese mismo trimestre. De intentarlo, el sistema arrojará un error descriptivo indicando exactamente en qué trimestre y por qué monto se está superando el límite físico de reducción.

### 3. Gestión del Tipo de Crédito y Desasignaciones
Cada partida se categoriza bajo un *Tipo de Crédito*. El sistema permite realizar cambios de tipo o desasignaciones parciales de crédito de forma controlada. Cada desasignación de fondos de una partida registra logs específicos de auditoría detallando los motivos.

---

## Módulo 2: Distribución de Techos a Unidades Ejecutoras (UU.CC.)

Una vez que los Créditos Presupuestarios globales (AA.PP.) están cargados en el SGC, el administrador debe transferir o 'distribuir' esos fondos a las distintas **Unidades de Consumo / Unidades Ejecutoras (UU.CC.)** del COAN (ej: Escuadra Aeronaval Nº 1, Base Aeronaval Comandante Espora, etc.). Esta distribución crea un **Techo Presupuestario de Unidad**.

### 1. Mecánica de Distribución y Asignación de Techos
Para realizar una distribución, el administrador ingresa a **'Distribución (UU.CC.)'** y selecciona **'Nueva Distribución de Crédito'**:
* **Crédito Origen:** Se selecciona la partida presupuestaria global cargada en el paso anterior. La interfaz muestra un indicador dinámico en tiempo real que detalla el **Saldo Disponible para Distribuir** del crédito seleccionado, evitando que el administrador haga cálculos manuales.
* **Unidad Destino:** Se elige el comando o dependencia militar que recibirá los fondos.
* **Montos Trimestrales (T1 a T4):** Se definen las cuotas trimestrales asignadas a la unidad. Al guardar, el total asignado se consolida atómicamente.

### 2. Vinculación con Proyectos / Planes de Gasto (Trazabilidad Extrema)
Con el objetivo de maximizar el control financiero, cada distribución de crédito puede asociarse a uno o más **Proyectos / Planes de Gasto** (anteriormente denominados 'Clasificaciones'). Estos proyectos son definidos por la comandancia para agrupar metas físicas de la fuerza (ej: *'Plan de Gasto para Mantenimiento de Aviones Super Etendard'*, *'Meta Adquisición de Grasas Especiales 2026'*).

Esta asociación permite obtener reportes consolidados cruzando las distribuciones con metas de gasto preestablecidas (target_amount), permitiendo verificar en cualquier momento si los fondos asignados se condicen con las metas estimadas.

### 3. Monitoreo Activo de Saldos de Techo
El SGC calcula para cada registro de Distribución tres campos monetarios dinámicos fundamentales:
* **Monto Asignado (Techo Total):** La suma del presupuesto transferido a la unidad (T1 + T2 + T3 + T4).
* **Monto Comprometido Acumulado (Spent Amount):** La sumatoria de todos los gastos reservados o ejecutados y registrados por la unidad contra ese techo.
* **Saldo Disponible:** Calculado de forma estricta como *Monto Asignado menos Monto Comprometido*. Este es el saldo de control preventivo en tiempo real.

---

## Módulo 3: Flujo de Ejecución del Gasto (Paso a Paso)

El corazón operativo de la plataforma SGC radica en el control del gasto público militar a través de un flujo secuencial, estricto y ordenado de tres pasos que corresponden a las etapas administrativas del Presupuesto Público Argentino: **1. Compromiso -> 2. Devengado -> 3. Pago**.

### Flujo de Operación Secuencial
El flujo de ejecución del gasto debe respetarse obligatoriamente de forma cronológica y cuantitativa:

| Fase del Gasto | Monto Límite | Efecto Financiero |
| :--- | :--- | :--- |
| **1. Compromiso** | Hasta el Saldo Disponible del Techo | Reserva presupuesto del techo trimestral. Impide usar el dinero para otra compra. |
| **2. Devengado** | Hasta el Monto Comprometido | Registra la recepción conforme del bien/servicio o factura. Consolida el gasto. |
| **3. Pago** | Hasta el Monto Devengado | Registra la salida física del dinero o cancelación de la obligación al proveedor. |

### Fase 1: Registro del Compromiso
Cuando una Unidad Operativa requiere iniciar un proceso de compra o gasto, debe registrar un Compromiso contra su techo asignado. Para ello ingresa a **'Ejecución'**, selecciona **'Comprometer Gasto'** y completa el formulario con los siguientes campos clave:
* **Distribución / Techo:** Se selecciona el techo disponible asignado. El combo autocompleta el saldo disponible actualizado de forma visual para evitar errores de selección.
* **Número de Expediente / Referencia:** Código oficial (ej: *'Exp. 14/2026'*) que avala el gasto administrativamente.
* **ID de Control Único:** Código opcional externo para prevenir de forma absoluta la duplicación involuntaria de la carga (ej: número de factura de proveedor, ID externo, etc.).
* **Monto a Comprometer:** Importe en pesos. Si se marca la casilla *'¿Comprometer el total disponible?'*, el sistema rellena automáticamente el campo con el saldo exacto remanente de la distribución, facilitando la liquidación final de partidas.
* **Tipo de Gasto (TG):** Clasificador específico para los incisos de operación regular (Obligatorio para Incisos 1, 2, 3 y 5).
* **Número de Obra:** Identificador de 5 dígitos requerido específicamente para inversiones e infraestructura (Obligatorio para Inciso 4, excepto si FF es 13 o 99).
* **Afecta PG 117:** Casilla de verificación para denotar si el gasto impacta las partidas especiales contempladas bajo el programa PG 117.
* **Fecha de Compromiso:** Fecha oficial de reserva de los fondos.

---

## El Motor de Imputación Variable Automática

Uno de los desarrollos más complejos del SGC es el **Motor de Imputación Variable Automática**. Este sistema elimina por completo la necesidad de que los operadores de unidad conozcan y conformen manualmente las largas y complejas cadenas de imputación del nomenclador público argentino al comprometer un gasto.

### Reglas de Negocio para el Cálculo Automático
Al guardar un Compromiso, el sistema SGC computa de forma atómica e inteligente dos variables presupuestarias complejas según el clasificador origen, la fuente de financiamiento (FF) y los campos cargados:

#### 1. Subcuenta Presupuestaria (SC) Automática:
Si la Fuente de Financiamiento (FF) del crédito es **13 (Recursos Propios)** o **99 (Otros)**, el sistema asigna automáticamente la subcuenta **'99'**. Para cualquier otra fuente de financiamiento (ej: FF 11 - Tesoro Nacional), el sistema asigna de forma predeterminada la subcuenta **'51'**.

#### 2. Subparcial Calculado de 5 Dígitos (SSSSS):
El subparcial de 5 dígitos se computa de forma dinámica mediante las siguientes tres reglas exclusivas:
* **Regla A (Obras Especiales):** Si el Inciso del crédito es **4 (Bienes de Uso / Obras)** y la Fuente de Financiamiento (FF) es **13** o **99**, el subparcial toma de forma automática el valor fijo **'99999'**.
* **Regla B (Obras Regulares):** Si el Inciso es **4** y la Fuente de Financiamiento (FF) es ordinaria (ej: FF 11), el subparcial se conforma obligatoriamente utilizando el **Número de Obra** de 5 dígitos ingresado por el operador (rellenado con ceros a la izquierda de ser necesario).
* **Regla C (Operaciones Corrientes):** Para el resto de los Incisos (1, 2, 3, 5), el subparcial de 5 dígitos se auto-conforma combinando:
  ```
  [Nomenclador Base (2 dígitos)] + [Código Tipo de Gasto (1 dígito)] + [Código Afectación PG117 (2 dígitos)]
  ```
  *(El Código de Afectación PG117 es '17' si está tildado, o '00' en caso contrario. El Nomenclador Base corresponde a los primeros 2 dígitos del SUBPC).*

### La Cadena de Imputación Variable Generada
Al concluir los cálculos, el SGC genera una cadena única denominada **Imputación Variable**, la cual representa la identidad formal de la reserva del gasto público ante la Contaduría de la Armada. Su estructura es:

```
UUUUUU . I . P . p . SSSSS . M . OOO . CC
```

| Segmento | Longitud | Significado Presupuestario |
| :--- | :--- | :--- |
| **UUUUUU** | 6 dígitos | Código único de Componente / Dependencia COAN |
| **I . P . p** | 3 dígitos | Inciso, Principal y Parcial de la partida de origen |
| **SSSSS** | 5 dígitos | Subparcial dinámico calculado (obras o regular) |
| **M** | 1 dígito | Código identificador del tipo de Moneda de la partida (normalmente '1') |
| **OOO** | 3 dígitos | Código OT (Orden de Trabajo) asignado a la Unidad Ejecutora |
| **CC** | 2 dígitos | Subcuenta de financiamiento asignada (51 / 99) |

---

## Seguridad Transaccional y Procesos Posteriores

Debido a que el SGC opera en una red que puede experimentar sobrecargas o accesos concurrentes de múltiples dependencias, el motor interno implementa mecanismos avanzados de protección para evitar la sobre-ejecución del presupuesto asignado.

### 1. Control Preventivo de Saldos y Bloqueo de Concurrencia
Cuando un operador presiona 'Guardar' en un compromiso, el sistema ejecuta de forma interna y atómica los siguientes pasos en la base de datos:
1. **Bloqueo Preventivo de Fila:** Utiliza una instrucción `SELECT FOR UPDATE` para bloquear el registro de la Distribución (Techo de la unidad). Esto impide que otros operadores ejecuten transacciones simultáneas sobre el mismo techo hasta que la operación actual finalice.
2. **Validación de Saldo Real:** Verifica si el monto solicitado es menor o igual al disponible exacto. Si el saldo es insuficiente, aborta la transacción lanzando una excepción controlada (`InsufficientFundsError`).
3. **Idempotencia y Prevención de Duplicados:** Intenta crear el registro de ejecución. Si se detecta una colisión simultánea por el `external_id`, cancela la nueva carga y retorna el registro preexistente, garantizando que el dinero no se debite dos veces.
4. **Actualización Atómica:** Suma el importe comprometido al total de gasto acumulado (`spent_amount`) del techo de forma directa.

### 2. Fase de Devengado y Pago
Una vez que el Compromiso está asentado en firme, el operador puede registrar las fases subsiguientes a medida que se concreta la compra:
* **Fase 2 - Devengado:** Al recibirse la factura de compra o los bienes conformes, el usuario edita el registro del Compromiso en el listado y selecciona **'Devengar Gasto'**. Ingrese el monto devengado (el cual no puede superar bajo ninguna circunstancia el monto comprometido originalmente) y la fecha de devengo.
* **Fase 3 - Pago:** Una vez librada la orden de pago bancaria o cheque, el usuario edita la ejecución devengada y selecciona **'Pagar Gasto'**. Ingrese el monto pagado (que no puede superar el monto devengado) y la fecha de pago efectiva.

### 3. Liberación de Sobrantes (Release Surplus)
Es común que un compromiso de gasto se reserve por un monto estimado (ej: $100.000) pero la compra final resulte inferior (ej: factura de devengado final por $85.000). En ese escenario, quedan $15.000 'bloqueados' en el sistema que la unidad ya no utilizará. Para resolver esto de forma segura:

El operador dispone del botón **'Liberar Sobrante'**. El SGC ajusta de forma atómica el monto comprometido original, igualándolo al monto devengado/pagado ($85.000) y reingresa automáticamente la diferencia sobrante ($15.000) de vuelta al saldo disponible del Techo Presupuestario de la unidad para que pueda ser utilizado en futuras compras.

### 4. Eliminación de Registros de Ejecución
Para resguardar la consistencia y auditoría de la contabilidad presupuestaria, el sistema prohíbe de forma general la eliminación de registros de ejecución por parte de usuarios comunes. Únicamente los **superusuarios** o administradores del sistema tienen la facultad de realizar un borrado físico. Al eliminar una ejecución, el sistema devuelve automáticamente el monto comprometido al techo de la unidad.

---

## Módulo 4: Compensaciones de Partidas

Durante el ejercicio financiero, es recurrente que ciertas partidas presupuestarias globales (AA.PP.) cuenten con saldo excedente mientras que otras se encuentren deficitarias. Para solucionar esto sin alterar la asignación total de presupuesto autorizada por la Armada, el SGC provee el módulo de **Compensaciones de Partidas Presupuestarias**.

### 1. Flujo y Reglas de Compensación
Las compensaciones se rigen por un estricto principio de partida doble y control administrativo:
* **Límite del Programa:** Para salvaguardar la normativa presupuestaria pública, la compensación solo se permite entre créditos pertenecientes al mismo **Programa Presupuestario**.
* **Monto en Origen:** La solicitud de fondos a transferir desde el Crédito de Origen no puede superar en ningún trimestre al saldo de crédito disponible no distribuido de dicho trimestre.

### 2. Circuito Administrativo de Aprobación
El proceso de compensación consta de un circuito formal con segregación de funciones:
1. **Solicitud:** Un operador o planificador crea una solicitud de compensación indicando el Crédito Origen, la Partida Destino (la cual puede crearse en el acto si no existía anteriormente en el catálogo), los montos a transferir por trimestre y las observaciones justificando el movimiento de fondos. El estado inicial de la solicitud queda como **Pendiente (PENDIENTE)** y los fondos de origen no se tocan aún.
2. **Autorización / Aprobación:** Un usuario con rol de Administrador o Comandante superior evalúa la solicitud. Tiene la facultad de **Aprobar (APROBADO)** o **Rechazar (RECHAZADO)** la solicitud.
3. **Ejecución Atómica:** Al aprobarse formalmente la solicitud, el SGC realiza el traspaso de fondos de forma atómica: resta los montos de cada trimestre en el crédito de origen y los suma al crédito de destino. Finalmente marca el estado de la compensación como **Ejecutado (EJECUTADO)** e imprime la firma digital del usuario que autorizó el movimiento.

| Estado | Significado Administrativo | Efecto Presupuestario |
| :--- | :--- | :--- |
| **PENDIENTE** | Creada por el planificador, en espera de revisión. | Sin efecto. Los saldos no se modifican. |
| **RECHAZADO** | Evaluada y descartada por la comandancia por improcedente. | Sin efecto. La solicitud queda archivada. |
| **EJECUTADO** | Aprobada y aplicada formalmente a los saldos. | **Atómico:** Resta en Origen, Suma en Destino de forma irreversible. |

---

## Consultas, Reportes y Exportación de Datos

Para facilitar la toma de decisiones estratégicas por parte de la Comandancia de la Aviación Naval, el SGC ofrece diversas herramientas interactivas de análisis, visualización y exportación de datos contables.

### 1. Estadísticas y Dashboard Presupuestario Interactivo
El Dashboard del SGC presenta una visualización consolidada y en tiempo real de la situación de los créditos:
* **Resumen Ejecutivo:** Gráficos de barras y dona que ilustran la relación entre el total asignado por partida y el nivel de compromiso y devengado.
* **Detalle Desglosado:** Los montos correspondientes a 'Distribuido' en los tooltips del gráfico son **interactivos y clickeables**. Al pulsarlos, se despliega de forma instantánea un sub-modal con el desglose exacto de los importes transferidos a cada una de las unidades de consumo, permitiendo un análisis 'drill-down' de la información.
* **Cálculo de Indicadores Críticos:** El sistema computa de forma automatizada indicadores clave como **Residuos Pasivos** (Compromiso no Devengado) y la **Deuda Flotante** (Devengado no Pagado) para evaluar el rezago de las compras.

### 2. Proyectos y Metas Presupuestarias (Clasificaciones)
A través de la vista de **'Proyectos / Planes de Gasto'**, la comandancia puede analizar el avance de ejecución de proyectos específicos vinculados a múltiples distribuciones de crédito. La vista detalla la meta de presupuesto del proyecto (target_amount), el monto real asignado y el porcentaje de ejecución respecto a la meta estimada, logrando trazabilidad gerencial absoluta.

### 3. Exportación de Rendiciones
Para los entes de control externos de la Armada, el sistema provee una herramienta de exportación unificada de rendiciones a formato **CSV** compatible con planillas Excel. La exportación incluye la apertura detallada de cada compromiso, devengado y pago, la imputación variable autocalculada, el número de obra y expediente, facilitando la auditoría y rendición de cuentas reglamentaria.

### Procedimiento ante Contingencias u Operación Offline
El SGC está diseñado para poder operar en entornos aislados o en servidores de bases navales que sufran pérdida temporal de red con el comando central. En caso de operar de forma offline, los operadores de unidad pueden seguir registrando compromisos y devengados en sus terminales locales. Una vez restablecido el enlace de comunicaciones, el sistema sincroniza automáticamente las tablas de ejecución utilizando los ID de control único como salvaguarda ante colisiones.

---
*Fin del Manual. Para soporte presupuestario o técnico, contacte a la Jefatura de Presupuesto y Finanzas del Comando de la Aviación Naval (COAN).*
"""
    with open("c:\\Materias-Grasas\\Manual_Usuario_SGC.md", "w", encoding="utf-8") as f:
        f.write(md_content)
    print("Markdown Generated successfully!")

if __name__ == "__main__":
    generate_manual()
