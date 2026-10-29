import os
import csv
import base64 # For encoding image data
import mimetypes # For guessing image type
import re # For email validation
import time # For rate limiting
import logging # For proper logging
import argparse # For command line arguments
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName,
    FileType, Disposition, ContentId, # For attachments/embedding
    Personalization, To # For personalization
)

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('email_sender.log')
    ]
)
logger = logging.getLogger('email_sender')

# --- Configuration ---
# Load configuration from environment
load_dotenv()
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'arhamawan200@gmail.com')  # Default can be overridden in .env
FROM_NAME = os.getenv('FROM_NAME', '')  # Optional sender name

# CSV Config (can be overridden via command line)
CSV_FILENAME = os.getenv('CSV_FILE', 'email_data.csv')
EMAIL_COLUMN_HEADER = os.getenv('EMAIL_HEADER', 'EMAIL')

# Content CSV Config (used only if combined CSV doesn't have content or separate content file is specified)
CSV_CONTENT_FILENAME = os.getenv('CONTENT_CSV', 'content.csv')
CONTENT_SUBJECT_HEADER = os.getenv('SUBJECT_HEADER', 'Subject')
CONTENT_HTML_HEADER = os.getenv('HTML_HEADER', 'HTML_Body')
CONTENT_IMAGE_PATH_HEADER = os.getenv('IMAGE_HEADER', 'Image_Attachment_Path')

# Attachment Settings
ATTACHMENT_CONTENT_ID = os.getenv('ATTACHMENT_CID', 'email_image')

# SendGrid Settings
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '1000'))  # Process recipients in batches
RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '0'))  # Seconds to wait between batches

# Email validation regex
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# --- CSV Column Name Handling ---
# Common alternative names for email columns
EMAIL_COLUMN_ALTERNATIVES = [
    'EMAIL', 'Email', 'email', 'EMAILS', 'Emails', 'emails',
    'RECIPIENT', 'Recipient', 'recipient', 'RECIPIENTS', 'Recipients', 'recipients',
    'TO', 'To', 'to', 'MAIL', 'Mail', 'mail', 'E-MAIL', 'E-mail', 'e-mail'
]

# Common alternative names for first name columns
FIRST_NAME_ALTERNATIVES = [
    'FIRST_NAME', 'First_Name', 'first_name', 'FIRSTNAME', 'Firstname', 'firstname',
    'FIRST NAME', 'First Name', 'first name', 'FNAME', 'FName', 'fname', 'GIVEN NAME', 'Given Name', 'given name',
    'NAME', 'Name', 'name'  # if only name column exists, assume it's first name
]

# Common alternative names for last name columns
LAST_NAME_ALTERNATIVES = [
    'LAST_NAME', 'Last_Name', 'last_name', 'LASTNAME', 'Lastname', 'lastname',
    'LAST NAME', 'Last Name', 'last name', 'LNAME', 'LName', 'lname', 'SURNAME', 'Surname', 'surname',
    'FAMILY NAME', 'Family Name', 'family name'
]

# Common alternative names for subject columns in content
SUBJECT_ALTERNATIVES = [
    'SUBJECT', 'Subject', 'subject', 'EMAIL SUBJECT', 'Email Subject', 'email subject',
    'TITLE', 'Title', 'title', 'HEADING', 'Heading', 'heading'
]

# Common alternative names for HTML body columns in content
HTML_BODY_ALTERNATIVES = [
    'HTML_BODY', 'Html_Body', 'html_body', 'HTML BODY', 'Html Body', 'html body',
    'BODY', 'Body', 'body', 'CONTENT', 'Content', 'content', 'HTML', 'Html', 'html',
    'MESSAGE', 'Message', 'message', 'EMAIL BODY', 'Email Body', 'email body',
    'TEXT', 'Text', 'text', 'HTML CONTENT', 'Html Content', 'html content'
]

# Common alternative names for image path columns in content
IMAGE_PATH_ALTERNATIVES = [
    'IMAGE_ATTACHMENT_PATH', 'Image_Attachment_Path', 'image_attachment_path',
    'IMAGE PATH', 'Image Path', 'image path', 'IMAGE', 'Image', 'image',
    'ATTACHMENT', 'Attachment', 'attachment', 'PICTURE', 'Picture', 'picture',
    'LOGO', 'Logo', 'logo', 'BANNER', 'Banner', 'banner'
]

