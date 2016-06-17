from lib.FileManager.workers.baseWorkerCustomer import BaseWorkerCustomer
from lib.FileManager.SFTPConnection import SFTPConnection
from lib.FileManager.FM import REQUEST_DELAY
from config.main import TMP_DIR

import traceback
import os
import time
import libarchive


class CreateArchive(BaseWorkerCustomer):
    def __init__(self, params, session, *args, **kwargs):
        super(CreateArchive, self).__init__(*args, **kwargs)

        self.path = params.get('path')
        self.session = session
        self.type = params.get('type', 'zip')
        self.file_items = params.get('files', [])

        self.params = params

    def run(self):
        try:
            self.preload()
            sftp = SFTPConnection.create(self.login, self.session.get('server_id'), self.logger)
            abs_archive_path = os.path.join(TMP_DIR, self.login, self.random_hash())
            archive_dir = os.path.dirname(abs_archive_path)
            if not os.path.exists(archive_dir):
                os.makedirs(archive_dir)
            dir_name = os.path.dirname(self.path)

            if not sftp.exists(dir_name):
                sftp.makedirs(dir_name)
            if not sftp.isdir(dir_name):
                raise Exception("Destination path is not a directory")

            archive_type = self.get_archive_type(self.type)
            if not archive_type:
                raise Exception("Unknown archive type")

            archive_path = abs_archive_path + "." + archive_type
            if os.path.exists(archive_path):
                raise Exception("Archive file already exist")
            self.on_running(self.status_id, pid=self.pid, pname=self.name)

            archive = libarchive.Archive(archive_path, "w")
            next_tick = time.time() + REQUEST_DELAY
            i = 0
            for file_item in self.file_items:
                try:
                    abs_path = file_item.get("path")
                    file_basename = os.path.basename(abs_path)
                    if sftp.isfile(abs_path):
                        self.logger.info("Packing file: %s" % (abs_path,))
                        f = sftp.open(abs_path, 'rb')
                        archive.write(self.make_entry(abs_path, file_basename), data=f.read())
                        f.close()
                    elif sftp.isdir(abs_path):
                        self.logger.info("Packing dir: %s" % (abs_path,))
                        for current, dirs, files in sftp.walk(abs_path):
                            for f in files:
                                file_path = os.path.join(current, f)
                                file_obj = sftp.open(file_path, 'rb')
                                rel_path = os.path.relpath(file_path, abs_path)
                                base_path = os.path.join(file_basename, rel_path)
                                archive.write(self.make_entry(file_path, base_path), data=file_obj.read())
                                file_obj.close()

                    i += 1
                    if time.time() > next_tick:
                        progress = {
                            'percent': round(float(i) / float(len(self.file_items)), 2),
                            'text': str(int(round(float(i) / float(len(self.file_items)), 2) * 100)) + '%'
                        }
                        self.on_running(self.status_id, progress=progress, pid=self.pid, pname=self.name)
                        next_tick = time.time() + REQUEST_DELAY

                except Exception as e:
                    self.logger.error(
                        "Error archive file %s , error %s , %s" % (str(file_item), str(e), traceback.format_exc()))
                    raise e

            self.logger.info("Uploading created archive {} to remote path".format(abs_archive_path, self.path))
            remote_path = self.path + '.' + archive_type
            r = sftp.sftp.put(archive_path, remote_path)
            self.logger.info("sftp put result local_path {} remote_path {}, sftp_results {}".format(
                                        archive_path, remote_path, r))

            progress = {
                'percent': round(float(i) / float(len(self.file_items)), 2),
                'text': str(int(round(float(i) / float(len(self.file_items)), 2) * 100)) + '%'
            }
            result = {
                "archive": self._make_file_info(archive_path)
            }

            self.on_success(self.status_id, data=result, progress=progress, pid=self.pid, pname=self.name)

        except Exception as e:
            result = {
                "error": True,
                "message": str(e),
                "traceback": traceback.format_exc()
            }
            self.logger.error("SFTP createArchive error = {}".format(result))

            self.on_error(self.status_id, result, pid=self.pid, pname=self.name)

    @staticmethod
    def get_archive_type(extension):
        archive_type = False
        if extension == 'zip':
            archive_type = 'zip'
        elif extension == 'gzip':
            archive_type = 'tar.gz'
        elif extension == 'bz2':
            archive_type = 'tar.bz2'
        elif extension == 'tar':
            archive_type = 'tar'
        return archive_type

    def make_entry(self, f, base_path):
        sftp = SFTPConnection.create(self.login, self.session.get('server_id'), self.logger)
        entry = libarchive.Entry(encoding='utf-8')
        st = sftp.stat(f)
        entry.pathname = base_path
        entry.size = st.st_size
        entry.mtime = st.st_mtime
        entry.mode = st.st_mode

        return entry
