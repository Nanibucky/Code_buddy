# Code Buddy

![Code Buddy](https://github.com/Nanibucky/Code_buddy/blob/main/images/image.png))

Code Buddy is an interactive coding platform that enhances your programming skills through AI-powered challenges, real-time collaboration, and personalized assistance.

## Features

### 🚀 AI-Powered Coding Challenges
- **Dynamic Question Generation**: Get unique coding problems tailored to your skill level
- **Multiple Difficulty Levels**: Choose from easy, medium, or hard challenges
- **Topic Selection**: Focus on specific programming concepts or algorithms
- **Automated Test Cases**: Verify your solutions with comprehensive test cases

### 👥 Collaborative Coding
- **Coding Rooms**: Create or join rooms to code with friends in real-time
- **Screen Sharing**: Share your screen to collaborate on complex problems
- **Real-time Code Synchronization**: See changes as they happen
- **Room Management**: Create rooms with specific difficulty levels and topics

### 🤖 Intelligent Coding Assistant
- **Personalized Help**: Get hints and guidance when you're stuck
- **Code Analysis**: Receive feedback on your solution approach
- **Concept Explanations**: Learn programming concepts as you solve problems
- **Debugging Assistance**: Get help identifying and fixing bugs in your code

### 💻 Modern Coding Environment
- **Syntax Highlighting**: Code with a beautiful, customized Monaco editor
- **Code Formatting**: Automatic indentation and formatting
- **Mobile-Friendly Interface**: Code on any device with a responsive design
- **User Authentication**: Secure login and account management

## Getting Started

### Prerequisites
- Python 3.8 or higher
- Node.js and npm (for frontend dependencies)
- OpenAI API key (for AI features)

### Installation

1. Clone the repository
   ```
   git clone https://github.com/Nanibucky/Code_buddy.git
   cd code-buddy
   ```

2. Install Python dependencies
   ```
   pip install -r requirements.txt
   ```

3. Install Node.js dependencies
   ```
   npm install
   ```

4. Create a `.env` file in the root directory with the following variables:
   ```
   SECRET_KEY=your_secret_key
   OPENAI_API_KEY=your_openai_api_key
   ```

5. Run the application
   ```
   python app.py
   ```

6. Open your browser and navigate to `http://localhost:5000`

## Technologies Used

### Backend
- **Flask**: Web framework
- **Socket.IO**: Real-time communication
- **OpenAI API**: AI-powered question generation and assistance
- **SQLite**: Database for user data and rooms

### Frontend
- **HTML/CSS/JavaScript**: Core web technologies
- **Bootstrap**: Responsive design framework
- **Monaco Editor**: Code editor with syntax highlighting
- **Socket.IO Client**: Real-time communication with the server

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for providing the AI capabilities
- Monaco Editor for the excellent code editing experience
- All contributors who have helped shape this project
