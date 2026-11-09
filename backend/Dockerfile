# Image backend JedaCut untuk Hugging Face Spaces (Docker SDK).
# Basis Debian 13 "trixie" karena render.py memakai opsi -/filter_complex yang butuh FFmpeg 7.0+
# (trixie membawa FFmpeg 7.1). Basis bookworm hanya FFmpeg 5.1 sehingga render akan gagal.
FROM python:3.12-slim-trixie

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# HF Spaces menjalankan container sebagai user ID 1000. Folder app harus milik user ini
# karena main.py menulis file upload ke storage/ di sebelahnya.
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user *.py ./

EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
