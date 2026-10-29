import { useState } from 'react'
import ApiKeyConfig from './components/ApiKeyConfig'
import RecipientsUpload from './components/RecipientsUpload'
import ContentManager from './components/ContentManager'
import EmailSender from './components/EmailSender'

function App() {
  const [apiKey, setApiKey] = useState('')
  const [fromEmail, setFromEmail] = useState('')
  const [recipients, setRecipients] = useState([])
  const [emailContent, setEmailContent] = useState({
    subject: '',
    htmlContent: '',
    imagePath: null
  })
  const [imageFile, setImageFile] = useState(null)
  const [sendingStatus, setSendingStatus] = useState({
    status: 'idle', // 'idle', 'sending', 'success', 'error'
    message: ''
  })

  return (
    <div className="min-h-screen bg-gray-100 py-6 flex flex-col justify-center sm:py-12">
      <div className="relative py-3 sm:max-w-3xl sm:mx-auto">
        <div className="relative px-4 py-10 bg-white shadow-lg sm:rounded-3xl sm:p-10">
          <h1 className="text-3xl font-bold mb-6 text-center text-gray-800">SendGrid Email Manager</h1>
          
          <div className="space-y-8">
            <ApiKeyConfig 
              apiKey={apiKey} 
              setApiKey={setApiKey}
              fromEmail={fromEmail}
              setFromEmail={setFromEmail}
            />
            
            <RecipientsUpload 
              setRecipients={setRecipients} 
              recipients={recipients}
            />
            
            <ContentManager 
              emailContent={emailContent}
              setEmailContent={setEmailContent}
              setImageFile={setImageFile}
            />
            
            <EmailSender 
              apiKey={apiKey}
              fromEmail={fromEmail}
              recipients={recipients}
              emailContent={emailContent}
              imageFile={imageFile}
              sendingStatus={sendingStatus}
              setSendingStatus={setSendingStatus}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
