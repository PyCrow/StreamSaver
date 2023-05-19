from __future__ import annotations

from datetime import datetime
from typing import Iterable

from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QLinearGradient, \
    QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLineEdit, \
    QListView, QAbstractItemView, QLabel, QSpinBox

from ui.dynamic_style import STYLE
from utils import check_exists_and_callable, is_callable


class ChannelStatus:
    OFF = 0
    QUEUE = 1
    REC = 2
    FAIL = 3


def _get_channel_status_color(status_id) -> QLinearGradient:
    colors = {ChannelStatus.OFF: QColor(50, 50, 50),
              ChannelStatus.QUEUE: QColor(200, 200, 0),
              ChannelStatus.REC: QColor(0, 200, 0),
              ChannelStatus.FAIL: QColor(200, 0, 0)}
    color = colors[status_id]
    gradient = QLinearGradient(0, 0, 280, 0)
    gradient.setColorAt(0.0, QColor(25, 25, 25))
    gradient.setColorAt(0.9, QColor(25, 25, 25))
    gradient.setColorAt(1.0, color)
    return gradient


class ListView(QListView):

    def __init__(self):
        super().__init__()
        self._model = QStandardItemModel()
        self.setModel(self._model)
        self.setWordWrap(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    def add_str_item(self, text: str):
        item = QStandardItem(text)
        item.setEditable(False)
        self._model.appendRow(item)

    def add_str_items(self, list_items: Iterable[str]):
        for i in list_items:
            self.add_str_item(i)

    def del_item_by_name(self, item_name: str):
        for row in range(self._model.rowCount()):
            if self._model.item(row).text() == item_name:
                self._model.removeRow(row)
                break


class ListChannels(ListView):

    def set_stream_status(self, ch_index: int, status_id: int):
        """ Sets channel's row color """
        # TODO: make it with a dynamic_style or any other way
        color = _get_channel_status_color(status_id)
        self._model.item(ch_index).setBackground(color)


class LogWidget(ListView):
    _items_limit = 500

    @property
    def time(self):
        now = datetime.now()
        return now.strftime("%H:%M:%S")

    def __init__(self):
        super().__init__()

    def add_message(self, text):
        message = f"{self.time} {text}"
        self.add_str_item(message)
        if self._model.rowCount() > self._items_limit:
            self._model.removeRow(0)
        self.scrollToBottom()


class SettingsWindow(QWidget):
    def __init__(self):
        super(SettingsWindow, self).__init__()
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("StreamSaver | Settings")
        self.setWindowModality(Qt.ApplicationModal)

        self.setMinimumWidth(400)
        self.setMaximumWidth(750)
        self.setMinimumHeight(300)
        self.setMaximumHeight(500)
        self.resize(500, 360)

        self.field_ffmpeg = QLineEdit(parent=self)
        self.field_ffmpeg.setPlaceholderText(
            "Enter path to ffmpeg")
        self.field_ffmpeg.textChanged[str].connect(self._check_ffmpeg)
        self.field_ffmpeg.setToolTip(
            "Checks:\n"
            "1. Is the specified path available as a file.\n"
            "2. Is the specified file can be called.\n"
            "The field is highlighted in red if the path file is"
            " not available."
        )

        self.field_ytdlp = QLineEdit(parent=self)
        self.field_ytdlp.setPlaceholderText(
            "Enter command or path to yt-dlp")
        self.field_ytdlp.textChanged[str].connect(self._check_ytdlp)
        self.field_ytdlp.setToolTip(
            "Checks:\n"
            "1. Is called as a command.\n"
            "2. Is the specified path available as a file.\n"
            "3. Is the specified file can be called.\n"
            "The field is highlighted in red if the path file is"
            " not available."
        )

        self.box_max_downloads = QSpinBox(self)
        self.box_max_downloads.setToolTip(
            "Range from 1 to 50.\n"
            "It is not recommended to set a value greater than 12 or 0.\n"
            "0 - no restrictions."
        )
        self.box_max_downloads.setRange(0, 50)
        self.box_max_downloads.valueChanged[int].connect(
            self._check_max_downloads)

        self.box_scanner_sleep = QSpinBox(self)
        self.box_scanner_sleep.setToolTip(
            "Waiting time between channel scans (minutes).\n"
            "Range from 1 to 60.\n"
            "It is not recommended to set it to less than 5 minutes, so\n"
            " that YouTube does not consider the scan as a DoS attack."
        )
        self.box_scanner_sleep.setRange(1, 60)
        self.box_scanner_sleep.valueChanged[int].connect(
            self._check_scanner_sleep)

        self.button_apply = QPushButton("Accept", self)

        vbox = QVBoxLayout()
        vbox.addWidget(QLabel("Path to ffmpeg"))
        vbox.addWidget(self.field_ffmpeg)
        vbox.addStretch(0)
        vbox.addWidget(QLabel("Command or path to yt-dlp"))
        vbox.addWidget(self.field_ytdlp)
        vbox.addStretch(0)
        vbox.addWidget(QLabel("Maximum number of synchronous downloads"))
        vbox.addWidget(self.box_max_downloads)
        vbox.addStretch(0)
        vbox.addWidget(QLabel("Time between scans (minutes)"))
        vbox.addWidget(self.box_scanner_sleep)
        vbox.addStretch(0)
        vbox.addWidget(self.button_apply)

        self.setLayout(vbox)

    @pyqtSlot(int)
    def _check_max_downloads(self, value: int):
        if value == 0 or value > 12:
            self.box_max_downloads.setStyleSheet(STYLE.SPIN_WARNING)
        else:
            self.box_max_downloads.setStyleSheet(STYLE.SPIN_VALID)

    @pyqtSlot(str)
    def _check_ffmpeg(self, ffmpeg_path: str):
        suc = check_exists_and_callable(ffmpeg_path)
        if not suc:
            self.field_ffmpeg.setStyleSheet(STYLE.LINE_INVALID)
        else:
            self.field_ffmpeg.setStyleSheet(STYLE.LINE_VALID)

    @pyqtSlot(str)
    def _check_ytdlp(self, ytdlp_path: str):
        suc = is_callable(ytdlp_path)
        if not suc:
            self.field_ytdlp.setStyleSheet(STYLE.LINE_INVALID)
        else:
            self.field_ytdlp.setStyleSheet(STYLE.LINE_VALID)

    @pyqtSlot(int)
    def _check_scanner_sleep(self, value: int):
        if value < 5:
            self.box_scanner_sleep.setStyleSheet(STYLE.SPIN_WARNING)
        else:
            self.box_scanner_sleep.setStyleSheet(STYLE.SPIN_VALID)
