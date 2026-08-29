"""
Standalone scene generation spike (Milestone 2 from PRD.md).

Decoupled from segmentation and compositing. Used to benchmark candidate backends
(Replicate, fal.ai, Stability AI, Mock) for cost, latency, and image quality.

Note: Rate limiting is out of scope for this standalone script but is a v1 requirement per rules.md once this becomes an actual API endpoint.

Usage:
    python backend/app/scene_gen_spike.py --prompt "person trekking on a mountain trail at sunset" --output data/outputs/test_scene.png
    python backend/app/scene_gen_spike.py --benchmark
"""

import argparse
import csv
import json
import os
import time
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# Load environment variables from .env if present
load_dotenv()

# Standard test prompts mapping to initial theme set (PRD.md)
BENCHMARK_PROMPTS = [
    "person trekking on a mountain trail at sunset",
    "person on a tropical beach at midday",
    "person in a cyberpunk city street at night",
]

# Published fixed pricing per image for supported models (as of official API pricing rate cards)
MODEL_PRICING_USD: Dict[str, float] = {
    # Replicate published model rates
    "black-forest-labs/flux-schnell": 0.003,
    "stability-ai/sdxl": 0.002,
    # fal.ai published model rates
    "fal-ai/flux/schnell": 0.003,
    "fal-ai/fast-sdxl": 0.0015,
    # Stability AI published credit rates ($0.01 per credit)
    "stable-image/generate/core": 0.03,  # 3 credits
    "stable-image/generate/sd3": 0.065,  # 6.5 credits
    # Mock local provider
    "mock-generator-v1": 0.000,
}


@dataclass
class GenerationResult:
    provider: str
    model: str
    prompt: str
    output_path: str
    latency_seconds: float
    cost_usd: float
    timestamp: str
    status: str = "success"
    error_message: Optional[str] = None


