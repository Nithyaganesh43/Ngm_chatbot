const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
require('dotenv').config();
const app = express();
app.use(express.json());
app.use(cors(
    {origin: 'http://localhost:3000', optionsSuccessStatus: 200}
));

// MongoDB Models
const chatSchema = new mongoose.Schema({
  title: { type: String, required: true, maxLength: 255 },
  createdAt: { type: Date, default: Date.now },
});

const conversationSchema = new mongoose.Schema({
  chatId: { type: mongoose.Schema.Types.ObjectId, ref: 'Chat', required: true },
  role: { type: String, enum: ['user', 'AI'], required: true },
  message: { type: String, required: true },
  createdAt: { type: Date, default: Date.now },
});

const Chat = mongoose.model('Chat', chatSchema);
const Conversation = mongoose.model('Conversation', conversationSchema);

// PDF Links
const pdfLinks = {
  'PG-SF-1-TT-TEST-I-AUGUST-2025':
    'https://coe.ngmc.ac.in/wp-content/uploads/files/timetable/PG-SF-1-TT-TEST-I-AUGUST-2025.pdf',
  'PG-SF-3-TT-TEST-I-AUGUST-2025':
    'https://coe.ngmc.ac.in/wp-content/uploads/files/timetable/PG-SF-3-TT-TEST-I-AUGUST-2025.pdf',
  'UG-1TT-F_N-TEST-I-AUGUST-2025':
    'https://coe.ngmc.ac.in/wp-content/uploads/files/timetable/UG-1TT-F_N-TEST-I-AUGUST-2025.pdf',
  'UG-3TT-F_N-TEST-I-AUGUST-2025':
    'https://coe.ngmc.ac.in/wp-content/uploads/files/timetable/UG-3TT-F_N-TEST-I-AUGUST-2025.pdf',
  'UG-5TT-F_N-TEST-I-AUGUST-2025':
    'https://coe.ngmc.ac.in/wp-content/uploads/files/timetable/UG-5TT-F_N-TEST-I-AUGUST-2025.pdf',
  'UG-SF-1-TT-AN-New-TEST-I-AUGUST-2025':
    'https://coe.ngmc.ac.in/wp-content/uploads/files/timetable/UG-SF-1-TT-AN-New-TEST-I-AUGUST-2025.pdf',
  'SF-TEST-I-SEATING-ARRANGEMENT':
    'https://coe.ngmc.ac.in/wp-content/uploads/files/Seating/SF-TEST-I-SEATING-ARRANGEMENT-23_08_2025-FN.pdf',
};

// Random responses (short and long)
const randomResponses = [
  'Hello! How can I help you today?',
  'Thanks for your query.',
  'NGMC is a premier institution in Pollachi, Tamil Nadu.',
  'Nallamuthu Gounder Mahalingam College (NGMC), located in Pollachi, is an esteemed institution known for its dedication to quality education and research. It offers a variety of undergraduate and postgraduate courses across diverse fields such as Computer Science, Mathematics, Information Technology, Commerce, Business Administration, and more.',
  'Sure, I can help you with that information.',
  'Please check our official website for more details.',
  'The college offers excellent facilities and experienced faculty members.',
  'For admission queries, please contact our admissions office directly.',
  'Our placement cell has good connections with various companies in the industry.',
  'NGMC provides state-of-the-art infrastructure and modern laboratories for practical learning.',
  'The college has a rich history of academic excellence and student development programs.',
  'We offer both undergraduate and postgraduate programs in multiple disciplines including Engineering, Arts, Science, and Management.',
  'For specific course details and eligibility criteria, please visit the respective department offices.',
  'The campus provides hostel facilities, library, sports complex, and other student amenities.',
  'Contact the college administration for any specific queries or concerns.',
  'Check the notice board for latest updates.',
  'Visit our website: https://www.ngmc.org',
];

