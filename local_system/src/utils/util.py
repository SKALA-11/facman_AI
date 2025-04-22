import base64
import smtplib
from ..core.config import EMAIL_ADDRESS, EMAIL_PASSWORD
from io import BytesIO
from PIL import Image
from email.message import EmailMessage

def encode_image(file):
    img = Image.open(BytesIO(file))
    img = img.convert("RGB")

    max_size = (800, 800)
    img.thumbnail(max_size, Image.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=70)
    compressed_bytes = buffer.getvalue()

    file_encoded = base64.b64encode(compressed_bytes).decode("utf-8")

    return file_encoded

def make_pdf(content):
    buffer = BytesIO()
    
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='Korean',
        fontName='Helvetica',
        fontSize=10,
        leading=12,
        firstLineIndent=0,
        alignment=4
    ))
    
    story = []
    
    paragraphs = content.split('\n')
    for para in paragraphs:
        if para.strip():
            p = Paragraph(para, styles['Korean'])
            story.append(p)
            story.append(Spacer(1, 6))
    
    doc.build(story)
    
    buffer.seek(0)
    return buffer.read()

def send_email(email, data):
    msg = EmailMessage()
    msg['Subject'] = 'PDF 파일 전송'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email
    msg.set_content('첨부된 PDF 파일을 확인해주세요.')

    msg.add_attachment(data, maintype='application', subtype='pdf', filename='document.pdf')

    with smtplib.SMTP_SSL('smtp.naver.com', 587) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)