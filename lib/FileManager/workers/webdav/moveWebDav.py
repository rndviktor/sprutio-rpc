from lib.FileManager.workers.baseWorkerCustomer import BaseWorkerCustomer
from lib.FileManager.WebDavConnection import WebDavConnection
from lib.FileManager.workers.progress_helper import update_progress
from lib.FileManager.FM import REQUEST_DELAY
import traceback
import threading
import time


class MoveWebDav(BaseWorkerCustomer):
    def __init__(self, source, target, paths, overwrite, *args, **kwargs):
        super(MoveWebDav, self).__init__(*args, **kwargs)

        self.source = source
        self.target = target
        self.paths = paths
        self.overwrite = overwrite

    def run(self):
        try:
            self.preload()
            success_paths = []
            error_paths = []

            operation_progress = {
                "total_done": False,
                "total": 0,
                "operation_done": False,
                "processed": 0
            }

            source_path = self.source.get('path')
            target_directory = self.target.get('path')

            if source_path is None:
                raise Exception("Source path empty")

            if target_directory is None:
                raise Exception("Target path empty")

            self.logger.info("MoveWebDav process run source = %s , target = %s" % (source_path, target_directory))

            webdav = WebDavConnection.create(self.login, self.target.get('server_id'), self.logger)
            t_total = threading.Thread(target=self.get_total, args=(operation_progress, self.paths))
            t_total.start()

            # sleep for a while for better total counting
            time.sleep(REQUEST_DELAY)

            t_progress = threading.Thread(target=update_progress, args=(operation_progress,))
            t_progress.start()

            for path in self.paths:
                try:
                    self.logger.info("target_directory=%s" % target_directory)
                    parent_t_dir = target_directory.strip()
                    self.logger.info("parent =%s" % parent_t_dir)
                    if parent_t_dir != '/':
                        target_path = target_directory + path
                    else:
                        target_path = path.replace(source_path, "", 1)

                    if webdav.isfile(path):
                        self.logger.info("move file from source_path=%s to target_path=%s" % (path, target_path))
                        copy_result = webdav.copy_file(path, webdav.path(target_path), overwrite=True)
                        if not copy_result['success'] or len(copy_result['file_list']['failed']) > 0:
                            raise copy_result['error'] if copy_result['error'] is not None else Exception(
                                "Upload error")
                        operation_progress["processed"] += 1
                    elif webdav.isdir(path):
                        self.logger.info("move directory from source_path=%s to target_path=%s" % (path, target_path))
                        success_paths, copy_error_paths = webdav.copy_directory_recusively(path, webdav.path(target_path), self.overwrite)
                        if len(copy_error_paths) > 0:
                            error_paths.append(path)
                        operation_progress["processed"] += 1
                    else:
                        error_paths.append(path)
                        break

                    success_paths.append(path)
                    self.logger.info("error_paths=%s" % error_paths)
                    if path not in error_paths:
                        webdav.remove(path)

                except Exception as e:
                    self.logger.error(
                        "Error copy %s , error %s , %s" % (str(path), str(e), traceback.format_exc()))
                    error_paths.append(path)

            operation_progress["operation_done"] = True

            result = {
                "success": success_paths,
                "errors": error_paths
            }

            # иначе пользователям кажется что скопировалось не полностью )
            progress = {
                'percent': round(float(len(success_paths)) / float(len(self.paths)), 2),
                'text': str(int(round(float(len(success_paths)) / float(len(self.paths)), 2) * 100)) + '%'
            }
            time.sleep(REQUEST_DELAY)
            self.on_success(self.status_id, data=result, progress=progress, pid=self.pid, pname=self.name)

        except Exception as e:
            result = {
                "error": True,
                "message": str(e),
                "traceback": traceback.format_exc()
            }

            self.on_error(self.status_id, result, pid=self.pid, pname=self.name)

    def get_total(self, progress_object, paths, count_dirs=True, count_files=True):
        self.logger.debug("start get_total() dirs = %s , files = %s" % (count_dirs, count_files))
        webdav = WebDavConnection.create(self.login, self.target.get('server_id'), self.logger)
        for path in paths:
            try:
                if count_dirs:
                    progress_object["total"] += 1

                for file in webdav.listdir(path):
                    if webdav.isdir(file):
                        progress_object["total"] += 1
                    else:
                        progress_object["total"] += 1
            except Exception as e:
                self.logger.error("Error get_total file %s , error %s" % (str(path), str(e)))
                continue

        progress_object["total_done"] = True
        self.logger.debug("done get_total()")
        return
