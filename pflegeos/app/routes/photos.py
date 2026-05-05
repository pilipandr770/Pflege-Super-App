"""
Photo capture and management for patient documentation.
Supports GPS geolocation and multiple photo types (general, wound, pressure ulcer, etc).
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, send_from_directory, send_file
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Patient, PatientPhoto, Employee
from app.utils.auth import patient_access_required, log_action, allowed_file, save_upload
from datetime import datetime
import os
from PIL import Image
from PIL.ExifTags import TAGS
import json

photos_bp = Blueprint('photos', __name__, url_prefix='/photos')


def extract_exif_data(image_path):
    """Extract EXIF metadata from image file."""
    try:
        image = Image.open(image_path)
        exif_data = image.getexif()

        metadata = {
            'device_model': None,
            'datetime': None,
            'geo_lat': None,
            'geo_lng': None
        }

        # Extract GPS coordinates if available
        gps_ifd = exif_data.get_ifd(0x8825) if exif_data else None
        if gps_ifd:
            try:
                # GPS Latitude
                lat = gps_ifd.get(2)  # GPSLatitude tag
                lat_ref = gps_ifd.get(1)  # GPSLatitudeRef
                if lat:
                    lat_decimal = lat[0] + lat[1] / 60 + lat[2] / 3600
                    if lat_ref == 'S':
                        lat_decimal = -lat_decimal
                    metadata['geo_lat'] = round(lat_decimal, 6)

                # GPS Longitude
                lng = gps_ifd.get(4)  # GPSLongitude tag
                lng_ref = gps_ifd.get(3)  # GPSLongitudeRef
                if lng:
                    lng_decimal = lng[0] + lng[1] / 60 + lng[2] / 3600
                    if lng_ref == 'W':
                        lng_decimal = -lng_decimal
                    metadata['geo_lng'] = round(lng_decimal, 6)
            except (IndexError, TypeError, ZeroDivisionError):
                pass

        # Extract other metadata
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)

            if tag_name == 'Model':  # Camera model
                metadata['device_model'] = str(value)[:255]
            elif tag_name == 'DateTime':  # Photo timestamp
                metadata['datetime'] = str(value)

        return metadata
    except Exception as e:
        # Silently fail if EXIF extraction doesn't work
        return {}



@photos_bp.route('/patient/<patient_id>')
@login_required
@patient_access_required()
def list_photos(patient_id):
    """List all photos for a patient."""
    patient = Patient.query.filter_by(
        id=patient_id,
        company_id=current_user.company_id,
        deleted_at=None
    ).first_or_404()

    photos = PatientPhoto.query.filter_by(
        patient_id=patient_id,
        company_id=current_user.company_id,
        is_active=True
    ).order_by(PatientPhoto.created_at.desc()).all()

    return render_template('photos/list.html', patient=patient, photos=photos)


@photos_bp.route('/patient/<patient_id>/capture', methods=['GET', 'POST'])
@login_required
@patient_access_required()
def capture(patient_id):
    """Capture and upload photo with GPS metadata."""
    patient = Patient.query.filter_by(
        id=patient_id,
        company_id=current_user.company_id,
        deleted_at=None
    ).first_or_404()

    if request.method == 'POST':
        try:
            # Get photo file
            if 'photo' not in request.files:
                return jsonify({'error': 'No photo provided'}), 400

            file = request.files['photo']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            if not allowed_file(file.filename):
                return jsonify({'error': 'File type not allowed'}), 400

            # Save file
            file_path = save_upload(file, subfolder=f'photos/{current_user.company_id}')
            if not file_path:
                return jsonify({'error': 'Failed to save file'}), 400

            # Get full path for EXIF extraction and file size
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)

            # Extract EXIF metadata from image
            exif_metadata = extract_exif_data(full_path)

            # Get GPS data from request (will override EXIF if provided)
            geo_lat = request.form.get('geo_lat', type=float) or exif_metadata.get('geo_lat')
            geo_lng = request.form.get('geo_lng', type=float) or exif_metadata.get('geo_lng')
            geo_accuracy = request.form.get('geo_accuracy', type=float)
            device_model = request.form.get('device_model', '') or exif_metadata.get('device_model', '')
            device_mac = request.form.get('device_mac', '')
            photo_type = request.form.get('photo_type', 'GENERAL')
            description = request.form.get('description', '')
            tags = request.form.get('tags', '')

            # Validate photo_type
            valid_types = ['GENERAL', 'WOUND', 'PRESSURE_ULCER', 'INSPECTION']
            if photo_type not in valid_types:
                photo_type = 'GENERAL'

            # Get file size from saved file
            file_size = os.path.getsize(full_path) if os.path.exists(full_path) else 0

            # Create photo record
            photo = PatientPhoto(
                company_id=current_user.company_id,
                patient_id=patient_id,
                employee_id=current_user.id,
                file_path=file_path,
                file_size=file_size,
                mime_type=file.content_type or 'image/jpeg',
                geo_lat=geo_lat,
                geo_lng=geo_lng,
                geo_accuracy=geo_accuracy,
                device_model=device_model,
                device_mac=device_mac,
                photo_type=photo_type,
                description=description,
                tags=tags
            )

            db.session.add(photo)
            db.session.commit()

            log_action('PHOTO_CAPTURED', 'PatientPhoto', photo.id, new_values={
                'patient': patient.full_name,
                'type': photo_type,
                'location': f"{geo_lat},{geo_lng}" if geo_lat and geo_lng else "No GPS"
            })

            return jsonify({
                'success': True,
                'photo_id': photo.id,
                'message': f'Photo captured successfully'
            }), 201

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return render_template('photos/capture.html', patient=patient)


@photos_bp.route('/<photo_id>')
@login_required
def view_photo(photo_id):
    """View single photo with metadata."""
    photo = PatientPhoto.query.filter_by(
        id=photo_id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    # Check access to patient
    patient = photo.patient
    if not current_user.is_admin:
        from app.models import EmployeePatientAssignment
        assignment = EmployeePatientAssignment.query.filter_by(
            employee_id=current_user.id,
            patient_id=patient.id,
            is_active=True
        ).first_or_404()

    return render_template('photos/view.html', photo=photo, patient=patient)


@photos_bp.route('/<photo_id>/view-file')
@login_required
def view_photo_file(photo_id):
    """Serve photo file for inline viewing."""
    photo = PatientPhoto.query.filter_by(
        id=photo_id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    # Check access to patient
    patient = photo.patient
    if not current_user.is_admin:
        from app.models import EmployeePatientAssignment
        assignment = EmployeePatientAssignment.query.filter_by(
            employee_id=current_user.id,
            patient_id=patient.id,
            is_active=True
        ).first_or_404()

    # Send file for inline viewing with proper headers
    full_path = os.path.abspath(os.path.join(current_app.config['UPLOAD_FOLDER'], photo.file_path))
    if not os.path.isfile(full_path):
        from flask import abort
        abort(404)

    response = send_file(full_path, mimetype=photo.mime_type or 'image/jpeg')
    response.headers['Cache-Control'] = 'public, max-age=86400'
    response.headers['X-Content-Type-Options'] = 'nosniff'

    return response


@photos_bp.route('/<photo_id>/download')
@login_required
def download_photo(photo_id):
    """Download photo file."""
    photo = PatientPhoto.query.filter_by(
        id=photo_id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    # Check access to patient
    patient = photo.patient
    if not current_user.is_admin:
        from app.models import EmployeePatientAssignment
        assignment = EmployeePatientAssignment.query.filter_by(
            employee_id=current_user.id,
            patient_id=patient.id,
            is_active=True
        ).first_or_404()

    log_action('PHOTO_DOWNLOADED', 'PatientPhoto', photo_id)

    # Send file
    full_path = os.path.abspath(os.path.join(current_app.config['UPLOAD_FOLDER'], photo.file_path))
    if not os.path.isfile(full_path):
        from flask import abort
        abort(404)
    return send_file(full_path, as_attachment=True, download_name=os.path.basename(photo.file_path))


@photos_bp.route('/<photo_id>/delete', methods=['POST'])
@login_required
def delete_photo(photo_id):
    """Soft delete photo (mark as inactive)."""
    photo = PatientPhoto.query.filter_by(
        id=photo_id,
        company_id=current_user.company_id
    ).first_or_404()

    patient = photo.patient

    # Only uploader or admin can delete
    if not current_user.is_admin and photo.employee_id != current_user.id:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('photos.list_photos', patient_id=patient.id))

    photo.is_active = False
    db.session.commit()

    log_action('PHOTO_DELETED', 'PatientPhoto', photo_id, old_values={'patient': patient.full_name})
    flash('Photo deleted', 'success')

    return redirect(url_for('photos.list_photos', patient_id=patient.id))


@photos_bp.route('/visit/<schedule_id>/upload', methods=['POST'])
@login_required
def visit_photo_upload(schedule_id):
    """
    Foto-Upload durch Pflegekraft während eines Besuchs.
    Zugriff wird über den EmployeeSchedule geprüft (nicht über Patientenzuweisung).
    Unterstützt mehrere Fotos, GPS-Daten und Fototyp.
    """
    from app.models import EmployeeSchedule

    # Zugriff: Nur die zuständige Pflegekraft darf hochladen
    schedule = EmployeeSchedule.query.filter_by(
        id=schedule_id,
        employee_id=current_user.id,
        company_id=current_user.company_id,
        is_active=True
    ).first_or_404()

    if 'photo' not in request.files:
        return jsonify({'error': 'Kein Foto übermittelt'}), 400

    file = request.files['photo']
    if not file or file.filename == '':
        return jsonify({'error': 'Keine Datei ausgewählt'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Dateityp nicht erlaubt (JPG, PNG, WEBP)'}), 400

    try:
        # Datei speichern
        file_path = save_upload(file, subfolder=f'photos/{current_user.company_id}/visits')
        if not file_path:
            return jsonify({'error': 'Fehler beim Speichern der Datei'}), 500

        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)

        # EXIF-Metadaten extrahieren (GPS aus Kamera-App)
        exif_meta = extract_exif_data(full_path)

        # GPS: zuerst aus Formular (Browser-GPS), dann aus EXIF
        geo_lat  = request.form.get('geo_lat',  type=float) or exif_meta.get('geo_lat')
        geo_lng  = request.form.get('geo_lng',  type=float) or exif_meta.get('geo_lng')
        geo_acc  = request.form.get('geo_accuracy', type=float)

        photo_type  = request.form.get('photo_type', 'VISIT')
        description = request.form.get('description', '').strip()
        device_mac  = request.form.get('device_mac', '').strip()
        nfc_tag_id  = request.form.get('nfc_tag_id', '').strip() or None

        # Gültigen Fototyp sicherstellen
        valid_types = ['VISIT', 'GENERAL', 'WOUND', 'PRESSURE_ULCER', 'INSPECTION', 'BEFORE', 'AFTER']
        if photo_type not in valid_types:
            photo_type = 'VISIT'

        file_size = os.path.getsize(full_path) if os.path.exists(full_path) else 0

        # Tags: visit-ID + optionaler NFC-Tag
        tags_list = [f'visit:{schedule_id}']
        if nfc_tag_id:
            tags_list.append(f'nfc:{nfc_tag_id}')
        tags_str = ','.join(tags_list)

        photo = PatientPhoto(
            company_id=current_user.company_id,
            patient_id=schedule.patient_id,
            employee_id=current_user.id,
            file_path=file_path,
            file_size=file_size,
            mime_type=file.content_type or 'image/jpeg',
            geo_lat=geo_lat,
            geo_lng=geo_lng,
            geo_accuracy=geo_acc,
            device_model=exif_meta.get('device_model', ''),
            device_mac=device_mac,
            photo_type=photo_type,
            description=description or f'Besuchsfoto — {schedule.scheduled_date}',
            tags=tags_str,
        )

        db.session.add(photo)
        db.session.commit()

        log_action('VISIT_PHOTO_UPLOADED', 'PatientPhoto', photo.id, new_values={
            'schedule_id': schedule_id,
            'patient': schedule.patient.full_name,
            'type': photo_type,
            'gps': f'{geo_lat},{geo_lng}' if geo_lat else 'kein GPS',
        })

        return jsonify({
            'success':     True,
            'photo_id':    photo.id,
            'preview_url': url_for('photos.view_photo_file', photo_id=photo.id),
            'type':        photo_type,
            'has_gps':     bool(geo_lat and geo_lng),
            'geo_lat':     geo_lat,
            'geo_lng':     geo_lng,
        }), 201

    except Exception as e:
        current_app.logger.error(f'visit_photo_upload error: {e}')
        return jsonify({'error': str(e)}), 500


@photos_bp.route('/leistung-upload', methods=['POST'])
@login_required
def leistung_photo_upload():
    """
    Foto-Upload beim Ausfüllen eines Leistungsnachweises.
    Zugriff: jeder authentifizierte Mitarbeiter der gleichen Company.
    Der patient_id wird aus dem Formular gelesen und auf Company geprüft.
    """
    patient_id = request.form.get('patient_id', '').strip()
    if not patient_id:
        return jsonify({'error': 'patient_id fehlt'}), 400

    # Sicherstellen, dass Patient zur Company gehört
    from app.models import Patient
    patient = Patient.query.filter_by(
        id=patient_id,
        company_id=current_user.company_id,
        deleted_at=None
    ).first()
    if not patient:
        return jsonify({'error': 'Patient nicht gefunden'}), 404

    if 'photo' not in request.files:
        return jsonify({'error': 'Kein Foto übermittelt'}), 400

    file = request.files['photo']
    if not file or file.filename == '':
        return jsonify({'error': 'Keine Datei ausgewählt'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Dateityp nicht erlaubt (JPG, PNG, WEBP)'}), 400

    try:
        file_path = save_upload(file, subfolder=f'photos/{current_user.company_id}/leistung')
        if not file_path:
            return jsonify({'error': 'Fehler beim Speichern'}), 500

        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)
        exif_meta = extract_exif_data(full_path)

        geo_lat  = request.form.get('geo_lat',  type=float) or exif_meta.get('geo_lat')
        geo_lng  = request.form.get('geo_lng',  type=float) or exif_meta.get('geo_lng')
        geo_acc  = request.form.get('geo_accuracy', type=float)
        nfc_tag  = request.form.get('nfc_tag_id', '').strip() or None
        photo_type = request.form.get('photo_type', 'GENERAL')
        valid_types = ['GENERAL', 'WOUND', 'PRESSURE_ULCER', 'INSPECTION', 'BEFORE', 'AFTER']
        if photo_type not in valid_types:
            photo_type = 'GENERAL'

        file_size = os.path.getsize(full_path) if os.path.exists(full_path) else 0

        tags_list = ['leistung:pending']
        if nfc_tag:
            tags_list.append(f'nfc:{nfc_tag}')

        photo = PatientPhoto(
            company_id=current_user.company_id,
            patient_id=patient_id,
            employee_id=current_user.id,
            file_path=file_path,
            file_size=file_size,
            mime_type=file.content_type or 'image/jpeg',
            geo_lat=geo_lat,
            geo_lng=geo_lng,
            geo_accuracy=geo_acc,
            device_model=exif_meta.get('device_model', ''),
            device_mac=request.form.get('device_mac', '').strip(),
            photo_type=photo_type,
            description=request.form.get('description', '').strip() or f'Leistungsnachweis-Foto',
            tags=','.join(tags_list),
        )
        db.session.add(photo)
        db.session.commit()

        log_action('LEISTUNG_PHOTO_UPLOADED', 'PatientPhoto', photo.id, new_values={
            'patient': patient.full_name,
            'gps': f'{geo_lat},{geo_lng}' if geo_lat else 'kein GPS',
        })

        return jsonify({
            'success':     True,
            'photo_id':    photo.id,
            'preview_url': url_for('photos.view_photo_file', photo_id=photo.id),
            'has_gps':     bool(geo_lat and geo_lng),
        }), 201

    except Exception as e:
        current_app.logger.error(f'leistung_photo_upload error: {e}')
        return jsonify({'error': str(e)}), 500


@photos_bp.route('/api/patient/<patient_id>/photos')
@login_required
@patient_access_required()
def api_patient_photos(patient_id):
    """API: Get all photos for a patient (JSON)."""
    photos = PatientPhoto.query.filter_by(
        patient_id=patient_id,
        company_id=current_user.company_id,
        is_active=True
    ).order_by(PatientPhoto.created_at.desc()).all()

    return jsonify([{
        'id': p.id,
        'photo_type': p.photo_type,
        'description': p.description,
        'created_at': p.created_at.isoformat(),
        'employee': p.employee.full_name,
        'geo_lat': p.geo_lat,
        'geo_lng': p.geo_lng,
        'tags': p.tags,
        'photo_url': url_for('photos.view_photo_file', photo_id=p.id, _external=True),
        'thumbnail_url': url_for('photos.view_photo_file', photo_id=p.id, _external=True)
    } for p in photos])


@photos_bp.route('/api/geolocation', methods=['POST'])
@login_required
def api_store_geolocation():
    """API: Store current geolocation (from Capacitor)."""
    try:
        data = request.get_json()
        geo_lat = data.get('latitude')
        geo_lng = data.get('longitude')
        geo_accuracy = data.get('accuracy')

        if not (geo_lat and geo_lng):
            return jsonify({'error': 'Missing coordinates'}), 400

        # Store in session for later use
        from flask import session
        session['last_geolocation'] = {
            'latitude': geo_lat,
            'longitude': geo_lng,
            'accuracy': geo_accuracy,
            'timestamp': datetime.utcnow().isoformat()
        }

        return jsonify({
            'success': True,
            'message': 'Geolocation stored'
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
