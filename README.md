# Scene Swap App

See DESIGN.md, PROPOSAL.md, PRD.md, and rules.md for full context.

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# edit .env with real values as needed

# 4. Run the API (once there's more than a health check)
uvicorn backend.app.main:app --reload --port 8000
```

## Current Status

Milestone 2 validated: Scene generation benchmark suite and provider-agnostic spike script (`backend/app/scene_gen_spike.py`).

### 1. Test Segmentation (Milestone 1)
```bash
python backend/app/segmentation_spike.py path/to/test_photo.jpg path/to/output_cutout.png
```

### 2. Benchmark Scene Generation Backends (Milestone 2)
Run the benchmark suite in mock mode (no API key required):
```bash
python backend/app/scene_gen_spike.py --benchmark
```

To run against live providers (Replicate, fal.ai, Stability AI), configure `.env`:
```env
SCENE_GEN_PROVIDER=fal          # Options: mock, replicate, fal, stability
SCENE_GEN_API_KEY=your_api_key
SCENE_GEN_MODEL=fal-ai/flux/schnell
```

Then run single prompt or benchmark:
```bash
python backend/app/scene_gen_spike.py --prompt "person trekking on a mountain trail at sunset" --output data/outputs/test_scene.png
```

Benchmark output metrics (latency, exact model cost, timestamp) are automatically recorded to `data/benchmarks/scene_gen_benchmark.json` and `scene_gen_benchmark.csv`.

## Milestones (from PRD.md)

1. Segmentation pipeline working standalone [DONE]
2. Scene generation working standalone <- **you are here**
3. Compositing pipeline joining the two
4. End-to-end web flow
5. Cost/latency benchmarking and backend decision finalized
6. Polish pass

