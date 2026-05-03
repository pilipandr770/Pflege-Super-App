from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors


def generate_patient_summary_pdf(patient):
    """Generate PDF summary of patient with key information."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a5f7a'),
        spaceAfter=12,
    )
    elements.append(Paragraph(f"Patienten-Übersicht: {patient.full_name}", title_style))
    elements.append(Spacer(1, 0.5*cm))

    # Patient Info Table
    patient_data = [
        ['Name', patient.full_name],
        ['Geburtsdatum', patient.geburtsdatum.strftime('%d.%m.%Y') if patient.geburtsdatum else '—'],
        ['Alter', f"{patient.age} Jahre" if patient.age else '—'],
        ['Pflegegrad', f"PG {patient.pflegegrad}" if patient.pflegegrad else '—'],
        ['Aufnahmedatum', patient.aufnahmedatum.strftime('%d.%m.%Y') if patient.aufnahmedatum else '—'],
        ['Zimmer', f"{patient.zimmer_nr}/{patient.bett_nr}" if patient.zimmer_nr else '—'],
        ['Versicherung', patient.krankenversicherung or '—'],
    ]

    table = Table(patient_data, colWidths=[4*cm, 10*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4f8')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5*cm))

    # Risks
    risk_text = []
    if patient.sturzrisiko:
        risk_text.append("🚨 Sturzrisiko")
    if patient.dekubitusrisiko:
        risk_text.append("🚨 Dekubitus-Risiko")
    if patient.ernaehrungsrisiko:
        risk_text.append("🚨 Ernährungs-Risiko")

    if risk_text:
        elements.append(Paragraph("<b>⚠ Identifizierte Risiken:</b> " + " | ".join(risk_text), styles['Normal']))

    # Footer
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph(
        f"<i>Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')} • PflegeOS Dokumentationssystem</i>",
        styles['Normal']
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_sis_assessment_pdf(patient, sis):
    """Generate PDF of SIS assessment."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#1a5f7a'),
        spaceAfter=6,
    )

    elements.append(Paragraph(f"SIS-Einschätzung: {patient.full_name}", title_style))
    elements.append(Paragraph(f"Datum: {sis.assessment_date.strftime('%d.%m.%Y')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*cm))

    # Assessment Summary
    blocks = [
        ('Kognition', sis.kb1_freitext or 'Keine Notizen'),
        ('Mobilität', sis.kb2_freitext or 'Keine Notizen'),
        ('Krankheitsbezogen', sis.kb3_freitext or 'Keine Notizen'),
        ('Selbstversorgung', sis.kb4_freitext or 'Keine Notizen'),
        ('Soziales', sis.kb5_freitext or 'Keine Notizen'),
    ]

    for block_name, block_text in blocks:
        elements.append(Paragraph(f"<b>{block_name}</b>", styles['Heading3']))
        elements.append(Paragraph(block_text, styles['Normal']))
        elements.append(Spacer(1, 0.2*cm))

    # Care goals
    if sis.ziele:
        elements.append(Paragraph("<b>Pflege-Ziele</b>", styles['Heading3']))
        elements.append(Paragraph(sis.ziele, styles['Normal']))

    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(
        f"<i>Erstellt: {sis.created_at.strftime('%d.%m.%Y %H:%M')} • Status: {sis.status}</i>",
        styles['Normal']
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_medication_plan_pdf(patient, plan):
    """Generate PDF of medication plan."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#1a5f7a'),
        spaceAfter=6,
    )

    elements.append(Paragraph(f"Medikationsplan: {patient.full_name}", title_style))
    elements.append(Paragraph(f"Gültig von: {plan.valid_from.strftime('%d.%m.%Y')} bis {plan.valid_until.strftime('%d.%m.%Y') if plan.valid_until else '(unbegrenzt)'}", styles['Normal']))
    elements.append(Spacer(1, 0.3*cm))

    # Medications table
    med_data = [['Medikament', 'Stärke', 'Morgens', 'Mittags', 'Abends', 'Nachts', 'Besonderheiten']]
    for med in plan.medications:
        med_data.append([
            med.handelsname,
            med.staerke or '—',
            med.morgens or '—',
            med.mittags or '—',
            med.abends or '—',
            med.nachts or '—',
            ('BtM' if med.is_btm else '') + (' Bei Bedarf' if med.bei_bedarf else ''),
        ])

    if len(med_data) > 1:
        table = Table(med_data, colWidths=[2.5*cm, 1.5*cm, 1.2*cm, 1.2*cm, 1.2*cm, 1.2*cm, 1.8*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5f7a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)

    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(
        f"<i>Erstellt: {plan.created_at.strftime('%d.%m.%Y %H:%M')} • PflegeOS</i>",
        styles['Normal']
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
