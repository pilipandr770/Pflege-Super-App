from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, PageBreak, HRFlowable)
from reportlab.lib import colors

PFLEGEOS_BLUE  = colors.HexColor('#1a5f7a')
PFLEGEOS_LIGHT = colors.HexColor('#e8f4f8')


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


# ─────────────────────────────────────────────────────────────
# HKP — Häusliche Krankenpflege (§37 SGB V, Muster 12)
# ─────────────────────────────────────────────────────────────

def generate_hkp_pdf(hkp, company):
    """Druckfertiges HKP-Formular (angelehnt an Muster 12)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=2*cm,
        leftMargin=2*cm, rightMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    el = []

    head = ParagraphStyle('HKPHead', parent=styles['Heading1'],
                          fontSize=13, textColor=PFLEGEOS_BLUE, spaceAfter=2)
    sub  = ParagraphStyle('HKPSub',  parent=styles['Normal'],
                          fontSize=8,  textColor=colors.grey, spaceAfter=4)
    bold = ParagraphStyle('HKPBold', parent=styles['Normal'],
                          fontSize=9, fontName='Helvetica-Bold')
    norm = ParagraphStyle('HKPNorm', parent=styles['Normal'], fontSize=9)

    # ── Kopfzeile ────────────────────────────────────────────
    el.append(Paragraph('Verordnung häusliche Krankenpflege', head))
    el.append(Paragraph('§37 SGB V  •  Muster 12  •  Original für Krankenkasse', sub))
    el.append(HRFlowable(width='100%', thickness=1, color=PFLEGEOS_BLUE))
    el.append(Spacer(1, 0.3*cm))

    # ── Pflegedienst ─────────────────────────────────────────
    el.append(Paragraph('Pflegedienst (Leistungserbringer)', bold))
    el.append(Paragraph(
        f"{company.name}<br/>"
        f"{company.strasse} {company.hausnummer}, {company.plz} {company.ort}<br/>"
        f"IK-Nummer: {company.ik_nummer or '—'}  |  Tel: {company.telefon or '—'}",
        norm))
    el.append(Spacer(1, 0.4*cm))

    # ── Arzt + Patient nebeneinander ─────────────────────────
    patient = hkp.patient
    arzt_block = (
        f"<b>Verordnender Arzt</b><br/>"
        f"{hkp.arzt_name}<br/>"
        f"{(hkp.arzt_adresse or '').replace(chr(10), '<br/>')}<br/>"
        f"LANR: {hkp.arzt_lanr or '—'}  BSNR: {hkp.arzt_bsnr or '—'}"
    )
    pat_block = (
        f"<b>Patient/in</b><br/>"
        f"{patient.full_name}<br/>"
        f"geb. {patient.geburtsdatum.strftime('%d.%m.%Y') if patient.geburtsdatum else '—'}<br/>"
        f"Vers.-Nr.: {patient.versicherungsnummer or '—'}<br/>"
        f"Krankenkasse: {patient.krankenversicherung or '—'}"
    )
    two_col = Table(
        [[Paragraph(arzt_block, norm), Paragraph(pat_block, norm)]],
        colWidths=[8.5*cm, 8.5*cm],
    )
    two_col.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX',    (0, 0), (0, 0), 0.5, colors.grey),
        ('BOX',    (1, 0), (1, 0), 0.5, colors.grey),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
    ]))
    el.append(two_col)
    el.append(Spacer(1, 0.4*cm))

    # ── Zeitraum ─────────────────────────────────────────────
    el.append(Paragraph('<b>Verordnungszeitraum</b>', bold))
    zt = Table([[
        'Von', hkp.gueltig_von.strftime('%d.%m.%Y'),
        'Bis', hkp.gueltig_bis.strftime('%d.%m.%Y'),
        'Dauer', f"{hkp.dauer_wochen or '—'} Wochen",
    ]], colWidths=[1.5*cm, 3.5*cm, 1*cm, 3.5*cm, 2*cm, 3*cm])
    zt.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
        ('FONTNAME', (4, 0), (4, 0), 'Helvetica-Bold'),
        ('BOX',  (0, 0), (-1, -1), 0.5, colors.grey),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    el.append(zt)
    el.append(Spacer(1, 0.4*cm))

    # ── Diagnosen ────────────────────────────────────────────
    el.append(Paragraph('<b>Diagnose(n) nach ICD-10</b>', bold))
    diag_data = [['ICD-Code', 'Diagnosetext']]
    for d in hkp.diagnosen_list:
        diag_data.append([d.get('icd', ''), d.get('text', '')])
    if len(diag_data) == 1:
        diag_data.append(['—', '—'])
    dt = Table(diag_data, colWidths=[3*cm, 14*cm])
    dt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PFLEGEOS_BLUE),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    el.append(dt)
    el.append(Spacer(1, 0.4*cm))

    # ── Verordnete Leistungen ────────────────────────────────
    el.append(Paragraph('<b>Verordnete Leistungen (§37 SGB V)</b>', bold))
    leis_data = [['Typ', 'Leistung / Maßnahme', 'Häufigkeit']]
    for lv in hkp.leistungen_list:
        leis_data.append([
            lv.get('typ', ''),
            lv.get('bezeichnung', ''),
            lv.get('haeufigkeit', ''),
        ])
    if len(leis_data) == 1:
        leis_data.append(['—', '—', '—'])
    lt = Table(leis_data, colWidths=[3.5*cm, 10.5*cm, 3*cm])
    lt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PFLEGEOS_BLUE),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PFLEGEOS_LIGHT]),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    el.append(lt)

    if hkp.begruendung_langzeit:
        el.append(Spacer(1, 0.3*cm))
        el.append(Paragraph(
            f'<b>Begründung Langzeitverordnung:</b> {hkp.begruendung_langzeit}', norm))

    el.append(Spacer(1, 0.5*cm))

    # ── Genehmigung ──────────────────────────────────────────
    if hkp.status == 'GENEHMIGT':
        el.append(Paragraph('<b>Genehmigung der Krankenkasse</b>', bold))
        gt = Table([[
            'Genehmigt am',
            hkp.genehmigt_am.strftime('%d.%m.%Y') if hkp.genehmigt_am else '—',
            'Genehmigungsnr.',
            hkp.genehmigungsnummer or '—',
        ]], colWidths=[3.5*cm, 4*cm, 3.5*cm, 6*cm])
        gt.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOX',  (0, 0), (-1, -1), 0.5, colors.green),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        el.append(gt)
        el.append(Spacer(1, 0.4*cm))

    # ── Unterschriften ───────────────────────────────────────
    el.append(Spacer(1, 1.2*cm))
    sig = Table([
        ['Datum, Unterschrift Arzt', '', 'Datum, Stempel Pflegedienst'],
        ['\n\n_____________________________', '',
         '\n\n_____________________________'],
    ], colWidths=[7*cm, 3*cm, 7*cm])
    sig.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN',    (0, 0), (-1, -1), 'CENTER'),
    ]))
    el.append(sig)

    # ── Fußzeile ─────────────────────────────────────────────
    el.append(Spacer(1, 0.5*cm))
    el.append(HRFlowable(width='100%', thickness=0.5, color=colors.grey))
    el.append(Paragraph(
        f'Erstellt: {datetime.now().strftime("%d.%m.%Y %H:%M")}  •  PflegeOS  •  '
        f'Verordnungs-Nr.: {hkp.verordnungs_nr or hkp.id[:8].upper()}',
        ParagraphStyle('HKPFooter', parent=styles['Normal'],
                       fontSize=7, textColor=colors.grey, spaceBefore=4)
    ))
    doc.build(el)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────────────────────
# LEISTUNGSNACHWEIS — Monatlicher Nachweis für Krankenkasse
# ─────────────────────────────────────────────────────────────

def generate_leistungsnachweis_pdf(patient, lns, monat_str, company):
    """
    Druckfertiger Leistungsnachweis für einen Patienten (ein Monat).
    monat_str: 'YYYY-MM'
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=2*cm,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
    )
    styles = getSampleStyleSheet()
    el = []

    head  = ParagraphStyle('LNHead',  parent=styles['Heading1'],
                           fontSize=13, textColor=PFLEGEOS_BLUE, spaceAfter=2)
    sub   = ParagraphStyle('LNSub',   parent=styles['Normal'],
                           fontSize=8, textColor=colors.grey, spaceAfter=4)
    bold  = ParagraphStyle('LNBold',  parent=styles['Normal'],
                           fontSize=9, fontName='Helvetica-Bold')
    norm  = ParagraphStyle('LNNorm',  parent=styles['Normal'], fontSize=9)
    small = ParagraphStyle('LNSmall', parent=styles['Normal'], fontSize=8)

    # ── Kopfzeile ────────────────────────────────────────────
    el.append(Paragraph('Leistungsnachweis Häusliche Pflege', head))
    el.append(Paragraph(
        f'Abrechnungsmonat: {monat_str}  •  §36 SGB XI / §37 SGB V', sub))
    el.append(HRFlowable(width='100%', thickness=1, color=PFLEGEOS_BLUE))
    el.append(Spacer(1, 0.3*cm))

    # ── Dienst + Patient ─────────────────────────────────────
    dienst_txt = (
        f"<b>{company.name}</b><br/>"
        f"{company.strasse} {company.hausnummer}, {company.plz} {company.ort}<br/>"
        f"IK-Nr.: {company.ik_nummer or '—'}  Tel.: {company.telefon or '—'}"
    )
    pat_txt = (
        f"<b>{patient.full_name}</b><br/>"
        f"geb. {patient.geburtsdatum.strftime('%d.%m.%Y') if patient.geburtsdatum else '—'}<br/>"
        f"Vers.-Nr.: {patient.versicherungsnummer or '—'}<br/>"
        f"Kasse: {patient.krankenversicherung or '—'}  PG: {patient.pflegegrad or '—'}"
    )
    header_tbl = Table(
        [[Paragraph(dienst_txt, norm), Paragraph(pat_txt, norm)]],
        colWidths=[8.5*cm, 8.5*cm],
    )
    header_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX',  (0, 0), (0, 0), 0.5, colors.grey),
        ('BOX',  (1, 0), (1, 0), 0.5, colors.grey),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
    ]))
    el.append(header_tbl)
    el.append(Spacer(1, 0.5*cm))

    # ── Leistungstabelle ─────────────────────────────────────
    el.append(Paragraph('<b>Erbrachte Leistungen</b>', bold))
    el.append(Spacer(1, 0.2*cm))

    tbl_data = [['Datum', 'Uhrzeit', 'Leistung (LK-Nr.)', 'Min.', 'Mitarbeiter', 'HZ']]
    total_min = 0
    for ln in sorted(lns, key=lambda x: (x.durchgefuehrt_am, x.durchgefuehrt_um)):
        leistung_label = (
            f"{ln.leistung.leistung_nr}  {ln.leistung.bezeichnung}"
            if ln.leistung else '—'
        )
        dauer = ln.dauer_minuten or (ln.leistung.dauer_minuten if ln.leistung else 0) or 0
        tbl_data.append([
            ln.durchgefuehrt_am.strftime('%d.%m.'),
            ln.durchgefuehrt_um.strftime('%H:%M') if ln.durchgefuehrt_um else '—',
            leistung_label,
            str(dauer) if dauer else '—',
            ln.employee.full_name if ln.employee else '—',
            '',
        ])
        total_min += dauer

    tbl = Table(tbl_data,
                colWidths=[1.6*cm, 1.5*cm, 7.5*cm, 1.2*cm, 4.0*cm, 1.7*cm],
                repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PFLEGEOS_BLUE),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 8),
        ('GRID',       (0, 0), (-1, -1), 0.3, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [PFLEGEOS_LIGHT, colors.white]),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    el.append(tbl)

    total_h = total_min // 60
    total_m = total_min % 60
    el.append(Spacer(1, 0.3*cm))
    el.append(Paragraph(
        f'<b>Gesamt: {len(lns)} Einsätze  •  {total_h}h {total_m}min</b>', bold))

    # ── Unterschrift ─────────────────────────────────────────
    el.append(Spacer(1, 1*cm))
    el.append(Paragraph(
        'Hiermit bestätige ich, dass die aufgeführten Leistungen ordnungsgemäß erbracht wurden.',
        small))
    el.append(Spacer(1, 0.8*cm))
    sig2 = Table([
        ['Datum, Unterschrift Patient/in bzw. Bevollmächtigte/r', '',
         'Datum, Stempel Pflegedienst'],
        ['\n\n_______________________________', '',
         '\n\n_______________________________'],
    ], colWidths=[7.5*cm, 2*cm, 7.5*cm])
    sig2.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN',    (0, 0), (-1, -1), 'CENTER'),
    ]))
    el.append(sig2)

    # ── Fußzeile ─────────────────────────────────────────────
    el.append(Spacer(1, 0.5*cm))
    el.append(HRFlowable(width='100%', thickness=0.5, color=colors.grey))
    el.append(Paragraph(
        f'Erstellt: {datetime.now().strftime("%d.%m.%Y %H:%M")}  •  PflegeOS Dokumentationssystem',
        ParagraphStyle('LNFooter', parent=styles['Normal'],
                       fontSize=7, textColor=colors.grey, spaceBefore=4)
    ))
    doc.build(el)
    buffer.seek(0)
    return buffer
