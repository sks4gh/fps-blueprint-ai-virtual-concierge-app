# Use a Python base image
FROM python:3.9-slim-buster

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
# We copy it from the build context root, which is 'virtual-concierge-app/'
COPY reservation-api-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code of the API service
# We copy it from the build context root, which is 'virtual-concierge-app/'
COPY reservation-api-service/src/ .

# Expose the port on which the FastAPI application will run
EXPOSE 8000

# Command to run the FastAPI application using Uvicorn
# --host 0.0.0.0 makes the server accessible from outside the container
# --port 8000 specifies the port
# main:app refers to the 'app' object in 'main.py'
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
