"""
PDF Generation Service for Certificates and Invoices
Uses WeasyPrint to generate PDF from HTML templates
"""
import os
import io
import qrcode
import base64
from datetime import date
from jinja2 import Template

# Try to import weasyprint (optional dependency)
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except Exception:
    HTML = None
    CSS = None
    WEASYPRINT_AVAILABLE = False


# Base path for storing certificates
CERTIFICATES_DIR = "uploads/certificates"
INVOICES_DIR = "uploads/invoices"


def generate_certificate_pdf(
    html_template: str,
    certificate_number: str,
    student_name: str,
    course_name: str,
    issue_date: date,
    expiry_date: date | None,
    template_name: str,
    background_image_url: str | None = None,
    verification_url: str = ""
) -> bytes:
    """
    Generate PDF certificate from HTML template
    
    Args:
        html_template: HTML template with {{placeholders}}
        certificate_number: Unique certificate number
        student_name: Student's full name
        course_name: Course name
        issue_date: Date certificate was issued
        expiry_date: Date certificate expires (optional)
        template_name: Name of the template used
        background_image_url: URL for background image
        verification_url: URL to verify certificate
        
    Returns:
        PDF as bytes
    """
    if not WEASYPRINT_AVAILABLE:
        raise RuntimeError("PDF generation is not available. Please install weasyprint with GTK libraries.")
    
    # Generate QR code
    qr_code_base64 = ""
    if verification_url:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(verification_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    # Format dates
    issue_date_str = issue_date.strftime("%B %d, %Y") if issue_date else ""
    expiry_date_str = expiry_date.strftime("%B %d, %Y") if expiry_date else "Lifetime"
    
    # Prepare context for template
    context = {
        "student_name": student_name,
        "course_name": course_name,
        "certificate_number": certificate_number,
        "issue_date": issue_date_str,
        "expiry_date": expiry_date_str,
        "template_name": template_name,
        "qr_code_base64": qr_code_base64,
        "verification_url": verification_url,
        "background_image_url": background_image_url,
    }
    
    # Render HTML with Jinja2
    template = Template(html_template)
    rendered_html = template.render(**context)
    
    # Add CSS for styling
    css = """
        @page {
            size: A4 landscape;
            margin: 0;
        }
        body {
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
        }
    """
    
    # Generate PDF using WeasyPrint
    html_doc = HTML(string=rendered_html)
    pdf = html_doc.write_pdf(stylesheets=[CSS(string=css)])
    
    return pdf


def save_certificate_pdf(
    pdf_bytes: bytes,
    certificate_number: str,
    issue_date: date
) -> str:
    """
    Save PDF to storage and return the file path
    
    Args:
        pdf_bytes: PDF content as bytes
        certificate_number: Certificate number (used in filename)
        issue_date: Issue date (used for directory structure)
        
    Returns:
        Relative path to saved PDF
    """
    # Create directory structure: {year}/{month}/
    year = issue_date.year
    month = f"{issue_date.month:02d}"
    
    dir_path = os.path.join(CERTIFICATES_DIR, str(year), month)
    os.makedirs(dir_path, exist_ok=True)
    
    # Create filename
    filename = f"{certificate_number}.pdf"
    file_path = os.path.join(dir_path, filename)
    
    # Save PDF
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)
    
    # Return relative path
    relative_path = os.path.join(str(year), month, filename)
    return relative_path


def get_certificate_pdf_path(certificate_number: str, issue_date: date) -> str:
    """
    Get the expected path for a certificate PDF
    
    Args:
        certificate_number: Certificate number
        issue_date: Issue date
        
    Returns:
        Relative path to PDF
    """
    year = issue_date.year
    month = f"{issue_date.month:02d}"
    return os.path.join(str(year), month, f"{certificate_number}.pdf")


