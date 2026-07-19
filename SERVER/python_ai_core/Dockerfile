FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install google-generativeai for actual LLM calls
RUN pip install --no-cache-dir google-generativeai google-genai

COPY . .

CMD ["python", "-u", "ai_supervisor.py"]
