import json
import logging
from pathlib import Path
from typing import List, Optional
from eval.schemas import EvaluationSample

logger = logging.getLogger(__name__)

DATASETS_ROOT = Path(__file__).parent / "datasets"


def load_dataset_samples(version: str = "v1", domain: Optional[str] = None, strict: bool = False) -> List[EvaluationSample]:
    """
    Load golden evaluation samples from disk for a given dataset version and optional domain filter.
    """
    version_dir = DATASETS_ROOT / version
    if not version_dir.exists():
        raise FileNotFoundError(f"Evaluation dataset version '{version}' not found at {version_dir}")

    samples: List[EvaluationSample] = []

    domains = [domain] if domain else [p.name for p in version_dir.iterdir() if p.is_dir()]

    for d in domains:
        domain_path = version_dir / d
        if not domain_path.exists():
            continue

        for json_file in domain_path.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sample = EvaluationSample.model_validate(data)
                    samples.append(sample)
            except Exception as e:
                if strict: raise ValueError(f"Invalid evaluation fixture: {json_file.name}") from e
                logger.error("Failed to load evaluation sample from %s: %s", json_file, e)

    return samples
