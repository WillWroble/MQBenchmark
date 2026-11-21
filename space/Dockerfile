FROM python:3.12-slim
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app
COPY --chown=user space/requirements.txt space/requirements.txt
RUN pip install --no-cache-dir -r space/requirements.txt
COPY --chown=user . .
CMD ["python", "-m", "uvicorn", "space.app:app", "--host", "0.0.0.0", "--port", "7860"]
