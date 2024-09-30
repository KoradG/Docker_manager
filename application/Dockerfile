# Use a lightweight Python image as the base
FROM python:3.9-slim

# Set metadata as described above
LABEL maintainer="Your Name <your.email@example.com>"
LABEL version="1.0"
LABEL description="A simple Flask API application."

# Set build arguments
ARG APP_ENV=production
ENV APP_ENV=${APP_ENV}

# Set environment variables
ENV MY_ENV_VAR="Hello, World!" 
ENV PORT=5000

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the port the app runs on
EXPOSE ${PORT}

# Create a volume for data persistence (optional)
VOLUME ["/app/data"]

# Run the application
CMD ["python", "app.py"]
