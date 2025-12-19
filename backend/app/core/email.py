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
    <div style="background-color: #f4f7f6; padding: 30px; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.08);">
            <tr>
                <td align="center" style="padding: 40px 20px; background: linear-gradient(135deg, #2e7d32 0%, #4caf50 100%);">
                    <h1 style="color: #ffffff; margin: 0; font-size: 28px; letter-spacing: 1px;">GABRIEL SOLAR</h1>
                    <p style="color: #e8f5e9; margin: 5px 0 0 0; font-size: 14px; text-transform: uppercase;">Energie curată pentru viitor</p>
                </td>
            </tr>
            <tr>
                <td style="padding: 40px 30px;">
                    <h2 style="color: #2c3e50; margin-top: 0;">Salut, {{ first_name }}! 👋</h2>
                    <p style="color: #546e7a; line-height: 1.6; font-size: 16px;">
                        Ne bucurăm să te avem alături! Pentru a activa contul tău pe platforma <strong>Gabriel Solar Energy</strong> și a începe monitorizarea sistemului tău, te rugăm să confirmi adresa de email apăsând butonul de mai jos.
                    </p>
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin: 30px 0;">
                        <tr>
                            <td align="center">
                                <a href="{{ verify_link }}" style="background-color: #4caf50; color: #ffffff; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block; box-shadow: 0 4px 6px rgba(76,175,80,0.2);">
                                    ACTIVEAZĂ CONTUL ACUM
                                </a>
                            </td>
                        </tr>
                    </table>
                    <p style="color: #90a4ae; font-size: 13px; text-align: center;">
                        Link-ul este valabil 24 de ore. Dacă nu ai creat acest cont, poți ignora acest mesaj.
                    </p>
                </td>
            </tr>
            <tr>
                <td style="padding: 20px; background-color: #fcfdfd; border-top: 1px solid #edf2f4; text-align: center;">
                    <p style="color: #b0bec5; font-size: 12px; margin: 0;">
                        © 2025 Gabriel Solar Energy | România <br>
                        Sustenabilitate prin Tehnologie
                    </p>
                </td>
            </tr>
        </table>
    </div>
    """,

    "reset_password": """
    <div style="background-color: #fefefe; padding: 30px; font-family: 'Segoe UI', sans-serif;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; border: 1px solid #eee; border-radius: 16px;">
            <tr>
                <td style="padding: 40px 30px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <span style="font-size: 50px;">🔒</span>
                    </div>
                    <h2 style="color: #2c3e50; text-align: center;">Resetare Parolă</h2>
                    <p style="color: #546e7a; font-size: 16px; line-height: 1.6;">
                        Salut, <strong>{{ first_name }}</strong>. Am primit o solicitare de resetare a parolei pentru contul tău. Dacă tu ai făcut această cerere, apasă butonul de mai jos:
                    </p>
                    <div style="text-align: center; margin: 35px 0;">
                        <a href="{{ reset_link }}" style="background-color: #d32f2f; color: #ffffff; padding: 15px 35px; border-radius: 50px; text-decoration: none; font-weight: bold; display: inline-block;">
                            RESETEAZĂ PAROLA
                        </a>
                    </div>
                    <p style="color: #f44336; font-size: 12px; background-color: #fff5f5; padding: 10px; border-radius: 5px; text-align: center;">
                        Link-ul expiră în 15 minute din motive de securitate.
                    </p>
                </td>
            </tr>
        </table>
    </div>
    """,

    "contact_notification": """
    <div style="background-color: #eceff1; padding: 30px; font-family: 'Segoe UI', sans-serif;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
            <tr>
                <td style="padding: 30px; background-color: #1976d2; border-radius: 8px 8px 0 0;">
                    <h2 style="color: #ffffff; margin: 0;">🚀 Lead Nou de pe Site</h2>
                </td>
            </tr>
            <tr>
                <td style="padding: 30px;">
                    <table width="100%" style="border-collapse: collapse;">
                        <tr>
                            <td style="padding: 12px 0; border-bottom: 1px solid #f0f4f8; color: #78909c; font-size: 14px;">CLIENT</td>
                            <td style="padding: 12px 0; border-bottom: 1px solid #f0f4f8; color: #263238; font-weight: bold; text-align: right;">{{ full_name }}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0; border-bottom: 1px solid #f0f4f8; color: #78909c; font-size: 14px;">EMAIL</td>
                            <td style="padding: 12px 0; border-bottom: 1px solid #f0f4f8; color: #1976d2; font-weight: bold; text-align: right;">{{ email }}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0; border-bottom: 1px solid #f0f4f8; color: #78909c; font-size: 14px;">TELEFON</td>
                            <td style="padding: 12px 0; border-bottom: 1px solid #f0f4f8; color: #263238; font-weight: bold; text-align: right;">{{ phone }}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px 0; border-bottom: 1px solid #f0f4f8; color: #78909c; font-size: 14px;">INTERES</td>
                            <td style="padding: 12px 0; border-bottom: 1px solid #f0f4f8; color: #388e3c; font-weight: bold; text-align: right;">{{ interest }}</td>
                        </tr>
                    </table>
                    <div style="margin-top: 25px; padding: 20px; background-color: #f8f9fa; border-radius: 8px; border-left: 4px solid #1976d2;">
                        <strong style="color: #455a64; display: block; margin-bottom: 8px;">MESAJ CLIENT:</strong>
                        <p style="color: #546e7a; font-style: italic; margin: 0; line-height: 1.5;">"{{ message }}"</p>
                    </div>
                </td>
            </tr>
        </table>
    </div>
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