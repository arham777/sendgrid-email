import os
from dotenv import load_dotenv  # <-- Add this
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Load environment variables from .env file
load_dotenv()  # <-- Automatically looks for ".env" in current directory

# Debug: Verify the API key is loaded
print("API Key Loaded:", bool(os.getenv("SENDGRID_API_KEY")))  # Should print "True"

message = Mail(
    from_email='arhamawan200@gmail.com',
    to_emails='arham.athar@cybergen.com',
    subject='Testing SendGrid with Python',
    html_content='<strong>hi there, this is arham from cybergen checking sendgrid email automation so will integrate to our systems later</strong>'
)

try:
    sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))  # <-- Get key from .env
    response = sg.send(message)
    print("Status Code:", response.status_code)  # Should print 202 if successful
    print(response.body)
    print(response.headers)
except Exception as e:
    print("Error:", str(e))  # Check for detailed error messages
