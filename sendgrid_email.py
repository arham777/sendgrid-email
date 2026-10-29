import argparse
import csv
import logging
import os
import re
import time
from email_validator import validate_email, EmailNotValidError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Personalization, To, Attachment, FileContent, FileName, FileType, Disposition
from sendgrid import SendGridException
import base64

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Maximum batch size per SendGrid API call
BATCH_SIZE = 1000

def extract_placeholders(html_content):
    """Extract unique placeholders from HTML content (e.g., {{FIRST_NAME}})."""
    pattern = r'\{\{(.*?)\}\}'
    matches = re.findall(pattern, html_content)
    return {match.strip() for match in matches if match.strip()}

def get_substitution_value(placeholder, recipient_data):
    """Find the value for a placeholder in recipient data with flexible matching."""
    # Exact match
    if placeholder in recipient_data:
        return recipient_data[placeholder]
    # Case-insensitive match
    for key in recipient_data:
        if key.lower() == placeholder.lower():
            return recipient_data[key]
    # Match with spaces or underscores
    placeholder_with_spaces = placeholder.replace('_', ' ')
    placeholder_with_underscores = placeholder.replace(' ', '_')
    for key in recipient_data:
        key_lower = key.lower()
        if key_lower == placeholder_with_spaces.lower() or key_lower == placeholder_with_underscores.lower():
            return recipient_data[key]
    return None

def create_attachment(image_path):
    """Create an attachment from an image file with size validation."""
    if not os.path.isfile(image_path):
        logger.error(f"Image file not found at path: {image_path}")
        return None
    try:
        with open(image_path, 'rb') as f:
            data = f.read()
        file_size_mb = len(data) / (1024 * 1024)
        if file_size_mb > 10:
            logger.warning(f"Attachment size {file_size_mb:.2f}MB exceeds 10MB, may be rejected by SendGrid or recipients.")
        encoded = base64.b64encode(data).decode()
        attachment = Attachment()
        attachment.file_content = FileContent(encoded)
        attachment.file_name = FileName(os.path.basename(image_path))
        attachment.file_type = FileType('image/jpeg')  # Adjust based on file type if needed
        attachment.disposition = Disposition('attachment')
        return attachment
    except Exception as e:
        logger.error(f"Failed to create attachment from {image_path}: {e}")
        return None