# --- Helper Functions ---

def validate_email(email):
    """Validates email format using regex."""
    return bool(re.match(EMAIL_REGEX, email))

def get_recipients_from_csv(filename, column_header, validate=True):
    """Reads email addresses from the specified column_header of a CSV file.
    
    Args:
        filename: Path to the CSV file
        column_header: Column header containing email addresses
        validate: Whether to validate email formats
        
    Returns:
        List of dictionaries containing recipient data (email and other fields for personalization)
        or None if error
    """
    recipients = []
    invalid_emails = []
    logger.info(f"Reading recipients from '{filename}'")
    
    try:
        with open(filename, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            if column_header not in reader.fieldnames:
                logger.error(f"CSV file '{filename}' missing required header '{column_header}'")
                logger.error(f"Available headers: {reader.fieldnames}")
                return None
                
            logger.info(f"Reading data from '{filename}'")
            for row_num, row in enumerate(reader, start=2):
                if row and column_header in row:
                    email_address = row[column_header].strip()
                    if email_address:
                        # Validate email format
                        if validate and not validate_email(email_address):
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
                logger.warning(f"No valid emails found in column '{column_header}'")
                
            if invalid_count > 0:
                logger.warning(f"Found {invalid_count} invalid email addresses")
                for row_num, email in invalid_emails[:5]:  # Show first 5 invalid emails
                    logger.warning(f"  Row {row_num}: '{email}'")
                if invalid_count > 5:
                    logger.warning(f"  ... and {invalid_count - 5} more")
                    
            return recipients if valid_count > 0 else None

    except FileNotFoundError:
        logger.error(f"Recipients CSV file '{filename}' not found")
        return None
    except Exception as e:
        logger.error(f"Error reading recipients CSV '{filename}': {e}")
        return None

def get_content_from_input():
    """Gets subject, HTML content, and optional image path from user input."""
    logger.info("Getting email content via input")
    
    # Get subject
    subject = input("Enter Subject: ").strip()
    while not subject:
        logger.error("Subject cannot be empty")
        subject = input("Enter Subject: ").strip()

    # Get HTML content
    print("Enter HTML Content (press Enter twice to finish):")
    html_lines = []
    try:
        while True:
            line = input()
            if line == "":
                break
            html_lines.append(line)
    except EOFError:  # Handles pasting multi-line content ending without double Enter
        pass
        
    html_content = "\n".join(html_lines).strip()
    while not html_content:
        logger.error("HTML Content cannot be empty")
        print("Enter HTML Content (press Enter twice to finish):")
        html_lines = []
        try:
            while True:
                line = input()
                if line == "":
                    break
                html_lines.append(line)
        except EOFError:
            pass
        html_content = "\n".join(html_lines).strip()

    # Check for personalization
    if "{" in html_content or "}" in html_content:
        logger.info("Detected potential personalization tags in content")
        print("\nIMPORTANT: For personalization, use {{field_name}} syntax where field_name")
        print("matches a column header in your recipients CSV file.")
        print("Example: 'Hello {{NAME}},' will be replaced with recipient's NAME value.\n")

    # Get image path
    image_path = input("Enter full path to image attachment (optional, press Enter to skip): ").strip()

    return {
        'subject': subject,
        'html_content': html_content,
        'image_path': image_path or None  # Store None if empty
    }

def get_content_from_csv(filename, subject_hdr, html_hdr, image_hdr):
    """Reads subject, HTML content, and optional image path from the first data row of a CSV."""
    logger.info(f"Reading content from CSV '{filename}'")
    
    try:
        with open(filename, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            required_headers = {subject_hdr, html_hdr}
            available_headers = set(reader.fieldnames)

            if not required_headers.issubset(available_headers):
                missing = required_headers - available_headers
                logger.error(f"Content CSV '{filename}' missing required headers: {', '.join(missing)}")
                logger.error(f"Available headers: {reader.fieldnames}")
                return None

            # Read the first data row
            first_row = next(reader, None)
            if not first_row:
                logger.error(f"Content CSV '{filename}' is empty or contains only headers")
                return None

            subject = first_row.get(subject_hdr, '').strip()
            html_content = first_row.get(html_hdr, '').strip()
            image_path = None
            if image_hdr in available_headers:
                image_path = first_row.get(image_hdr, '').strip() or None

            if not subject:
                logger.error(f"Subject value is empty in column '{subject_hdr}'")
                return None
            if not html_content:
                logger.error(f"HTML content value is empty in column '{html_hdr}'")
                return None

            logger.info(f"Subject: '{subject}'")
            logger.info(f"HTML Content: Read (length: {len(html_content)})")
            logger.info(f"Image Path: {'Provided (' + image_path + ')' if image_path else 'Not Provided'}")

            # Check for personalization
            if "{" in html_content or "}" in html_content:
                logger.info("Detected potential personalization tags in content")
                print("\nIMPORTANT: For personalization, use {{field_name}} syntax where field_name")
                print("matches a column header in your recipients CSV file.")
                print("Example: 'Hello {{FIRST_NAME}},' will be replaced with recipient's FIRST_NAME value.\n")

            return {
                'subject': subject,
                'html_content': html_content,
                'image_path': image_path
            }

    except FileNotFoundError:
        logger.error(f"Content CSV file '{filename}' not found")
        return None
    except StopIteration:
        logger.error(f"Content CSV '{filename}' seems to be empty (no data rows)")
        return None
    except Exception as e:
        logger.error(f"Error reading content CSV '{filename}': {e}")
        return None

def create_attachment(image_path, content_id):
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
            FileName(os.path.basename(image_path)),  # Use just the filename
            FileType(file_type),
            Disposition('inline'),  # 'inline' for embedding, 'attachment' for attaching
            ContentId(content_id)   # Crucial for embedding with <img src='cid:xxx'>
        )
        logger.info(f"Attachment created successfully (Type: {file_type}, Content-ID: {content_id})")
        return attachment

    except FileNotFoundError:
        logger.error(f"Image file not found: {image_path}")
        return None
    except Exception as e:
        logger.error(f"Error creating attachment for '{image_path}': {e}")
        return None

def find_best_column_match(fieldnames, alternatives):
    """Find the best matching column from alternatives in the CSV fieldnames."""
    # First try exact matches
    for field in fieldnames:
        if field in alternatives:
            return field
    
    # Try case-insensitive matches
    for field in fieldnames:
        for alt in alternatives:
            if field.lower() == alt.lower():
                return field
                
    # Try partial matches (field contains alternative or vice versa)
    for field in fieldnames:
        for alt in alternatives:
            if alt.lower() in field.lower() or field.lower() in alt.lower():
                return field
    
    # No match found
    return None

def detect_csv_columns(filename):
    """Detect and map column names in a CSV file to our expected columns."""
    try:
        with open(filename, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)
            fieldnames = next(reader)  # Get the header row
            
            # Create a mapping of our expected columns to the actual CSV columns
            column_mapping = {
                'email': find_best_column_match(fieldnames, EMAIL_COLUMN_ALTERNATIVES),
                'first_name': find_best_column_match(fieldnames, FIRST_NAME_ALTERNATIVES),
                'last_name': find_best_column_match(fieldnames, LAST_NAME_ALTERNATIVES),
                'subject': find_best_column_match(fieldnames, SUBJECT_ALTERNATIVES),
                'html_body': find_best_column_match(fieldnames, HTML_BODY_ALTERNATIVES),
                'image_path': find_best_column_match(fieldnames, IMAGE_PATH_ALTERNATIVES)
            }
            
            # Check if we found critical columns
            if not column_mapping['email']:
                logger.warning(f"Could not detect email column in '{filename}'")
                print("\nWARNING: Could not automatically detect the email column in your CSV file.")
                print("Available columns:", ", ".join(fieldnames))
                email_col = input("Please enter the exact name of the email column: ").strip()
                if email_col in fieldnames:
                    column_mapping['email'] = email_col
                else:
                    logger.error(f"Specified column '{email_col}' not found in CSV")
                    return None
            
            # Log what we found
            logger.info(f"Detected columns in '{filename}':")
            for key, value in column_mapping.items():
                if value:
                    logger.info(f"  - {key}: '{value}'")
                else:
                    logger.info(f"  - {key}: Not found")
            
            return column_mapping
            
    except Exception as e:
        logger.error(f"Error detecting columns in '{filename}': {e}")
        return None

def print_csv_usage_guide():
    """Print a guide for users on CSV file format."""
    print("\n=== CSV FILE FORMAT GUIDE ===")
    print("Your CSV file should contain the following:")
    
    print("\n1. REQUIRED COLUMNS:")
    print("   - Email addresses (can be named: EMAIL, Email, email, RECIPIENT, etc.)")
    
    print("\n2. OPTIONAL RECIPIENT COLUMNS (for personalization):")
    print("   - First names (can be named: FIRST_NAME, First Name, firstname, etc.)")
    print("   - Last names (can be named: LAST_NAME, Last Name, surname, etc.)")
    print("   - Any other fields you want to use for personalization")
    
    print("\n3. EMAIL CONTENT (can be in the same CSV or separate):")
    print("   - Subject (can be named: SUBJECT, Subject, Title, etc.)")
    print("   - HTML Body (can be named: HTML_BODY, Body, Content, Message, etc.)")
    print("   - Image Path (optional, can be named: IMAGE_PATH, Image, Attachment, etc.)")
    
    print("\n4. PERSONALIZATION:")
    print("   - Use {{COLUMN_NAME}} in your HTML to insert recipient data")
    print("   - Example: 'Hello {{FIRST_NAME}}' will be replaced with the recipient's first name")
    print("   - The system will try various case formats: {{FIRST_NAME}}, {{First_Name}}, {{first_name}}")
    
    print("\n5. CSV STRUCTURE OPTIONS:")
    print("   - Option 1: One row with email content + multiple rows with recipient emails")
    print("   - Option 2: All rows with recipient emails, separate CSV for content")
    print("   - Option 3: All rows with recipient emails, enter content manually")
    
    print("\nThe script will try to automatically detect your columns, but you may be prompted")
    print("to clarify if the detection is ambiguous.\n")
    
    # Ask the user to continue
    input("Press Enter to continue...")

def get_recipients_from_combined_csv(filename, column_mapping, content_row=None, validate=True):
    """Reads email addresses from CSV file, optionally skipping a content row.
    Uses the provided column mapping to find the right columns.
    """
    recipients = []
    invalid_emails = []
    email_column = column_mapping['email']
    logger.info(f"Reading recipients from '{filename}' using column '{email_column}'")
    
    try:
        with open(filename, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            if email_column not in reader.fieldnames:
                logger.error(f"Email column '{email_column}' not found in CSV file")
                logger.error(f"Available headers: {reader.fieldnames}")
                return None
                
            logger.info(f"Reading data from '{filename}'")
            for row_num, row in enumerate(reader, start=2):
                # Skip the content row if specified
                if content_row and row_num == content_row:
                    logger.info(f"Skipping row {row_num} (used for content)")
                    continue
                    
                if row and email_column in row:
                    email_address = row[email_column].strip()
                    if email_address:
                        # Validate email format
                        if validate and not validate_email(email_address):
                            invalid_emails.append((row_num, email_address))
                            continue
                            
                        # Store all row data for personalization, with standardized email field
                        recipient_data = row.copy()
                        # Store email under our standard EMAIL key for consistency
                        recipient_data['EMAIL'] = email_address
                        recipients.append(recipient_data)
            
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
                    
            return recipients if valid_count > 0 else None

    except FileNotFoundError:
        logger.error(f"CSV file '{filename}' not found")
        return None
    except Exception as e:
        logger.error(f"Error reading CSV '{filename}': {e}")
        return None

def get_content_from_recipients_csv(filename, column_mapping):
    """Checks if recipients CSV contains content data and extracts it using the column mapping."""
    subject_column = column_mapping['subject']
    html_body_column = column_mapping['html_body']
    image_path_column = column_mapping['image_path']
    
    # If we don't have required content columns, return None
    if not (subject_column and html_body_column):
        logger.info(f"Content columns not found in '{filename}'")
        return None
    
    logger.info(f"Checking for content data in '{filename}'")
    
    try:
        with open(filename, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Look for a row with both subject and HTML content
            for row_num, row in enumerate(reader, start=2):
                if not row:
                    continue
                    
                subject = row.get(subject_column, '').strip()
                html_content = row.get(html_body_column, '').strip()
                
                # If we have both required values, use this row for content
                if subject and html_content:
                    image_path = None
                    if image_path_column:
                        image_path = row.get(image_path_column, '').strip() or None
                    
                    logger.info(f"Found content in row {row_num}")
                    logger.info(f"Subject: '{subject}'")
                    logger.info(f"HTML Content: Read (length: {len(html_content)})")
                    logger.info(f"Image Path: {'Provided (' + image_path + ')' if image_path else 'Not Provided'}")
                    
                    # Check for personalization tags
                    check_personalization_tags(html_content)
                    
                    return {
                        'subject': subject,
                        'html_content': html_content,
                        'image_path': image_path,
                        'row_num': row_num
                    }
            
            # If we got here, we found the headers but no row with content
            logger.warning(f"Found content columns in '{filename}' but no row has both subject and HTML content.")
            return None
            
    except Exception as e:
        logger.error(f"Error checking for content in '{filename}': {e}")
        return None

def get_content_from_csv(filename, column_mapping):
    """Reads subject, HTML content, and optional image path from the first data row of a CSV."""
    subject_column = column_mapping['subject']
    html_body_column = column_mapping['html_body']
    image_path_column = column_mapping['image_path']
    
    logger.info(f"Reading content from CSV '{filename}'")
    
    # If we don't have required content columns, return None
    if not (subject_column and html_body_column):
        logger.error(f"Required content columns not found in '{filename}'")
        return None
    
    try:
        with open(filename, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)

            # Read the first data row
            first_row = next(reader, None)
            if not first_row:
                logger.error(f"Content CSV '{filename}' is empty or contains only headers")
                return None

            subject = first_row.get(subject_column, '').strip()
            html_content = first_row.get(html_body_column, '').strip()
            image_path = None
            if image_path_column:
                image_path = first_row.get(image_path_column, '').strip() or None

            if not subject:
                logger.error(f"Subject value is empty in column '{subject_column}'")
                return None
            if not html_content:
                logger.error(f"HTML content value is empty in column '{html_body_column}'")
                return None

            logger.info(f"Subject: '{subject}'")
            logger.info(f"HTML Content: Read (length: {len(html_content)})")
            logger.info(f"Image Path: {'Provided (' + image_path + ')' if image_path else 'Not Provided'}")

            # Check for personalization tags
            check_personalization_tags(html_content)

            return {
                'subject': subject,
                'html_content': html_content,
                'image_path': image_path
            }

    except FileNotFoundError:
        logger.error(f"Content CSV file '{filename}' not found")
        return None
    except StopIteration:
        logger.error(f"Content CSV '{filename}' seems to be empty (no data rows)")
        return None
    except Exception as e:
        logger.error(f"Error reading content CSV '{filename}': {e}")
        return None

def check_personalization_tags(content):
    """Check HTML content for personalization tags and provide guidance if found."""
    if "{{" in content and "}}" in content:
        logger.info("Detected personalization tags in content")
        
        # Extract all tags to help the user understand what fields are being used
        tags = []
        current_pos = 0
        while True:
            open_tag = content.find("{{", current_pos)
            if open_tag == -1:
                break
                
            close_tag = content.find("}}", open_tag)
            if close_tag == -1:
                break
                
            tag = content[open_tag+2:close_tag].strip()
            if tag:
                tags.append(tag)
            current_pos = close_tag + 2
        
        if tags:
            print("\nPERSONALIZATION DETECTED:")
            print("Your email content uses these fields for personalization:")
            for tag in sorted(set(tags)):
                print(f"  - {tag}")
            print("\nMake sure these fields exist in your recipient CSV file.")
            print("The system will try to match variations of these names (uppercase, lowercase, etc.)")
            print("For each recipient, {{FIELD_NAME}} will be replaced with their data.\n")

def send_personalized_emails(sg_client, from_email, from_name, recipients, subject, html_content, attachment=None, test_mode=False, batch_size=1000, rate_delay=0):
    """Sends personalized emails to recipients in batches."""
    total_recipients = len(recipients)
    batches = [recipients[i:i+batch_size] for i in range(0, total_recipients, batch_size)]
    total_batches = len(batches)
    
    logger.info(f"Sending to {total_recipients} recipients in {total_batches} batch(es)")
    if test_mode:
        logger.info("TEST MODE: Emails will not actually be sent")
    
    success_count = 0
    failed_batches = []
    
    for batch_num, batch in enumerate(batches, 1):
        batch_recipients = len(batch)
        logger.info(f"Processing batch {batch_num}/{total_batches} ({batch_recipients} recipients)")
        
        try:
            # Process each recipient in the batch
            for recipient_data in batch:
                # Make sure we have the email under our standard key
                email = recipient_data.get('EMAIL', '')
                if not email:
                    # Try to find the email in other keys
                    for key in recipient_data:
                        if key.lower() in ['email', 'emails', 'recipient', 'recipients', 'mail', 'e-mail']:
                            email = recipient_data[key].strip()
                            break
                
                # Skip if somehow an invalid email made it this far
                if not email or not validate_email(email):
                    logger.warning(f"Skipping invalid or missing email: {email}")
                    continue
                
                # Prepare from_email (with name if provided)
                from_email_obj = from_email
                if from_name:
                    from_email_obj = f"{from_name} <{from_email}>"
                
                # Create personalized content for this recipient
                personalized_content = html_content
                has_personalization = False
                
                # Process each potential placeholder in the content
                for key, value in recipient_data.items():
                    if not value:  # Skip empty values
                        continue
                        
                    # Look for {{key}} in various forms (original, uppercase, lowercase, etc.)
                    possible_placeholders = [
                        "{{" + key + "}}",               # Original
                        "{{" + key.upper() + "}}",       # UPPERCASE
                        "{{" + key.lower() + "}}",       # lowercase
                        "{{" + key.title() + "}}",       # Title Case
                        "{{" + key.capitalize() + "}}"   # Capitalized
                    ]
                    
                    # Also try variants with spaces replaced by underscores and vice versa
                    if '_' in key:
                        key_with_spaces = key.replace('_', ' ')
                        possible_placeholders.extend([
                            "{{" + key_with_spaces + "}}",
                            "{{" + key_with_spaces.upper() + "}}",
                            "{{" + key_with_spaces.lower() + "}}",
                            "{{" + key_with_spaces.title() + "}}",
                            "{{" + key_with_spaces.capitalize() + "}}"
                        ])
                    elif ' ' in key:
                        key_with_underscores = key.replace(' ', '_')
                        possible_placeholders.extend([
                            "{{" + key_with_underscores + "}}",
                            "{{" + key_with_underscores.upper() + "}}",
                            "{{" + key_with_underscores.lower() + "}}",
                            "{{" + key_with_underscores.title() + "}}",
                            "{{" + key_with_underscores.capitalize() + "}}"
                        ])
                    
                    # Replace all matching placeholders with the value
                    for placeholder in possible_placeholders:
                        if placeholder in personalized_content:
                            personalized_content = personalized_content.replace(placeholder, value)
                            has_personalization = True
                
                # For the recipient name, we'll check various fields using the same flexibility
                recipient_name = None
                
                # Try to find first name
                first_name = None
                for key in recipient_data:
                    key_lower = key.lower()
                    if (key_lower == 'first_name' or key_lower == 'firstname' or 
                        key_lower == 'first name' or key_lower == 'fname' or 
                        (key_lower == 'name' and not recipient_name)):
                        first_name = recipient_data[key]
                        break
                
                # Try to find last name
                last_name = None
                for key in recipient_data:
                    key_lower = key.lower()
                    if (key_lower == 'last_name' or key_lower == 'lastname' or 
                        key_lower == 'last name' or key_lower == 'lname' or 
                        key_lower == 'surname' or key_lower == 'family name'):
                        last_name = recipient_data[key]
                        break
                
                # Combine names if available
                if first_name:
                    recipient_name = first_name
                    if last_name:
                        recipient_name += f" {last_name}"
                
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
                    response = sg_client.send(message)
                    status_code = response.status_code
                    
                    if 200 <= status_code < 300:  # Success
                        logger.info(f"Email sent to {email} (Status: {status_code})")
                        success_count += 1
                    else:
                        logger.error(f"Failed to send to {email} (Status: {status_code})")
                        if hasattr(response, 'body'):
                            logger.error(f"Response Body: {response.body}")
                        # We don't increment failed_batches here since we're tracking individual emails
                else:
                    # Test mode - simulate success
                    logger.info(f"TEST MODE - Would send to: {email}")
                    if has_personalization:
                        logger.info(f"TEST MODE - Personalized content preview: {personalized_content[:100]}...")
                    success_count += 1
                
                # Small delay between individual emails to avoid rate limits
                time.sleep(0.05)
            
            # Respect rate limits if specified and if more batches remain
            if rate_delay > 0 and batch_num < total_batches:
                logger.info(f"Rate limiting: waiting {rate_delay} seconds before next batch")
                time.sleep(rate_delay)
                
        except Exception as e:
            logger.error(f"Error sending batch {batch_num}: {e}")
            if hasattr(e, 'body'):
                logger.error(f"Error details: {e.body}")
            failed_batches.append(batch_num)
            
    return success_count, failed_batches

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='SendGrid Bulk Email Sender')
    parser.add_argument('--test', action='store_true', help='Test mode - validate but do not send emails')
    parser.add_argument('--csv', type=str, help=f'CSV file with recipient data and optionally content (default: {CSV_FILENAME})')
    parser.add_argument('--content-csv', type=str, help=f'Separate content CSV file (default: {CSV_CONTENT_FILENAME})')
    parser.add_argument('--input-content', action='store_true', help='Force manual content input')
    parser.add_argument('--guide', action='store_true', help='Show CSV format guide')
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO',
                       help='Set logging level')
    parser.add_argument('--batch-size', type=int, help=f'Recipients per batch (default: {BATCH_SIZE})')
    parser.add_argument('--delay', type=float, help=f'Seconds between batches (default: {RATE_LIMIT_DELAY})')
    
    return parser.parse_args()

# --- Main Execution ---
def main():
    """Main function to orchestrate the email sending process."""
    print("=====================================")
    print(" SendGrid Bulk Email Script ")
    print("=====================================")
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Set log level from arguments
    logger.setLevel(getattr(logging, args.log_level))
    
    # Show usage guide if requested
    if args.guide:
        print_csv_usage_guide()
    else:
        # Show a brief intro about CSV files
        print("\nThis script allows you to send personalized emails using SendGrid.")
        print("You'll need a CSV file with recipient emails and optional personalization fields.")
        print("The same CSV can also contain email content, or you can use a separate file or direct input.")
        print("\nTip: Use --guide to see detailed CSV format instructions.")
    
    # Get CSV file path - prompt if not provided via command line
    csv_file = args.csv
    if not csv_file:
        print("\nPlease specify the CSV file containing email data.")
        csv_file = input("CSV file path: ").strip()
        while not csv_file:
            print("CSV file path cannot be empty.")
            csv_file = input("CSV file path: ").strip()
            
        # Check if file exists
        if not os.path.isfile(csv_file):
            logger.error(f"File not found: '{csv_file}'")
            print(f"Error: File '{csv_file}' not found. Please check the path and try again.")
            return
    
    content_csv = args.content_csv or CSV_CONTENT_FILENAME
    test_mode = args.test
    force_input_content = args.input_content
    batch_size = args.batch_size or BATCH_SIZE
    rate_delay = args.delay if args.delay is not None else RATE_LIMIT_DELAY
    
    if test_mode:
        logger.info("TEST MODE ENABLED - Emails will not actually be sent")
    
    # Verify API key
    if not SENDGRID_API_KEY:
        logger.error("SENDGRID_API_KEY not found in environment variables")
        logger.error("Please ensure a .env file exists with your key")
        return
        
    # Detect columns in the main CSV file
    csv_column_mapping = detect_csv_columns(csv_file)
    if not csv_column_mapping:
        logger.error(f"Failed to detect columns in '{csv_file}' - Exiting")
        return
        
    # Detect columns in the content CSV file if provided
    content_column_mapping = None
    if args.content_csv:
        content_column_mapping = detect_csv_columns(content_csv)
        if not content_column_mapping:
            logger.error(f"Failed to detect columns in content CSV '{content_csv}' - Exiting")
            return

    # 1. Content Source Selection
    content_data = None
    content_row = None
    
    # First try to get content from the main CSV file (unless forced to input)
    if not force_input_content:
        content_result = get_content_from_recipients_csv(csv_file, csv_column_mapping)
        if content_result:
            content_data = {
                'subject': content_result['subject'],
                'html_content': content_result['html_content'],
                'image_path': content_result['image_path']
            }
            content_row = content_result['row_num']
            logger.info(f"Using content from '{csv_file}' (row {content_row})")
    
    # If no content in main CSV or forced input, proceed with other options
    if not content_data:
        # Ask user how they want to provide content
        while True:
            print("\nContent not found in main CSV file or separate content specified.")
            mode = input("Get content from (1) Input Fields or (2) Separate CSV File? [1/2]: ").strip()
            if mode == '1':
                content_data = get_content_from_input()
                break
            elif mode == '2':
                # Prompt for content CSV if not provided via command line
                if not args.content_csv:
                    print("\nPlease specify the CSV file containing email content.")
                    content_csv = input("Content CSV file path: ").strip()
                    while not content_csv:
                        print("Content CSV file path cannot be empty.")
                        content_csv = input("Content CSV file path: ").strip()
                    
                    # Check if file exists
                    if not os.path.isfile(content_csv):
                        logger.error(f"File not found: '{content_csv}'")
                        print(f"Error: File '{content_csv}' not found. Please check the path and try again.")
                        continue
                
                if not content_column_mapping:
                    content_column_mapping = detect_csv_columns(content_csv)
                    if not content_column_mapping:
                        logger.error(f"Failed to detect columns in content CSV '{content_csv}'")
                        continue
                
                content_data = get_content_from_csv(content_csv, content_column_mapping)
                break
            else:
                logger.error("Invalid choice. Please enter 1 or 2")

    if not content_data:
        logger.error("Failed to obtain email content - Exiting")
        return

    # 2. Get Recipients (excluding the content row if needed)
    recipient_data = get_recipients_from_combined_csv(csv_file, csv_column_mapping, content_row)

    if not recipient_data:
        logger.error("Failed to obtain recipients or recipient list is empty - Exiting")
        return

    # 3. Create Attachment (if image path provided)
    email_attachment = None
    if content_data.get('image_path'):
        email_attachment = create_attachment(content_data['image_path'], ATTACHMENT_CONTENT_ID)
        if not email_attachment and content_data.get('image_path'):
            logger.warning("An image path was provided, but attachment creation failed. Sending without image")

    # 4. Initialize SendGrid client
    try:
        logger.info("Initializing SendGrid client")
        sg = SendGridAPIClient(SENDGRID_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize SendGrid client: {e}")
        return

    # 5. Send emails in batches with personalization
    success_count, failed_batches = send_personalized_emails(
        sg_client=sg,
        from_email=FROM_EMAIL,
        from_name=FROM_NAME,
        recipients=recipient_data,
        subject=content_data['subject'],
        html_content=content_data['html_content'],
        attachment=email_attachment,
        test_mode=test_mode,
        batch_size=batch_size,
        rate_delay=rate_delay
    )
    
    # 6. Report results
    total_recipients = len(recipient_data)
    logger.info("====== Email Sending Complete ======")
    logger.info(f"Total recipients processed: {total_recipients}")
    logger.info(f"Successfully sent: {success_count}")
    
    if failed_batches:
        logger.warning(f"Failed batches: {len(failed_batches)}")
        failed_count = total_recipients - success_count
        logger.warning(f"Approximately {failed_count} emails failed to send")
    else:
        logger.info("All emails processed successfully")
        
    if test_mode:
        logger.info("TEST MODE: No emails were actually sent")
    
    print("\n=====================================")
    print(" Script Finished ")
    print("=====================================")

# --- Run the main function ---
if __name__ == "__main__":
    main()