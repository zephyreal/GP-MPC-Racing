FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 RACE_SANDBOX=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /runner
RUN pip install --no-cache-dir numpy==2.5.4 scipy==1.18.1
COPY gp_mpc_racing ./gp_mpc_racing
USER 65534:65534
ENTRYPOINT ["python", "-m", "gp_mpc_racing.agent_service"]