def get_content_from_csv(filename, column_mapping):
    """Extract content (subject, HTML, image path) from the first row of a CSV."""
    with open(filename, 'r', newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        first_row = next(reader, None)
        if first_row:
            subject = first_row.get(column_mapping['subject'], '').strip()
            html_content = first_row.get(column_mapping['html_body'], '').strip()
            image_path = first_row.get(column_mapping['image_path'], '').strip() if column_mapping['image_path'] else None
            if subject and html_content:
                return {
                    'subject': subject,
                    'html_content': html_content,
                    'image_path': image_path
                }
    return None

def get_recipients_from_csv(filename, column_mapping, start_row=1):
    """Generator to yield recipients from a CSV file."""
    with open(filename, 'r', newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for _ in range(start_row - 1):
            next(reader, None)  # Skip to start_row
        for row in reader:
            email = row.get(column_mapping['email'], '').strip()
            if email:
                try:
                    validate_email(email, check_deliverability=False)
                    yield row
                except EmailNotValidError:
                    logger.warning(f"Invalid email skipped: {email}")

def send_personalized_emails(sg_client, from_email, from_name, recipient_generator, subject, html_content=None, attachment=None, template_id=None):
    """Send emails in batches using SendGrid."""
    max_retries = 3
    while True:
        batch = []
        for _ in range(BATCH_SIZE):
            recipient = next(recipient_generator, None)
            if recipient is None:
                break
            batch.append(recipient)
        if not batch:
            break

        mail = Mail(from_email=from_email, subject=subject)
        mail.from_name = from_name
        if attachment:
            mail.add_attachment(attachment)
        if template_id:
            mail.template_id = template_id
        else:
            if html_content:
                mail.html_content = html_content
            else:
                logger.error("HTML content required when not using a template.")
                return

        for recipient in batch:
            personalization = Personalization()
            email = recipient[column_mapping['email']]
            # Construct recipient name
            name = recipient.get('NAME', '')
            if not name:
                first_name = recipient.get('FIRST_NAME', '')
                last_name = recipient.get('LAST_NAME', '')
                name = f"{first_name} {last_name}".strip()
            personalization.add_to(To(email, name=name))

            if template_id:
                # Use all columns except email as dynamic template data
                dynamic_data = {k: v for k, v in recipient.items() if k != column_mapping['email']}
                personalization.dynamic_template_data = dynamic_data
            else:
                # Use substitutions for placeholders in HTML content
                placeholders = extract_placeholders(html_content)
                for placeholder in placeholders:
                    value = get_substitution_value(placeholder, recipient)
                    if value is not None:
                        personalization.add_substitution(placeholder, value)
                    else:
                        logger.warning(f"No value for placeholder '{placeholder}' for {email}")
                        personalization.add_substitution(placeholder, '')
            mail.add_personalization(personalization)

        # Send the batch with retries
        for attempt in range(1, max_retries + 1):
            try:
                response = sg_client.send(mail)
                if response.status_code == 202:
                    logger.info(f"Batch of {len(batch)} emails sent successfully")
                    break
                else:
                    logger.error(f"Batch send failed with status {response.status_code}")
                    break
            except SendGridException as e:
                if e.status_code == 429:
                    retry_after = float(e.response.headers.get('Retry-After', attempt * 5))
                    logger.warning(f"Rate limit hit, attempt {attempt}, waiting {retry_after} seconds")
                    time.sleep(retry_after)
                else:
                    logger.error(f"SendGrid error on attempt {attempt}: {e}")
                    break
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt}: {e}")
                break
        else:
            logger.error(f"Failed to send batch after {max_retries} attempts")

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Send bulk personalized emails via SendGrid.")
    parser.add_argument('--api-key', required=True, help="SendGrid API key")
    parser.add_argument('--from-email', required=True, help="Sender email address")
    parser.add_argument('--from-name', default="Sender", help="Sender name")
    parser.add_argument('--csv-file', required=True, help="Path to recipient CSV file")
    parser.add_argument('--subject', help="Email subject (required if not in CSV)")
    parser.add_argument('--html-content', help="HTML content with placeholders (required if not in CSV)")
    parser.add_argument('--image-path', help="Path to attachment image")
    parser.add_argument('--template-id', help="SendGrid template ID (optional)")
    parser.add_argument('--email-col', default='EMAIL', help="Name of the email column in CSV")
    return parser.parse_args()

def main():
    """Main function to orchestrate email sending."""
    args = parse_arguments()

    # Initialize SendGrid client
    sg = SendGridAPIClient(args.api_key)

    # Define column mappings (simplified for this example)
    global column_mapping
    column_mapping = {
        'email': args.email_col,
        'subject': 'SUBJECT',
        'html_body': 'HTML_CONTENT',
        'image_path': 'IMAGE_PATH'
    }

    # Determine content source
    content_data = get_content_from_csv(args.csv_file, column_mapping) if not args.template_id and not args.html_content else None
    start_row = 2 if content_data else 1
    subject = args.subject or (content_data and content_data['subject'])
    html_content = args.html_content or (content_data and content_data['html_content'])
    image_path = args.image_path or (content_data and content_data.get('image_path'))

    if not subject:
        logger.error("Subject is required.")
        return

    # Prepare attachment if provided
    attachment = create_attachment(image_path) if image_path else None

    # Get recipient generator
    recipient_generator = get_recipients_from_csv(args.csv_file, column_mapping, start_row=start_row)

    # Send emails
    send_personalized_emails(
        sg_client=sg,
        from_email=args.from_email,
        from_name=args.from_name,
        recipient_generator=recipient_generator,
        subject=subject,
        html_content=html_content,
        attachment=attachment,
        template_id=args.template_id
    )

    # Compliance reminder
    if html_content and '{{UNSUBSCRIBE_URL}}' in html_content:
        logger.info("Detected {{UNSUBSCRIBE_URL}} placeholder. Ensure the CSV includes a matching column (e.g., 'UNSUBSCRIBE_URL').")
    else:
        logger.warning("No unsubscribe link detected. Include {{UNSUBSCRIBE_URL}} in your content and a corresponding CSV column for compliance (e.g., CAN-SPAM, GDPR).")

if __name__ == "__main__":
    main()