# Invoice PDF Generation
INVOICE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Invoice</title>
  <style>
    @page {
      margin: 2cm 2cm 3cm 2cm;
    }

    body {
      font-family: 'Helvetica Neue', Arial, sans-serif;
      font-size: 13px;
      color: #333;
      line-height: 1.5;
      margin: 0;
      padding: 20px;
    }

    .header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 1cm;
    }

    .header-left {
      width: 60%;
    }

    .logo {
      height: 50px;
      display: block;
      margin-bottom: 8px;
    }

    .company-info {
      line-height: 1.4;
    }

    .invoice-meta {
      text-align: right;
    }

    .invoice-title {
      font-size: 24px;
      font-weight: 600;
      margin-bottom: 10px;
    }

    .recipient {
      margin-bottom: 1cm;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      border-bottom: 1px solid #ddd;
      margin-bottom: 1.5cm;
    }

    th,
    td {
      border-top: 1px solid #ddd;
      padding: 6px 4px;
      text-align: left;
      vertical-align: top;
    }

    th {
      background: #f5f5f5;
      font-weight: 600;
    }

    .totals {
      width: 40%;
      float: right;
      margin-bottom: 0.5cm;
    }

    .totals td {
      padding: 4px 0;
    }

    .bottom-container {
      display: flex;
      justify-content: space-between;
      margin-top: 1.5cm;
      margin-bottom: 1.5cm;
      page-break-inside: avoid;
    }

    .sender-details,
    .bank-info {
      width: 48%;
    }

    .bank-info {
      text-align: right;
    }

    .notes {
      clear: both;
      margin-bottom: 1.5cm;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="header-left">
      <div class="company-info"><strong>Mulat Beauty Training Institute</strong><br>Addis Ababa, Ethiopia<br>Phone: +251 911 123 456<br>Email: info@mulatbeauty.edu.et</div>
    </div>
    <div class="invoice-meta">
      <div class="invoice-title">Invoice</div>
      <div><strong>Invoice No.:</strong> {{invoice_number}}</div>
      <div><strong>Date:</strong> {{issue_date}}</div>
      <div><strong>Due Date:</strong> {{due_date}}</div>
    </div>
  </div>

  <div class="recipient">
    <strong>Recipient:</strong><br>{{student_name}}<br>{{student_email}}<br>{{student_phone}}
  </div>

  <table>
    <thead>
      <tr>
        <th style="width:5%">#</th>
        <th>Description</th>
        <th style="width:10%; text-align: right;">Qty</th>
        <th style="width:15%; text-align: right;">Unit Price</th>
        <th style="width:15%; text-align: right;">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for item in items %}
      <tr>
        <td>{{loop.index}}</td>
        <td>{{item.description}}</td>
        <td style="text-align: right;">{{item.quantity}}</td>
        <td style="text-align: right;">ETB {{item.unit_price}}</td>
        <td style="text-align: right;">ETB {{item.amount}}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="totals">
    <table>
      <tr><td>Subtotal:</td><td style="text-align:right;">ETB {{subtotal}}</td></tr>
      <tr><td>Discount:</td><td style="text-align:right;">ETB {{discount}}</td></tr>
      <tr><td>VAT ({{tax_rate}}%):</td><td style="text-align:right;">ETB {{tax}}</td></tr>
      <tr><td><strong>Total:</strong></td><td style="text-align:right;"><strong>ETB {{grand_total}}</strong></td></tr>
    </table>
  </div>

  
  <div class="notes">
    Thank you for your business! Payment is due within 30 days.
  </div>
  

  <div class="bottom-container">
    <div class="sender-details">
      <strong>Mulat Beauty Training Institute</strong><br>
      Addis Ababa, Ethiopia<br><br>
      Phone: +251 911 123 456<br>
      Email: info@mulatbeauty.edu.et
    </div>

    
  </div>
</body>
</html>"""


def generate_invoice_pdf_bytes(
    invoice_number: str,
    issue_date: str,
    due_date: str,
    student_name: str,
    student_email: str,
    student_phone: str,
    items: list,
    subtotal: float,
    discount: float,
    tax: float,
    grand_total: float,
    tax_rate: float = 15
) -> bytes:
    """
    Generate PDF for invoice using the provided template
    
    Returns:
        PDF as bytes
    """
    if not WEASYPRINT_AVAILABLE:
        raise RuntimeError("PDF generation is not available. Please install weasyprint with GTK libraries.")
    
    # Render HTML template with Jinja2
    template = Template(INVOICE_HTML_TEMPLATE)
    rendered_html = template.render(
        invoice_number=invoice_number,
        issue_date=issue_date,
        due_date=due_date,
        student_name=student_name,
        student_email=student_email,
        student_phone=student_phone,
        items=items,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        grand_total=grand_total,
        tax_rate=tax_rate
    )
    
    # Generate PDF using WeasyPrint
    html_doc = HTML(string=rendered_html)
    pdf = html_doc.write_pdf()
    
    return pdf


def save_invoice_pdf(pdf_bytes: bytes, invoice_number: str) -> str:
    """
    Save invoice PDF to storage
    
    Returns:
        Relative path to saved PDF
    """
    # Create directory
    os.makedirs(INVOICES_DIR, exist_ok=True)
    
    # Create filename
    filename = f"{invoice_number}.pdf"
    file_path = os.path.join(INVOICES_DIR, filename)
    
    # Save PDF
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)
    
    return f"/uploads/invoices/{filename}"
