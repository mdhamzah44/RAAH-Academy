# RAAH Academy

RAAH Academy is an interactive online learning platform that facilitates real-time communication between educators and students. This web-based application supports live video streaming, interactive whiteboard functionality, and various engagement tools to enhance the online learning experience.

## Author

Mohd Hamzah
```
 For Live Demo Visit :- https://app.arkvision.online
```
## Features

- User authentication and role-based access control (teacher/student)
- Real-time video streaming for educators
- Interactive whiteboard with various drawing tools
- Live polling system with real-time results
- Comment section for student-teacher interaction
- Class creation and management for teachers
- Student enrollment system
- Responsive design for cross-device compatibility

## Technologies Used

- Frontend: HTML5, CSS3, JavaScript, Canvas API
- Backend: Python, Flask
- Database: MySQL
- Real-time Communication: Socket.IO, WebRTC
- PDF Handling: pdfkit

## Setup and Installation

1. Clone the repository:
   ```
   git clone https://github.com/mohdhamzah/raah-academy.git
   cd raah-academy
   ```

2. Set up a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Set up the MySQL database and update the configuration in `app.py`.

5. Run the application:
   ```
   python app.py
   ```

6. Access the application at `http://localhost:5000`

## Project Structure

- `app.py`: Main Flask application file
- `templates/`: HTML templates for the application
- `static/`: Static files (CSS, JavaScript, images)
- `data/`: Directory for storing JSON data files

## Contributing

Contributions to RAAH Academy are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Flask documentation
- Socket.IO documentation
- WebRTC documentation
