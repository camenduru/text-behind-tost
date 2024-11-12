FROM runpod/pytorch:2.2.1-py3.10-cuda12.1.1-devel-ubuntu22.04
WORKDIR /content
ENV PATH="/home/camenduru/.local/bin:${PATH}"

RUN adduser --disabled-password --gecos '' camenduru && \
    adduser camenduru sudo && \
    echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers && \
    chown -R camenduru:camenduru /content && \
    chmod -R 777 /content && \
    chown -R camenduru:camenduru /home && \
    chmod -R 777 /home && \
    apt update -y && add-apt-repository -y ppa:git-core/ppa && apt update -y && apt install -y aria2 git git-lfs unzip ffmpeg

USER camenduru

RUN pip install torch==2.5.0+cu124 torchvision==0.20.0+cu124 torchaudio==2.5.0+cu124 torchtext==0.18.0 torchdata==0.8.0 --extra-index-url https://download.pytorch.org/whl/cu124 && \
    pip install xformers==0.0.28.post2 https://github.com/camenduru/wheels/releases/download/torch-2.5.0-cu124/flash_attn-2.6.3-cp310-cp310-linux_x86_64.whl && \
    pip install opencv-python imageio imageio-ffmpeg ffmpeg-python av runpod && \
    pip install torchsde einops diffusers transformers accelerate peft timm kornia && \
    git clone https://github.com/comfyanonymous/ComfyUI /content/ComfyUI && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager /content/ComfyUI/custom_nodes/ComfyUI-Manager && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite /content/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite && \
    git clone https://github.com/camenduru/add_text_2_img /content/ComfyUI/custom_nodes/add_text_2_img && \
    git clone https://github.com/lldacing/ComfyUI_BiRefNet_ll /content/ComfyUI/custom_nodes/ComfyUI_BiRefNet_ll && \
    git clone https://github.com/kijai/ComfyUI-KJNodes /content/ComfyUI/custom_nodes/ComfyUI-KJNodes && \
    aria2c --console-log-level=error -c -x 16 -s 16 -k 1M https://huggingface.co/ZhengPeng7/BiRefNet/resolve/main/model.safetensors -d /content/ComfyUI/models/BiRefNet -o General.safetensors

COPY ./worker_runpod.py /content/ComfyUI/worker_runpod.py
WORKDIR /content/ComfyUI
CMD python worker_runpod.py