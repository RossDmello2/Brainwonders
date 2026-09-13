"""Killable request-owned child processes for untrusted DOCX work."""
import multiprocessing as mp
import os
import queue
import time

from ..errors import AppError


def _worker(send, operation, payload):
    try:
        if os.name == "posix":
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        from .template_engine import generate_docx, validate_pair
        result = validate_pair(payload["docx"], payload["config"]) if operation == "validate" else generate_docx(
            payload["docx"], payload["config"], payload["values"], payload["fingerprint"])
        send.put(("ok", result), timeout=2)
    except AppError as exc:
        send.put(("error", (exc.code, exc.status, exc.details, exc.retryable, exc.retry_after)), timeout=2)
    except BaseException:
        send.put(("error", ("DOCUMENT_FAILED", 500, [], False, None)), timeout=2)


def _stop(child):
    if child.is_alive():
        child.terminate(); child.join(2)
    if child.is_alive():
        child.kill(); child.join()


def run_isolated(operation, payload, timeout=25, cancel_event=None):
    # Vercel's serverless sandbox does not expose POSIX multiprocessing
    # semaphores. The function instance is already request-scoped there, so
    # retain the same validation/rendering path without creating a child.
    if os.getenv("VERCEL"):
        try:
            from .template_engine import generate_docx, validate_pair
            if cancel_event is not None and cancel_event.is_set():
                raise AppError("DOCUMENT_FAILED", 499)
            return validate_pair(payload["docx"], payload["config"]) if operation == "validate" else generate_docx(
                payload["docx"], payload["config"], payload["values"], payload["fingerprint"])
        except AppError:
            raise
        except BaseException:
            raise AppError("DOCUMENT_FAILED", 500)
    context = mp.get_context("spawn")
    channel = context.Queue(maxsize=1)
    child = context.Process(target=_worker, args=(channel, operation, payload), daemon=True)
    child.start()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                _stop(child)
                raise AppError("DOCUMENT_FAILED", 499)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _stop(child)
                raise AppError("DOCUMENT_TIMEOUT", 503)
            try:
                kind, result = channel.get(timeout=min(.25, remaining))
                break
            except queue.Empty:
                if not child.is_alive():
                    raise AppError("DOCUMENT_FAILED", 500)
    finally:
        channel.close(); channel.join_thread()
    child.join(2)
    _stop(child)
    if kind == "error": raise AppError(*result)
    return result
