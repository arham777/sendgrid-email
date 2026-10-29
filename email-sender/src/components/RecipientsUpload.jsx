import { useState, useRef } from 'react';
import Papa from 'papaparse';

function RecipientsUpload({ setRecipients, recipients }) {
  const [fileName, setFileName] = useState('');
  const [emailColumnHeader, setEmailColumnHeader] = useState('EMAIL');
  const [availableHeaders, setAvailableHeaders] = useState([]);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setFileName(file.name);
    setError('');

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: function(results) {
        if (results.errors.length > 0) {
          setError(`Error parsing CSV: ${results.errors[0].message}`);
          return;
        }

        if (results.meta.fields && results.meta.fields.length > 0) {
          setAvailableHeaders(results.meta.fields);
          
          // Auto-select EMAIL header if it exists
          const emailHeader = results.meta.fields.find(
            header => header.toUpperCase() === 'EMAIL'
          );
          if (emailHeader) {
            setEmailColumnHeader(emailHeader);
          }
        }

        // Extract emails from the selected column
        const extractedEmails = [];
        results.data.forEach(row => {
          if (row[emailColumnHeader] && row[emailColumnHeader].trim()) {
            extractedEmails.push(row[emailColumnHeader].trim());
          }
        });

        setRecipients(extractedEmails);
      }
    });
  };

  const handleHeaderChange = (e) => {
    setEmailColumnHeader(e.target.value);
    setError('');

    // Re-parse the file with the new header
    if (fileInputRef.current.files.length > 0) {
      const file = fileInputRef.current.files[0];
      
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: function(results) {
          const extractedEmails = [];
          results.data.forEach(row => {
            if (row[e.target.value] && row[e.target.value].trim()) {
              extractedEmails.push(row[e.target.value].trim());
            }
          });
          
          setRecipients(extractedEmails);
        }
      });
    }
  };

  return (
    <div className="bg-gray-50 p-4 rounded-lg shadow-sm border border-gray-200">
      <h2 className="text-xl font-semibold mb-4 text-gray-700">Recipients</h2>
      
      <div className="space-y-4">
        <div>
          <label htmlFor="file-upload" className="block text-sm font-medium text-gray-700 mb-1">
            Upload Recipients CSV
          </label>
          <div className="flex">
            <input
              ref={fileInputRef}
              id="file-upload"
              name="file-upload"
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              className="sr-only"
            />
            <label
              htmlFor="file-upload"
              className="cursor-pointer inline-flex items-center px-4 py-2 border border-gray-300 
                rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 
                focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              Choose File
            </label>
            <span className="ml-3 text-gray-500 text-sm self-center">
              {fileName || "No file chosen"}
            </span>
          </div>
        </div>

        {availableHeaders.length > 0 && (
          <div>
            <label htmlFor="email-column" className="block text-sm font-medium text-gray-700 mb-1">
              Email Column Header
            </label>
            <select
              id="email-column"
              value={emailColumnHeader}
              onChange={handleHeaderChange}
              className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm 
                focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            >
              {availableHeaders.map(header => (
                <option key={header} value={header}>
                  {header}
                </option>
              ))}
            </select>
          </div>
        )}

        {error && (
          <div className="text-red-500 text-sm mt-1">
            {error}
          </div>
        )}

        {recipients.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-1">
              {recipients.length} Recipients Found
            </h3>
            <div className="mt-1 max-h-40 overflow-y-auto bg-white border border-gray-200 rounded-md p-2">
              <ul className="list-disc pl-5 space-y-1">
                {recipients.slice(0, 10).map((email, index) => (
                  <li key={index} className="text-xs text-gray-600">
                    {email}
                  </li>
                ))}
                {recipients.length > 10 && (
                  <li className="text-xs text-gray-500">
                    ... and {recipients.length - 10} more
                  </li>
                )}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default RecipientsUpload; 