import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from jinja2 import Template
from pathlib import Path
import logging

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

EMAIL_TEMPLATES = {
    "verify_email": """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #2e7d32 0%, #4caf50 100%); 
                      color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
            .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
            .button { display: inline-block; padding: 12px 30px; background: #4caf50; 
                      color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
            .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌞 Gabriel Solar Energy</h1>
            </div>
            <div class="content">
                <h2>Bine ai venit, {{ first_name }}!</h2>
                <p>Mulțumim că te-ai înregistrat pe platforma noastră.</p>
                <p>Pentru a-ți activa contul, te rugăm să confirmi adresa de email:</p>
                <div style="text-align: center;">
                    <a href="{{ verify_link }}" class="button">Activează Contul</a>
                </div>
                <p><small>Acest link este valabil 24 de ore.</small></p>
            </div>
            <div class="footer">
                <p>© 2024 Gabriel Solar Energy. Toate drepturile rezervate.</p>
            </div>
        </div>
    </body>
    </html>
    """,

    "reset_password": """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #d32f2f 0%, #f44336 100%); 
                      color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
            .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
            .button { display: inline-block; padding: 12px 30px; background: #f44336; 
                      color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔒 Resetare Parolă</h1>
            </div>
            <div class="content">
                <h2>Salut, {{ first_name }}!</h2>
                <p>Am primit o solicitare de resetare a parolei pentru contul tău.</p>
                <div style="text-align: center;">
                    <a href="{{ reset_link }}" class="button">Resetează Parola</a>
                </div>
                <p><small>Acest link este valabil 15 minute.</small></p>
                <p><small>Dacă nu ai solicitat resetarea parolei, te rugăm să ignori acest email.</small></p>
            </div>
        </div>
    </body>
    </html>
    """,

    "contact_notification": """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #1976d2 0%, #2196f3 100%); 
                      color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
            .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
            .info-box { background: white; padding: 15px; margin: 10px 0; border-left: 4px solid #2196f3; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📧 Contact Nou</h1>
            </div>
            <div class="content">
                <h2>Lead Nou din Formular Contact</h2>
                <div class="info-box">
                    <p><strong>Nume:</strong> {{ full_name }}</p>
                    <p><strong>Email:</strong> {{ email }}</p>
                    <p><strong>Telefon:</strong> {{ phone }}</p>
                    <p><strong>Tip Proprietate:</strong> {{ property_type }}</p>
                    <p><strong>Interes:</strong> {{ interest }}</p>
                    <p><strong>Mesaj:</strong><br>{{ message }}</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
}


async def send_email(
        to_email: str,
        subject: str,
        template_name: str,
        context: dict,
        attachments: list = None
):
    try:
        template = Template(EMAIL_TEMPLATES[template_name])
        html_content = template.render(**context)

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        message["To"] = to_email

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        if attachments:
            for attachment in attachments:
                message.attach(attachment)

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            start_tls=True,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
        )

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False