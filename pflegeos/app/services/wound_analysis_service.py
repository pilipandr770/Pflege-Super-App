"""
KI-gestützte Wundanalyse via Claude Vision (claude-sonnet-5).

Analysiert Wundfoto(s) und gibt strukturierte medizinische Einschätzung zurück.
Das Ergebnis wird als JSON in WoundAssessment.foto_ai_analysis gespeichert.
"""
import base64
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Du bist ein erfahrener Wundmanagement-Assistent für professionelle Pflegekräfte in Deutschland.
Du analysierst Wundfotos und erstellst eine strukturierte medizinische Einschätzung auf Deutsch.
Deine Einschätzung unterstützt die Pflegekraft, sie ersetzt KEINE ärztliche Diagnose.
Antworte AUSSCHLIESSLICH mit gültigem JSON – kein Prosa, keine Erklärungen außerhalb des JSON.
"""

_USER_PROMPT = """\
Analysiere das/die beigefügte(n) Wundfoto(s) und gib eine strukturierte Einschätzung zurück.

Kontext:
- Wunde: {wunde_bezeichnung}
- Lokalisation: {lokalisation}
- Stadium (vom Pfleger dokumentiert): {stage}
- Bisherige Tendenz: {tendenz}

Antworte mit folgendem JSON-Schema (alle Felder Pflicht, leerer String wenn nicht beurteilbar):
{{
  "wundgroesse_schätzung": "klein < 4cm² | mittel 4-16cm² | groß > 16cm²",
  "wundstadium_ki": "I | II | III | IV | nicht beurteilbar",
  "wundgrund_ki": "Beschreibung des sichtbaren Wundgrundes",
  "exsudat_ki": "keine | gering | mäßig | stark",
  "infektion_hinweise": true,
  "infektion_merkmale": "sichtbare Merkmale oder leerer String",
  "tendenz_ki": "Verbesserung | Stagnation | Verschlechterung | nicht beurteilbar",
  "empfehlungen": ["Empfehlung 1", "Empfehlung 2"],
  "dringlichkeit": "routine | erhöht | dringend",
  "arzt_informieren": true,
  "arzt_grund": "Begründung oder leerer String",
  "hinweis": "Allgemeiner Hinweis an die Pflegekraft"
}}
"""


def analyse_wound_photos(assessment, app=None) -> dict | None:
    """
    Analysiert die Fotos eines WoundAssessment mit Claude Vision.

    Args:
        assessment: WoundAssessment-Objekt (muss foto_paths als JSON-Liste haben)
        app: Flask-App (optional, für Standalone-Aufruf)

    Returns:
        dict mit KI-Analyse oder None bei Fehler
    """
    try:
        foto_paths = json.loads(assessment.foto_paths or '[]')
    except Exception:
        foto_paths = []

    if not foto_paths:
        logger.info(f"[WoundAI] Assessment {assessment.id}: keine Fotos, übersprungen.")
        return None

    api_key = None
    upload_folder = None

    if app:
        api_key = app.config.get('ANTHROPIC_API_KEY')
        upload_folder = app.config.get('UPLOAD_FOLDER', '')
    else:
        from flask import current_app
        api_key = current_app.config.get('ANTHROPIC_API_KEY')
        upload_folder = current_app.config.get('UPLOAD_FOLDER', '')

    if not api_key:
        logger.warning("[WoundAI] Kein ANTHROPIC_API_KEY konfiguriert.")
        return None

    import anthropic

    content = []

    # Bis zu 3 Fotos mitschicken (Token-Limit beachten)
    for rel_path in foto_paths[:3]:
        abs_path = Path(upload_folder) / rel_path
        if not abs_path.exists():
            logger.warning(f"[WoundAI] Foto nicht gefunden: {abs_path}")
            continue
        try:
            with open(abs_path, 'rb') as fh:
                raw = fh.read()
            b64 = base64.standard_b64encode(raw).decode('ascii')
            ext = abs_path.suffix.lower().lstrip('.')
            media_type = {
                'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                'png': 'image/png', 'webp': 'image/webp',
                'gif': 'image/gif',
            }.get(ext, 'image/jpeg')
            content.append({
                'type': 'image',
                'source': {'type': 'base64', 'media_type': media_type, 'data': b64},
            })
        except Exception as e:
            logger.error(f"[WoundAI] Fehler beim Lesen von {abs_path}: {e}")

    if not content:
        logger.warning(f"[WoundAI] Assessment {assessment.id}: keine lesbaren Fotos.")
        return None

    # Text-Prompt hinzufügen
    wound = assessment.wound
    user_text = _USER_PROMPT.format(
        wunde_bezeichnung=wound.wunde_bezeichnung,
        lokalisation=wound.lokalisation,
        stage=assessment.stage or wound.stage or 'nicht angegeben',
        tendenz=assessment.tendenz or 'nicht bekannt',
    )
    content.append({'type': 'text', 'text': user_text})

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model='claude-sonnet-5',
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': content}],
        )
        raw_text = response.content[0].text.strip()

        # JSON aus der Antwort extrahieren
        if raw_text.startswith('```'):
            raw_text = raw_text.split('```')[1]
            if raw_text.startswith('json'):
                raw_text = raw_text[4:]
            raw_text = raw_text.rsplit('```', 1)[0]

        result = json.loads(raw_text)
        logger.info(f"[WoundAI] Assessment {assessment.id}: Analyse erfolgreich.")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[WoundAI] JSON-Parse-Fehler: {e} | Antwort: {raw_text[:200]}")
        return None
    except Exception as e:
        logger.error(f"[WoundAI] API-Fehler: {e}")
        return None


def run_analysis_and_save(assessment_id: str, app=None) -> bool:
    """
    Lädt ein WoundAssessment, analysiert Fotos und speichert das Ergebnis in foto_ai_analysis.

    Gedacht für asynchrone Aufrufe (z.B. nach dem Speichern eines Assessments).
    """
    ctx = None
    if app:
        ctx = app.app_context()
        ctx.push()

    try:
        from app.extensions import db
        from app.models import WoundAssessment

        assessment = WoundAssessment.query.get(assessment_id)
        if not assessment:
            logger.error(f"[WoundAI] Assessment {assessment_id} nicht gefunden.")
            return False

        if assessment.foto_ai_analysis:
            logger.info(f"[WoundAI] Assessment {assessment_id}: Analyse bereits vorhanden.")
            return True

        result = analyse_wound_photos(assessment, app=app)
        if result is None:
            return False

        assessment.foto_ai_analysis = json.dumps(result, ensure_ascii=False)
        db.session.commit()
        logger.info(f"[WoundAI] Assessment {assessment_id}: Analyse gespeichert.")
        return True

    except Exception as e:
        logger.error(f"[WoundAI] Fehler in run_analysis_and_save: {e}")
        return False
    finally:
        if ctx:
            ctx.pop()
