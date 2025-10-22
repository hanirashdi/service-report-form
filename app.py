from flask import Flask, render_template, request, send_file
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import base64, os
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def form():
    return render_template("form.html")

@app.route('/submit', methods=['POST'])
def submit():
    from PIL import ImageOps, ExifTags
    
    customer = request.form['customer']
    address = request.form['address']
    machine_type = request.form['machine_type']
    serial_number = request.form['serial_number']
    type_of_service = request.form['type_of_service']
    report_no = request.form['report_no']
    service_date = request.form['service_date']
    service_time = request.form['service_time']
    req_date = request.form['req_date']
    payment = request.form['payment']
    quotation = request.form['quotation']
    po = request.form['po']
    invoice = request.form['invoice']
    status = request.form['status']
    problem = request.form['problem']
    summary = request.form['summary']
    signature_service = request.form['signService']
    tech_name = request.form['tech_name']
    designation = request.form['designation']
    signature_cust = request.form['signCust']
    cust_name = request.form['cust_name']
    stamp = request.form['stamp']
    
    # --- Process up to 4 uploaded images safely (size + resolution limit) ---
    photo_files = []
    MAX_FILE_SIZE_MB = 10         # reject anything above 10 MB
    MAX_RESOLUTION = (4000, 4000) # reject absurdly huge images
    TARGET_SIZE = (800, 800)      # resize to this for PDF

    for i in range(1, 5):
        file = request.files.get(f'photo{i}')
        if not file or not file.filename:
            continue

        try:
            file.seek(0, os.SEEK_END)
            size_mb = file.tell() / (1024 * 1024)
            file.seek(0)

            # --- Reject if too large in size ---
            if size_mb > MAX_FILE_SIZE_MB:
                print(f"Skipped {file.filename}: {size_mb:.2f} MB > {MAX_FILE_SIZE_MB} MB limit")
                continue

            img = Image.open(file.stream)

            # --- Fix rotation using EXIF ---
            try:
                from PIL import ExifTags, ImageOps
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break
                exif = img._getexif()
                if exif and orientation in exif:
                    img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            # --- Validate resolution ---
            if img.width > MAX_RESOLUTION[0] or img.height > MAX_RESOLUTION[1]:
                print(f"Resizing large image: {img.width}x{img.height}")
                img.thumbnail(MAX_RESOLUTION)

            # --- Resize to target size for PDF ---
            img.thumbnail(TARGET_SIZE)

            # --- Convert to RGB (remove alpha) ---
            img = img.convert("RGB")

            # --- Save to memory (compress to JPEG) ---
            img_buffer = BytesIO()
            img.save(img_buffer, format="JPEG", quality=85, optimize=True)
            img_buffer.seek(0)
            photo_files.append(img_buffer)

        except Exception as e:
            print(f"Error processing {file.filename}: {e}")

    print("Uploaded files:", [f.name if hasattr(f, 'name') else 'in-memory' for f in photo_files])
    
    # Create overlay PDF
    packet = BytesIO()
    can = canvas.Canvas(packet)
    can.setFont("Helvetica", 10)

    can.drawString(120, 680, customer)
    can.drawString(120, 625, machine_type)
    can.drawString(120, 600, serial_number)
    can.drawString(120, 580, type_of_service)
    can.drawString(450, 680, report_no)
    can.drawString(450, 668, service_date)
    can.drawString(450, 656, service_time)
    can.drawString(450, 646, req_date)
    can.drawString(450, 635, payment)
    can.drawString(450, 623, quotation)
    can.drawString(450, 610, po)
    can.drawString(450, 598, invoice)
    can.drawString(450, 587, status)
    can.drawString(85, 58, tech_name)
    can.drawString(85, 48, designation)
    can.drawString(270, 58, cust_name)
    can.drawString(270, 48, stamp)

    # --- Wrapping ---
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 9
    normal.leading = 11  # spacing between lines

    # --- Address (wrap automatically) ---
    addr_para = Paragraph(address.replace("\n", "<br/>"), normal)
    w, h = addr_para.wrap(250, 100)  # width, height of box
    addr_para.drawOn(can, 120, 670 - h)

    # --- Problem (short text, still allow wrap) ---
    prob_para = Paragraph(problem.replace("\n", "<br/>"), normal)
    w, h = prob_para.wrap(440, 80)
    prob_para.drawOn(can, 120, 515 - h)

    # --- Summary (can be long, wrap automatically) ---
    sum_para = Paragraph(summary.replace("\n", "<br/>"), normal)
    w, h = sum_para.wrap(500, 400)  # bigger box for long text
    sum_para.drawOn(can, 50, 473 - h)


    # --- Add uploaded photos to PDF ---
    if photo_files:
        can.setFont("Helvetica-Bold", 10)
        can.drawString(50, 270, "Attached Photos:")

        x_positions = [50, 180, 300, 420]  # 4 columns
        y_position = 160                   # vertical placement
        max_width = 110
        max_height = 100

        labels = ["Photo 1", "Photo 2", "Photo 3", "Photo 4"]
        for idx, img_buffer in enumerate(photo_files[:4]):
            try:
                img = Image.open(img_buffer)
                w, h = img.size
                aspect_ratio = w / h

                # Compute scaled size
                if aspect_ratio >= 1:  # landscape
                    draw_w = max_width
                    draw_h = max_width / aspect_ratio
                else:  # portrait
                    draw_h = max_height
                    draw_w = max_height * aspect_ratio

                # Keep inside bounds
                draw_w = min(draw_w, max_width)
                draw_h = min(draw_h, max_height)

                # Compute coordinates
                x = x_positions[idx % 4]
                y = y_position

                # Draw image
                can.drawImage(ImageReader(img_buffer), x, y, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')
                can.setFont("Helvetica", 8)
                can.drawString(x, y - 12, labels[idx])
            except Exception as e:
                print("Error drawing photo:", e)
    
    # Decode base64 signature (flatten transparency)
    if signature_service and ',' in signature_service:
        header, encoded = signature_service.split(',', 1)
        sig_bytes_serv = base64.b64decode(encoded)
        serv_img = Image.open(BytesIO(sig_bytes_serv))
        serv_buffer = BytesIO()
        serv_img.save(serv_buffer, format="PNG")
        serv_buffer.seek(0)
        can.drawImage(ImageReader(serv_buffer), 50, 60, width=120, height=60, mask='auto')
        can.drawString(85, 38, service_date)
     
    if signature_cust and ',' in signature_cust:
        header, encoded = signature_cust.split(',', 1)
        sig_bytes_cust = base64.b64decode(encoded)
        cust_img = Image.open(BytesIO(sig_bytes_cust))
        cust_buffer = BytesIO()
        cust_img.save(cust_buffer, format="PNG")
        cust_buffer.seek(0)
        can.drawImage(ImageReader(cust_buffer), 220, 60, width=120, height=60, mask='auto')
        can.drawString(270, 38, service_date)

    can.save()
    packet.seek(0)

    overlay_pdf = PdfReader(packet)
    base_pdf = PdfReader(open("report.pdf", "rb"))
    writer = PdfWriter()

    page = base_pdf.pages[0]
    page.merge_page(overlay_pdf.pages[0])
    writer.add_page(page)

    safe_customer = customer.replace(" ", "_")
    safe_name = cust_name.replace(" ", "_")
    safe_date = service_date.replace("-", "")
    output_filename = os.path.join(
    UPLOAD_FOLDER,
    f"{safe_customer}_{safe_name}_{safe_date}_ServiceReport.pdf"
)

    with open(output_filename, "wb") as f:
        writer.write(f)
        upload_to_drive_and_email(output_filename, customer_email="technical@pebblereka.com")

    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    def upload_to_drive_and_email(pdf_path, customer_email=None):
        # Load credentials (Render secret files are mounted under /etc/secrets)
        creds = Credentials.from_authorized_user_file("/etc/secrets/token.json", [
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/gmail.send"
        ])

        # --- Upload to Google Drive ---
        drive_service = build("drive", "v3", credentials=creds)
        folder_id = "https://drive.google.com/drive/folders/1b_JEWA3m-kYgFXELWIfOKWG14w4SeJOR?usp=sharing"  # Replace with your Drive folder ID
        file_metadata = {
            "name": os.path.basename(pdf_path),
            "parents": [folder_id]
        }
        media = MediaFileUpload(pdf_path, mimetype="application/pdf")
        file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        print(f"✅ Uploaded to Drive, file ID: {file.get('id')}")

        # --- Send Email (optional) ---
        if customer_email:
            gmail_service = build("gmail", "v1", credentials=creds)
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders

            msg = MIMEMultipart()
            msg["to"] = customer_email
            msg["subject"] = "Service Report PDF"
            msg.attach(MIMEText("Attached is the completed service report.", "plain"))

            with open(pdf_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(pdf_path)}")
                msg.attach(part)

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
            print(f"✅ Email sent to {customer_email}")

    return send_file(output_filename, as_attachment=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    # Never use debug=True in production

    app.run(host="0.0.0.0", port=port)

