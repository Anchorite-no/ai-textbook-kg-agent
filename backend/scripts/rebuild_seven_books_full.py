from __future__ import annotations

import argparse
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.models.schemas import SampleDatasetPrepareRequest  # noqa: E402
from app.services.sample_dataset import create_prepare_seven_books_job, get_seven_books_dataset, run_prepare_seven_books  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the seven-book demo dataset with full KG assets.")
    parser.add_argument("--max-sections", type=int, default=3000)
    parser.add_argument("--max-nodes-per-section", type=int, default=12)
    parser.add_argument("--use-llm", action="store_true")
    args = parser.parse_args()

    request = SampleDatasetPrepareRequest(
        force_rebuild=True,
        build_graph=True,
        build_layered_graph=True,
        build_rag=True,
        build_alignment=True,
        build_integration=True,
        use_llm=args.use_llm,
        max_sections=args.max_sections,
        max_nodes_per_section=args.max_nodes_per_section,
        alignment_max_nodes=4000,
        integration_max_nodes=4000,
    )
    job_id = create_prepare_seven_books_job(request)
    print(f"job_id={job_id}", flush=True)
    run_prepare_seven_books(job_id, request)
    dataset = get_seven_books_dataset()
    print(dataset.model_dump_json(indent=2), flush=True)


if __name__ == "__main__":
    main()
