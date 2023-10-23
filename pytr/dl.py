import re

from concurrent.futures import as_completed
from pathlib import Path
from requests_futures.sessions import FuturesSession
from requests.sessions import Session

from pathvalidate import sanitize_filepath

from pytr.utils import preview, Timeline, get_logger
from pytr.api import TradeRepublicError


class DL:
    def __init__(
        self,
        tr,
        output_path,
        filename_fmt,
        since_timestamp=0,
        history_file="pytr_history",
        max_workers=8,
    ):
        """
        tr: api object
        output_path: name of the directory where the downloaded files are saved
        filename_fmt: format string to customize the file names
        since_timestamp: downloaded files since this date (unix timestamp)
        """
        self.tr = tr
        self.output_path = Path(output_path)
        self.history_file = self.output_path / history_file
        self.filename_fmt = filename_fmt
        self.since_timestamp = since_timestamp

        requests_session = Session()

        if self.tr._weblogin:
            requests_session.headers = self.tr._default_headers_web
        else:
            requests_session.headers = self.tr._default_headers
        self.session = FuturesSession(max_workers=max_workers, session=requests_session)
        self.futures = []

        self.docs_request = 0
        self.done = 0
        self.filepaths = []
        self.doc_urls_history = []
        self.tl = Timeline(self.tr)
        self.log = get_logger(__name__)
        self.load_history()
        self.download_list = []

    def load_history(self):
        """
        Read history file with URLs if it exists, otherwise create empty file
        """
        if self.history_file.exists():
            with self.history_file.open() as f:
                self.doc_urls_history = f.read().splitlines()
            self.log.info("Found %s lines in history file", len(self.doc_urls_history))
        else:
            self.history_file.parent.mkdir(exist_ok=True, parents=True)
            self.history_file.touch()
            self.log.info("Created history file")

    async def dl_loop(self):
        await self.tl.get_next_timeline(max_age_timestamp=self.since_timestamp)

        while True:
            try:
                _subscription_id, subscription, response = await self.tr.recv()
            except TradeRepublicError as e:
                self.log.fatal(str(e))

            if subscription["type"] == "timeline":
                await self.tl.get_next_timeline(
                    response, max_age_timestamp=self.since_timestamp
                )
            elif subscription["type"] == "timelineDetail":
                await self.tl.timeline_detail(
                    response, self, max_age_timestamp=self.since_timestamp
                )
            else:
                self.log.warning(
                    "unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    preview(response),
                )

    def to_dl_list(self, doc, title_text, subtitle_text, subfolder=None):
        """
        Creates the local file destination path based on the document data
        and saves it in the download list along with the source URL for later download.
        """
        doc_url = doc["action"]["payload"]
        doc_url_base = doc_url.split("?")[0]

        date = doc["detail"]
        iso_date = "-".join(date.split(".")[::-1])
        doc_id = doc["id"]

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

        filepath = sanitize_filepath(filepath, "_", "auto")
        filepath_with_doc_id = sanitize_filepath(filepath_with_doc_id, "_", "auto")

        download_job = {
            "doc_url": doc_url,
            "doc_url_base": doc_url_base,
            "filepath": filepath,
            "filepath_with_doc_id": filepath_with_doc_id,
        }

        if doc_url_base in self.doc_urls_history:
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

    def work_responses(self):
        """
        process responses of async requests
        """
        if len(self.download_list) == 0:
            self.log.info("Nothing to download")
            exit(0)

        with self.history_file.open("a") as history_file:
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
                    history_file.write(f"{future.doc_url_base}\n")

                    self.log.debug(
                        "%3s/%s %s",
                        self.done,
                        len(self.download_list),
                        future.filepath.name,
                    )

                if self.done == len(self.download_list):
                    self.log.info("Done.")
                    exit(0)
