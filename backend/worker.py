import logging
import os
import signal
import threading
import time

from . import store
from .settings import DEADLINE, UPLOADS

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


def main():
    store.init()
    store.recover()
    store.worker_state(False, 'loading_models')
    from .pipeline import Pipeline, AnalysisUnavailable
    pipeline = Pipeline()
    def heartbeat():
        while True:
            store.worker_state(True, 'ready')
            time.sleep(5)
    threading.Thread(target=heartbeat, daemon=True).start()
    def timeout(signum, frame):
        raise TimeoutError('Job deadline exceeded')
    signal.signal(signal.SIGALRM, timeout)
    while True:
        store.cleanup()
        row = store.claim()
        if not row:
            time.sleep(.5)
            continue
        job_id = row['id']
        path = UPLOADS / (job_id + '.mov')
        origin = row['started'] if row['client_id'] else row['created']
        remaining = DEADLINE - (time.time() - origin)
        if remaining < 10:
            store.fail(job_id, 'processing_timeout')
            path.unlink(missing_ok=True)
            continue
        signal.alarm(max(1, int(remaining)))
        try:
            result = pipeline.analyze(path, lambda s: store.stage(job_id, s))
            store.complete(job_id, result)
            log.info('Job %s done in %.2fs, events=%s', job_id, time.time() - row['created'], len(result['violations']))
        except TimeoutError:
            store.fail(job_id, 'processing_timeout')
            path.unlink(missing_ok=True)
            log.exception('Timeout %s; worker will restart', job_id)
            os._exit(1)
        except AnalysisUnavailable as exc:
            store.fail(job_id, exc.code)
            log.warning('Analysis unavailable %s: %s', job_id, exc.code)
        except Exception:
            store.fail(job_id, 'analysis_failed')
            log.exception('Analysis failed %s', job_id)
        finally:
            signal.alarm(0)
            path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
