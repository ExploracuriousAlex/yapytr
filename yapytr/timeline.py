"""
A Timeline class.
"""


import json
from datetime import datetime

from .utils import get_colored_logger, export_transactions


class Timeline:
    """
    Class to receive timeline information from Trade Republic.


    Receive timeline information from Trade Republic.
    Receive time line details and export data or download documents accordingly.
    """

    def __init__(self, tr_api):
        """Initializes the instance.

        Args:
          tr_api: The `TradeRepublicApi` object to be used to interact with Trade Republic.
        """
        self._log = get_colored_logger(__name__)
        self._tr_api = tr_api

        self._num_timelines = 0
        self._num_timeline_details = 0

        self._requested_detail = 0
        self.received_detail = 0

        self._timeline_events = []
        self._timeline_events_with_docs = []
        self._timeline_events_without_docs = []

        self._processed_doc_ids = []

    async def get_timeline(self, response=None, max_age_timestamp=0):
        """
        Receive timeline.

        Subscribe to timline information from Trade Republic websocket.
        When receiving timeline information, get timeline details contained.
        If present subscribe to the next part of the timeline.

        Args:
            response: The response of the server with the previous timeline. Defaults to None.
            max_age_timestamp: Maximum age for data to be fetched. Defaults to 0.
        """

        if response is None:
            # empty response / first timeline

            self._log.info("Awaiting timeline part 1.")
            await self._tr_api.timeline()

        else:
            timestamp = response["data"][-1]["data"]["timestamp"]

            self._num_timelines += 1
            self._num_timeline_details += len(response["data"])

            for timeline_event in response["data"]:
                self._timeline_events.append(timeline_event)

            after = response["cursors"].get("after")

            if after is None:
                # last timeline is reached

                self._log.info(
                    "Received timeline part %s (last part).", self._num_timelines
                )

                await self._get_timeline_details(5)

            elif max_age_timestamp != 0 and timestamp < max_age_timestamp:
                self._log.info("Received timeline part %s.", self._num_timelines + 1)

                self._log.info(
                    "Reached last relevant timeline part "
                    + "according to your --last_days configuration."
                )

                await self._get_timeline_details(5, max_age_timestamp=max_age_timestamp)

            else:
                self._log.info(
                    "Received timeline part %s, awaiting timeline part %s.",
                    self._num_timelines,
                    self._num_timelines + 1,
                )

                await self._tr_api.timeline(after)

    async def _get_timeline_details(self, num_torequest, max_age_timestamp=0):
        """
        Receive timeline details.

        Subscribe to a defined number of timlineDetail information from Trade Republic websocket.
        Save it in the `Timeline` object upon receipt.

        Args:
            num_torequest: Number of timline events to be processed to retrieve timeline details.
            max_age_timestamp: Maximum age for data to be fetched. Defaults to 0.
        """

        while num_torequest > 0:
            if len(self._timeline_events) == 0:
                self._log.info("All timeline details requested")
                return

            timeline_event = self._timeline_events.pop()
            action = timeline_event["data"].get("action")

            msg = ""

            if (
                max_age_timestamp != 0
                and timeline_event["data"]["timestamp"] > max_age_timestamp
            ):
                msg += "Skip: too old"

            elif action is None:
                if timeline_event["data"].get("actionLabel") is None:
                    msg += "Skip: no action"

            elif action.get("type") != "timelineDetail":
                msg += f"Skip: action type unmatched ({action['type']})"

            elif action.get("payload") != timeline_event["data"]["id"]:
                msg += f"Skip: payload unmatched ({action['payload']})"

            if msg == "":
                self._timeline_events_with_docs.append(timeline_event)

            else:
                self._timeline_events_without_docs.append(timeline_event)

                self._log.debug(
                    "%s %s: %s %s",
                    msg,
                    timeline_event["data"]["title"],
                    timeline_event["data"].get("body"),
                    json.dumps(timeline_event),
                )

                self._num_timeline_details -= 1
                continue

            num_torequest -= 1

            self._requested_detail += 1

            await self._tr_api.timeline_detail(timeline_event["data"]["id"])

    async def process_timeline_detail(self, response, dl, max_age_timestamp=0):
        """
        Process timeline details for extraction and export of data.

        Args:
            response: Received time line detail from Trade Republic websocket.
            dl: The DocDownload object that takes care of document downloads.
            max_age_timestamp: Maximum age for data to be fetched. Defaults to 0.
        """

        self.received_detail += 1

        self._log.debug("Received Timeline Detail %s.", self.received_detail)

        # when all requested timeline events are received request 5 new

        if self.received_detail == self._requested_detail:
            remaining = len(self._timeline_events)
            if remaining < 5:
                await self._get_timeline_details(remaining)

            else:
                await self._get_timeline_details(5)

        # print(f'len timeline_events: {len(self.timeline_events)}')

        is_savings_plan = False

        if response["subtitleText"] == "Sparplan":
            is_savings_plan = True

        else:
            # some savingsPlan don't have the subtitleText == 'Sparplan'
            # but there are actions just for savingsPans

            # but maybe these are unneeded duplicates

            for section in response["sections"]:
                if section["type"] == "actionButtons":
                    for button in section["data"]:
                        if button["action"]["type"] in [
                            "editSavingsPlan",
                            "deleteSavingsPlan",
                        ]:
                            is_savings_plan = True
                            break

        if response["subtitleText"] != "Sparplan" and is_savings_plan is True:
            savings_plan_fmt = " -- SPARPLAN"
        else:
            savings_plan_fmt = ""

        max_details_digits = len(str(self._num_timeline_details))

        self._log.info(
            f"{self.received_detail:>{max_details_digits}}/{self._num_timeline_details}: "
            + f"{response['titleText']} -- {response['subtitleText']}{savings_plan_fmt}"
        )

        for section in response["sections"]:
            if section["type"] == "documents":
                for doc in section["documents"]:
                    if doc["id"] in self._processed_doc_ids:
                        self._log.debug(
                            "Document with id '%s' was already processed. Skipping..."
                        )
                        continue

                    self._processed_doc_ids.append(doc["id"])

                    try:
                        timestamp = (
                            datetime.strptime(doc["detail"], "%d.%m.%Y").timestamp()
                            * 1000
                        )

                    except ValueError:
                        timestamp = datetime.now().timestamp() * 1000

                    if max_age_timestamp == 0 or max_age_timestamp < timestamp:
                        # save all savingsplan documents in a subdirectory

                        if is_savings_plan:
                            dl.update_download_list(
                                doc,
                                response["titleText"],
                                response["subtitleText"],
                                subfolder="Sparplan",
                            )

                        else:
                            # In case of a stock transfer (Wertpapierübertrag) add
                            # additional information to the document title

                            if response["titleText"] == "Wertpapierübertrag":
                                body = next(
                                    item["data"]["body"]
                                    for item in self._timeline_events_with_docs
                                    if item["data"]["id"] == response["id"]
                                )

                                dl.update_download_list(
                                    doc,
                                    response["titleText"] + " - " + body,
                                    response["subtitleText"],
                                )

                            else:
                                dl.update_download_list(
                                    doc, response["titleText"], response["subtitleText"]
                                )

        if self.received_detail == self._num_timeline_details:
            self._log.info("All timeline details have been received.")

            dl.output_path.mkdir(parents=True, exist_ok=True)

            with open(dl.output_path / "other_events.json", "w", encoding="utf-8") as f:
                json.dump(
                    self._timeline_events_without_docs, f, ensure_ascii=False, indent=2
                )

            with open(
                dl.output_path / "events_with_documents.json", "w", encoding="utf-8"
            ) as f:
                json.dump(
                    self._timeline_events_with_docs, f, ensure_ascii=False, indent=2
                )

            export_transactions(
                dl.output_path / "other_events.json",
                dl.output_path / "account_transactions.csv",
            )

            dl.dl_docs()