// Generate random response with occasional PDF links
function generateRandomResponse(userMessage) {
  const message = userMessage.toLowerCase();

  // Check for specific keywords to include PDF links
  if (
    message.includes('seating') ||
    message.includes('seat') ||
    message.includes('allotment')
  ) {
    const responses = [
      'You can find the seating arrangements for the tests at this link: [Seating Arrangement](https://coe.ngmc.ac.in/wp-content/uploads/files/Seating/SF-TEST-I-SEATING-ARRANGEMENT-23_08_2025-FN.pdf)',
      "Here's the seating allotment: [Download PDF](https://coe.ngmc.ac.in/wp-content/uploads/files/Seating/SF-TEST-I-SEATING-ARRANGEMENT-23_08_2025-FN.pdf)",
      'Check the seating arrangement document: [Seating PDF](https://coe.ngmc.ac.in/wp-content/uploads/files/Seating/SF-TEST-I-SEATING-ARRANGEMENT-23_08_2025-FN.pdf)',
    ];
    return responses[Math.floor(Math.random() * responses.length)];
  }

  if (
    message.includes('timetable') ||
    message.includes('schedule') ||
    message.includes('time table')
  ) {
    const pdfKeys = Object.keys(pdfLinks).filter((key) => key.includes('TT'));
    const randomPdf = pdfKeys[Math.floor(Math.random() * pdfKeys.length)];
    const pdfUrl = pdfLinks[randomPdf];
    return `Here's the timetable for your reference: [${randomPdf}](${pdfUrl})`;
  }

  if (message.includes('test') || message.includes('exam')) {
    const testPdfs = Object.keys(pdfLinks).filter((key) =>
      key.includes('TEST')
    );
    const randomPdf = testPdfs[Math.floor(Math.random() * testPdfs.length)];
    const pdfUrl = pdfLinks[randomPdf];
    return `Check this test schedule: [${randomPdf}](${pdfUrl})`;
  }

  // 20% chance to include a random PDF link
  if (Math.random() < 0.2) {
    const pdfKeys = Object.keys(pdfLinks);
    const randomPdf = pdfKeys[Math.floor(Math.random() * pdfKeys.length)];
    const pdfUrl = pdfLinks[randomPdf];
    const baseResponse =
      randomResponses[Math.floor(Math.random() * randomResponses.length)];
    return `${baseResponse} You might also find this useful: [${randomPdf}](${pdfUrl})`;
  }

  return randomResponses[Math.floor(Math.random() * randomResponses.length)];
}

// Generate random title
function generateRandomTitle(userMessage) {
  const titles = [
    'General Inquiry',
    'Course Information',
    'Admission Query',
    'Seating Arrangements',
    'Timetable Request',
    'Test Schedule',
    'About NGMC',
    'Student Services',
    'Academic Information',
    'Campus Facilities',
    'Examination Details',
    'Seating Allotment Information',
    'About Nallamuthu Gounder Mahalingam College',
  ];

  const message = userMessage.toLowerCase();
  if (message.includes('seating') || message.includes('seat'))
    return 'Seating Arrangements';
  if (message.includes('timetable') || message.includes('schedule'))
    return 'Timetable Request';
  if (message.includes('test') || message.includes('exam'))
    return 'Test Schedule';
  if (message.includes('admission')) return 'Admission Query';
  if (message.includes('about') || message.includes('college'))
    return 'About Nallamuthu Gounder Mahalingam College';

  return titles[Math.floor(Math.random() * titles.length)];
}

// Validation function
function validateMessage(msg) {
  if (!msg || msg.trim().length === 0) return 'Valid message is required';
  if (msg.length > 1000) return 'Message too long (max 1000 chars)';
  return null;
}

