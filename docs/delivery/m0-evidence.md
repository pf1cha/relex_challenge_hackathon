# M0 feasibility evidence

Date: 2026-09-19. Contract: frozen revision 4, baseline `a1d61f72ea337b843edcaa45c03ca1de85b66120`.
Status: **incomplete: configured real model and embedding endpoints are missing**. No functional-product acceptance or reviewer PASS claimed.

## Executed probes

All repository writes are under `/scratch/project_2020551/relex`. CPU execution uses the same shared filesystem via `roihu-cpu.csc.fi`; GPU inference was not launched. Official CSC guidance puts interactive web applications on allocated compute nodes: https://docs.csc.fi/computing/running/interactive-usage/ . Separate CPU/GPU architectures require separate environments.

1. `pwd; git status --short; git rev-parse HEAD`: authoritative path and baseline match. Inherited root `production-behavior.md` deletion and untracked docs/corpus/spec preserved.
2. `podman info --format '{{.Host.Security.Rootless}}'`: exit 125; `cannot clone: No space left on device`, `user namespaces are not enabled in /proc/sys/user/max_user_namespaces`. Podman not usable; this did not imply disk exhaustion or that Apptainer was unavailable.
3. `apptainer version`: 1.4.5-3.el9. Pulled official `postgres:17` and `qdrant/qdrant:v1.17.0` into ignored `.runtime/images/`. Success.
4. `python3 -m venv .venv; .venv/bin/python -m pip install fastapi uvicorn` on GPU login: exit 0, Python 3.14.7 ARM, FastAPI 0.141.1, Uvicorn 0.53.0. `/usr/bin/python3 -m venv .venv-cpu; .venv-cpu/bin/python -m pip install fastapi uvicorn` on CPU login: exit 0, Python 3.9.25 x86_64, FastAPI 0.128.8, Uvicorn 0.39.0. Only local dependency installation; no shared Python changes.
5. GPU test request without a GPU was correctly rejected; switched to CPU test partition rather than reserving a GPU for service verification. `srun --account=project_2020551 --partition=test --nodes=1 --ntasks=1 --cpus-per-task=2 --mem=4G --time=00:02:00 --immediate=10 hostname`: exit 0, job 1411683, `rc4284`.
6. First service probe (job 1411689) failed because daemonized PostgreSQL lost its Apptainer mount when the launcher exited. Fixed to run PostgreSQL as a foreground container process owned by the job. Not counted as a successful probe.
7. `srun --account=project_2020551 --partition=test --nodes=1 --ntasks=1 --cpus-per-task=2 --mem=4G --time=00:05:00 --immediate=10 bash scripts/m0-services.sh`: **exit 0**, job 1411694, node rc4284. PostgreSQL 17.11 SQL insert, stop/start, SELECT returned `persistence-probe`. Qdrant 1.17.0 collection insert, stop/start, GET point returned ID 1 / payload `probe=persistence`; disposable collection deleted. Both services stopped by cleanup. Qdrant's synthetic 3D point only verifies storage, not embedding/model behavior. Full secret-free output retained in ignored `.runtime/m0-service-probe.log`.
8. Browser route: job 1411699 ran `.venv-cpu/bin/python -m uvicorn scripts.m0_web:app --host 0.0.0.0 --port 28080` with the same 2 CPU / 4 GiB limits, 10-minute maximum. SSH forward `-L 127.0.0.1:18886:rc4284:28080` via CPU login. Actual in-app browser at `http://127.0.0.1:18886/` rendered heading **RELEX remote route works** and explicit incomplete-product notice. `curl -fsS http://127.0.0.1:18886/health`: exit 0, `{"probe":"connectivity","product_ready":false,"model_verified":false}`. This is connectivity verification only, not R9 product acceptance.
9. `.venv/bin/python scripts/m0_models.py`: **exit 1**, `M0 model probe failed: RELEX_MODEL: base URL and model identifier must be configured`. No project `.env` or configured model/embedding environment variables found. No private corpus sent anywhere. No unrelated repository credentials inspected.

Existing login shell tries to activate ARM conda on CPU and reports syntax errors; explicit `/usr/bin/python3` / `.venv-cpu/bin/python` work. Apptainer emits missing `libargos-*.so` LD_PRELOAD warnings; SQL/Qdrant probes succeeded despite these warnings. Shared shell/site configuration was not modified.

## Remaining gate and acceptance

Need authorized generation endpoint/model and embedding endpoint/model plus private credential configuration path. `.env.example` lists expected environment keys; do not paste secrets into evidence or commit them. `scripts/m0_models.py` makes synthetic real tool-call and embedding requests and reports only model IDs/dimensions.

R1: service feasibility subset verified, application persistence not yet implemented.
R2-R12: product behavior not implemented/verified.
R13: initial repeatable feasibility commands and evidence only.
I1/I5: inherited files preserved; bounded owned CPU jobs/services; no shared-service changes. I2-I4 product invariants remain unverified.

Do not proceed to substantial application implementation until the remaining M0 model gate passes. This follows the frozen contract rather than substituting mocks or building against imaginary model access.
