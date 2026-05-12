import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListItem, ListFlowable
from reportlab.lib.enums import TA_JUSTIFY

def clean_tags(text):
    """Simple replacement for bold tags that reportlab understands."""
    parts = text.split('**')
    res = ""
    for i, part in enumerate(parts):
        if i % 2 == 1:
            res += f"<b>{part}</b>"
        else:
            res += part
    return res

def generate_manual_pdf(input_md_path, output_pdf_path):
    doc = SimpleDocTemplate(output_pdf_path, pagesize=A4,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    styles.add(ParagraphStyle(name='Justify', parent=styles['Normal'], alignment=TA_JUSTIFY, spaceAfter=8))
    styles.add(ParagraphStyle(name='Header1', parent=styles['Heading1'], fontSize=20, spaceAfter=14))
    styles.add(ParagraphStyle(name='Header2', parent=styles['Heading2'], fontSize=16, spaceBefore=12, spaceAfter=10))
    styles.add(ParagraphStyle(name='Header3', parent=styles['Heading3'], fontSize=14, spaceBefore=10, spaceAfter=8))

    elements = []
    
    if not os.path.exists(input_md_path):
        print(f"Error: {input_md_path} not found.")
        return

    with open(input_md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_list = False
    list_items = []

    for line in lines:
        line = line.strip()
        
        # Handle headers
        if line.startswith('# '):
            if in_list:
                elements.append(ListFlowable(list_items, bulletType='bullet'))
                list_items = []
                in_list = False
            elements.append(Paragraph(line[2:], styles['Header1']))
        elif line.startswith('## '):
            if in_list:
                elements.append(ListFlowable(list_items, bulletType='bullet'))
                list_items = []
                in_list = False
            elements.append(Paragraph(line[3:], styles['Header2']))
        elif line.startswith('### '):
            if in_list:
                elements.append(ListFlowable(list_items, bulletType='bullet'))
                list_items = []
                in_list = False
            elements.append(Paragraph(line[4:], styles['Header3']))
        elif line.startswith('---'):
            if in_list:
                elements.append(ListFlowable(list_items, bulletType='bullet'))
                list_items = []
                in_list = False
            elements.append(Spacer(1, 12))
        elif line.startswith('* ') or line.startswith('- '):
            in_list = True
            clean_item = clean_tags(line[2:])
            list_items.append(ListItem(Paragraph(clean_item, styles['Normal'])))
        elif line == '':
            if in_list:
                elements.append(ListFlowable(list_items, bulletType='bullet', spaceAfter=10))
                list_items = []
                in_list = False
            elements.append(Spacer(1, 6))
        else:
            if in_list:
                elements.append(ListFlowable(list_items, bulletType='bullet', spaceAfter=10))
                list_items = []
                in_list = False
            clean_line = clean_tags(line)
            elements.append(Paragraph(clean_line, styles['Justify']))

    if in_list:
        elements.append(ListFlowable(list_items, bulletType='bullet'))

    doc.build(elements)
    print(f"PDF successfully generated: {output_pdf_path}")

if __name__ == "__main__":
    generate_manual_pdf('manual_usuario.md', 'manual_usuario.pdf')

if __name__ == "__main__":
    generate_manual_pdf('manual_usuario.md', 'manual_usuario.pdf')
