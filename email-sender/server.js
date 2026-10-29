import express from 'express';
import multer from 'multer';
import path from 'path';
import { fileURLToPath } from 'url';
import sgMail from '@sendgrid/mail';
import fs from 'fs';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

// Get API key from environment
const SENDGRID_API_KEY = process.env.SENDGRID_API_KEY;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 3001;

// Middleware
app.use(express.json());
app.use(express.static(path.join(__dirname, 'dist')));

// Configure multer for file upload
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024, // 10MB limit
  },
});

// API endpoint for sending emails
app.post('/api/send-email', upload.single('image'), async (req, res) => {
  try {
    const { apiKey, fromEmail, subject, htmlContent, imagePath } = req.body;
    const recipientsList = JSON.parse(req.body.recipients);
    
    console.log("API Request received with:");
    console.log("- From Email:", fromEmail);
    console.log("- Recipients count:", recipientsList.length);
    console.log("- Subject:", subject.substring(0, 30) + (subject.length > 30 ? '...' : ''));
    console.log("- HTML length:", htmlContent.length);
    console.log("- Image path from CSV:", imagePath);
    console.log("- File upload:", req.file ? req.file.originalname : 'None');
    
    if (!apiKey || !fromEmail || !recipientsList || !recipientsList.length || !subject || !htmlContent) {
      return res.status(400).json({
        success: false,
        message: 'Missing required fields'
      });
    }

    // Set SendGrid API key - use environment variable as fallback
    const keyToUse = apiKey || SENDGRID_API_KEY;
    sgMail.setApiKey(keyToUse);
    
    // Validate API key format (basic check)
    if (!keyToUse || !keyToUse.startsWith('SG.')) {
      return res.status(400).json({
        success: false,
        message: 'Invalid SendGrid API key format - should start with "SG."'
      });
    }

    // Create email message
    const message = {
      to: recipientsList,
      from: fromEmail,
      subject: subject,
      html: htmlContent,
    };

    // Fix for recipient format - ensure it's a proper array of strings
    if (typeof recipientsList === 'string') {
      message.to = [recipientsList]; // Convert to array if it's a single string
    } else if (Array.isArray(recipientsList)) {
      // Make sure all elements are strings and valid email format
      message.to = recipientsList
        .map(recipient => String(recipient).trim())
        .filter(email => {
          // Simple email validation
          const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
          if (!isValid) {
            console.warn(`Skipping invalid email: ${email}`);
          }
          return isValid;
        });
      
      // Check if we have any valid recipients left
      if (message.to.length === 0) {
        return res.status(400).json({
          success: false,
          message: 'No valid email addresses in recipient list'
        });
      }
    }

    console.log("Email details:", {
      from: message.from,
      to: message.to,
      subject: message.subject,
      htmlLength: message.html.length
    });

    // Add attachment if provided
    if (req.file) {
      const attachment = {
        content: req.file.buffer.toString('base64'),
        filename: req.file.originalname,
        type: req.file.mimetype,
        disposition: 'attachment',
        content_id: 'email_image'
      };
      
      message.attachments = [attachment];
    } 
    // Handle image path from CSV if no file was uploaded
    else if (imagePath) {
      try {
        console.log("Processing image path from CSV:", imagePath);
        
        // Check if it's a URL (for remote images)
        if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
          // For URLs, we'd need to fetch the image
          // This would require additional code to download the image
          // For now, just notify that URL attachments aren't supported yet
          console.log('URL image paths not supported yet:', imagePath);
        } else {
          // Try to read local file path
          try {
            // Check if file exists (try multiple possible locations)
            // 1. Try the exact path as specified
            let filePath = path.isAbsolute(imagePath) ? 
              imagePath : 
              path.join(__dirname, imagePath);
            
            // 2. If path starts with / but file not found, try relative to server root
            if (!fs.existsSync(filePath) && imagePath.startsWith('/')) {
              filePath = path.join(__dirname, imagePath.substring(1));
            }
            
            // 3. Try with /public prefix if not already there
            if (!fs.existsSync(filePath) && !imagePath.includes('/public/')) {
              filePath = path.join(__dirname, 'public', imagePath);
            }
            
            // 4. Try with /public/images prefix if not already there
            if (!fs.existsSync(filePath) && !imagePath.includes('/images/')) {
              filePath = path.join(__dirname, 'public/images', path.basename(imagePath));
            }
            
            // Debug all attempted paths
            console.log("Image path resolution attempts:");
            console.log(`- Original path: ${imagePath}`);
            console.log(`- Final resolved path: ${filePath}`);
            console.log(`- File exists: ${fs.existsSync(filePath)}`);
            
            if (fs.existsSync(filePath)) {
              // Read the file
              try {
                const buffer = fs.readFileSync(filePath);
                const mimeType = getMimeType(filePath);
                const fileName = path.basename(filePath);
                
                console.log(`Successfully found and loaded image at: ${filePath}`);
                console.log(`- File size: ${buffer.length} bytes`);
                console.log(`- MIME type: ${mimeType}`);
                
                const attachment = {
                  content: buffer.toString('base64'),
                  filename: fileName,
                  type: mimeType,
                  disposition: 'attachment',
                  content_id: 'email_image'
                };
                
                message.attachments = [attachment];
              } catch (readError) {
                console.error(`Error reading image file: ${readError.message}`);
              }
            } else {
              console.log(`File not found after trying all possible paths: ${imagePath}`);
              console.log(`Last attempted path: ${filePath}`);
            }
          } catch (fileError) {
            console.error('Error reading local file:', fileError);
          }
        }
      } catch (imgError) {
        console.error('Failed to process image path:', imgError);
        // Continue without the attachment rather than failing
      }
    }

    // Send email
    try {
      console.log("Sending email to SendGrid API...");

      // Test the API key first
      try {
        await sgMail.send({
          to: fromEmail, // Test by sending to yourself
          from: fromEmail,
          subject: 'API Key Test',
          text: 'Testing SendGrid API key validity',
          html: '<p>Testing SendGrid API key validity</p>'
        });
        console.log("API key test successful");
      } catch (testError) {
        console.error("API key test failed:", testError);
        if (testError.response) {
          console.error('API key test error details:', JSON.stringify(testError.response.body, null, 2));
          
          // Check for common authentication errors
          if (testError.response.body.errors && testError.response.body.errors.some(e => 
            e.message && (
              e.message.includes('authorization') || 
              e.message.includes('authenticate') || 
              e.message.includes('permission')
            )
          )) {
            return res.status(401).json({
              success: false,
              message: 'SendGrid API key authentication failed. Please check your API key or create a new one.'
            });
          }
        }
      }
      
      // Now send the actual email
      await sgMail.send(message);
      console.log("Email sent successfully");
      
      res.json({
        success: true,
        message: `Email sent to ${recipientsList.length} recipient(s)`
      });
    } catch (sendError) {
      console.error("SendGrid send error:", sendError);
      
      // Check for common SendGrid errors
      let errorMessage = sendError.message;
      
      if (sendError.response) {
        console.error('SendGrid API error details:', JSON.stringify(sendError.response.body, null, 2));
        const errors = sendError.response.body.errors || [];
        
        // Extract specific error messages
        if (errors.length > 0) {
          errorMessage = errors.map(e => e.message || e).join(', ');
        } else {
          errorMessage = `SendGrid API Error: ${JSON.stringify(sendError.response.body)}`;
        }
      }
      
      res.status(500).json({
        success: false,
        message: errorMessage
      });
    }
  } catch (error) {
    console.error('Error processing request:', error);
    
    // Add detailed error logging
    if (error.response) {
      console.error('SendGrid API error details:', JSON.stringify(error.response.body, null, 2));
    }
    
    const errorMessage = error.response 
      ? `SendGrid API Error: ${JSON.stringify(error.response.body)}` 
      : error.message;
    
    res.status(500).json({
      success: false,
      message: errorMessage
    });
  }
});

// For any other requests, serve the React app
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

// Add a simple health check endpoint
app.get('/api/status', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Improved server startup with error handling
const server = app.listen(port, '0.0.0.0', (err) => {
  if (err) {
    console.error('Error starting server:', err);
    process.exit(1);
  }
  
  const address = server.address();
  const host = address.address === '0.0.0.0' ? 'localhost' : address.address;
  console.log(`Server running at http://${host}:${port}`);
  console.log(`Health check available at http://${host}:${port}/api/status`);
  
  // Log env info
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`API Key set: ${SENDGRID_API_KEY ? 'Yes' : 'No'}`);
});

// Handle server errors
server.on('error', (error) => {
  if (error.code === 'EADDRINUSE') {
    console.error(`Error: Port ${port} is already in use. Another process may be running.`);
    console.error('Please stop that process or change the port number.');
  } else {
    console.error('Server error:', error);
  }
  process.exit(1);
});

// Helper function to guess MIME type
function getMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg';
    case '.png':
      return 'image/png';
    case '.gif':
      return 'image/gif';
    case '.bmp':
      return 'image/bmp';
    case '.webp':
      return 'image/webp';
    case '.svg':
      return 'image/svg+xml';
    default:
      return 'application/octet-stream';
  }
} 