// Auth middleware
function authRequired(req, res, next) {
  const password = req.headers['x-api-key'];
  if (password !== process.env.PASSWORD) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

// Delay function to simulate processing time
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Routes
// GET /checkAuth - Check authentication if successful save the password in local storage
app.get('/checkAuth', authRequired, (req, res) => {
  res.json({ status: 'Authorized' });   
});

// POST /postchat/ - Create new chat
app.post('/postchat/', authRequired, async (req, res) => {
  try {
    const { message } = req.body;
    const userMessage = message?.trim();

    const validationError = validateMessage(userMessage);
    if (validationError) {
      return res.status(400).json({ error: validationError });
    }

    // Random delay between 500ms to 2000ms
    const randomDelay = Math.floor(Math.random() * 1500) + 500;
    await delay(randomDelay);

    // Generate random response and title
    const reply = generateRandomResponse(userMessage);
    const title = generateRandomTitle(userMessage);

    // Create new chat
    const chat = new Chat({ title });
    await chat.save();

    // Create conversations
    const conversations = [
      new Conversation({
        chatId: chat._id,
        role: 'user',
        message: userMessage,
      }),
      new Conversation({ chatId: chat._id, role: 'AI', message: reply }),
    ];

    await Conversation.insertMany(conversations);

    // Mock cost logging
    const mockTokens = Math.floor(Math.random() * 200) + 50;
    const mockCost = (Math.random() * 0.5).toFixed(2);
    console.log(
      `[LOG] Tokens used → prompt=${mockTokens}, completion=${Math.floor(
        mockTokens / 2
      )}, total=${mockTokens + Math.floor(mockTokens / 2)}, cost≈₹${mockCost}`
    );

    res.json({
      chatId: chat._id,
      reply: reply,
      title: title,
    });
  } catch (error) {
    console.error('Error in post_chat:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// POST /postchat/:chat_id/ - Continue existing chat
app.post('/postchat/:chat_id/', authRequired, async (req, res) => {
  try {
    const { chat_id } = req.params;
    const { message } = req.body;
    const userMessage = message?.trim();

    const validationError = validateMessage(userMessage);
    if (validationError) {
      return res.status(400).json({ error: validationError });
    }

    // Check if chat exists
    const chat = await Chat.findById(chat_id);
    if (!chat) {
      return res.status(404).json({ error: 'Chat not found' });
    }

    // Random delay between 500ms to 2000ms
    const randomDelay = Math.floor(Math.random() * 1500) + 500;
    await delay(randomDelay);

    // Generate random response
    const reply = generateRandomResponse(userMessage);

    // Create conversations
    const conversations = [
      new Conversation({
        chatId: chat._id,
        role: 'user',
        message: userMessage,
      }),
      new Conversation({ chatId: chat._id, role: 'AI', message: reply }),
    ];

    await Conversation.insertMany(conversations);

    // Mock cost logging
    const mockTokens = Math.floor(Math.random() * 200) + 50;
    const mockCost = (Math.random() * 0.5).toFixed(2);
    console.log(
      `[LOG] Tokens used → prompt=${mockTokens}, completion=${Math.floor(
        mockTokens / 2
      )}, total=${mockTokens + Math.floor(mockTokens / 2)}, cost≈₹${mockCost}`
    );

    res.json({
      chatId: chat._id,
      reply: reply,
    });
  } catch (error) {
    console.error('Error in continue_chat:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// GET /getchat/ - Get all chats with conversations
app.get('/getchat/', authRequired, async (req, res) => {
  try {
    const chats = await Chat.find().sort({ _id: -1 });
    const chatsData = [];

    for (const chat of chats) {
      const conversations = await Conversation.find({ chatId: chat._id }).sort({
        createdAt: 1,
      });

      chatsData.push({
        id: chat._id,
        title: chat.title,
        created_at: chat.createdAt.toISOString(),
        conversations: conversations.map((conv) => ({
          id: conv._id,
          role: conv.role,
          message: conv.message,
          created_at: conv.createdAt.toISOString(),
        })),
      });
    }

    res.json(chatsData);
  } catch (error) {
    console.error('Error in get_chats:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'OK',
    message: 'NGMC Mock Chatbot Server is running',
    timestamp: new Date().toISOString(),
  });
});

// Initialize server
const PORT = process.env.PORT || 8000;
// MongoDB connection
mongoose
  .connect(process.env.MONOGDB_CONNECTION_STRING+'_mock')
  .then(() => {
    console.log('✅ Connected to MongoDB')


app.listen(PORT, '0.0.0.0', () => {
  console.log('Starting NGMC Chatbot Server...');
  console.log(`Server will start at http://0.0.0.0:${PORT}`);
  console.log('Database initialized successfully!');
  console.log('🚀 NGMC Mock Chatbot Server started successfully!');
});
})
  .catch((err) => console.error('❌ MongoDB error:', err));
