# Threshold Urban Growth - Backend API

A FastAPI backend for the urban growth visualization platform with MongoDB integration.

## Project Structure

```
Backend/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── config.example.env      # Environment configuration example
├── api/
│   └── routes/
│       ├── auth.py        # Authentication routes
│       └── users.py       # User management routes
├── database/
│   └── connection.py      # MongoDB connection
├── models/
│   └── user.py           # User data models
├── services/
│   └── user_service.py   # User business logic
└── utils/
    └── auth.py           # Authentication utilities
```

## Features

- **User Registration**: Create new accounts with name, email, password, and profession
- **User Authentication**: JWT-based login system
- **Password Security**: Bcrypt password hashing
- **Database**: MongoDB with Motor async driver
- **API Documentation**: Automatic OpenAPI/Swagger docs
- **CORS Support**: Cross-origin resource sharing for frontend integration

## User Professions

- Citizen
- Builder
- Urban Contractor
- Other

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Create new user account
- `POST /api/auth/login` - Authenticate and get access token
- `GET /api/auth/me` - Get current user information
- `POST /api/auth/verify-token` - Verify access token

### Users
- `GET /api/users/profile` - Get user profile
- `GET /api/users/{user_id}` - Get user by ID

## Setup Instructions

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   - Copy `config.example.env` to `.env`
   - Update MongoDB URL and other settings as needed

3. **Start MongoDB**:
   - Ensure MongoDB is running locally or configure remote connection

4. **Run the Server**:
   ```bash
   python main.py
   ```

5. **API Documentation**:
   - Visit `http://localhost:8000/docs` for interactive API documentation
   - Visit `http://localhost:8000/redoc` for alternative documentation

## Environment Variables

- `MONGODB_URL`: MongoDB connection string
- `DATABASE_NAME`: Database name
- `SECRET_KEY`: JWT secret key
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time

## Development

The server runs with auto-reload enabled for development. Any changes to the code will automatically restart the server.
