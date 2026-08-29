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

Milestone 1 in progress: segmentation pipeline, standalone.

Test the segmentation spike directly, no API needed:

```bash
python backend/app/segmentation_spike.py path/to/test_photo.jpg path/to/output_cutout.png
```

Run this against several varied test photos (different lighting, backgrounds,
clothing) before moving to Milestone 2 (scene generation benchmark).

## Milestones (from PRD.md)

1. Segmentation pipeline working standalone <- **you are here**
2. Scene generation working standalone
3. Compositing pipeline joining the two
4. End-to-end web flow
5. Cost/latency benchmarking and backend decision finalized
6. Polish pass
