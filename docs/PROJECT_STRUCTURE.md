# DHIS Project Structure

## Simplified Repository Structure

```
dhis/
├── backend/                 # Django Backend
│   ├── api/                # Main API application
│   │   ├── models.py       # Database models
│   │   ├── views.py        # API endpoints
│   │   ├── serializers.py  # Data serialization
│   │   ├── urls.py         # URL routing
│   │   ├── utils.py        # S3 & Portkey LLM handlers
│   │   └── middleware.py   # CSRF middleware
│   ├── image_processor/    # Django project settings
│   │   ├── settings.py     # Main settings
│   │   ├── urls.py         # Root URL config
│   │   └── wsgi.py         # WSGI application
│   ├── media/              # Uploaded images (git ignored)
│   ├── static/             # Static files (git ignored)
│   ├── Dockerfile          # Multi-stage Docker build
│   ├── requirements.txt    # Python dependencies
│   ├── environment.yml     # Conda environment config
│   ├── manage.py           # Django management
│   ├── start_local.sh      # Local dev with Conda
│   └── README_LOCAL.md     # Local development guide
│
├── frontend/               # React Frontend (Optional)
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API services
│   │   └── App.tsx         # Main app component
│   ├── public/
│   ├── package.json
│   ├── .env.example        # Frontend environment template
│   ├── start_local.sh      # Local dev startup script
│   ├── README_LOCAL.md     # Frontend dev guide
│   └── Dockerfile
│
├── nginx/                  # Nginx Configuration (Production)
│   ├── nginx.conf          # Main Nginx config
│   └── conf.d/
│       └── default.conf    # Server configuration
│
├── docker-compose.yml      # Single Docker Compose file
├── .env.example           # Single environment template
├── .env                   # Environment configuration (git ignored)
├── .gitignore             # Git ignore rules
├── start.sh               # Main startup script
└── README.md              # Project documentation
```

## Key Improvements

### 1. Single Docker Configuration
- **One Dockerfile** with multi-stage build (development/production)
- **One docker-compose.yml** with profiles for different modes
- Simplified container orchestration

### 2. Unified Environment Configuration
- **Single .env.example** file with all settings
- Clear separation of required vs optional settings
- Environment-based configuration

### 3. Simplified Scripts
- **start.sh**: Main script for Docker operations
- **backend/start_local.sh**: Local development with Conda

### 4. Clean Documentation
- **README.md**: Main documentation
- **PROJECT_STRUCTURE.md**: This file
- Removed duplicate/redundant docs

## Usage Modes

### Development Mode (Default)
```bash
./start.sh dev
```
- PostgreSQL database
- Django development server
- Hot reload enabled

### Production Mode
```bash
BUILD_TARGET=production ./start.sh prod
```
- PostgreSQL + Redis
- Gunicorn server
- Nginx reverse proxy
- Static file serving

### With Frontend
```bash
./start.sh full    # Includes React frontend
```

## Environment Variables

All configuration is in `.env`:
- Database settings (PostgreSQL)
- Portkey LLM configuration
- AWS S3 (optional)
- CORS settings
- Port configurations

## Benefits of Consolidation

1. **Easier Maintenance**: Single source of truth for each configuration type
2. **Reduced Complexity**: Fewer files to manage and understand
3. **Better Organization**: Clear separation of concerns
4. **Flexible Deployment**: Use profiles for different environments
5. **Cleaner Repository**: No duplicate or conflicting configurations