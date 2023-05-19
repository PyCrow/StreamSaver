from __future__ import annotations

import sys
import logging as lg
from logging import DEBUG, INFO, WARNING, ERROR
from queue import Queue
from signal import SIGINT
from time import sleep
import subprocess
from typing import Any

import yt_dlp
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, Qt, QMutex
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel
)

from static_vars import (
    UNKNOWN, LOG_FILE,
    KEY_FFMPEG, KEY_YTDLP, KEY_CHANNELS, KEY_MAX_DOWNLOADS, KEY_SCANNER_SLEEP,
    DEFAULT_MAX_DOWNLOADS, DEFAULT_SCANNER_SLEEP,
    StopThreads, RecordProcess,
    STYLESHEET_PATH, FLAG_LIVE)
from ui.classes import ListChannels, LogWidget, ChannelStatus, SettingsWindow
from utils import (
    get_config, save_config,
    is_callable, check_exists_and_callable,
    get_channel_dir,
)

PATH_TO_FFMPEG = ''
YTDLP_COMMAND = 'python -m yt_dlp'

GLOBAL_STOP = False
THREADS_LOCK = QMutex()

handler = lg.FileHandler(LOG_FILE, encoding='utf-8')
handler.setLevel(lg.INFO)
handler.setFormatter(lg.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s', "%Y-%m-%d %H:%M:%S"))
logger = lg.getLogger()
logger.setLevel(DEBUG)
logger.addHandler(handler)
DEBUG_LEVELS = {DEBUG: 'DEBUG', INFO: 'INFO',
                WARNING: 'WARNING', ERROR: 'ERROR'}


class ThreadSafeList(list):
    def __contains__(self, _obj) -> bool:
        THREADS_LOCK.lock()
        ret = super(ThreadSafeList, self).__contains__(_obj)
        THREADS_LOCK.unlock()
        return ret

    def __len__(self) -> int:
        THREADS_LOCK.lock()
        ret = super(ThreadSafeList, self).__len__()
        THREADS_LOCK.unlock()
        return ret

    def append(self, _obj) -> None:
        THREADS_LOCK.lock()
        super(ThreadSafeList, self).append(_obj)
        THREADS_LOCK.unlock()

    def pop(self, __index: int = ...) -> Any:
        THREADS_LOCK.lock()
        ret = super(ThreadSafeList, self).pop(__index)
        THREADS_LOCK.unlock()
        return ret


def logger_handler(func):
    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if not isinstance(e, StopThreads):
                logger.exception("Function {func_name} got exception: {err}"
                                 .format(func_name=func.__name__, err=e),
                                 stack_info=True)
            raise e

    return _wrapper


def set_stop_threads():
    global GLOBAL_STOP
    GLOBAL_STOP = True


def raise_on_stop_threads(func=None):
    def _check():
        global GLOBAL_STOP
        if GLOBAL_STOP:
            raise StopThreads

    if func is None:
        _check()
        return

    def _wrapper(*args, **kwargs):
        _check()
        ret = func(*args, **kwargs)
        _check()
        return ret

    return _wrapper


class MainWindow(QWidget):
    def __init__(self):
        super(MainWindow, self).__init__()
        self._channels: list[str] = []

        self._init_ui()
        self._load_config()

        self.Master = Master(self._channels)
        self.Master.s_log[int, str].connect(self.add_log_message)
        self.Master.s_stream_off[str].connect(self._stream_off)
        self.Master.s_stream_in_queue[str].connect(self._stream_in_queue)
        self.Master.Slave.s_stream_rec[str].connect(self._stream_rec)
        self.Master.Slave.s_stream_off[str].connect(self._stream_off)
        self.Master.Slave.s_stream_fail[str].connect(self._stream_fail)

    def _load_config(self):
        """ Loading configuration """
        config: dict | None = get_config()
        if config is None:
            self.add_log_message(ERROR, "Settings loading error!")
            return
        self._channels: list = config.get(KEY_CHANNELS, [])
        if len(self._channels) > 0:
            self._widget_list_channels.add_str_items(self._channels)
        # ffmpeg path will be checked on field "textChanged" signal
        ffmpeg_value = config.get(KEY_FFMPEG, PATH_TO_FFMPEG)
        ytdlp_value = config.get(KEY_YTDLP, YTDLP_COMMAND)
        max_downloads = config.get(KEY_MAX_DOWNLOADS, DEFAULT_MAX_DOWNLOADS)
        scanner_sleep = config.get(KEY_SCANNER_SLEEP, DEFAULT_SCANNER_SLEEP)
        self.settings_window.field_ffmpeg.setText(ffmpeg_value)
        self.settings_window.field_ytdlp.setText(ytdlp_value)
        self.settings_window.box_max_downloads.setValue(max_downloads)
        self.settings_window.box_scanner_sleep.setValue(scanner_sleep // 60)

    @pyqtSlot()
    def _save_config(self):
        """ Saving configuration """
        ffmpeg_path = (self.settings_window.field_ffmpeg.text()
                       or PATH_TO_FFMPEG)
        ytdlp_command = (self.settings_window.field_ytdlp.text()
                         or YTDLP_COMMAND)
        max_downloads = self.settings_window.box_max_downloads.value()
        scanner_sleep = self.settings_window.box_scanner_sleep.value() * 60
        suc = save_config({
            KEY_FFMPEG: ffmpeg_path,
            KEY_YTDLP: ytdlp_command,
            KEY_MAX_DOWNLOADS: max_downloads,
            KEY_SCANNER_SLEEP: scanner_sleep,
            KEY_CHANNELS: self._channels,
        })
        if not suc:
            self.add_log_message(ERROR, "Settings saving error!")

        # Edit configuration when scanning and recording in progress
        THREADS_LOCK.lock()
        self.Master.scanner_sleep = scanner_sleep
        self.Master.Slave.max_downloads = max_downloads
        self.Master.Slave.ytdlp_command = ytdlp_command
        THREADS_LOCK.unlock()

        self.add_log_message(INFO, "Threads settings updated.")

    def _init_ui(self):
        self.setWindowTitle("StreamSaver")
        self.resize(980, 600)

        # Окно настроек
        button_settings = QPushButton('Settings')
        button_settings.clicked[bool].connect(self.clicked_open_settings)
        self.settings_window = SettingsWindow()
        self.settings_window.button_apply.clicked.connect(self._save_config)

        self._field_channels_edit = QLineEdit()
        self._field_channels_edit.setPlaceholderText("Enter channel name")

        button_add_channel = QPushButton("Add channel")
        button_add_channel.clicked[bool].connect(self.add_channel)
        button_del_channel = QPushButton("Delete channel")
        button_del_channel.clicked[bool].connect(self.del_channel)
        hbox_channel_buttons = QHBoxLayout()
        hbox_channel_buttons.addWidget(button_add_channel)
        hbox_channel_buttons.addWidget(button_del_channel)

        label_channels = QLabel("Monitored channels")

        self._widget_list_channels = ListChannels()

        left_vbox = QVBoxLayout()
        left_vbox.addWidget(button_settings)
        left_vbox.addWidget(self._field_channels_edit)
        left_vbox.addLayout(hbox_channel_buttons)
        left_vbox.addWidget(label_channels, alignment=Qt.AlignHCenter)
        left_vbox.addWidget(self._widget_list_channels)

        label_log = QLabel("Event log")
        self._widget_log = LogWidget()
        vbox_log = QVBoxLayout()
        vbox_log.addWidget(label_log, alignment=Qt.AlignHCenter)
        vbox_log.addWidget(self._widget_log)

        main_hbox = QHBoxLayout()
        main_hbox.addLayout(left_vbox, 1)
        main_hbox.addLayout(vbox_log, 2)

        self.start_button = QPushButton("Start")
        self.start_button.clicked[bool].connect(self.run_master)
        self.stop_button = QPushButton("Stop all")
        self.stop_button.clicked[bool].connect(set_stop_threads)
        hbox_master_buttons = QHBoxLayout()
        hbox_master_buttons.addWidget(self.start_button)
        hbox_master_buttons.addWidget(self.stop_button)

        main_box = QVBoxLayout()
        main_box.addLayout(main_hbox)
        main_box.addLayout(hbox_master_buttons)

        self.setLayout(main_box)

        # Загрузка стиля
        style = STYLESHEET_PATH.read_text()
        self.setStyleSheet(style)
        self.settings_window.setStyleSheet(style)

    @pyqtSlot(bool)
    def clicked_open_settings(self):
        self.settings_window.show()

    @pyqtSlot(bool)
    def run_master(self):
        ytdlp_command = self.settings_window.field_ytdlp.text()
        if not is_callable(ytdlp_command):
            self.add_log_message(WARNING, "yt-dlp not found.")
            return

        ffmpeg_path = self.settings_window.field_ffmpeg.text()
        if not check_exists_and_callable(ffmpeg_path):
            self.add_log_message(WARNING, "ffmpeg not found.")
            return

        if self.Master.isRunning():
            return

        global GLOBAL_STOP
        GLOBAL_STOP = False

        self.Master.Slave.ytdlp_command = ytdlp_command
        self.Master.Slave.path_to_ffmpeg = ffmpeg_path
        self.Master.start()

    @pyqtSlot(int, str)
    def add_log_message(self, lvl: int, text: str):
        self._widget_log.add_message(f"[{DEBUG_LEVELS[lvl]}] {text}")
        logger.log(lvl, text)

    @pyqtSlot(bool)
    def add_channel(self):
        """ Проверяем есть ли канал в списке, и добавляем его в потоки"""
        channel_name = self._field_channels_edit.text()
        if channel_name in self._channels:
            return
        self._channels.append(channel_name)
        self._save_config()
        self.Master.channels.append(channel_name)
        self._widget_list_channels.add_str_item(channel_name)
        self._field_channels_edit.clear()

    @pyqtSlot(bool)
    def del_channel(self):
        channel_name = self._field_channels_edit.text()
        if channel_name not in self._channels:
            return
        self._channels.remove(channel_name)
        self._save_config()
        self.Master.channels.remove(channel_name)
        self._widget_list_channels.del_item_by_name(channel_name)
        self._field_channels_edit.clear()

    @pyqtSlot(str)
    def _stream_off(self, ch_name: str):
        ch_index = self._channels.index(ch_name)
        self._widget_list_channels.set_stream_status(ch_index,
                                                     ChannelStatus.OFF)

    @pyqtSlot(str)
    def _stream_in_queue(self, ch_name: str):
        ch_index = self._channels.index(ch_name)
        self._widget_list_channels.set_stream_status(ch_index,
                                                     ChannelStatus.QUEUE)

    @pyqtSlot(str)
    def _stream_rec(self, ch_name: str):
        ch_index = self._channels.index(ch_name)
        self._widget_list_channels.set_stream_status(ch_index,
                                                     ChannelStatus.REC)

    @pyqtSlot(str)
    def _stream_fail(self, ch_name: str):
        ch_index = self._channels.index(ch_name)
        self._widget_list_channels.set_stream_status(ch_index,
                                                     ChannelStatus.FAIL)


class Master(QThread):
    """
    Master:
     - run Slave
     - search for new streams
     - edit Slave's queue
    """

    s_log = pyqtSignal(int, str)
    s_stream_off = pyqtSignal(str)
    s_stream_in_queue = pyqtSignal(str)

    def __init__(self, channels):
        super(Master, self).__init__()
        self.channels: list[str] = ThreadSafeList(channels)
        self.last_status: dict[str, bool] = {}
        self.scheduled_streams: dict[str, bool] = {}
        self.scanner_sleep: int = DEFAULT_SCANNER_SLEEP * 60
        self.Slave = Slave()
        self.Slave.s_log[int, str].connect(self.log)

    def log(self, level: int, text: str):
        self.s_log[int, str].emit(level, text)

    def run(self) -> None:
        self.log(INFO, "Scanning channels started.")
        self.Slave.start()

        try:
            while True:
                raise_on_stop_threads()
                for channel_name in self.channels:
                    self._check_for_stream(channel_name)
                raise_on_stop_threads()
                sleep(self.scanner_sleep)
        except StopThreads:
            pass
        self.log(INFO, "Scanning channels stopped.")

    def channel_status_changed(self, channel_name: str, status: bool):
        if (channel_name in self.last_status
                and self.last_status[channel_name] == status):
            return False
        self.last_status[channel_name] = status
        return True

    @raise_on_stop_threads
    @logger_handler
    def _check_for_stream(self, channel_name: str):
        url = f'https://www.youtube.com/@{channel_name}/live'
        ytdl_options = {'quiet': True, 'default_search': 'ytsearch'}

        with yt_dlp.YoutubeDL(ytdl_options) as ydl:
            try:
                info_dict: dict = ydl.extract_info(
                    url, download=False,
                    extra_info={'quiet': True, 'verbose': False})
            except yt_dlp.utils.UserNotLive:
                self.s_stream_off[str].emit(channel_name)
                return
            except yt_dlp.utils.DownloadError as e:
                # Check for live flag and last status
                if (FLAG_LIVE in str(e)
                        and self.scheduled_streams.get(channel_name,
                                                       False) is False):
                    warn = str(e)
                    leftover = warn[warn.find(FLAG_LIVE) + len(FLAG_LIVE):]
                    self.log(WARNING,
                             f"{channel_name} stream in {leftover}.")
                    self.scheduled_streams[channel_name] = True
                self.s_stream_off[str].emit(channel_name)
                return
            except Exception as e:
                logger.exception(e)
                self.log(ERROR, f"<yt-dlp>: {str(e)}")
                self.s_stream_off[str].emit(channel_name)
                return

        # Check channel stream is on
        if info_dict.get("is_live"):
            if self.channel_status_changed(channel_name, True):
                self.log(INFO, f"Channel {channel_name} is online.")

            # Проверка готов ли Загрузчик
            # TODO: check stream_data not in self.Slave.queue
            if channel_name not in self.Slave.active_downloading_channels:
                stream_data = {'channel_name': channel_name,
                               'url': info_dict.get('webpage_url')}
                self.Slave.queue.put(stream_data, block=True)
                self.log(INFO, f"Recording {channel_name} added to queue.")
                self.s_stream_in_queue[str].emit(channel_name)
        elif self.channel_status_changed(channel_name, False):
            self.s_stream_off[str].emit(channel_name)
            self.log(INFO, f"Channel {channel_name} is offline.")


class Slave(QThread):
    # TODO: add memory check
    s_log = pyqtSignal(int, str)
    s_stream_rec = pyqtSignal(str)
    s_stream_off = pyqtSignal(str)
    s_stream_fail = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ytdlp_command = YTDLP_COMMAND
        self.path_to_ffmpeg = PATH_TO_FFMPEG
        self.active_downloading_channels: list[str] = []
        self.queue: Queue[dict[str, str]] = Queue(-1)
        self.max_downloads: int = DEFAULT_MAX_DOWNLOADS
        self.running_downloads: list[RecordProcess] = []

    def log(self, level: int, text: str):
        self.s_log[int, str].emit(level, text)

    def run(self):
        self.log(INFO, "Recorder started.")

        try:
            while True:
                self.check_running_downloads()
                if self.ready_to_download() and not self.queue.empty():
                    stream_data = self.queue.get()
                    self.record_stream(stream_data)
                sleep(10)
        except StopThreads:
            self.stop_downloads()
        self.log(INFO, "Recorder stopped.")

    @raise_on_stop_threads
    def check_running_downloads(self):

        list_running = []

        for proc in self.running_downloads:
            ret_code = proc.poll()

            if ret_code is None:
                list_running.append(proc)
                continue
            if ret_code == 0:
                self.s_stream_off[str].emit(proc.channel)
                self.log(INFO, f"Recording {proc.channel} finished.")
            else:
                self.s_stream_fail[str].emit(proc.channel)
                self.log(ERROR, f"Recording {proc.channel} "
                                f"stopped with an error code: {ret_code}")
                # TODO: add temp buffer
                if proc.stdout:
                    self.log(ERROR, f"Process[{proc.pid}] output:")
                    for i in proc.stdout.readlines():
                        self.log(ERROR, ">>> " + i)
                if proc.stderr:
                    self.log(ERROR, f"Process[{proc.pid}] errors:")
                    for i in proc.stderr.readlines():
                        self.log(ERROR, ">>> " + i)
            self.active_downloading_channels.remove(proc.channel)

        self.running_downloads = list_running

    def ready_to_download(self) -> bool:
        if self.max_downloads == 0:
            return True
        if len(self.running_downloads) < self.max_downloads:
            return True
        return False

    @raise_on_stop_threads
    @logger_handler
    def record_stream(self, stream_data: dict[str, str]):
        """ Starts stream recording """

        channel_name = stream_data.get('channel_name', UNKNOWN)
        stream_url = stream_data.get('url')

        channel_dir = str(get_channel_dir(channel_name))
        file_name = '%(title)s.%(ext)s'

        self.log(INFO, f"Recording {channel_name} started.")

        cmd = self.ytdlp_command.split() + [
            stream_url,
            '-P', channel_dir,
            '-o', file_name,
            '--ffmpeg-location', self.path_to_ffmpeg,
            # Загружать с самого начала
            '--live-from-start',
            # Сразу в один файл
            '--no-part',
            # Обновить сокет при падении
            '--socket-timeout', '5',
            '--retries', '10',
            '--retry-sleep', '5',
            # Без прогресс-бара
            '--no-progress',
            # Лучшее качество
            '-f', 'bestvideo*+bestaudio/best',
            # Объединить в один файл mp4 или mkv
            '--merge-output-format', 'mp4/mkv',
            # Снизить шанс поломки при форсивной остановке
            '--hls-use-mpegts',
        ]

        proc = RecordProcess(
            cmd,
            stdin=subprocess.PIPE,
            # TODO: add temp buffer
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True)
        proc.channel = channel_name
        self.active_downloading_channels.append(channel_name)
        self.running_downloads.append(proc)

        self.s_stream_rec[str].emit(channel_name)

    @logger_handler
    def stop_downloads(self):
        """ Stop all downloads """
        if not self.running_downloads:
            return
        self.log(INFO, "Stopping records.")
        # FIXME: refactor iteration
        for proc in self.running_downloads:
            try:
                self.log(INFO, f"Stopping process {proc.pid}...")
                # FIXME: subprocess on Windows cannot identify SIGINT
                proc.send_signal(SIGINT)
                # TODO: add editing "wait-for-process-stopped"
                ret = proc.wait(30)
                if ret == 0:
                    self.s_stream_off[str].emit(proc.channel)
                else:
                    self.s_stream_fail[str].emit(proc.channel)
                    self.log(ERROR, "Error while stopping channel {} record :("
                             .format(proc.channel))
            except subprocess.TimeoutExpired:
                proc.kill()
                self.s_stream_fail[str].emit(proc.channel)
                self.log(WARNING,
                         "Recording[{}] of channel {} resisted, but I'm "
                         "stronger!".format(proc.pid, proc.channel))
            except ValueError:
                self.log(ERROR, "Record stop error. Forced stop.")
                proc.kill()
                self.s_stream_fail[str].emit(proc.channel)
                self.log(WARNING,
                         "Recording[{}] of channel {} resisted, but I'm "
                         "stronger!".format(proc.pid, proc.channel))


if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()

        sys.exit(app.exec_())
    except Exception as e_:
        logger.exception(e_)
    finally:
        GLOBAL_STOP = True
