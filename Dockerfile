FROM python:3.11-slim

WORKDIR /pokemon
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/app.py .
COPY src/templates/ templates/

ENV FLASK_SECRET_KEY=change-me-in-production
EXPOSE 5000

CMD ["python", "src/app.py"]