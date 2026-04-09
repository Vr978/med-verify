"""
Batch Model Hash Integrity Validator
=====================================
Validates 800+ model update hashes per federated learning round to ensure
no tampered or corrupted model checkpoint reaches the aggregation phase.

Each model hash is re-computed from the file on disk and compared against
the submitted SHA-256 digest. Only hashes that pass this integrity check
are forwarded to the DPoS blockchain ledger in MongoDB.

Typical usage inside the aggregate endpoint:
    from fl_backend.core.batch_validator import BatchValidator
    report = BatchValidator.validate(model_paths, expected_hashes)
    if not report["all_valid"]:
        raise ValueError(f"{report['failed']} model(s) failed integrity check")
"""

import hashlib
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum threshold the resume references — at least 800 updates validated
MIN_VALIDATION_THRESHOLD = 800


@dataclass
class ValidationResult:
    """Per-model validation outcome."""
    path: str
    submitted_hash: str
    computed_hash: str
    valid: bool
    error: Optional[str] = None


@dataclass
class BatchValidationReport:
    """Aggregate report for a full training-round validation pass."""
    round_id: str
    total: int
    passed: int
    failed: int
    all_valid: bool
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total > 0 else 0.0

    def summary(self) -> str:
        return (
            f"[BatchValidator] Round {self.round_id} | "
            f"Total={self.total} Passed={self.passed} Failed={self.failed} "
            f"PassRate={self.pass_rate:.1f}%"
        )


class BatchValidator:
    """
    Validates the integrity of model update hashes for a federated learning round.

    Design decisions
    ----------------
    - Re-computes SHA-256 from the actual .pt file bytes to detect any
      on-disk corruption or MITM substitution of model checkpoints.
    - Processes all models in a single pass (O(n) in bytes read).
    - Emits structured per-model results so the aggregator can quarantine
      individual bad actors without dropping the whole round.
    - When fewer than MIN_VALIDATION_THRESHOLD models are present (e.g., in
      dev/test), the validator still processes all available models and logs
      a warning — it never silently skips validation.
    """

    @staticmethod
    def _compute_sha256(file_path: str) -> str:
        """Stream-hash a file to avoid loading the entire checkpoint into RAM."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @classmethod
    def validate(
        cls,
        model_paths: list[str],
        expected_hashes: list[str],
        round_id: str = "unknown",
    ) -> BatchValidationReport:
        """
        Validate integrity of model checkpoints submitted for a training round.

        Parameters
        ----------
        model_paths : list[str]
            Absolute filesystem paths to .pt model checkpoint files.
        expected_hashes : list[str]
            SHA-256 hashes as reported by each FL client node.
        round_id : str
            Identifier of the active DPoS election round.

        Returns
        -------
        BatchValidationReport
            Structured report; ``all_valid`` is True only if every model passes.
        """
        if len(model_paths) != len(expected_hashes):
            raise ValueError(
                f"Mismatch: {len(model_paths)} model paths but "
                f"{len(expected_hashes)} expected hashes."
            )

        total = len(model_paths)
        if total < MIN_VALIDATION_THRESHOLD:
            logger.warning(
                "[BatchValidator] Round %s has only %d model updates "
                "(below production threshold of %d). Proceeding anyway.",
                round_id, total, MIN_VALIDATION_THRESHOLD,
            )
        else:
            logger.info(
                "[BatchValidator] Validating %d model updates for round %s …",
                total, round_id,
            )

        results: list[ValidationResult] = []
        passed = 0
        failed = 0

        for path, submitted_hash in zip(model_paths, expected_hashes):
            if not os.path.exists(path):
                res = ValidationResult(
                    path=path,
                    submitted_hash=submitted_hash,
                    computed_hash="",
                    valid=False,
                    error="File not found on disk",
                )
                failed += 1
                results.append(res)
                logger.error("[BatchValidator] ❌ Missing file: %s", path)
                continue

            try:
                computed = cls._compute_sha256(path)
                is_valid = hmac_safe_compare(computed, submitted_hash)
                res = ValidationResult(
                    path=path,
                    submitted_hash=submitted_hash,
                    computed_hash=computed,
                    valid=is_valid,
                    error=None if is_valid else "Hash mismatch — possible tampering",
                )
                if is_valid:
                    passed += 1
                    logger.debug("[BatchValidator] ✅ %s … OK", os.path.basename(path))
                else:
                    failed += 1
                    logger.warning(
                        "[BatchValidator] ❌ HASH MISMATCH for %s | "
                        "submitted=%s … computed=%s …",
                        os.path.basename(path),
                        submitted_hash[:12],
                        computed[:12],
                    )
            except Exception as exc:
                res = ValidationResult(
                    path=path,
                    submitted_hash=submitted_hash,
                    computed_hash="",
                    valid=False,
                    error=str(exc),
                )
                failed += 1
                logger.error("[BatchValidator] ❌ Error hashing %s: %s", path, exc)

            results.append(res)

        report = BatchValidationReport(
            round_id=round_id,
            total=total,
            passed=passed,
            failed=failed,
            all_valid=(failed == 0),
            results=results,
        )

        log_fn = logger.info if report.all_valid else logger.warning
        log_fn(report.summary())

        return report


def hmac_safe_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison to prevent timing-based side-channel attacks
    when comparing model hashes.
    """
    import hmac as _hmac
    return _hmac.compare_digest(a.lower(), b.lower())


# ─── Quick self-test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import tempfile
    import random

    logging.basicConfig(level=logging.INFO)

    N = 10  # small local test; in production this is 800+
    tmp_dir = tempfile.mkdtemp()
    paths, hashes = [], []

    for i in range(N):
        fpath = os.path.join(tmp_dir, f"model_{i}.pt")
        data = bytes(random.getrandbits(8) for _ in range(1024))
        with open(fpath, "wb") as f:
            f.write(data)
        h = hashlib.sha256(data).hexdigest()
        paths.append(fpath)
        hashes.append(h)

    report = BatchValidator.validate(paths, hashes, round_id="test_round_001")
    assert report.all_valid, "Self-test failed!"
    print(f"\n✅ Self-test passed: {report.summary()}")
