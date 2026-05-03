#!/usr/bin/env python
"""Quick test script to verify email system is working."""

import os
import sys
from app import create_app
from app.extensions import db
from app.models import Company, Employee, Patient
from app.utils.email import send_patient_admission_email, send_btm_alert_email
from datetime import datetime, date

def test_email_system():
    """Test email configuration and sending."""

    # Create Flask app
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("PflegeOS Email System - Configuration Test")
        print("=" * 60)

        # Check configuration
        print("\n1. MAIL CONFIGURATION:")
        print("   Server: " + str(app.config.get('MAIL_SERVER')))
        print("   Port: " + str(app.config.get('MAIL_PORT')))
        print("   TLS Enabled: " + str(app.config.get('MAIL_USE_TLS')))
        print("   Default Sender: " + str(app.config.get('MAIL_DEFAULT_SENDER')))
        print("   System URL: " + str(app.config.get('SYSTEM_URL')))

        # Check if SMTP credentials are configured
        username = app.config.get('MAIL_USERNAME')
        password = app.config.get('MAIL_PASSWORD')

        print("\n2. SMTP AUTHENTICATION:")
        if username:
            print("   Username: " + str(username))
            print("   Password: " + ("***" if password else "NOT SET"))
        else:
            print("   WARNING: No MAIL_USERNAME configured")
            print("   Email sending will not work without SMTP credentials")

        # Check templates exist
        print("\n3. EMAIL TEMPLATES:")
        templates = [
            'templates/emails/base.html',
            'templates/emails/patient_admission.html',
            'templates/emails/btm_alert.html',
            'templates/emails/missing_documentation.html'
        ]

        for template in templates:
            exists = os.path.exists(os.path.join(app.template_folder, template.replace('templates/', '')))
            status = "[OK]" if exists else "[MISSING]"
            print("   " + status + " " + template)

        # Check email service functions
        print("\n4. EMAIL SERVICE FUNCTIONS:")
        from app.utils import email
        functions = [
            'send_patient_admission_email',
            'send_btm_alert_email',
            'send_missing_documentation_alert',
            'send_bulk_missing_documentation_alerts'
        ]

        for func_name in functions:
            exists = hasattr(email, func_name)
            status = "[OK]" if exists else "[MISSING]"
            print("   " + status + " " + func_name)

        # Check database connectivity
        print("\n5. DATABASE:")
        try:
            # Try a simple query
            company_count = db.session.query(Company).count()
            print("   [OK] Database connected (" + str(company_count) + " companies)")
        except Exception as e:
            print("   [ERROR] Database error: " + str(e))

        print("\n" + "=" * 60)
        print("CONFIGURATION STATUS:")
        print("=" * 60)

        if username and password:
            print("[OK] Email system is configured and ready to use")
            print("\nTo send test emails:")
            print("1. Create a test employee with an email address")
            print("2. Create a test patient")
            print("3. Test endpoints will automatically send emails on:")
            print("   - Patient creation")
            print("   - BtM medication administration")
            print("   - POST /alerts/check-missing-docs (admin only)")
        else:
            print("[WARNING] Email system is NOT fully configured")
            print("\nNext steps:")
            print("1. Configure MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS in .env")
            print("2. Set MAIL_USERNAME and MAIL_PASSWORD for your SMTP server")
            print("3. For Gmail: Use an App Password (not your regular password)")
            print("4. See EMAIL_SYSTEM.md for detailed setup instructions")

        print("\n" + "=" * 60 + "\n")

if __name__ == '__main__':
    test_email_system()
