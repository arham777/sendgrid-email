import { useState, useRef, useEffect } from 'react';
import Papa from 'papaparse';

function ContentManager({ emailContent, setEmailContent, setImageFile }) {
  const [contentSource, setContentSource] = useState('input');
  const [csvFile, setCsvFile] = useState(null);
  const [csvFileName, setCsvFileName] = useState('');
  const [csvHeaders, setCsvHeaders] = useState({
    subject: 'Subject',
    htmlBody: 'HTML_Body',
    imagePath: 'Image_Attachment_Path'
  });
  const [csvParseError, setCsvParseError] = useState('');
  const [imageFileName, setImageFileName] = useState('');
  const [showHtmlPreview, setShowHtmlPreview] = useState(false);
  const [inlineImageCount, setInlineImageCount] = useState(0);
  const imageInputRef = useRef(null);
  const inlineImageInputRef = useRef(null);
  const editorRef = useRef(null);

  // Initialize editor content when component mounts
  useEffect(() => {
    if (editorRef.current && !editorRef.current.innerHTML) {
      editorRef.current.innerHTML = emailContent.htmlContent || '';
    }
  }, [emailContent.htmlContent]);

  const handleContentSourceChange = (source) => {
    setContentSource(source);
  };

  const handleSubjectChange = (e) => {
    setEmailContent({
      ...emailContent,
      subject: e.target.value
    });
  };

  const handleFormatText = (command, value = null) => {
    document.execCommand(command, false, value);
    handleEditorChange();
  };

  const handleEditorChange = () => {
    if (editorRef.current) {
      const content = editorRef.current.innerHTML;
      if (content !== emailContent.htmlContent) {
        setEmailContent({
          ...emailContent,
          htmlContent: content
        });
      }
    }
  };

  // Add focus handler to set initial placeholder
  const handleEditorFocus = (e) => {
    if (!emailContent.htmlContent && e.target.innerHTML === '') {
      e.target.innerHTML = '';
    }
  };

  // Add blur handler to restore placeholder if empty
  const handleEditorBlur = (e) => {
    if (!e.target.innerHTML.trim()) {
      e.target.innerHTML = '';
    }
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setImageFileName(file.name);
    setImageFile(file);
    
    // Update the path in emailContent
    setEmailContent({
      ...emailContent,
      imagePath: file.name
    });
  };

  const handleInlineImageUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const imageId = `inline_image_${inlineImageCount}`;
      setInlineImageCount(prev => prev + 1);
      
      if (editorRef.current) {
        const imageHtml = `<img src="${e.target.result}" alt="${file.name}" style="max-width: 100%; height: auto; display: block; margin: 0;" />`;
        document.execCommand('insertHTML', false, imageHtml);
        handleEditorChange();
      }
    };
    reader.readAsDataURL(file);
  };

  const handleCsvUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setCsvFileName(file.name);
    setCsvFile(file);
    setCsvParseError('');

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: function(results) {
        if (results.errors.length > 0) {
          setCsvParseError(`Error parsing CSV: ${results.errors[0].message}`);
          return;
        }

        if (results.data.length === 0) {
          setCsvParseError('CSV file is empty or contains only headers.');
          return;
        }

        const availableHeaders = results.meta.fields;
        
        // Auto-detect headers
        const subjectHeader = availableHeaders.find(h => 
          h.toLowerCase().includes('subject')) || csvHeaders.subject;
        
        const htmlHeader = availableHeaders.find(h => 
          h.toLowerCase().includes('html') || h.toLowerCase().includes('body')) || csvHeaders.htmlBody;
        
        const imageHeader = availableHeaders.find(h => 
          h.toLowerCase().includes('image') || h.toLowerCase().includes('attachment')) || csvHeaders.imagePath;

        setCsvHeaders({
          subject: subjectHeader,
          htmlBody: htmlHeader,
          imagePath: imageHeader
        });

        // Extract content from first row
        const firstRow = results.data[0];
        
        if (firstRow[subjectHeader] && firstRow[htmlHeader]) {
          setEmailContent({
            subject: firstRow[subjectHeader].trim(),
            htmlContent: firstRow[htmlHeader].trim(),
            imagePath: firstRow[imageHeader] ? firstRow[imageHeader].trim() : null
          });
          
          // Show warning if image path is provided but not a URL
          if (firstRow[imageHeader] && firstRow[imageHeader].trim()) {
            const imagePath = firstRow[imageHeader].trim();
            if (!imagePath.startsWith('http://') && !imagePath.startsWith('https://')) {
              setCsvParseError('Note: Local image path detected. The server will try to find this file.');
            }
          }
        } else {
          setCsvParseError('Required content columns not found in CSV.');
        }
      }
    });
  };

  const fontSizes = [
    { label: 'Small', value: '1' },
    { label: 'Normal', value: '3' },
    { label: 'Large', value: '5' },
    { label: 'Huge', value: '7' }
  ];

  const fontFamilies = [
    { label: 'Arial', value: 'Arial, sans-serif' },
    { label: 'Times New Roman', value: 'Times New Roman, serif' },
    { label: 'Courier New', value: 'Courier New, monospace' },
    { label: 'Georgia', value: 'Georgia, serif' },
    { label: 'Verdana', value: 'Verdana, sans-serif' }
  ];

  const colors = [
    { label: 'Black', value: '#000000' },
    { label: 'Red', value: '#FF0000' },
    { label: 'Green', value: '#008000' },
    { label: 'Blue', value: '#0000FF' },
    { label: 'Purple', value: '#800080' }
  ];

  return (
    <div className="bg-gray-50 p-4 rounded-lg shadow-sm border border-gray-200">
      <h2 className="text-xl font-semibold mb-4 text-gray-700">Email Content</h2>
      
      <div className="space-y-5">
        <div>
          <span className="block text-sm font-medium text-gray-700 mb-2">Content Source</span>
          <div className="flex space-x-4">
            <button
              type="button"
              onClick={() => handleContentSourceChange('input')}
              className={`px-4 py-2 text-sm font-medium rounded-md ${
                contentSource === 'input'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300'
              }`}
            >
              Direct Input
            </button>
            <button
              type="button"
              onClick={() => handleContentSourceChange('csv')}
              className={`px-4 py-2 text-sm font-medium rounded-md ${
                contentSource === 'csv'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300'
              }`}
            >
              CSV File
            </button>
          </div>
        </div>

        {contentSource === 'input' ? (
          <>
            <div>
              <label htmlFor="subject" className="block text-sm font-medium text-gray-700 mb-1">
                Subject
              </label>
              <input
                id="subject"
                type="text"
                value={emailContent.subject}
                onChange={handleSubjectChange}
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="Email Subject"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email Content
              </label>
              
              {/* Formatting Toolbar */}
              <div className="mb-2 p-2 bg-gray-100 border border-gray-300 rounded-t-md flex flex-wrap gap-2">
                {/* Text Style Controls */}
                <div className="flex items-center space-x-1 border-r pr-2">
                  <button
                    type="button"
                    onClick={() => handleFormatText('bold')}
                    className="p-1 hover:bg-gray-200 rounded"
                    title="Bold"
                  >
                    <strong>B</strong>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleFormatText('italic')}
                    className="p-1 hover:bg-gray-200 rounded"
                    title="Italic"
                  >
                    <em>I</em>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleFormatText('underline')}
                    className="p-1 hover:bg-gray-200 rounded"
                    title="Underline"
                  >
                    <u>U</u>
                  </button>
                </div>

                {/* Font Family */}
                <select
                  onChange={(e) => handleFormatText('fontName', e.target.value)}
                  className="px-2 py-1 border rounded text-sm"
                  title="Font Family"
                >
                  <option value="">Font</option>
                  {fontFamilies.map((font) => (
                    <option key={font.value} value={font.value}>
                      {font.label}
                    </option>
                  ))}
                </select>

                {/* Font Size */}
                <select
                  onChange={(e) => handleFormatText('fontSize', e.target.value)}
                  className="px-2 py-1 border rounded text-sm"
                  title="Font Size"
                >
                  <option value="">Size</option>
                  {fontSizes.map((size) => (
                    <option key={size.value} value={size.value}>
                      {size.label}
                    </option>
                  ))}
                </select>

                {/* Text Color */}
                <select
                  onChange={(e) => handleFormatText('foreColor', e.target.value)}
                  className="px-2 py-1 border rounded text-sm"
                  title="Text Color"
                >
                  <option value="">Color</option>
                  {colors.map((color) => (
                    <option key={color.value} value={color.value}>
                      {color.label}
                    </option>
                  ))}
                </select>

                {/* Alignment Controls */}
                <div className="flex items-center space-x-1 border-l pl-2">
                  <button
                    type="button"
                    onClick={() => handleFormatText('justifyLeft')}
                    className="p-1 hover:bg-gray-200 rounded"
                    title="Align Left"
                  >
                    ←
                  </button>
                  <button
                    type="button"
                    onClick={() => handleFormatText('justifyCenter')}
                    className="p-1 hover:bg-gray-200 rounded"
                    title="Center"
                  >
                    ↔
                  </button>
                  <button
                    type="button"
                    onClick={() => handleFormatText('justifyRight')}
                    className="p-1 hover:bg-gray-200 rounded"
                    title="Align Right"
                  >
                    →
                  </button>
                </div>

                {/* List Controls */}
                <div className="flex items-center space-x-1 border-l pl-2">
                  <button
                    type="button"
                    onClick={() => handleFormatText('insertUnorderedList')}
                    className="p-1 hover:bg-gray-200 rounded"
                    title="Bullet List"
                  >
                    •
                  </button>
                  <button
                    type="button"
                    onClick={() => handleFormatText('insertOrderedList')}
                    className="p-1 hover:bg-gray-200 rounded"
                    title="Numbered List"
                  >
                    1.
                  </button>
                </div>

                {/* Add Insert Image button in toolbar */}
                <div className="flex items-center space-x-1 border-l pl-2">
                  <input
                    ref={inlineImageInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleInlineImageUpload}
                    className="sr-only"
                  />
                  <button
                    type="button"
                    onClick={() => inlineImageInputRef.current?.click()}
                    className="p-1 hover:bg-gray-200 rounded"
                    title="Insert Image"
                  >
                    📷
                  </button>
                </div>

                {/* Preview Toggle */}
                <button
                  type="button"
                  onClick={() => setShowHtmlPreview(!showHtmlPreview)}
                  className="ml-auto px-2 py-1 text-sm border rounded hover:bg-gray-200"
                >
                  {showHtmlPreview ? 'Hide HTML' : 'Show HTML'}
                </button>
              </div>

              {/* Editor Area */}
              <div className="border border-gray-300 rounded-b-md">
                <div
                  ref={editorRef}
                  contentEditable
                  onInput={handleEditorChange}
                  className="min-h-[200px] p-3 focus:outline-none text-gray-900 prose max-w-none"
                  style={{
                    direction: 'ltr',
                    unicodeBidi: 'embed'
                  }}
                  suppressContentEditableWarning={true}
                  onPaste={(e) => {
                    e.preventDefault();
                    const text = e.clipboardData.getData('text/plain');
                    document.execCommand('insertText', false, text);
                  }}
                />
              </div>

              {/* HTML Preview */}
              {showHtmlPreview && (
                <div className="mt-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    HTML Preview
                  </label>
                  <pre className="p-2 bg-gray-100 border rounded-md text-xs overflow-x-auto">
                    {emailContent.htmlContent}
                  </pre>
                </div>
              )}
            </div>

            <div>
              <label htmlFor="image-upload" className="block text-sm font-medium text-gray-700 mb-1">
                Add Image Attachment
              </label>
              <div className="space-y-3">
                <div className="flex items-center space-x-4">
                  <div className="flex">
                    <input
                      ref={imageInputRef}
                      id="image-upload"
                      name="image-upload"
                      type="file"
                      accept="image/*"
                      onChange={handleImageUpload}
                      className="sr-only"
                    />
                    <label
                      htmlFor="image-upload"
                      className="cursor-pointer inline-flex items-center px-4 py-2 border border-gray-300 
                        rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 
                        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      Choose Attachment
                    </label>
                    <span className="ml-3 text-gray-500 text-sm self-center">
                      {imageFileName || "No attachment chosen"}
                    </span>
                  </div>
                </div>
                <p className="text-sm text-gray-500">
                  This image will be sent as an email attachment.
                </p>
              </div>
            </div>
          </>
        ) : (
          <div>
            <label htmlFor="csv-upload" className="block text-sm font-medium text-gray-700 mb-1">
              Content CSV File
            </label>
            <div className="flex">
              <input
                id="csv-upload"
                name="csv-upload"
                type="file"
                accept=".csv"
                onChange={handleCsvUpload}
                className="sr-only"
              />
              <label
                htmlFor="csv-upload"
                className="cursor-pointer inline-flex items-center px-4 py-2 border border-gray-300 
                  rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 
                  focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              >
                Choose CSV
              </label>
              <span className="ml-3 text-gray-500 text-sm self-center">
                {csvFileName || "No file chosen"}
              </span>
            </div>
            
            {csvParseError && (
              <div className="mt-2 text-red-500 text-sm">
                {csvParseError}
              </div>
            )}

            {csvFileName && (
              <div className="mt-2 space-y-2">
                <p className="text-xs text-gray-600">
                  <strong>Tip:</strong> For the Image_Attachment_Path column, you can use:
                  <ul className="list-disc pl-5 mt-1">
                    <li>Just the filename (e.g., "logo.png") - will look in public/images folder</li>
                    <li>Path from project root (e.g., "public/images/logo.png")</li>
                    <li>Absolute path (e.g., "C:/Images/logo.png")</li>
                  </ul>
                </p>
                
                {!csvParseError && (
                  <div className="p-3 bg-white rounded-md border border-gray-200">
                    <h4 className="font-medium text-sm text-gray-700">Preview:</h4>
                    <div className="mt-1 grid grid-cols-2 gap-2 text-xs">
                      <span className="text-gray-500">Subject:</span>
                      <span className="font-medium">{emailContent.subject}</span>
                      
                      <span className="text-gray-500">HTML Content:</span>
                      <span className="font-medium">
                        {emailContent.htmlContent ? 
                          `${emailContent.htmlContent.substring(0, 50)}${emailContent.htmlContent.length > 50 ? '...' : ''}` 
                          : 'Not found'}
                      </span>
                      
                      <span className="text-gray-500">Image Path:</span>
                      <span className="font-medium">{emailContent.imagePath || 'Not specified'}</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ContentManager; 