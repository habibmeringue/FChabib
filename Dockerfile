# ---- Base image ----
FROM python:3.11-slim

# ---- Install Chrome & dependencies ----
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg \
    libnss3 libxss1 libasound2 fonts-liberation libatk-bridge2.0-0 \
    libgtk-3-0 libdrm2 libgbm1 xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb

# Install chromedriver matching chrome
RUN CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+') \
    && DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}") \
    && wget -q "https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip" \
    && unzip chromedriver_linux64.zip -d /usr/local/bin/ \
    && rm chromedriver_linux64.zip

# ---- Python deps ----
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- App ----
COPY . /app

ENV TELEGRAM_TOKEN=""
ENV CHROMEDRIVER_PATH="/usr/local/bin/chromedriver"

CMD ["python", "main.py"]
