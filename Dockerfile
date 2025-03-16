# Use Python base image
FROM python:3.13

RUN apt-get update && apt-get install -y libpq-dev

# Set the working directory inside the container
WORKDIR /app

# Copy project files to the container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask default port
EXPOSE 5000

# Run the Flask app
CMD ["python", "run.py"]
