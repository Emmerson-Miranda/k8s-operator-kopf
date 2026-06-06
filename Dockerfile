FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY my_operator/ ./my_operator/
RUN pip install .
CMD ["kopf", "run", "my_operator/operator.py", "--all-namespaces"]
