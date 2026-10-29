import { useState } from 'react';
import axios from 'axios';

function EmailSender({ apiKey, fromEmail, recipients, emailContent, imageFile, sendingStatus, setSendingStatus }) {
  const [showConfirmation, setShowConfirmation] = useState(false);
  
  const validateInputs = () => {
    const errors = [];
    
    if (!apiKey) errors.push('SendGrid API Key is required');
    if (!fromEmail) errors.push('From Email is required');
    if (recipients.length === 0) errors.push('At least one recipient is required');
    if (!emailContent.subject) errors.push('Email subject is required');
    if (!emailContent.htmlContent) errors.push('Email HTML content is required');
    
    return errors;
  };
  
  const handleSendClick = () => {
    const errors = validateInputs();
    
    if (errors.length > 0) {
      setSendingStatus({
        status: 'error',
        message: `Please correct the following: ${errors.join(', ')}`
      });
      return;
    }
    
    setShowConfirmation(true);
  };
  
  const handleConfirmSend = async () => {
    setSendingStatus({
      status: 'sending',
      message: 'Sending emails...'
    });
    
    try {
      // Prepare form data with files
      const formData = new FormData();
      formData.append('apiKey', apiKey);
      formData.append('fromEmail', fromEmail);
      formData.append('recipients', JSON.stringify(recipients));
      formData.append('subject', emailContent.subject);
      formData.append('htmlContent', emailContent.htmlContent);
      
      if (imageFile) {
        formData.append('image', imageFile);
      } else if (emailContent.imagePath) {
        // If no file but we have a path (from CSV), include that
        formData.append('imagePath', emailContent.imagePath);
      }
      
      // Make request to your backend API
      const response = await axios.post('/api/send-email', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      if (response.data.success) {
        setSendingStatus({
          status: 'success',
          message: `Successfully sent emails to ${recipients.length} recipient(s)`
        });
      } else {
        setSendingStatus({
          status: 'error',
          message: response.data.message || 'Failed to send emails'
        });
      }
    } catch (error) {
      console.error('Error sending emails:', error);
      
      // Improved error extraction and display
      let errorMessage = 'An unknown error occurred';
      
      if (error.response) {
        // The server responded with an error
        console.error('Server error details:', error.response.data);
        
        if (error.response.data && error.response.data.message) {
          errorMessage = error.response.data.message;
        } else {
          errorMessage = `Server error ${error.response.status}: ${error.response.statusText}`;
        }
      } else if (error.request) {
        // Request was made but no response received
        errorMessage = 'No response received from server. Please try again.';
      } else {
        // Something else happened
        errorMessage = error.message || 'Failed to send the request';
      }
      
      setSendingStatus({
        status: 'error',
        message: errorMessage
      });
    }
    
    setShowConfirmation(false);
  };
  
  const handleCancelSend = () => {
    setShowConfirmation(false);
  };

  return (
    <div>
      <div className="mt-4 flex justify-between items-center">
        <div>
          {sendingStatus.status !== 'idle' && (
            <div className={`text-sm ${
              sendingStatus.status === 'success' ? 'text-green-600' :
              sendingStatus.status === 'error' ? 'text-red-600' :
              'text-blue-600'
            }`}>
              {sendingStatus.message}
            </div>
          )}
        </div>
        
        <button
          type="button"
          onClick={handleSendClick}
          disabled={sendingStatus.status === 'sending'}
          className={`inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium 
            rounded-md shadow-sm text-white ${
              sendingStatus.status === 'sending'
                ? 'bg-indigo-400 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500'
            }`}
        >
          {sendingStatus.status === 'sending' ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Sending...
            </>
          ) : (
            'Send Email'
          )}
        </button>
      </div>

      {/* Confirmation Modal */}
      {showConfirmation && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Confirm Email Send</h3>
            <div className="mb-4">
              <p className="text-sm text-gray-500">
                You are about to send an email to {recipients.length} recipient(s).
                Are you sure you want to proceed?
              </p>
            </div>
            <div className="space-y-2 mb-4">
              <div className="text-xs text-gray-700">
                <span className="font-medium">Subject:</span> {emailContent.subject}
              </div>
              <div className="text-xs text-gray-700">
                <span className="font-medium">From:</span> {fromEmail}
              </div>
              {imageFile && (
                <div className="text-xs text-gray-700">
                  <span className="font-medium">Image Attachment:</span> {imageFile.name}
                </div>
              )}
              {!imageFile && emailContent.imagePath && (
                <div className="text-xs text-gray-700">
                  <span className="font-medium">Image Path:</span> {emailContent.imagePath}
                </div>
              )}
            </div>
            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={handleCancelSend}
                className="inline-flex justify-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmSend}
                className="inline-flex justify-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              >
                Confirm Send
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default EmailSender; 