# SAM 3 image PCS microservice (GPU).
# Meta ships no official image — this wraps facebookresearch/sam3 for HTTP.
# Context7 checked: /facebookresearch/sam3 — build_sam3_image_model + Sam3Processor.
FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models/huggingface

RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      libgl1 \
      libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# sam3 needs a recent pip / setuptools; install server deps first for layer cache
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
 && pip install --no-cache-dir "git+https://github.com/facebookresearch/sam3.git"

COPY server.py /app/server.py

EXPOSE 8090
VOLUME ["/models"]

# Weights download on first request (needs HF_TOKEN + gated access to facebook/sam3)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8090"]
