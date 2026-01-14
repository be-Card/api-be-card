import logging
import smtplib
import ssl
from email.message import EmailMessage
import html
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def _from_header() -> Optional[str]:
        if settings.smtp_from:
            return settings.smtp_from
        if settings.smtp_from_email and settings.smtp_from_name:
            return f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        if settings.smtp_from_email:
            return settings.smtp_from_email
        return None

    @staticmethod
    def _render_html_template(
        *,
        preheader: str,
        title: str,
        message_html: str,
        cta_text: str,
        cta_link: str,
        secondary_text: str,
        footer_note: str,
    ) -> str:
        preheader_esc = html.escape(preheader)
        title_esc = html.escape(title)
        cta_text_esc = html.escape(cta_text)
        cta_link_esc = html.escape(cta_link, quote=True)
        secondary_text_esc = html.escape(secondary_text)
        footer_note_esc = html.escape(footer_note)

        return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <meta name="color-scheme" content="dark" />
    <meta name="supported-color-schemes" content="dark" />
    <title>{title_esc}</title>
  </head>
  <body style="margin:0; padding:0; background-color:#0f0f0f;">
    <div style="display:none; max-height:0; overflow:hidden; opacity:0; color:transparent;">
      {preheader_esc}
    </div>
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#0f0f0f; padding:24px 0;">
      <tr>
        <td align="center" style="padding:0 16px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="width:600px; max-width:600px;">
            <tr>
              <td style="padding:0 0 14px 0;">
                <div style="font-family:Inter, Arial, Helvetica, sans-serif; font-size:20px; font-weight:800; letter-spacing:0.2px; color:#ffffff;">
                  BeCard
                </div>
                <div style="margin-top:6px; height:3px; width:84px; background:linear-gradient(90deg,#f8d02d,#f06f26); border-radius:99px;"></div>
              </td>
            </tr>
            <tr>
              <td style="background-color:#121212; border:1px solid #333333; border-radius:14px; padding:22px 20px;">
                <div style="font-family:Inter, Arial, Helvetica, sans-serif; font-size:18px; font-weight:800; color:#ffffff; margin:0;">
                  {title_esc}
                </div>
                <div style="margin-top:10px; font-family:Inter, Arial, Helvetica, sans-serif; font-size:14px; line-height:20px; color:#d9d9d9;">
                  {message_html}
                </div>
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:18px;">
                  <tr>
                    <td bgcolor="#f8d02d" style="border-radius:10px;">
                      <a href="{cta_link_esc}" style="display:inline-block; padding:12px 18px; font-family:Inter, Arial, Helvetica, sans-serif; font-size:14px; font-weight:800; color:#121212; text-decoration:none;">
                        {cta_text_esc}
                      </a>
                    </td>
                  </tr>
                </table>
                <div style="margin-top:14px; font-family:Inter, Arial, Helvetica, sans-serif; font-size:12px; line-height:18px; color:#a7a7a7;">
                  {secondary_text_esc}
                </div>
                <div style="margin-top:14px; font-family:Inter, Arial, Helvetica, sans-serif; font-size:12px; line-height:18px; color:#a7a7a7;">
                  Si el botón no funciona, copiá y pegá este link en tu navegador:<br />
                  <a href="{cta_link_esc}" style="color:#f8d02d; text-decoration:none; word-break:break-all;">{cta_link_esc}</a>
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:14px 4px 0 4px; font-family:Inter, Arial, Helvetica, sans-serif; font-size:12px; line-height:18px; color:#7a7a7a;">
                {footer_note_esc}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

    @staticmethod
    def send_email(
        *,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
    ) -> bool:
        if settings.email_backend == "disabled":
            return False
        if settings.email_backend != "smtp":
            return False
        from_header = EmailService._from_header()
        if not settings.smtp_host or not from_header:
            if settings.environment == "production":
                logger.error("SMTP mal configurado (host/from). Email no enviado a %s", to_email)
            return False

        msg = EmailMessage()
        msg["From"] = from_header
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(text_body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        try:
            if settings.smtp_use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=10) as server:
                    if settings.smtp_username and settings.smtp_password:
                        server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(msg)
                    return True

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                server.ehlo()
                if settings.smtp_use_tls:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                if settings.smtp_username and settings.smtp_password:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(msg)
                return True
        except Exception:
            logger.exception("No se pudo enviar email a %s", to_email)
            return False

    @staticmethod
    def send_password_reset_email(*, to_email: str, reset_link: str) -> bool:
        subject = "BeCard - Restablecer contraseña"
        text_body = (
            "Recibimos una solicitud para restablecer tu contraseña.\n\n"
            f"Abrí este link para continuar: {reset_link}\n\n"
            "Si vos no solicitaste este cambio, podés ignorar este email."
        )
        html_body = EmailService._render_html_template(
            preheader="Restablecé tu contraseña en BeCard.",
            title="Restablecer contraseña",
            message_html=(
                "<p style=\"margin:0 0 10px 0;\">Recibimos una solicitud para restablecer tu contraseña.</p>"
                "<p style=\"margin:0;\">Hacé clic en el botón para continuar.</p>"
            ),
            cta_text="Restablecer contraseña",
            cta_link=reset_link,
            secondary_text="Este link vence en 30 minutos.",
            footer_note="Si vos no solicitaste este cambio, podés ignorar este email.",
        )
        return EmailService.send_email(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body)

    @staticmethod
    def send_email_verification(*, to_email: str, verification_link: str) -> bool:
        subject = "BeCard - Confirmá tu cuenta"
        text_body = (
            "Tu cuenta fue creada correctamente.\n\n"
            f"Confirmá tu email para poder iniciar sesión: {verification_link}\n\n"
            "Si vos no creaste esta cuenta, podés ignorar este email."
        )
        html_body = EmailService._render_html_template(
            preheader="Confirmá tu cuenta para iniciar sesión en BeCard.",
            title="Confirmar cuenta",
            message_html=(
                "<p style=\"margin:0 0 10px 0;\">Tu cuenta fue creada correctamente.</p>"
                "<p style=\"margin:0;\">Confirmá tu email para poder iniciar sesión.</p>"
            ),
            cta_text="Confirmar mi cuenta",
            cta_link=verification_link,
            secondary_text="Este link vence en 24 horas.",
            footer_note="Si vos no creaste esta cuenta, podés ignorar este email.",
        )
        return EmailService.send_email(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
