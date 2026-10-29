import os
import csv
import base64
import mimetypes
import re
import time
import logging
import tempfile
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, validator
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Query, status, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition, ContentId

# --- Load Configuration ---
load_dotenv()
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'arhamawan200@gmail.com')
FROM_NAME = os.getenv('FROM_NAME', '')
ATTACHMENT_CONTENT_ID = os.getenv('ATTACHMENT_CID', 'email_image')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '1000'))
RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '0'))

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('email_api.log')
    ]
)
logger = logging.getLogger('email_api')

# Email validation regex
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Create FastAPI app
app = FastAPI(
    title="Email Sender API",
    description="API for sending personalized emails via SendGrid",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Specify your allowed origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class EmailRecipient(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    custom_fields: Optional[Dict[str, str]] = Field(default_factory=dict)

class EmailContent(BaseModel):
    subject: str
    html_content: str
    
    @validator('subject')
    def subject_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Subject cannot be empty')
        return v
        
    @validator('html_content')
    def html_not_empty(cls, v):
        if not v.strip():
            raise ValueError('HTML content cannot be empty')
        return v

class EmailRequest(BaseModel):
    recipients: List[EmailRecipient]
    content: EmailContent
    test_mode: bool = False

class JobStatus(BaseModel):
    job_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    total_recipients: int
    success_count: int = 0
    failed_count: int = 0
    error_message: Optional[str] = None

# Dictionary to store job statuses
email_jobs: Dict[str, JobStatus] = {}

# --- Helper Functions ---
def validate_email(email: str) -> bool:
    """Validates email format using regex."""
    return bool(re.match(EMAIL_REGEX, email))

def save_uploaded_file(upload_file: UploadFile) -> str:
    """Saves an uploaded file to a temporary location and returns the path."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(upload_file.filename)[1])
    try:
        contents = upload_file.file.read()
        temp_file.write(contents)
        temp_file.close()
        return temp_file.name
    except Exception as e:
        temp_file.close()
        os.unlink(temp_file.name)
        raise e

def read_recipients_from_csv(file_path: str, email_column: str = "EMAIL") -> List[Dict[str, Any]]:
    """Reads recipient data from a CSV file."""
    recipients = []
    invalid_emails = []
    
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            if email_column not in reader.fieldnames:
                raise ValueError(f"CSV file missing required header '{email_column}'")
                
            logger.info(f"Reading data from CSV file")
            for row_num, row in enumerate(reader, start=2):
                if row and email_column in row:
                    email_address = row[email_column].strip()
                    if email_address:
                        # Validate email format
                        if not validate_email(email_address):
                            invalid_emails.append((row_num, email_address))
                            continue
                            
                        # Store all row data for personalization
                        recipients.append(row)
            
            # Report on findings
            valid_count = len(recipients)
            invalid_count = len(invalid_emails)
            
            if valid_count > 0:
                logger.info(f"Found {valid_count} valid email addresses")
            else:
                logger.warning(f"No valid emails found in column '{email_column}'")
                
            if invalid_count > 0:
                logger.warning(f"Found {invalid_count} invalid email addresses")
                for row_num, email in invalid_emails[:5]:  # Show first 5 invalid emails
                    logger.warning(f"  Row {row_num}: '{email}'")
                if invalid_count > 5:
                    logger.warning(f"  ... and {invalid_count - 5} more")
            
            if valid_count == 0:
                raise ValueError("No valid emails found in CSV")
                    
            return recipients

    except Exception as e:
        logger.error(f"Error reading recipients CSV: {e}")
        raise ValueError(f"Error reading recipients CSV: {e}")

def read_content_from_csv(file_path: str) -> Dict[str, Any]:
    """Reads email content data from a CSV file."""
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            required_headers = {"Subject", "HTML_Body"}
            available_headers = set(reader.fieldnames)

            if not required_headers.issubset(available_headers):
                missing = required_headers - available_headers
                raise ValueError(f"Content CSV missing required headers: {', '.join(missing)}")

            # Read the first data row
            first_row = next(reader, None)
            if not first_row:
                raise ValueError(f"Content CSV is empty or contains only headers")

            subject = first_row.get("Subject", '').strip()
            html_content = first_row.get("HTML_Body", '').strip()
            image_path = None
            if "Image_Attachment_Path" in available_headers:
                image_path = first_row.get("Image_Attachment_Path", '').strip() or None

            if not subject:
                raise ValueError(f"Subject value is empty")
            if not html_content:
                raise ValueError(f"HTML content value is empty")

            logger.info(f"Subject: '{subject}'")
            logger.info(f"HTML Content: Read (length: {len(html_content)})")
            logger.info(f"Image Path: {'Provided (' + image_path + ')' if image_path else 'Not Provided'}")

            return {
                'subject': subject,
                'html_content': html_content,
                'image_path': image_path
            }

    except Exception as e:
        logger.error(f"Error reading content CSV: {e}")
        raise ValueError(f"Error reading content CSV: {e}")

def create_attachment(image_path: str, content_id: str) -> Optional[Attachment]:
    """Creates a SendGrid Attachment object from an image file path."""
    if not image_path:
        return None

    logger.info(f"Processing attachment from '{image_path}'")
    
    try:
        # Check if file exists before opening
        if not os.path.isfile(image_path):
            logger.error(f"Image file not found at path: {image_path}")
            return None

        # Read image data
        with open(image_path, 'rb') as f:
            data = f.read()

        # Check file size
        file_size_kb = len(data) / 1024
        if file_size_kb > 10240:  # 10MB limit
            logger.warning(f"Attachment is {file_size_kb:.2f}KB - Emails with large attachments may be rejected")

        # Encode to Base64
        encoded_file = base64.b64encode(data).decode()

        # Guess MIME type
        file_type, _ = mimetypes.guess_type(image_path)
        if not file_type:
            file_type = 'application/octet-stream'  # Default if type cannot be guessed
            logger.warning(f"Could not determine MIME type for '{image_path}', using default: {file_type}")

        # Create Attachment object
        attachment = Attachment(
            FileContent(encoded_file),
            FileName(os.path.basename(image_path)),
            FileType(file_type),
            Disposition('inline'),
            ContentId(content_id)
        )
        logger.info(f"Attachment created successfully (Type: {file_type}, Content-ID: {content_id})")
        return attachment

    except Exception as e:
        logger.error(f"Error creating attachment for '{image_path}': {e}")
        return None

def send_emails(
    recipients: List[Dict[str, Any]], 
    subject: str, 
    html_content: str, 
    attachment: Optional[Attachment] = None,
    test_mode: bool = False,
    job_id: Optional[str] = None
) -> Dict[str, Any]:
    """Sends personalized emails to recipients."""
    if not SENDGRID_API_KEY:
        error_msg = "SENDGRID_API_KEY not found in environment variables"
        logger.error(error_msg)
        if job_id:
            update_job_status(job_id, "failed", error_message=error_msg)
        raise ValueError(error_msg)
    
    total_recipients = len(recipients)
    batches = [recipients[i:i+BATCH_SIZE] for i in range(0, total_recipients, BATCH_SIZE)]
    total_batches = len(batches)
    
    logger.info(f"Sending to {total_recipients} recipients in {total_batches} batch(es)")
    if test_mode:
        logger.info("TEST MODE: Emails will not actually be sent")
    
    success_count = 0
    failed_count = 0
    
    try:
        # Initialize SendGrid client
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        
        for batch_num, batch in enumerate(batches, 1):
            batch_recipients = len(batch)
            logger.info(f"Processing batch {batch_num}/{total_batches} ({batch_recipients} recipients)")
            
            try:
                # Process each recipient in the batch
                for recipient_data in batch:
                    email = recipient_data["EMAIL"].strip()
                    
                    # Skip if somehow an invalid email made it this far
                    if not validate_email(email):
                        logger.warning(f"Skipping invalid email: {email}")
                        failed_count += 1
                        continue
                    
                    # Prepare from_email (with name if provided)
                    from_email_obj = FROM_EMAIL
                    if FROM_NAME:
                        from_email_obj = f"{FROM_NAME} <{FROM_EMAIL}>"
                    
                    # Create personalized content for this recipient
                    personalized_content = html_content
                    has_personalization = False
                    
                    # Process each potential placeholder in the content
                    for key, value in recipient_data.items():
                        if value:  # Only replace if value exists
                            # Try both case variants: {{NAME}} and {{Name}}
                            placeholders = [
                                "{{" + key + "}}",
                                "{{" + key.upper() + "}}",
                                "{{" + key.lower() + "}}",
                                "{{" + key.capitalize() + "}}"
                            ]
                            for placeholder in placeholders:
                                if placeholder in personalized_content:
                                    personalized_content = personalized_content.replace(placeholder, value)
                                    has_personalization = True
                    
                    # For the recipient name, we'll check various fields
                    recipient_name = None
                    if "FIRST_NAME" in recipient_data and recipient_data["FIRST_NAME"]:
                        recipient_name = recipient_data["FIRST_NAME"]
                        if "LAST_NAME" in recipient_data and recipient_data["LAST_NAME"]:
                            recipient_name += f" {recipient_data['LAST_NAME']}"
                    elif "NAME" in recipient_data and recipient_data["NAME"]:
                        recipient_name = recipient_data["NAME"]
                    elif "Name" in recipient_data and recipient_data["Name"]:
                        recipient_name = recipient_data["Name"]
                    
                    # Format recipient for SendGrid
                    to_email = email
                    if recipient_name:
                        to_email = f"{recipient_name} <{email}>"
                    
                    # Create a simple message with personalized content
                    message = Mail(
                        from_email=from_email_obj,
                        to_emails=to_email,
                        subject=subject,
                        html_content=personalized_content
                    )
                    
                    # Add attachment if provided
                    if attachment:
                        message.add_attachment(attachment)
                    
                    # Send the email (or simulate in test mode)
                    if not test_mode:
                        response = sg.send(message)
                        status_code = response.status_code
                        
                        if 200 <= status_code < 300:  # Success
                            logger.info(f"Email sent to {email} (Status: {status_code})")
                            success_count += 1
                        else:
                            logger.error(f"Failed to send to {email} (Status: {status_code})")
                            if hasattr(response, 'body'):
                                logger.error(f"Response Body: {response.body}")
                            failed_count += 1
                    else:
                        # Test mode - simulate success
                        logger.info(f"TEST MODE - Would send to: {email}")
                        if has_personalization:
                            logger.info(f"TEST MODE - Personalized content preview: {personalized_content[:100]}...")
                        success_count += 1
                    
                    # Small delay between individual emails to avoid rate limits
                    time.sleep(0.05)
                
                # Respect rate limits if specified and if more batches remain
                if RATE_LIMIT_DELAY > 0 and batch_num < total_batches:
                    logger.info(f"Rate limiting: waiting {RATE_LIMIT_DELAY} seconds before next batch")
                    time.sleep(RATE_LIMIT_DELAY)
                    
            except Exception as e:
                logger.error(f"Error sending batch {batch_num}: {e}")
                if hasattr(e, 'body'):
                    logger.error(f"Error details: {e.body}")
                # Continue with next batch even if this one failed
                failed_count += len(batch)
        
        # Final report
        logger.info("====== Email Sending Complete ======")
        logger.info(f"Total recipients processed: {total_recipients}")
        logger.info(f"Successfully sent: {success_count}")
        logger.info(f"Failed to send: {failed_count}")
        
        if test_mode:
            logger.info("TEST MODE: No emails were actually sent")
            
        # Update job status if job_id is provided
        if job_id:
            if failed_count > 0:
                update_job_status(
                    job_id, 
                    "completed_with_errors",
                    success_count=success_count,
                    failed_count=failed_count
                )
            else:
                update_job_status(
                    job_id, 
                    "completed",
                    success_count=success_count
                )
                
        # Return result summary
        return {
            "status": "success",
            "total_recipients": total_recipients,
            "success_count": success_count,
            "failed_count": failed_count,
            "test_mode": test_mode
        }
            
    except Exception as e:
        error_msg = f"Error sending emails: {str(e)}"
        logger.error(error_msg)
        if job_id:
            update_job_status(job_id, "failed", error_message=error_msg)
        raise ValueError(error_msg)

def process_emails_background(
    job_id: str,
    recipients: List[Dict[str, Any]],
    subject: str,
    html_content: str,
    attachment_path: Optional[str] = None,
    test_mode: bool = False
) -> None:
    """Process emails in the background."""
    try:
        # Create attachment if image path is provided
        attachment = None
        if attachment_path:
            attachment = create_attachment(attachment_path, ATTACHMENT_CONTENT_ID)
        
        # Send emails
        send_emails(
            recipients=recipients,
            subject=subject,
            html_content=html_content,
            attachment=attachment,
            test_mode=test_mode,
            job_id=job_id
        )
        
    except Exception as e:
        logger.error(f"Background task error: {e}")
        update_job_status(job_id, "failed", error_message=str(e))
        
    finally:
        # Clean up temporary file if it exists and was created for this job
        if attachment_path and attachment_path.startswith(tempfile.gettempdir()):
            try:
                os.unlink(attachment_path)
                logger.info(f"Removed temporary file: {attachment_path}")
            except Exception as e:
                logger.error(f"Failed to remove temporary file {attachment_path}: {e}")

def create_job_id() -> str:
    """Create a unique job ID."""
    return datetime.now().strftime('%Y%m%d%H%M%S') + str(hash(datetime.now()))[-4:]

def update_job_status(
    job_id: str, 
    status: str, 
    success_count: int = 0, 
    failed_count: int = 0,
    error_message: Optional[str] = None
) -> None:
    """Update the status of a job."""
    if job_id in email_jobs:
        email_jobs[job_id].status = status
        email_jobs[job_id].completed_at = datetime.now().isoformat()
        email_jobs[job_id].success_count = success_count
        email_jobs[job_id].failed_count = failed_count
        if error_message:
            email_jobs[job_id].error_message = error_message
        logger.info(f"Updated job {job_id} status to {status}")

# --- API Endpoints ---
@app.get("/")
async def root():
    """Root endpoint that returns API info."""
    return {
        "name": "Email Sender API",
        "version": "1.0.0",
        "status": "running",
        "sendgrid_configured": bool(SENDGRID_API_KEY)
    }

@app.post("/send-email", status_code=status.HTTP_202_ACCEPTED)
async def send_email(
    request: EmailRequest,
    background_tasks: BackgroundTasks
):
    """Send emails to multiple recipients with personalized content."""
    # Validate request
    if not request.recipients:
        raise HTTPException(status_code=400, detail="No recipients provided")
    
    # Create a job ID
    job_id = create_job_id()
    
    # Format recipients for our sender
    formatted_recipients = []
    for recipient in request.recipients:
        recipient_dict = {
            "EMAIL": recipient.email
        }
        if recipient.first_name:
            recipient_dict["FIRST_NAME"] = recipient.first_name
        if recipient.last_name:
            recipient_dict["LAST_NAME"] = recipient.last_name
        # Add any custom fields
        if recipient.custom_fields:
            recipient_dict.update(recipient.custom_fields)
        formatted_recipients.append(recipient_dict)
    
    # Create job status
    email_jobs[job_id] = JobStatus(
        job_id=job_id,
        status="queued",
        started_at=datetime.now().isoformat(),
        total_recipients=len(formatted_recipients)
    )
    
    # Schedule the email sending task
    background_tasks.add_task(
        process_emails_background,
        job_id=job_id,
        recipients=formatted_recipients,
        subject=request.content.subject,
        html_content=request.content.html_content,
        test_mode=request.test_mode
    )
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Email sending job queued with {len(formatted_recipients)} recipients"
    }

@app.post("/send-email-from-csv", status_code=status.HTTP_202_ACCEPTED)
async def send_email_from_csv(
    background_tasks: BackgroundTasks,
    recipients_file: UploadFile = File(...),
    content_file: Optional[UploadFile] = File(None),
    subject: Optional[str] = Form(None),
    html_content: Optional[str] = Form(None),
    image_file: Optional[UploadFile] = File(None),
    email_column: str = Form("EMAIL"),
    test_mode: bool = Form(False)
):
    """Send emails using data from uploaded CSV files."""
    try:
        # Create a job ID
        job_id = create_job_id()
        
        # Save recipients file
        recipients_path = save_uploaded_file(recipients_file)
        logger.info(f"Saved recipients file to {recipients_path}")
        
        # Read recipients
        recipients = read_recipients_from_csv(recipients_path, email_column)
        
        # Initialize variables for content and attachment
        email_subject = subject
        email_html = html_content
        attachment_path = None
        
        # If content file is provided, use it
        if content_file:
            content_path = save_uploaded_file(content_file)
            logger.info(f"Saved content file to {content_path}")
            content_data = read_content_from_csv(content_path)
            email_subject = content_data['subject']
            email_html = content_data['html_content']
            
            # If image path is specified in content CSV, use it
            if content_data.get('image_path'):
                # This assumes the image path in CSV is relative to the API server
                attachment_path = content_data['image_path']
        
        # If subject or html is still None, raise error
        if not email_subject:
            raise HTTPException(status_code=400, detail="Subject is required")
        if not email_html:
            raise HTTPException(status_code=400, detail="HTML content is required")
        
        # If image file is uploaded, use it
        if image_file:
            attachment_path = save_uploaded_file(image_file)
            logger.info(f"Saved image file to {attachment_path}")
        
        # Create job status
        email_jobs[job_id] = JobStatus(
            job_id=job_id,
            status="queued",
            started_at=datetime.now().isoformat(),
            total_recipients=len(recipients)
        )
        
        # Schedule the email sending task
        background_tasks.add_task(
            process_emails_background,
            job_id=job_id,
            recipients=recipients,
            subject=email_subject,
            html_content=email_html,
            attachment_path=attachment_path,
            test_mode=test_mode
        )
        
        # Clean up the recipients file
        try:
            os.unlink(recipients_path)
        except:
            pass
        
        return {
            "job_id": job_id,
            "status": "queued",
            "message": f"Email sending job queued with {len(recipients)} recipients"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in send_email_from_csv: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of an email sending job."""
    if job_id not in email_jobs:
        raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")
    
    return email_jobs[job_id]

@app.get("/jobs")
async def list_jobs(
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None)
):
    """List email sending jobs."""
    filtered_jobs = []
    for job_id, job in email_jobs.items():
        if status is None or job.status == status:
            filtered_jobs.append(job)
    
    # Sort by started_at (newest first) and limit the results
    sorted_jobs = sorted(filtered_jobs, key=lambda x: x.started_at, reverse=True)[:limit]
    
    return sorted_jobs

# Start the API if run directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("email-sender:app", host="0.0.0.0", port=8000, reload=True) 