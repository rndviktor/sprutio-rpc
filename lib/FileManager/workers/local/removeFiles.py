from lib.FileManager.workers.baseWorkerCustomer import BaseWorkerCustomer
from lib.FileManager.FM import REQUEST_DELAY
import traceback
import shutil
import time
import os


class RemoveFiles(BaseWorkerCustomer):
    def __init__(self, paths, *args, **kwargs):
        super(RemoveFiles, self).__init__(*args, **kwargs)

        self.paths = paths

    def run(self):
        try:
            self.preload()
            success_paths = []
            error_paths = []

            next_tick = time.time() + REQUEST_DELAY

            for path in self.paths:
                try:
                    abs_path = self.get_abs_path(path)

                    if os.path.isfile(abs_path):
                        os.remove(abs_path)
                    elif os.path.islink(abs_path):
                        os.unlink(abs_path)
                    elif os.path.isdir(abs_path):
                        shutil.rmtree(abs_path)
                    else:
                        error_paths.append(abs_path)
                        break

                    success_paths.append(path)

                    if time.time() > next_tick:
                        progress = {
                            'percent': round(float(len(success_paths)) / float(len(self.paths)), 2),
                            'text': str(int(round(float(len(success_paths)) / float(len(self.paths)), 2) * 100)) + '%'
                        }

                        self.on_running(self.status_id, progress=progress, pid=self.pid, pname=self.name)
                        next_tick = time.time() + REQUEST_DELAY

                except Exception as e:
                    self.logger.error("Error removing file %s , error %s" % (str(path), str(e)))
                    error_paths.append(path)

            result = {
                "success": success_paths,
                "errors": error_paths
            }

            progress = {
                'percent': round(float(len(success_paths)) / float(len(self.paths)), 2),
                'text': str(int(round(float(len(success_paths)) / float(len(self.paths)), 2) * 100)) + '%'
            }

            self.on_success(self.status_id, data=result, progress=progress, pid=self.pid, pname=self.name)

        except Exception as e:
            result = {
                "error": True,
                "message": str(e),
                "traceback": traceback.format_exc()
            }

            self.on_error(self.status_id, result, pid=self.pid, pname=self.name)
