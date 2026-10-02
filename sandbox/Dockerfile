# Pixel-Check sandbox runtime. Built with `contree build`; runs with networking off.
# Playwright image ships browsers + OS deps, NOT the npm package; versions must match (1.63.0).
FROM mcr.microsoft.com/playwright:v1.63.0-noble

RUN apt-get update && apt-get install -y --no-install-recommends python3-pip && \
    python3 -m pip install --break-system-packages numpy==2.* pillow==11.* scikit-image==0.25.* && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pc
COPY package.json package-lock.json /opt/pc/
RUN npm ci --no-audit --no-fund

COPY fonts/ /opt/pc/fonts/
COPY selftest/ /opt/pc/selftest/
COPY render.mjs lint.mjs score.py integrity.py evaluate.py readable.py fluidity.py /opt/pc/
RUN cd /opt/pc && node render.mjs --selftest && node lint.mjs selftest/App.jsx && \
    node render.mjs --interact selftest/scenarios.json --in selftest/App.jsx --out /tmp/pc-interact && \
    node -e "const r=require('/tmp/pc-interact/interact.json'); process.exit(r.scenarios.length===2&&r.scenarios.every(s=>s.ok)?0:1)" && \
    python3 -c "import score, integrity, evaluate, readable, fluidity; print('py ok')"