class BenchmarkLogger:
    """Logs empirical benchmark metrics (latency, exact model cost, timestamp) to JSON and CSV."""

    def __init__(self, log_dir: str = "data/benchmarks"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.json_path = self.log_dir / "scene_gen_benchmark.json"
        self.csv_path = self.log_dir / "scene_gen_benchmark.csv"

    def log(self, result: GenerationResult) -> None:
        entry = asdict(result)

        # Append to JSON array
        records = []
        if self.json_path.exists() and self.json_path.stat().st_size > 0:
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []
        records.append(entry)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

        # Append to CSV
        file_exists = self.csv_path.exists() and self.csv_path.stat().st_size > 0
        fieldnames = [
            "timestamp",
            "provider",
            "model",
            "prompt",
            "latency_seconds",
            "cost_usd",
            "output_path",
            "status",
            "error_message",
        ]
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(entry)

        print(
            f"[BENCHMARK LOGGED] Provider: {result.provider} | Model: {result.model} | "
            f"Latency: {result.latency_seconds:.2f}s | Cost: ${result.cost_usd:.4f}"
        )


class BaseSceneGenProvider(ABC):
    """Abstract interface for provider-agnostic scene generation."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("SCENE_GEN_API_KEY", "")
        self.model = model or os.getenv("SCENE_GEN_MODEL", "")

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        pass

    def get_model_name(self) -> str:
        return self.model if self.model else self.default_model

    def get_cost_per_image(self) -> float:
        model = self.get_model_name()
        return MODEL_PRICING_USD.get(model, 0.0)

    @abstractmethod
    def _generate_image(self, prompt: str, output_path: Path) -> None:
        pass

    def generate(self, prompt: str, output_path: str) -> GenerationResult:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        model_name = self.get_model_name()
        cost = self.get_cost_per_image()

        start_time = time.time()
        try:
            self._generate_image(prompt, out_path)
            latency = time.time() - start_time
            return GenerationResult(
                provider=self.provider_name,
                model=model_name,
                prompt=prompt,
                output_path=str(out_path),
                latency_seconds=latency,
                cost_usd=cost,
                timestamp=datetime.now(timezone.utc).isoformat(),
                status="success",
            )
        except Exception as e:
            latency = time.time() - start_time
            return GenerationResult(
                provider=self.provider_name,
                model=model_name,
                prompt=prompt,
                output_path=str(out_path),
                latency_seconds=latency,
                cost_usd=0.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                status="error",
                error_message=str(e),
            )


class ReplicateProvider(BaseSceneGenProvider):
    @property
    def provider_name(self) -> str:
        return "replicate"

    @property
    def default_model(self) -> str:
        return "black-forest-labs/flux-schnell"

    def _generate_image(self, prompt: str, output_path: Path) -> None:
        if not self.api_key:
            raise ValueError("SCENE_GEN_API_KEY is required for Replicate provider.")

        model = self.get_model_name()
        url = f"https://api.replicate.com/v1/models/{model}/predictions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "wait",
        }
        payload = json.dumps({"input": {"prompt": prompt, "aspect_ratio": "1:1"}}).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Replicate API HTTP {err.code}: {err_body}") from err

        # Poll if not completed yet
        while data.get("status") in ["starting", "processing"]:
            time.sleep(1)
            get_url = data["urls"]["get"]
            get_req = urllib.request.Request(get_url, headers=headers)
            with urllib.request.urlopen(get_req) as resp:
                data = json.loads(resp.read().decode("utf-8"))

        if data.get("status") != "succeeded":
            raise RuntimeError(f"Replicate generation failed: {data.get('error')}")

        output_url = data["output"][0] if isinstance(data["output"], list) else data["output"]
        urllib.request.urlretrieve(output_url, output_path)


class FalAIProvider(BaseSceneGenProvider):
    @property
    def provider_name(self) -> str:
        return "fal"

    @property
    def default_model(self) -> str:
        return "fal-ai/flux/schnell"

    def _generate_image(self, prompt: str, output_path: Path) -> None:
        if not self.api_key:
            raise ValueError("SCENE_GEN_API_KEY is required for fal.ai provider.")

        model = self.get_model_name()
        url = f"https://fal.run/{model}"
        headers = {
            "Authorization": f"Key {self.api_key.strip()}",
            "Content-Type": "application/json",
            "User-Agent": "SceneSwap/1.0 (Python)",
        }
        payload = json.dumps({"prompt": prompt, "image_size": "square_hd"}).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"fal.ai API HTTP {err.code}: {err_body}") from err

        images = data.get("images", [])
        if not images or "url" not in images[0]:
            raise RuntimeError(f"fal.ai generation failed: {data}")

        image_url = images[0]["url"]
        img_req = urllib.request.Request(image_url, headers={"User-Agent": "SceneSwap/1.0 (Python)"})
        with urllib.request.urlopen(img_req) as img_resp:
            with open(output_path, "wb") as f:
                f.write(img_resp.read())


class StabilityAIProvider(BaseSceneGenProvider):
    @property
    def provider_name(self) -> str:
        return "stability"

    @property
    def default_model(self) -> str:
        return "stable-image/generate/core"

    def _generate_image(self, prompt: str, output_path: Path) -> None:
        if not self.api_key:
            raise ValueError("SCENE_GEN_API_KEY is required for Stability AI provider.")

        model = self.get_model_name()
        url = f"https://api.stability.ai/v2beta/{model}"
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="prompt"\r\n\r\n{prompt}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="output_format"\r\n\r\npng\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="aspect_ratio"\r\n\r\n1:1\r\n'
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "image/*",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                image_data = resp.read()
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Stability AI API HTTP {err.code}: {err_body}") from err

        with open(output_path, "wb") as f:
            f.write(image_data)


class MockProvider(BaseSceneGenProvider):
    """Local synthetic background generator for benchmarking pipeline without API keys."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-generator-v1"

    def _generate_image(self, prompt: str, output_path: Path) -> None:
        # Simulate ~0.35s network latency
        time.sleep(0.35)

        # Create a synthetic 1024x1024 background image with prompt text
        width, height = 1024, 1024
        img = Image.new("RGB", (width, height), color=(30, 40, 60))
        draw = ImageDraw.Draw(img)

        # Draw simple decorative background gradients/shapes
        draw.rectangle([0, 0, width, height // 2], fill=(70, 90, 130))
        draw.ellipse([width // 4, height // 4, 3 * width // 4, 3 * height // 4], fill=(120, 150, 200))

        # Add text overlay summarizing prompt
        title = "Mock Generated Background"
        draw.text((40, 40), title, fill=(255, 255, 255))
        draw.text((40, 90), f"Prompt: {prompt}", fill=(200, 230, 255))
        draw.text((40, 140), f"Model: {self.get_model_name()}", fill=(200, 230, 255))

        img.save(output_path)


def get_provider(provider_override: Optional[str] = None) -> BaseSceneGenProvider:
    provider_name = (provider_override or os.getenv("SCENE_GEN_PROVIDER", "mock")).strip().lower()

    if not provider_name or provider_name == "mock":
        return MockProvider()
    elif provider_name == "replicate":
        return ReplicateProvider()
    elif provider_name == "fal":
        return FalAIProvider()
    elif provider_name == "stability":
        return StabilityAIProvider()
    else:
        print(f"Warning: Unknown SCENE_GEN_PROVIDER '{provider_name}'. Falling back to MockProvider.")
        return MockProvider()


def run_benchmark(provider: BaseSceneGenProvider, logger: BenchmarkLogger) -> List[GenerationResult]:
    print(f"\n--- Running Scene Generation Benchmark Suite ---")
    print(f"Provider: {provider.provider_name} | Model: {provider.get_model_name()}")
    results = []
    output_dir = Path("data/outputs/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)

    for idx, prompt in enumerate(BENCHMARK_PROMPTS, 1):
        out_path = output_dir / f"benchmark_{provider.provider_name}_{idx}.png"
        print(f"\nTest {idx}/{len(BENCHMARK_PROMPTS)}: '{prompt}'")
        res = provider.generate(prompt, str(out_path))
        logger.log(res)
        results.append(res)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scene Generation Spike & Provider Benchmark Suite")
    parser.add_argument("--prompt", type=str, help="Prompt text to generate scene background")
    parser.add_argument(
        "--output",
        type=str,
        default="data/outputs/scene_gen_output.png",
        help="Path to save generated output image",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["mock", "replicate", "fal", "stability"],
        help="Override provider (defaults to SCENE_GEN_PROVIDER in .env)",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run standard 3-prompt benchmark suite and save metrics to log files",
    )

    args = parser.parse_args()

    provider = get_provider(args.provider)
    logger = BenchmarkLogger()

    if args.benchmark:
        run_benchmark(provider, logger)
    elif args.prompt:
        res = provider.generate(args.prompt, args.output)
        logger.log(res)
    else:
        print("No --prompt or --benchmark specified. Running standard benchmark suite by default...")
        run_benchmark(provider, logger)
