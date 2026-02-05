FROM python:3.11-slim-trixie

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml ./

# Copy all application code
COPY . .

# Install dependencies, build library, and cleanup in one layer to reduce image size
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        make \
        curl \
        libsixel-dev \
        python3-tk \
        cython3 \
        libcap2-bin \
        python3-dev \
        python3-setuptools \
        libjpeg-dev \
        zlib1g-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libopenjp2-7-dev \
        libtiff-dev \
        libwebp-dev && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    if [ ! -f ./rpi-rgb-led-matrix/Makefile ]; then \
        rm -rf ./rpi-rgb-led-matrix && \
        git clone https://github.com/hzeller/rpi-rgb-led-matrix.git ./rpi-rgb-led-matrix; \
    fi && \
    make -C ./rpi-rgb-led-matrix/examples-api-use && \
    cd rpi-rgb-led-matrix/bindings/python/rgbmatrix/shims && \
    for file in Imaging.h ImagingUtils.h ImPlatform.h Mode.h Arrow.h Access.h Quant.h QuantHash.h QuantHeap.h QuantOctree.h QuantPngQuant.h QuantTypes.h Storage.h Except.h Palette.h TkImaging.h; do \
        curl -O https://raw.githubusercontent.com/python-pillow/Pillow/master/src/libImaging/$file || true; \
    done && \
    cd /app && \
    make -C ./rpi-rgb-led-matrix build-python && \
    make -C ./rpi-rgb-led-matrix install-python && \
    rm -rf ./rpi-rgb-led-matrix/examples-api-use \
           ./rpi-rgb-led-matrix/.git \
           ./rpi-rgb-led-matrix/bindings/python/build \
           /root/.cache && \
    apt-get purge -y --auto-remove \
        build-essential \
        git \
        curl \
        python3-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set capabilities for hardware access and real-time priority
RUN setcap 'cap_sys_rawio,cap_sys_admin,cap_ipc_lock,cap_sys_nice=eip' /usr/local/bin/python3.11

# Expose Flask port (can be removed if not using Flask)
EXPOSE 5000

# Default command to run the project
CMD ["python", "src"]