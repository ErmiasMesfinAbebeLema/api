"""
Email Service - SMTP Email Sending with Template Support and Logging

This service handles all email operations including:
- SMTP email sending
- Template rendering (Jinja2)
- Email logging to database
- Retry handling for failed emails
"""

import smtplib
import logging
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models import EmailLog, User

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails with template support and logging"""
    
    # Email Types
    TYPE_WELCOME = "welcome"
    TYPE_PASSWORD_RESET = "password_reset"
    TYPE_EMAIL_VERIFICATION = "email_verification"
    TYPE_ENROLLMENT_CONFIRMATION = "enrollment_confirmation"
    TYPE_PAYMENT_RECEIPT = "payment_receipt"
    TYPE_INVOICE_SENT = "invoice_sent"
    TYPE_PAYMENT_REMINDER = "payment_reminder"
    TYPE_CERTIFICATE_ISSUED = "certificate_issued"
    TYPE_COURSE_COMPLETED = "course_completed"
    TYPE_ATTENDANCE_ALERT = "attendance_alert"
    TYPE_ANNOUNCEMENT = "announcement"
    
    def __init__(self):
        self.config = settings
        
        # Setup Jinja2 template environment
        template_path = Path(__file__).parent.parent / "templates" / "emails"
        if template_path.exists():
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            self.template_env = Environment(
                loader=FileSystemLoader(str(template_path)),
                autoescape=select_autoescape(["html", "xml"])
            )
        else:
            self.template_env = None
            logger.warning(f"Email templates directory not found: {template_path}")
    
    def _get_first_name(self, user: User) -> str:
        """Extract first name from user object - tries first_name then full_name"""
        first_name = getattr(user, 'first_name', None)
        if first_name:
            return first_name
        full_name = getattr(user, 'full_name', None)
        if full_name:
            return full_name.split()[0] if full_name.split() else 'Student'
        return 'Student'
    
    def _get_smtp_connection(self) -> smtplib.SMTP:
        """Create SMTP connection with TLS"""
        if self.config.email_use_ssl:
            server = smtplib.SMTP_SSL(self.config.email_host, self.config.email_port)
        else:
            server = smtplib.SMTP(self.config.email_host, self.config.email_port)
            if self.config.email_use_tls:
                server.starttls()
        
        if self.config.email_username and self.config.email_password:
            server.login(self.config.email_username, self.config.email_password)
        
        return server
    
    def _render_template(self, template_name: str, context: Dict[str, Any]) -> tuple:
        """Render email template and return (text, html) versions"""
        text_content = None
        html_content = None
        
        if not self.template_env:
            return None, None
        
        try:
            # Try to load HTML template
            html_template = self.template_env.get_template(f"{template_name}.html")
            html_content = html_template.render(**context)
        except Exception as e:
            logger.warning(f"Could not load HTML template {template_name}: {e}")
        
        try:
            # Try to load text template
            text_template = self.template_env.get_template(f"{template_name}.txt")
            text_content = text_template.render(**context)
        except Exception as e:
            logger.warning(f"Could not load text template {template_name}: {e}")
        
        # If no text content but HTML exists, strip HTML
        if not text_content and html_content:
            text_content = self._strip_html(html_content)
        
        return text_content, html_content
    
    def _strip_html(self, html: str) -> str:
        """Convert HTML to plain text"""
        text = re.sub(r'<br\s*/?>', '\n', html)
        text = re.sub(r'<p\s*/?>', '\n\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&', '&', text)
        text = re.sub(r'<', '<', text)
        text = re.sub(r'>', '>', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()
    
    def _create_email_log(
        self,
        db: AsyncSession,
        recipient_email: str,
        subject: str,
        email_type: str,
        template_name: Optional[str] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        context_data: Optional[Dict] = None,
        related_user_id: Optional[int] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[int] = None,
    ) -> EmailLog:
        """Create email log entry"""
        email_log = EmailLog(
            recipient_email=recipient_email,
            subject=subject,
            email_type=email_type,
            template_name=template_name,
            body_text=body_text,
            body_html=body_html,
            context_data=context_data,
            related_user_id=related_user_id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            status="pending",
            created_at=datetime.utcnow()
        )
        db.add(email_log)
        return email_log
    
    def _update_email_log(
        self,
        db: AsyncSession,
        email_log: EmailLog,
        status: str,
        error_message: Optional[str] = None
    ):
        """Update email log status"""
        email_log.status = status
        if error_message:
            email_log.error_message = error_message
        if status == "sent":
            email_log.sent_at = datetime.utcnow()
        elif status == "failed":
            email_log.retry_count = (email_log.retry_count or 0) + 1
            email_log.last_retry_at = datetime.utcnow()
    
    def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        text_content: Optional[str],
        html_content: Optional[str],
        attachments: Optional[List[tuple]] = None,
    ) -> tuple:
        """Send email via SMTP with optional attachments
        
        Args:
            to_email: Recipient email
            subject: Email subject
            text_content: Plain text body
            html_content: HTML body
            attachments: List of (filename, content, mime_type) tuples
        """
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{self.config.email_from_name} <{self.config.email_from_address}>"
        msg["To"] = to_email
        msg["Reply-To"] = self.config.email_reply_to
        
        # Create alternative part for text/html
        msg_alt = MIMEMultipart("alternative")
        
        if text_content:
            msg_alt.attach(MIMEText(text_content, "plain", "utf-8"))
        
        if html_content:
            msg_alt.attach(MIMEText(html_content, "html", "utf-8"))
        
        # Attach the alternative part
        msg.attach(msg_alt)
        
        # Add file attachments if any
        if attachments:
            for filename, content, mime_type in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(content)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                msg.attach(part)
        
        try:
            with self._get_smtp_connection() as server:
                server.send_message(msg)
            return True, None
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False, str(e)
    
    async def send_email(
        self,
        db: AsyncSession,
        to_email: str,
        subject: str,
        email_type: str,
        template_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        text_body: Optional[str] = None,
        html_body: Optional[str] = None,
        related_user_id: Optional[int] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[int] = None,
        attachments: Optional[List[tuple]] = None,
    ) -> EmailLog:
        """
        Send email with template or custom body.
        
        Args:
            db: Database session
            to_email: Recipient email address
            subject: Email subject line
            email_type: Type of email (see TYPE_* constants)
            template_name: Name of Jinja2 template (without extension)
            context: Variables to pass to template
            text_body: Plain text body (if not using template)
            html_body: HTML body (if not using template)
            related_user_id: ID of user this email relates to
            related_entity_type: Type of entity (e.g., 'payment', 'enrollment')
            related_entity_id: ID of related entity
            attachments: List of (filename, content, mime_type) tuples
            
        Returns:
            EmailLog: The created email log entry
        """
        context = context or {}
        
        # Add common context variables
        context["base_url"] = self.config.base_url
        context["year"] = datetime.now().year
        
        # Render template if provided
        if template_name:
            text_content, html_content = self._render_template(template_name, context)
            # Update subject if template has subject variable
            if "subject" in context:
                subject = context["subject"]
        else:
            text_content = text_body
            html_content = html_body
        
        # Create log entry
        email_log = self._create_email_log(
            db=db,
            recipient_email=to_email,
            subject=subject,
            email_type=email_type,
            template_name=template_name,
            body_text=text_content,
            body_html=html_content,
            context_data=context,
            related_user_id=related_user_id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        db.add(email_log)
        await db.flush()  # Get the ID without committing
        
        # Send email
        if self.config.email_debug:
            # In debug mode, just log and mark as sent
            logger.info(f"[EMAIL DEBUG] To: {to_email}, Subject: {subject}")
            self._update_email_log(db, email_log, "debug")
        elif not self.config.email_username or not self.config.email_password:
            # No SMTP configured, log and skip
            logger.warning(f"[EMAIL SKIP] No SMTP configured. To: {to_email}, Subject: {subject}")
            self._update_email_log(db, email_log, "skipped")
        else:
            # Actually send the email
            success, error = self._send_via_smtp(
                to_email=to_email,
                subject=subject,
                text_content=text_content,
                html_content=html_content,
                attachments=attachments,
            )
            
            if success:
                self._update_email_log(db, email_log, "sent")
                logger.info(f"[EMAIL SENT] To: {to_email}, Subject: {subject}")
            else:
                self._update_email_log(db, email_log, "failed", error)
                logger.error(f"[EMAIL FAILED] To: {to_email}, Error: {error}")
        
        await db.commit()
        await db.refresh(email_log)
        return email_log
    
    async def retry_failed_email(self, db: AsyncSession, email_log_id: int) -> EmailLog:
        """Retry sending a failed email"""
        result = await db.execute(select(EmailLog).where(EmailLog.id == email_log_id))
        email_log = result.scalar_one_or_none()
        
        if not email_log:
            raise ValueError(f"Email log {email_log_id} not found")
        
        if email_log.retry_count >= self.config.email_max_retries:
            email_log.status = "cancelled"
            email_log.error_message = "Max retries exceeded"
            await db.commit()
            await db.refresh(email_log)
            return email_log
        
        # Retry sending
        success, error = self._send_via_smtp(
            to_email=email_log.recipient_email,
            subject=email_log.subject,
            text_content=email_log.body_text,
            html_content=email_log.body_html,
        )
        
        email_log.retry_count = (email_log.retry_count or 0) + 1
        email_log.last_retry_at = datetime.utcnow()
        
        if success:
            email_log.status = "sent"
            email_log.sent_at = datetime.utcnow()
            email_log.error_message = None
        else:
            email_log.error_message = error
        
        await db.commit()
        await db.refresh(email_log)
        return email_log
    
    # ============== CONVENIENCE METHODS FOR COMMON EMAILS ==============
    
    async def send_welcome_email(
        self,
        db: AsyncSession,
        user: User,
        student_id: Optional[int] = None
    ) -> EmailLog:
        """Send welcome email to newly registered student"""
        first_name = self._get_first_name(user)
        
        return await self.send_email(
            db=db,
            to_email=user.email,
            subject="Welcome to YM Beauty Academy!",
            email_type=self.TYPE_WELCOME,
            template_name="welcome",
            context={
                "first_name": first_name,
                "email": user.email,
                "student_id": student_id,
            },
            related_user_id=user.id,
        )
    
    async def send_password_reset_email(
        self,
        db: AsyncSession,
        user: User,
        reset_token: str
    ) -> EmailLog:
        """Send password reset email"""
        first_name = self._get_first_name(user)
        reset_url = f"{self.config.base_url}/reset-password?token={reset_token}"
        
        return await self.send_email(
            db=db,
            to_email=user.email,
            subject="Password Reset Request - YM Beauty Academy",
            email_type=self.TYPE_PASSWORD_RESET,
            template_name="password_reset",
            context={
                "first_name": first_name,
                "reset_url": reset_url,
                "reset_token": reset_token,
            },
            related_user_id=user.id,
        )
    
    async def send_email_verification(
        self,
        db: AsyncSession,
        user: User,
        verification_token: str
    ) -> EmailLog:
        """Send email verification email"""
        first_name = self._get_first_name(user)
        verify_url = f"{self.config.base_url}/verify?token={verification_token}"
        
        return await self.send_email(
            db=db,
            to_email=user.email,
            subject="Verify Your Email - YM Beauty Academy",
            email_type=self.TYPE_EMAIL_VERIFICATION,
            template_name="email_verification",
            context={
                "first_name": first_name,
                "verify_url": verify_url,
                "verification_token": verification_token,
            },
            related_user_id=user.id,
        )
    
    async def send_enrollment_confirmation(
        self,
        db: AsyncSession,
        user: User,
        course_name: str,
        enrollment_id: int
    ) -> EmailLog:
        """Send enrollment confirmation email"""
        first_name = self._get_first_name(user)
        
        return await self.send_email(
            db=db,
            to_email=user.email,
            subject=f"Enrollment Confirmed - {course_name}",
            email_type=self.TYPE_ENROLLMENT_CONFIRMATION,
            template_name="enrollment_confirmation",
            context={
                "first_name": first_name,
                "course_name": course_name,
                "enrollment_id": enrollment_id,
            },
            related_user_id=user.id,
            related_entity_type="enrollment",
            related_entity_id=enrollment_id,
        )
    
    async def send_payment_receipt(
        self,
        db: AsyncSession,
        user: User,
        receipt_number: str,
        amount: str,
        payment_method: str,
        course_name: str,
        payment_id: int
    ) -> EmailLog:
        """Send payment receipt email"""
        first_name = self._get_first_name(user)
        
        return await self.send_email(
            db=db,
            to_email=user.email,
            subject=f"Payment Receipt - {course_name}",
            email_type=self.TYPE_PAYMENT_RECEIPT,
            template_name="payment_receipt",
            context={
                "first_name": first_name,
                "receipt_number": receipt_number,
                "payment_date": datetime.now().strftime("%B %d, %Y"),
                "amount": amount,
                "payment_method": payment_method,
                "course_name": course_name,
            },
            related_user_id=user.id,
            related_entity_type="payment",
            related_entity_id=payment_id,
        )
    
    async def send_payment_receipt_with_attachments(
        self,
        db: AsyncSession,
        user: User,
        receipt_number: str,
        amount: str,
        payment_method: str,
        course_name: str,
        payment_id: int,
        invoice_pdf_bytes: Optional[bytes] = None,
        receipt_pdf_bytes: Optional[bytes] = None,
        invoice_number: Optional[str] = None
    ) -> EmailLog:
        """
        Send payment receipt email with attached invoice and receipt PDFs.
        
        Args:
            db: Database session
            user: Recipient user
            receipt_number: Payment receipt number
            amount: Amount paid
            payment_method: Payment method used
            course_name: Course name
            payment_id: Payment ID
            invoice_pdf_bytes: Invoice PDF as bytes (optional)
            receipt_pdf_bytes: Receipt PDF as bytes (optional)
            invoice_number: Invoice number for naming attachment
        """
        first_name = self._get_first_name(user)
        
        # Build attachments list
        attachments = []
        
        if invoice_pdf_bytes and invoice_number:
            attachments.append((
                f"{invoice_number}.pdf",
                invoice_pdf_bytes,
                "application/pdf"
            ))
        
        if receipt_pdf_bytes and invoice_number:
            attachments.append((
                f"Receipt_{invoice_number}.pdf",
                receipt_pdf_bytes,
                "application/pdf"
            ))
        
        return await self.send_email(
            db=db,
            to_email=user.email,
            subject=f"Payment Receipt - {course_name}",
            email_type=self.TYPE_PAYMENT_RECEIPT,
            template_name="payment_receipt",
            context={
                "first_name": first_name,
                "receipt_number": receipt_number,
                "payment_date": datetime.now().strftime("%B %d, %Y"),
                "amount": amount,
                "payment_method": payment_method,
                "course_name": course_name,
            },
            related_user_id=user.id,
            related_entity_type="payment",
            related_entity_id=payment_id,
            attachments=attachments if attachments else None,
        )
    
    async def send_certificate_issued(
        self,
        db: AsyncSession,
        user: User,
        certificate_number: str,
        course_name: str,
        certificate_id: int
    ) -> EmailLog:
        """Send certificate issued notification email"""
        first_name = self._get_first_name(user)
        
        return await self.send_email(
            db=db,
            to_email=user.email,
            subject=f"Congratulations! Certificate Issued - {course_name}",
            email_type=self.TYPE_CERTIFICATE_ISSUED,
            template_name="certificate_issued",
            context={
                "first_name": first_name,
                "certificate_number": certificate_number,
                "course_name": course_name,
                "issue_date": datetime.now().strftime("%B %d, %Y"),
            },
            related_user_id=user.id,
            related_entity_type="certificate",
            related_entity_id=certificate_id,
        )
    
    async def send_certificate_issued_with_attachment(
        self,
        db: AsyncSession,
        user: User,
        certificate_number: str,
        course_name: str,
        certificate_id: int,
        certificate_pdf_bytes: Optional[bytes] = None
    ) -> EmailLog:
        """
        Send certificate issued notification email with PDF attachment.
        
        Args:
            db: Database session
            user: Recipient user
            certificate_number: Certificate number
            course_name: Course name
            certificate_id: Certificate ID
            certificate_pdf_bytes: Certificate PDF as bytes (optional)
        """
        first_name = self._get_first_name(user)
        
        # Build attachments list
        attachments = None
        if certificate_pdf_bytes:
            attachments = [(
                f"Certificate_{certificate_number}.pdf",
                certificate_pdf_bytes,
                "application/pdf"
            )]
        
        return await self.send_email(
            db=db,
            to_email=user.email,
            subject=f"Congratulations! Certificate Issued - {course_name}",
            email_type=self.TYPE_CERTIFICATE_ISSUED,
            template_name="certificate_issued",
            context={
                "first_name": first_name,
                "certificate_number": certificate_number,
                "course_name": course_name,
                "issue_date": datetime.now().strftime("%B %d, %Y"),
            },
            related_user_id=user.id,
            related_entity_type="certificate",
            related_entity_id=certificate_id,
            attachments=attachments,
        )
    
    async def send_invoice_sent(
        self,
        db: AsyncSession,
        user: User,
        invoice_number: str,
        issue_date: str,
        due_date: str,
        course_name: str,
        grand_total: str,
        invoice_id: int,
        invoice_pdf_bytes: Optional[bytes] = None
    ) -> EmailLog:
        """
        Send invoice notification email.
        
        Args:
            db: Database session
            user: Recipient user
            invoice_number: Invoice number
            issue_date: Invoice issue date
            due_date: Invoice due date
            course_name: Course name
            grand_total: Total amount due
            invoice_id: Invoice ID
            invoice_pdf_bytes: Invoice PDF as bytes (optional)
        """
        first_name = self._get_first_name(user)
        
        # Build attachments list
        attachments = None
        if invoice_pdf_bytes:
            attachments = [(
                f"{invoice_number}.pdf",
                invoice_pdf_bytes,
                "application/pdf"
            )]
        
        return await self.send_email(
            db=db,
            to_email=user.email,
            subject=f"New Invoice - {invoice_number}",
            email_type=self.TYPE_INVOICE_SENT,
            template_name="invoice_sent",
            context={
                "first_name": first_name,
                "invoice_number": invoice_number,
                "issue_date": issue_date,
                "due_date": due_date,
                "course_name": course_name,
                "grand_total": grand_total,
            },
            related_user_id=user.id,
            related_entity_type="invoice",
            related_entity_id=invoice_id,
            attachments=attachments,
        )


# Singleton instance
email_service = EmailService()
