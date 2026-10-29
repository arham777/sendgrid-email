import os
import csv
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, To

# --- Configuration ---
CSV_FILENAME = 'recipients.csv'
# *** IMPORTANT: Set this to the exact header name in your CSV file ***
EMAIL_COLUMN_HEADER = 'EMAIL'  # <-- Updated based on your image
# *******************************************************************
FROM_EMAIL = 'arham.athar@cybergen.com'
# FROM_EMAIL = 'arhamawan200@gmail.com'
SUBJECT = 'Testing SendGrid Bulk Email with Python'
HTML_CONTENT = '<strong>Hi there, this is a test email sent to multiple recipients from a CSV file using SendGrid!</strong>'
# --- End Configuration ---

# Load environment variables from .env file
load_dotenv()
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')

# --- Updated function to read emails from CSV using a configured header ---
def get_recipients_from_csv(filename, column_header):
    """Reads email addresses from the specified column_header of a CSV file."""
    emails = []
    try:
        with open(filename, mode='r', newline='', encoding='utf-8') as csvfile:
            # Use strip() to remove potential BOM (Byte Order Mark) if reading UTF-8 files saved by Excel
            # Peek at the first line to handle potential BOM
            first_line = csvfile.readline()
            if first_line.startswith('\ufeff'):
                 # File has BOM, continue reading from the current position
                 pass
            else:
                 # No BOM, reset file pointer to the beginning
                 csvfile.seek(0)

            reader = csv.DictReader(csvfile)

            # Check if the specified column header exists in the file's headers
            if column_header not in reader.fieldnames:
                print(f"Error: CSV file '{filename}' does not contain the specified column header '{column_header}'.")
                print(f"Available headers are: {reader.fieldnames}")
                return None # Indicate failure

            print(f"Reading emails from column '{column_header}' in {filename}...")
            count = 0
            for row in reader:
                # Check if the row itself is not empty and the specific column exists in the row
                if row and column_header in row:
                    email_address = row[column_header].strip() # Get email using the configured header
                    if email_address: # Ensure it's not an empty string
                        emails.append(email_address)
                        count += 1
                    # else: # Optional: uncomment to see rows with empty email fields
                    #    print(f"Warning: Found empty value in column '{column_header}' at row {reader.line_num}")
                # else: # Optional: uncomment to see potentially malformed rows
                #    print(f"Warning: Skipping potentially empty or malformed row {reader.line_num}")


            print(f"Read {count} email addresses.")
            if count == 0:
                print(f"Warning: No email addresses were found in column '{column_header}'. Please check the CSV and the EMAIL_COLUMN_HEADER setting.")

            return emails

    except FileNotFoundError:
        print(f"Error: CSV file '{filename}' not found.")
        return None
    except Exception as e:
        print(f"Error reading CSV file '{filename}': {e}")
        return None

# --- Main script logic ---
if not SENDGRID_API_KEY:
    print("Error: SENDGRID_API_KEY not found in environment variables.")
    print("Make sure you have a .env file with SENDGRID_API_KEY=YOUR_API_KEY")
else:
    print("SendGrid API Key loaded successfully.")

    # Get the list of recipient emails using the configured header
    recipient_emails = get_recipients_from_csv(CSV_FILENAME, EMAIL_COLUMN_HEADER) # <-- Pass the header name

    if recipient_emails and len(recipient_emails) > 0: # Proceed only if emails were read successfully and list is not empty
        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=recipient_emails, # Pass the list directly here
            subject=SUBJECT,
            html_content=HTML_CONTENT
        )

        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            print(f"Sending email to {len(recipient_emails)} recipients...")
            response = sg.send(message)

            print("SendGrid Response Status Code:", response.status_code)
            if response.status_code == 202:
                print("Email request accepted by SendGrid for processing.")
            else:
                print("There might have been an issue sending. Check SendGrid dashboard for details.")
                # print("Response Body:", response.body) # Uncomment for detailed error response

        except Exception as e:
            print(f"Error sending email via SendGrid: {e}")
            if hasattr(e, 'body'):
                 print("Error details:", e.body)
    elif recipient_emails is None:
         print("Script halted because CSV reading failed.")
    else: # recipient_emails is an empty list
         print("Script halted because no email addresses were found in the CSV file.")

# --- End of Script ---