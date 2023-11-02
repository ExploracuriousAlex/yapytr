"""
Module providing the DocDownload class for Trade Republic document download handling.
"""
import re
from concurrent.futures import as_completed
from pathlib import Path

from pathvalidate import sanitize_filepath
from requests.sessions import Session
from requests_futures.sessions import FuturesSession

from .timeline import Timeline
from .tr_api import TradeRepublicError
from .utils import get_colored_logger, json_preview


class DocDownload:
    """
    Class for handling document downloads from Trade Republic.
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




        tr: api object




        output_path: name of the directory where the downloaded files are saved




        filename_fmt: format string to customize the file names




        since_timestamp: downloaded files since this date (unix timestamp)
        """

        self.tr_api = tr_api

        self.output_path = Path(output_path)

        self.download_history_file = self.output_path / download_history_file

        self.filename_fmt = filename_fmt

        self.since_timestamp = since_timestamp

        requests_session = Session()

        if self.tr_api._weblogin:
            requests_session.headers = self.tr_api._default_headers_web

        else:
            requests_session.headers = self.tr_api._default_headers

        self.session = FuturesSession(max_workers=max_workers, session=requests_session)

        self.futures = []

        self.docs_request = 0

        self.done = 0

        self.filepaths = []

        self.download_history = []

        self.tl = Timeline(self.tr_api)

        self.log = get_colored_logger(__name__)

        self.read_or_create_download_history()

        self.download_list = []

    def read_or_create_download_history(self):
        """




        This function attempts to read the document download history.




        If the file does not exist, it creates an empty file.
        """

        if self.download_history_file.exists():
            with self.download_history_file.open() as f:
                self.download_history = f.read().splitlines()

            self.log.info(
                "Download history file contains %s entries.", len(self.download_history)
            )

        else:
            self.download_history_file.parent.mkdir(exist_ok=True, parents=True)

            self.download_history_file.touch()

            self.log.info("Successfully generated the document download history file.")

    async def dl_loop(self):
        """
        Requests timelines and timeline details from Trade Republic websocket
        and processes them upon receipt.

        When a timeline packet is received, a check is made to see
        if there is another part and if so, it is requested.
        When a timeline detail is received, processing is triggered.
        """
        await self.tl.get_timeline(max_age_timestamp=self.since_timestamp)

        while True:
            try:
                _subscription_id, subscription, response = await self.tr_api.recv()

            except TradeRepublicError as e:
                self.log.fatal(str(e))

            if subscription["type"] == "timeline":
                await self.tl.get_timeline(
                    response, max_age_timestamp=self.since_timestamp
                )

            elif subscription["type"] == "timelineDetail":
                await self.tl.process_timeline_detail(
                    response, self, max_age_timestamp=self.since_timestamp
                )

            else:
                self.log.warning(
                    "unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

    def update_download_list(self, doc, title_text, subtitle_text, subfolder=None):
        """




        This function generates a local file destination path based on the document data.




        It then saves this path, along with the source URL, in the download list for later download.
        """

        doc_url = doc["action"]["payload"]

        doc_url_base = doc_url.split("?")[0]

        date = doc["detail"]

        iso_date = "-".join(date.split(".")[::-1])

        doc_id = doc["id"]

        self.log.debug("Try adding doc with id '%s' to download list...", doc_id)

        # extract time from subtitleText

        time = re.findall("um (\\d+:\\d+) Uhr", subtitle_text)

        if time == []:
            time = ""

        else:
            time = f" {time[0]}"

        if subfolder is not None:
            directory = self.output_path / subfolder

        else:
            directory = self.output_path

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

        filename = self.filename_fmt.format(
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

        if doc_url_base in self.download_history:
            self.log.debug(
                "Source URL %s is already in history. Skipping...", doc_url_base
            )
            return

        elif (
            sum(
                1
                for dlj in self.download_list
                if dlj.get("doc_url_base") == doc_url_base
            )
            == 0
        ):
            self.download_list.append(download_job)

        else:
            self.log.debug(
                "Source URL %s is already in queue. Skipping...", doc_url_base
            )
            return

    def dl_docs(self):
        """



        Download the documents from the download list.
        """

        for dlj in self.download_list:
            doc_url = dlj.get("doc_url")

            doc_url_base = dlj.get("doc_url_base")

            filepath = dlj.get("filepath")

            filepath_with_doc_id = dlj.get("filepath_with_doc_id")

            future = self.session.get(doc_url)

            if (
                sum(
                    1
                    for entry in self.download_list
                    if entry.get("filepath") == filepath
                )
                == 1
            ):
                future.filepath = filepath

            else:
                if (
                    sum(
                        1
                        for entry in self.download_list
                        if entry.get("filepath_with_doc_id") == filepath_with_doc_id
                    )
                    == 1
                ):
                    future.filepath = filepath_with_doc_id

                else:
                    self.log.error(
                        "Can't do multiple downloads with the same destination %s.",
                        filepath_with_doc_id,
                    )
                    continue

            future.doc_url_base = doc_url_base

            self.futures.append(future)

            self.log.debug("Added %s to download queue", future.filepath)

        self.work_responses()

    def work_responses(self):
        """





        process responses of async requests
        """

        if len(self.download_list) == 0:
            self.log.info("Nothing to download")

            exit(0)

        with self.download_history_file.open("a") as download_history_file:
            self.log.info("Waiting for downloads to complete..")

            for future in as_completed(self.futures):
                if future.filepath.is_file() is True:
                    self.log.debug("file %s was already downloaded.", future.filepath)

                try:
                    r = future.result()

                except Exception as e:
                    self.log.fatal(str(e))

                future.filepath.parent.mkdir(parents=True, exist_ok=True)

                with open(future.filepath, "wb") as f:
                    f.write(r.content)

                    self.done += 1

                    download_history_file.write(f"{future.doc_url_base}\n")

                    self.log.debug(
                        "%3s/%s %s",
                        self.done,
                        len(self.download_list),
                        future.filepath.name,
                    )

                if self.done == len(self.download_list):
                    self.log.info("Done.")

                    exit(0)
