"""RAG Evaluation Pipeline using Ragas metrics.

Evaluates retrieval quality and answer generation against a test set.
Metrics: faithfulness, answer_relevancy, context_precision, context_recall.
"""

import json
import time
from pathlib import Path

import httpx
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

RAG_BASE_URL = "http://localhost:8001"
RESULTS_DIR = Path(__file__).parent / "results"

# Test questions with ground truth answers for evaluation
EVAL_SET = [
    {
        "question": "What are the three pillars of observability?",
        "ground_truth": "The three pillars of observability are metrics, logs, and traces.",
        "expected_contexts": ["observability-guide.md"],
    },
    {
        "question": "What is the difference between a Counter and a Gauge metric?",
        "ground_truth": "A Counter is a monotonically increasing value that can only go up or reset to zero, while a Gauge is a value that can go up or down.",
        "expected_contexts": ["observability-guide.md"],
    },
    {
        "question": "What are the benefits of multi-stage Docker builds?",
        "ground_truth": "Benefits include smaller images (often 10-100x reduction), reduced attack surface (no build tools in production), faster pulls and deployments, and cleaner separation of concerns.",
        "expected_contexts": ["docker-best-practices.md"],
    },
    {
        "question": "What is the role of etcd in Kubernetes?",
        "ground_truth": "etcd is a consistent, distributed key-value store used as Kubernetes' backing store for all cluster data. It stores the desired state of the cluster, including configuration, secrets, and service discovery information, and uses the Raft consensus algorithm.",
        "expected_contexts": ["kubernetes-basics.md"],
    },
    {
        "question": "What Kubernetes Service types are available?",
        "ground_truth": "Kubernetes Service types are ClusterIP (internal only, default), NodePort (exposes on each node's IP at a static port 30000-32767), LoadBalancer (exposes externally via cloud provider), and ExternalName (maps to a DNS name via CNAME).",
        "expected_contexts": ["kubernetes-basics.md"],
    },
    {
        "question": "How should secrets be managed in Docker containers?",
        "ground_truth": "Secrets should never be hardcoded in Dockerfiles, stored in docker-compose.yml environment variables committed to git, or included in image layers. Instead use Docker Secrets, runtime environment variables from a secrets manager, volume-mounted secret files, or external secrets managers like HashiCorp Vault.",
        "expected_contexts": ["docker-best-practices.md"],
    },
    {
        "question": "What is an error budget and how is it calculated?",
        "ground_truth": "Error budget equals 1 minus the SLO. For a 99.9% availability SLO, the 30-day error budget is 0.1% which equals 43.2 minutes of downtime. When the budget is consumed, reliability should be prioritized over features.",
        "expected_contexts": ["observability-guide.md"],
    },
    {
        "question": "What is the RED method for service monitoring?",
        "ground_truth": "The RED method stands for Rate (requests per second), Errors (failed requests per second), and Duration (distribution of request latencies). It is used for monitoring services.",
        "expected_contexts": ["observability-guide.md"],
    },
]


def query_rag(question: str, top_k: int = 5) -> dict:
    """Send a question to the RAG API and return the response."""
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{RAG_BASE_URL}/api/ask",
            json={"question": question, "top_k": top_k},
        )
        resp.raise_for_status()
        return resp.json()


def run_evaluation() -> dict:
    """Run the full evaluation pipeline."""
    print(f"Running evaluation with {len(EVAL_SET)} questions...")

    questions = []
    answers = []
    contexts = []
    ground_truths = []
    latencies = []
    retrieval_details = []

    for i, item in enumerate(EVAL_SET):
        print(f"  [{i + 1}/{len(EVAL_SET)}] {item['question'][:60]}...")
        start = time.time()

        try:
            result = query_rag(item["question"])
            elapsed = (time.time() - start) * 1000

            questions.append(item["question"])
            answers.append(result["answer"])
            contexts.append([c["content"] for c in result["citations"]])
            ground_truths.append(item["ground_truth"])
            latencies.append(elapsed)
            retrieval_details.append(
                {
                    "model": result["model"],
                    "method": result["retrieval_method"],
                    "api_latency_ms": result["latency_ms"],
                    "total_latency_ms": elapsed,
                    "num_citations": len(result["citations"]),
                    "source_docs": [c["document"] for c in result["citations"]],
                }
            )
        except Exception as e:
            print(f"    ERROR: {e}")
            questions.append(item["question"])
            answers.append(f"Error: {e}")
            contexts.append([])
            ground_truths.append(item["ground_truth"])
            latencies.append(0)
            retrieval_details.append({"error": str(e)})

    # Build Ragas dataset
    dataset = Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        }
    )

    print("\nComputing Ragas metrics...")
    try:
        ragas_result = evaluate(
            dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            ],
        )
        metrics = {k: round(v, 4) for k, v in ragas_result.items()}
    except Exception as e:
        print(f"  Ragas evaluation failed: {e}")
        print("  Saving results without Ragas metrics.")
        metrics = {"error": str(e)}

    # Build report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "num_questions": len(EVAL_SET),
        "metrics": metrics,
        "avg_latency_ms": round(sum(latencies) / max(len(latencies), 1), 1),
        "per_question": [
            {
                "question": questions[i],
                "ground_truth": ground_truths[i],
                "answer": answers[i],
                "latency_ms": round(latencies[i], 1),
                "retrieval": retrieval_details[i],
            }
            for i in range(len(questions))
        ],
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "eval_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nResults saved to {out_path}")
    print("\nMetrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print(f"  avg_latency_ms: {report['avg_latency_ms']}")

    return report


if __name__ == "__main__":
    run_evaluation()
