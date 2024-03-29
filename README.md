# OpenSourceStreamKeeper

A program to automate the tracking of YouTube channels and recording their streams.<br>
Main channel: https://t.me/OSSKProject

### ATTENTION!<br> Works stably on Linux systems, however, work on Windows systems may still fail. For example, video and audio tracks will not merged.<br> Report all bugs here: https://t.me/OSSKChat

All records will be saved to the root folder of the project: `./records/<CHANNEL_NAME>`<br>
The event log is stored in the `stream_saver.log` file.

Channel management:
- To add a channel, enter its YouTube tag in the box and click "Add channel"
- To configure a channel, right-click on its line and select "Channel settings"
- To delete a channel, right-click on its line and select "Delete channel" (can't delete a channel if it have non-finished download processes)

Process management:
 - to view the output of a process, open its context menu and select "Open tab"
 - to stop the process, select "Stop process" in its context menu
 - in order to hide a completed process, select "Hide process" from its context menu (the downloaded file *will not* be deleted).

Settings (`settings` file):
- in the _ffmpeg field_, enter the path to the ffmpeg library / .exe file
- in the _yt-dlp_ field, enter the run command or the path to the yt-dlp library / .exe file (default: `python -m yt_dlp`)
- you can specify a maximum number of concurrent downloads to limit CPU, disk and network usage (default: `2`)
- you can specify the idle time between full channel scan cycles in minutes (default: `5`).
  This option will avoid a ban from YouTube, which may consider the scan as a DoS attack.

Channel settings:
- if an alias is specified, it will be displayed in the channel line instead of its ID
- stream video quality[`480`, `720`, `1080`]: an attempt will be made downloads
 in this capacity. If the format is not available, the download will be cancelled.
- stream video quality[`best`]: search for the best available format (top to bottom).

---

Программа для автоматизации отслеживания YouTube каналов и записи их стримов.
Основной канал: https://t.me/OSSKProject

### ВНИМАНИЕ!<br> Стабильно работает в системах Linux, однако работа на системах Windows пока ещё может дать сбой. Например не объеденятся видео- и аудио-дорожки.<br> Обо всех ошибках пишите сюда: https://t.me/OSSKChat

Все записи будут сохраняться в корневую папку проекта: `./records/<НАЗВАНИЕ_КАНАЛА>`<br>
Журнал событий сохраняется в файл `stream_saver.log`.

Управление каналами:
- для добавления канала введите его YouTube тэг в поле, и нажмите "Добавить канал"
- для настройки канала щелкните по его строке правой кнопкой и выберите "Настройки канал"
- для удаления канала щелкните по его строке правой кнопкой и выберите "Удалить канал" (нельзя удалить канал, если у него имеются незавершенные процессы загрузки)

Управление процессами загрузки:
- для просмотра вывода процесса, откройте контекстное меню процесса и выберите "Открыть вкладку"
- для остановки процесса, выберите в его контекстном меню "Остановить процесс"
- для того, чтобы скрыть завершенный процесс, выберите в его контекстном меню "Скрыть процесс" (загруженный файл *не* будет удален).

Настройки (файл `settings`):
- в поле _ffmpeg_ введите путь до библиотеки / .exe-файла ffmpeg;
- в поле _yt-dlp_ введите команду запуска или путь до библиотеки / .exe-файла yt-dlp (по-умолчанию: `python -m yt_dlp`)
- можно указать максимальное количество одновременных загрузок для ограничения нагрузки на CPU, диск и сеть (по-умолчанию: `2`)
- можно указать время простоя между полными циклами сканирования каналов в минутах (по-умолчанию: `5`).
Эта опция позволит избежать бана со стороны YouTube, который может счесть сканирование за DoS атаку.

Настройки канала:
- если указан псевдоним, то он будет отображаться в строке канала вместо его ID
- качество записи видео-потока[`480`, `720`, `1080`]: будет произведена попытка
загрузки именно в этом качестве. Если формат недоступен - загрузка будет отменена.
- качество записи видео-потока[`best`]: будет произведен поиск лучшего
доступного формата (сверху вниз).
