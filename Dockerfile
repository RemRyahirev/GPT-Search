FROM python:3 as base

ENV PYTHONUNBUFFERED 1

WORKDIR /opt/app

RUN groupadd -g 999 appuser && \
    useradd -m -r -u 999 -g appuser appuser && \
    chown -R appuser:appuser /opt/app

USER appuser

COPY --chown=appuser:appuser app/requirements.txt ./

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY --chown=appuser:appuser app/ ./

ENV FLASK_APP app.py
ENV FLASK_ENVIRONMENT development
EXPOSE 5000

ENTRYPOINT python -m flask run --host=0.0.0.0