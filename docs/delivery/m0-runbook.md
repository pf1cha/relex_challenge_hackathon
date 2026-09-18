# Reproduce M0

Use direct certificate SSH options from project instructions. Work in `/scratch/project_2020551/relex`. Service images and `.venv-cpu` are x86_64, so submit service jobs from `roihu-cpu.csc.fi`. Do not run these services or inference on a login node.

```sh
cd /scratch/project_2020551/relex
mkdir -p .runtime/images
APPTAINER_CACHEDIR="$PWD/.runtime/cache" apptainer pull .runtime/images/postgres.sif docker://postgres:17
APPTAINER_CACHEDIR="$PWD/.runtime/cache" apptainer pull .runtime/images/qdrant.sif docker://qdrant/qdrant:v1.17.0
/usr/bin/python3 -m venv .venv-cpu
.venv-cpu/bin/python -m pip install -r requirements-m0.txt
srun --account=project_2020551 --partition=test --nodes=1 --ntasks=1 --cpus-per-task=2 --mem=4G --time=00:05:00 --immediate=10 bash scripts/m0-services.sh
```

Skip image pulls when files already exist; never overwrite running images/data. The probe owns `.runtime/m0`, Unix socket PostgreSQL port 25432, and loopback Qdrant ports 26333/26334 within its allocation. Cleanup stops its processes. Persistent data remains ignored. No GPU allocated.

For browser connectivity:

```sh
srun --account=project_2020551 --partition=test --nodes=1 --ntasks=1 --cpus-per-task=2 --mem=4G --time=00:10:00 --immediate=10 .venv-cpu/bin/python -m uvicorn scripts.m0_web:app --host 0.0.0.0 --port 28080
```

Find the assigned node using `squeue -u "$USER" -o '%i %N %j'`; locally forward localhost port 18886 to that node port 28080 through CPU login. Open `http://127.0.0.1:18886/` in a real browser. Cancel only your recorded probe job with `scancel JOB_ID`, and stop your forwarding process afterwards. The HTTP page is a connectivity probe, not the product; it contains no private data.

For the remaining real model probe, export private configuration corresponding to `.env.example`, then run `.venv-cpu/bin/python scripts/m0_models.py`. Base URLs must include the provider's API prefix (commonly `/v1`). It supports OpenAI-compatible chat completions with tool calls and embeddings. A different endpoint protocol requires an explicit adapter, not a simulated successful result. Only synthetic probe text is transmitted.
