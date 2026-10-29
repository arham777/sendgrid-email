// Test script to check if the server is running properly
import http from 'http';

const options = {
  hostname: 'localhost',
  port: 3001,
  path: '/',
  method: 'GET'
};

console.log('Testing connection to server at http://localhost:3001...');

const req = http.request(options, (res) => {
  console.log(`Server response status code: ${res.statusCode}`);
  
  let data = '';
  res.on('data', (chunk) => {
    data += chunk;
  });
  
  res.on('end', () => {
    console.log('Connection successful!');
    if (data.length < 1000) {
      console.log('Response data:', data);
    } else {
      console.log(`Response received (${data.length} bytes)`);
    }
  });
});

req.on('error', (error) => {
  console.error('Connection failed!');
  console.error(`Error: ${error.message}`);
  
  if (error.code === 'ECONNREFUSED') {
    console.error('\nTroubleshooting tips:');
    console.error('1. Make sure the server is running with: npm run start-backend');
    console.error('2. Check for any error messages when starting the server');
    console.error('3. Verify no other process is using port 3001');
    console.error('4. Try restarting your machine if all else fails');
  }
});

req.end(); 