import { useState } from 'react';

function ApiKeyConfig({ apiKey, setApiKey, fromEmail, setFromEmail }) {
  const [showApiKey, setShowApiKey] = useState(false);

  return (
    <div className="bg-gray-50 p-4 rounded-lg shadow-sm border border-gray-200">
      <h2 className="text-xl font-semibold mb-4 text-gray-700">SendGrid Configuration</h2>
      
      <div className="space-y-4">
        <div>
          <label htmlFor="api-key" className="block text-sm font-medium text-gray-700 mb-1">
            SendGrid API Key
          </label>
          <div className="relative">
            <input
              id="api-key"
              type={showApiKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Enter your SendGrid API Key"
            />
            <button
              type="button"
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-sm leading-5 text-gray-500 hover:text-gray-700"
              onClick={() => setShowApiKey(!showApiKey)}
            >
              {showApiKey ? "Hide" : "Show"}
            </button>
          </div>
          <p className="mt-1 text-sm text-gray-500">
            Find this in your SendGrid account settings.
          </p>
        </div>

        <div>
          <label htmlFor="from-email" className="block text-sm font-medium text-gray-700 mb-1">
            From Email Address
          </label>
          <input
            id="from-email"
            type="email"
            value={fromEmail}
            onChange={(e) => setFromEmail(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            placeholder="your-verified@email.com"
          />
          <p className="mt-1 text-sm text-gray-500">
            Must be a verified sender in your SendGrid account.
          </p>
        </div>
      </div>
    </div>
  );
}

export default ApiKeyConfig; 