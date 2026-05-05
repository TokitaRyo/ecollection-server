# 1. Use an official Python runtime as a parent image
FROM python:3.11-slim
 
# 2. Set the working directory inside the container
WORKDIR /app
 
# 3. Copy the requirements file into the container
COPY requirements.txt .
 
# 4. Install the needed packages
RUN pip install --no-cache-dir -r requirements.txt
 
# 5. Copy the rest of your application code
COPY . .
 
# 6. Run the application using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]