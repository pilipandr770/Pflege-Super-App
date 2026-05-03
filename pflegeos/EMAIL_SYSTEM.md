# PflegeOS Email System Documentation

## Overview

The email system is designed to automatically send notifications to staff about critical events:
- **Patient Admission**: When a new patient is admitted
- **BtM Alert**: When a controlled substance (BtM) medication is administered
- **Missing Documentation**: When critical documentation is missing (scheduled alerts)

## Configuration

### Environment Variables

Configure the following environment variables in your `.env` file:

```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=noreply@pflegeos.local
SYSTEM_URL=http://localhost:5000
```

### SMTP Setup for Gmail

1. Enable 2-factor authentication on your Gmail account
2. Create an "App Password" at https://myaccount.google.com/apppasswords
3. Use the 16-character password as `MAIL_PASSWORD`

### SMTP Setup for Other Providers

**Office 365/Outlook:**
```
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USERNAME=your_email@company.com
MAIL_PASSWORD=your_password
```

**Custom SMTP Server:**
```
MAIL_SERVER=mail.yourdomain.com
MAIL_PORT=587 (or 25, 465)
MAIL_USERNAME=username
MAIL_PASSWORD=password
```

## Email Events

### 1. Patient Admission Email

**Triggered when:** A new patient is created in the system
**Recipients:** All active employees in the company
**Template:** `app/templates/emails/patient_admission.html`
**Contents:** 
- Patient name, admission date, care level
- Checklist of next steps (SIS assessment, medication plan, risk documentation)
- Link to patient profile

### 2. BtM Alert Email

**Triggered when:** A controlled substance medication is administered
**Recipients:** All active employees in the company
**Template:** `app/templates/emails/btm_alert.html`
**Contents:**
- List of pending BtM entries requiring documentation
- Compliance requirements and legal warnings
- Four-eyes principle reminder
- Link to BtM-Buch documentation

### 3. Missing Documentation Alert

**Triggered when:** Manually via admin endpoint or scheduler
**Recipients:** All active employees in the company
**Template:** `app/templates/emails/missing_documentation.html`
**Contents:**
- List of patients with missing critical documentation
- Types of missing documents (SIS assessment, wound documentation)
- Link to dashboard for action

## API Endpoints

### Manual Alert Trigger

```
POST /alerts/check-missing-docs
```

**Authentication:** Requires admin login  
**Response:** JSON indicating success or failure

**Example:**
```bash
curl -X POST http://localhost:5000/alerts/check-missing-docs \
  -H "Content-Type: application/json"
```

## Integration Points

### 1. Patient Creation (`app/routes/patients.py`)

When a new patient is created:
```python
# Email is automatically sent to all employees
# No additional code needed - handled by the new() route
```

### 2. BtM Administration (`app/routes/medications.py`)

When BtM medication is administered:
```python
# Email is automatically sent to all employees
# Triggered in the administer() route after BtM entry creation
```

### 3. Scheduled Alerts

For periodic missing documentation checks, set up a cron job or scheduled task:

```bash
# Example: Daily at 9 AM
0 9 * * * curl -X POST http://localhost:5000/alerts/check-missing-docs
```

Or use a Python scheduler (APScheduler):
```python
from apscheduler.schedulers.background import BackgroundScheduler
from app.utils.email import send_bulk_missing_documentation_alerts

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=send_bulk_missing_documentation_alerts,
    args=(company_id,),
    trigger="cron",
    hour=9,
    minute=0
)
scheduler.start()
```

## Email Templates

All templates inherit from `app/templates/emails/base.html` and follow this structure:

```jinja2
{% extends "emails/base.html" %}
{% block content %}
  <!-- Email-specific content here -->
{% endblock %}
```

### Customizing Templates

Templates are located in `app/templates/emails/`:
- `base.html` - Base template with PflegeOS styling
- `patient_admission.html` - Patient admission notification
- `btm_alert.html` - BtM compliance alert
- `missing_documentation.html` - Missing documentation alert

### Template Variables

Each template has access to specific variables:

**patient_admission.html:**
- `employee_name` - Recipient's name
- `patient_name` - Patient's full name
- `patient_id` - Patient ID
- `admission_date` - Admission date
- `pflegegrad` - Care level (1-5)
- `system_url` - Base URL for links

**btm_alert.html:**
- `employee_name` - Recipient's name
- `pending_entries` - List of pending BtM entries
- `system_url` - Base URL for links

**missing_documentation.html:**
- `employee_name` - Recipient's name
- `missing_docs` - List of patients with missing documents
- `system_url` - Base URL for links

## Email Service Module

The email service is in `app/utils/email.py` and provides these functions:

### `send_patient_admission_email()`
Send patient admission notification to a specific employee.

### `send_btm_alert_email()`
Send BtM compliance alert to a specific employee.

### `send_missing_documentation_alert()`
Send missing documentation alert to a specific employee.

### `send_bulk_missing_documentation_alerts()`
Send missing documentation alerts to all employees in a company.

## Error Handling

All email functions include error handling and logging:
- Failed emails are logged but don't interrupt the application flow
- Errors are written to the application logs with error details
- Employees with missing email addresses are skipped

## Testing

### Test Email Configuration

```python
from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)
app.config.update(
    MAIL_SERVER='localhost',
    MAIL_PORT=1025,  # MailHog default port
    MAIL_USE_TLS=False
)
mail = Mail(app)
```

### Using MailHog for Local Testing

```bash
# Install MailHog
go get github.com/mailhog/MailHog

# Run MailHog
MailHog

# Access inbox at http://localhost:8025
```

### Manual Test

```python
from flask import current_app
from app.utils.email import send_patient_admission_email

send_patient_admission_email(
    'test@example.com',
    'Test Employee',
    'Test Patient',
    'patient-id-123',
    '2026-05-01',
    '2'
)
```

## Best Practices

1. **Never include sensitive information** in email templates (passwords, PINs, etc.)
2. **Use HTTPS** for all SYSTEM_URL links in production
3. **Monitor email delivery** - Check logs regularly for failed sends
4. **Test thoroughly** - Verify all template variables render correctly
5. **Keep sender address professional** - Use a company domain if possible
6. **Archive emails** - Configure your mail server for compliance record-keeping
7. **Limit recipients** - Consider filtering email recipients by role/department in future versions

## Troubleshooting

### "Connection refused" error

Check that MAIL_SERVER and MAIL_PORT are correct and the server is accessible.

### "Authentication failed"

Verify MAIL_USERNAME and MAIL_PASSWORD are correct. For Gmail, ensure you're using an App Password, not your regular password.

### Emails not sent

1. Check that Flask-Mail is installed: `pip install Flask-Mail`
2. Verify MAIL_SERVER configuration
3. Check application logs for error messages
4. Ensure employees have email addresses in the system

### HTML rendering issues in client

The base template uses inline CSS for maximum compatibility with email clients. If styles don't render:
1. Check the email client settings
2. Some email clients strip external stylesheets
3. Inline CSS is the recommended approach for email

## Future Enhancements

- Email templates for wound documentation alerts
- Scheduled email digest summaries
- Per-employee email preference settings
- Email delivery status tracking
- Multilingual email templates
- Email template versioning for compliance
