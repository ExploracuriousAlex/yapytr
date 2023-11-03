"""
A DocDownload class.
"""
import asyncio
import json
import re
import sys
from concurrent.futures import as_completed
from pathlib import Path

from pathvalidate import sanitize_filepath
from requests.sessions import Session
from requests_futures.sessions import FuturesSession

from .timeline import Timeline
from .tr_api import TradeRepublicError
from .utils import export_transactions, get_colored_logger, json_preview


class DocDownload:
    """
    Class to download document from Trade Republic.
    """

    def __init__(
        self,
        tr_api,
        output_path,
        filename_fmt,
        since_timestamp=0,
        download_history_file="download_history",
        max_workers=8,
    ):
        """
        Initializes the instance.

        Args:
            tr_api: The `TradeRepublicApi` object to be used to interact with Trade Republic.
            output_path: Name of the folder in which the files are to be saved.
            filename_fmt: File name format.
            since_timestamp: Earliest date of documents for download. Defaults to 0.
            download_history_file: Name of the file in which the download history is saved.
            Defaults to "download_history".
            max_workers: Number of parallel sessions for the download. Defaults to 8.
        """

        self._log = get_colored_logger(__name__)

        self.all_timeline_details_received = False

        self._tr_api = tr_api
        self._output_path = Path(output_path)
        self._filename_fmt = filename_fmt
        self._since_timestamp = since_timestamp
        self._download_history_file = self._output_path / download_history_file

        requests_session = Session()
        if self._tr_api._weblogin:
            requests_session.headers = self._tr_api._default_headers_web
        else:
            requests_session.headers = self._tr_api._default_headers
        self._session = FuturesSession(
            max_workers=max_workers, session=requests_session
        )

        self._futures = []
        self._completed_downloads = 0
        self._tl = Timeline(self._tr_api)
        self._download_history = []
        self._read_or_create_download_history()
        self._download_queue = []

        self._output_path.mkdir(parents=True, exist_ok=True)

    def _read_or_create_download_history(self):
        """
        Read download history.

        Attempts to read the document download history.
        If the file does not exist, create an empty file.
        """

        if self._download_history_file.exists():
            with self._download_history_file.open() as f:
                self._download_history = f.read().splitlines()
            self._log.info(
                "Download history file contains %s entries.",
                len(self._download_history),
            )
        else:
            self._download_history_file.parent.mkdir(exist_ok=True, parents=True)
            self._download_history_file.touch()
            self._log.info("Successfully generated the document download history file.")

    async def _download_loop(self):
        """
        Requests timelines and timeline details from Trade Republic websocket
        and processes them upon receipt.

        When a timeline packet is received, a check is made to see
        if there is another part and if so, it is requested.
        When a timeline detail is received, processing is triggered.
        """
        await self._tl.get_timeline(max_age_timestamp=self._since_timestamp)

        while not self.all_timeline_details_received:
            try:
                self._log.debug("Schubi...")
                _subscription_id, subscription, response = await self._tr_api.recv()
                self._log.debug("...dubidu")

            except TradeRepublicError as e:
                self._log.fatal(str(e))

            if subscription["type"] == "timeline":
                await self._tl.get_timeline(
                    response, max_age_timestamp=self._since_timestamp
                )
            elif subscription["type"] == "timelineDetail":
                await self._tl.process_timeline_detail(
                    response, self, max_age_timestamp=self._since_timestamp
                )
            else:
                self._log.warning(
                    "Unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

        self._save_timeline_events(
            self._tl.timeline_events_without_docs, "other_events.json"
        )
        self._save_timeline_events(
            self._tl.timeline_events_with_docs, "events_with_documents.json"
        )

        export_transactions(
            self._output_path / "other_events.json",
            self._output_path / "account_transactions.csv",
        )

        self._prepare_download()

    def _save_timeline_events(self, timeline_events, filename):
        """
        Save timeline events to file.

        Args:
            timeline_events: Timeline events.
            filename: File name.
        """
        with open(self._output_path / filename, "w", encoding="utf-8") as f:
            json.dump(timeline_events, f, ensure_ascii=False, indent=2)

    def add_to_download_queue(self, doc, title_text, subtitle_text, subfolder=None):
        """
        Add a document to be downloaded.

        Generate a local file destination path based on the document data.
        Save this path, along with the source URL, in the download list for later download.
        """

        doc_url = doc["action"]["payload"]
        doc_url_base = doc_url.split("?")[0]

        date = doc["detail"]
        iso_date = "-".join(date.split(".")[::-1])

        doc_id = doc["id"]
        self._log.debug("Try adding doc with id '%s' to download list...", doc_id)

        # extract time from subtitleText
        time = re.findall("um (\\d+:\\d+) Uhr", subtitle_text)

        if time == []:
            time = ""
        else:
            time = f" {time[0]}"

        if subfolder is not None:
            directory = self._output_path / subfolder
        else:
            directory = self._output_path

        # If doc_type is something like 'Kosteninformation 2',
        # then strip the 2 and save it in doc_type_num

        doc_type = doc["title"].rsplit(" ")

        if doc_type[-1].isnumeric() is True:
            doc_type_num = f" {doc_type.pop()}"
        else:
            doc_type_num = ""

        doc_type = " ".join(doc_type)

        title_text = title_text.replace("\n", "").replace("/", "-")

        subtitle_text = subtitle_text.replace("\n", "").replace("/", "-")

        filename = self._filename_fmt.format(
            iso_date=iso_date,
            time=time,
            title=title_text,
            subtitle=subtitle_text,
            doc_num=doc_type_num,
            id=doc_id,
        )

        filename_with_doc_id = filename + f" ({doc_id})"

        if doc_type in ["Kontoauszug", "Depotauszug"]:
            filepath = directory / "Abschlüsse" / f"{filename}" / f"{doc_type}.pdf"
            filepath_with_doc_id = (
                directory / "Abschlüsse" / f"{filename_with_doc_id}" / f"{doc_type}.pdf"
            )
        else:
            filepath = directory / doc_type / f"{filename}.pdf"
            filepath_with_doc_id = directory / doc_type / f"{filename_with_doc_id}.pdf"

        filepath = sanitize_filepath(filepath, "_", "universal")
        filepath_with_doc_id = sanitize_filepath(filepath_with_doc_id, "_", "universal")

        download_job = {
            "doc_url": doc_url,
            "doc_url_base": doc_url_base,
            "filepath": filepath,
            "filepath_with_doc_id": filepath_with_doc_id,
        }

        if doc_url_base in self._download_history:
            self._log.debug(
                "Source URL %s is already in history. Skipping...", doc_url_base
            )
            return

        if (
            sum(
                1
                for dlj in self._download_queue
                if dlj.get("doc_url_base") == doc_url_base
            )
            == 0
        ):
            self._download_queue.append(download_job)
        else:
            self._log.debug(
                "Source URL %s is already in queue. Skipping...", doc_url_base
            )

    def _prepare_download(self):
        """
        Prepare download.

        Check the download queue for conflicts (e.g. multiple downloads with the same target path)
        and fixes them.
        Initiate the download.
        """

        for dlj in self._download_queue:
            doc_url = dlj.get("doc_url")
            doc_url_base = dlj.get("doc_url_base")
            filepath = dlj.get("filepath")
            filepath_with_doc_id = dlj.get("filepath_with_doc_id")

            future = self._session.get(doc_url)

            if (
                sum(
                    1
                    for entry in self._download_queue
                    if entry.get("filepath") == filepath
                )
                == 1
            ):
                future.filepath = filepath
            else:
                if (
                    sum(
                        1
                        for entry in self._download_queue
                        if entry.get("filepath_with_doc_id") == filepath_with_doc_id
                    )
                    == 1
                ):
                    future.filepath = filepath_with_doc_id
                else:
                    self._log.error(
                        "Can't do multiple downloads with the same destination '%s'.",
                        filepath_with_doc_id,
                    )
                    continue

            future.doc_url_base = doc_url_base
            self._futures.append(future)
            self._log.debug("Added %s to the actual download queue.", future.filepath)

        self._run_downloads()

    def _run_downloads(self):
        """
        Execute documents download.
        """

        if len(self._download_queue) == 0:
            self._log.info("Nothing to download.")
            sys.exit(0)

        with open(
            self._download_history_file, "a", encoding="utf-8"
        ) as download_history_file:
            self._log.info("Waiting for downloads to complete..")

            for future in as_completed(self._futures):
                if future.filepath.is_file() is True:
                    self._log.warning(
                        "File '%s' was already downloaded. Overwrite.", future.filepath
                    )

                try:
                    r = future.result()
                except Exception as e:
                    self._log.fatal(str(e))

                future.filepath.parent.mkdir(parents=True, exist_ok=True)

                with open(future.filepath, "wb") as f:
                    f.write(r.content)

                    self._completed_downloads += 1

                    download_history_file.write(f"{future.doc_url_base}\n")

                    self._log.debug(
                        "%3s/%s %s",
                        self._completed_downloads,
                        len(self._download_queue),
                        future.filepath.name,
                    )

                # if self._completed_downloads == len(self.download_queue):
                #     self.log.info("Done.")

                #     sys.exit(0)
        self._log.info("Done.")

    def download(self):
        """
        Download documents.

        *** Execute the data receiving loop to receive the portfolio.
        *** The received data can be printed with `print_portfolio` method.
        """

        asyncio.get_event_loop().run_until_complete(self._download_loop())
