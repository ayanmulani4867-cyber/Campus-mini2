import os
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class EmailService:
    """Transactional email service leveraging the Brevo (Sendinblue) REST API."""

    def __init__(self):
        self._api_key = None
        self._sender_email = None
        self._sender_name = None
        self._erp_login_url = None

    def _load_config(self):
        self._api_key = os.environ.get("BREVO_API_KEY")
        self._sender_email = os.environ.get("BREVO_SENDER_EMAIL", "no-reply@campus.edu")
        self._sender_name = os.environ.get("BREVO_SENDER_NAME", "Campus Connect ERP")
        self._erp_login_url = os.environ.get("ERP_LOGIN_URL", "http://localhost:5000/login.html")

    @property
    def is_configured(self) -> bool:
        self._load_config()
        return bool(self._api_key and self._api_key.strip() and not self._api_key.startswith("xkeysib-your-"))

    def send_welcome_email(
        self,
        user: Any,
        profile: Any = None,
        password_setup_link: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sends an HTML welcome email with secure password setup link to a new user.
        
        Args:
            user: User model instance
            profile: Student or Faculty profile instance
            password_setup_link: Secure URL generated via Firebase Admin SDK
        
        Returns:
            Dict containing success status, message ID, or error details.
        """
        self._load_config()

        recipient_email = user.email
        recipient_name = user.full_name
        role_label = getattr(user, "role_label", user.role.capitalize())

        # Build role-specific details
        details = []
        if user.role == "student" and profile:
            if getattr(profile, "prn", None):
                details.append(("Student PRN", profile.prn))
            if getattr(profile, "student_code", None) and profile.student_code != getattr(profile, "prn", None):
                details.append(("Student ID", profile.student_code))
            if getattr(profile, "department", None):
                details.append(("Department", profile.department.name))
            if getattr(profile, "year_label", None):
                details.append(("Academic Year", profile.year_label))
            if getattr(profile, "division", None):
                details.append(("Division", profile.division))
        elif user.role == "faculty" and profile:
            if getattr(profile, "faculty_code", None):
                details.append(("Faculty ID", profile.faculty_code))
            if getattr(profile, "designation", None):
                details.append(("Designation", profile.designation))
            if getattr(profile, "department", None):
                details.append(("Department", profile.department.name))

        subject = f"Welcome to Campus Connect — Set Up Your {role_label} Account"
        html_content = self._render_welcome_html(
            name=recipient_name,
            role_label=role_label,
            email=recipient_email,
            details=details,
            setup_link=password_setup_link,
            login_url=self._erp_login_url,
            sender_name=self._sender_name,
        )

        # In local/testing mode where BREVO_API_KEY is not configured:
        if not self.is_configured:
            logger.info(
                "[SIMULATED EMAIL] Brevo API Key not configured. Welcome email to %s simulated.\nSetup Link: %s",
                recipient_email,
                password_setup_link,
            )
            return {
                "success": True,
                "simulated": True,
                "recipient": recipient_email,
                "setup_link": password_setup_link,
                "message": "Email sending simulated (BREVO_API_KEY not configured).",
            }

        headers = {
            "api-key": self._api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "sender": {
                "name": self._sender_name,
                "email": self._sender_email,
            },
            "to": [
                {
                    "email": recipient_email,
                    "name": recipient_name,
                }
            ],
            "subject": subject,
            "htmlContent": html_content,
        }

        try:
            response = requests.post(
                BREVO_API_URL,
                headers=headers,
                json=payload,
                timeout=12
            )
            if response.status_code in (200, 201):
                res_data = response.json() if response.content else {}
                msg_id = res_data.get("messageId", "ok")
                logger.info("Brevo welcome email delivered to %s (messageId: %s)", recipient_email, msg_id)
                return {
                    "success": True,
                    "simulated": False,
                    "message_id": msg_id,
                    "recipient": recipient_email,
                    "setup_link": password_setup_link,
                }
            else:
                err_text = response.text
                logger.warning(
                    "Brevo API returned error %s for %s: %s",
                    response.status_code,
                    recipient_email,
                    err_text,
                )
                return {
                    "success": False,
                    "simulated": False,
                    "status_code": response.status_code,
                    "error": f"Brevo HTTP {response.status_code}: {err_text}",
                    "recipient": recipient_email,
                    "setup_link": password_setup_link,
                }
        except Exception as e:
            logger.error("Failed to deliver welcome email via Brevo to %s: %s", recipient_email, e)
            return {
                "success": False,
                "simulated": False,
                "error": str(e),
                "recipient": recipient_email,
                "setup_link": password_setup_link,
            }

    def _render_welcome_html(
        self,
        name: str,
        role_label: str,
        email: str,
        details: list,
        setup_link: Optional[str],
        login_url: str,
        sender_name: str,
    ) -> str:
        """Generates a responsive, branded HTML email template."""
        details_rows = ""
        for label, val in details:
            details_rows += f"""
            <tr>
              <td style="padding: 8px 12px; color: #64748b; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f1f5f9;">{label}</td>
              <td style="padding: 8px 12px; color: #0f172a; font-size: 14px; font-weight: 600; border-bottom: 1px solid #f1f5f9; text-align: right;">{val}</td>
            </tr>
            """

        action_button = ""
        if setup_link:
            action_button = f"""
            <div style="text-align: center; margin: 32px 0 24px 0;">
              <a href="{setup_link}" style="background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-size: 15px; font-weight: 600; display: inline-block; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);">
                Set Up Your Password &rarr;
              </a>
            </div>
            <p style="color: #64748b; font-size: 12px; line-height: 1.5; margin: 0 0 16px 0; text-align: center;">
              Button not working? Copy and paste this link into your browser:<br>
              <a href="{setup_link}" style="color: #4f46e5; word-break: break-all; font-size: 11px;">{setup_link}</a>
            </p>
            """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome to Campus Connect</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; padding: 40px 15px;">
    <tr>
      <td align="center">
        <table width="100%" max-width="580" style="max-width: 580px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06); border: 1px solid #e2e8f0;">
          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); padding: 32px 28px; text-align: center;">
              <div style="font-size: 36px; line-height: 1; margin-bottom: 8px;">🎓</div>
              <h1 style="color: #ffffff; font-size: 22px; font-weight: 700; margin: 0; letter-spacing: -0.5px;">Campus Connect ERP</h1>
              <p style="color: #c7d2fe; font-size: 13px; margin: 6px 0 0 0; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Account Activation</p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding: 32px 28px;">
              <h2 style="color: #0f172a; font-size: 18px; font-weight: 600; margin: 0 0 12px 0;">Hello, {name}!</h2>
              <p style="color: #475569; font-size: 14px; line-height: 1.6; margin: 0 0 24px 0;">
                Your <strong>{role_label}</strong> account has been created on the Campus Connect college portal.
                Please activate your account by setting your secure personal password.
              </p>

              <!-- Account Details Card -->
              <table width="100%" style="background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 24px; border-collapse: collapse;">
                <tr>
                  <td style="padding: 8px 12px; color: #64748b; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f1f5f9;">Registered Email</td>
                  <td style="padding: 8px 12px; color: #0f172a; font-size: 14px; font-weight: 600; border-bottom: 1px solid #f1f5f9; text-align: right;">{email}</td>
                </tr>
                {details_rows}
              </table>

              <!-- Action Button -->
              {action_button}

              <!-- Security Notice -->
              <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 4px; margin-top: 24px;">
                <p style="color: #92400e; font-size: 12px; line-height: 1.5; margin: 0;">
                  <strong>🔒 Security Notice:</strong> This password setup link is personalized and secure. It expires automatically. No administrator will ever request your password.
                </p>
              </div>

              <!-- Login Portal Link -->
              <p style="color: #64748b; font-size: 13px; line-height: 1.6; margin: 24px 0 0 0; text-align: center;">
                Once set, you can access your workspace anytime at:<br>
                <a href="{login_url}" style="color: #4f46e5; font-weight: 600; text-decoration: none;">{login_url}</a>
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; padding: 20px 28px; text-align: center; border-top: 1px solid #e2e8f0;">
              <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                &copy; 2026 {sender_name}. All rights reserved. Automated notification.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# Global singleton instance
email_service = EmailService()
