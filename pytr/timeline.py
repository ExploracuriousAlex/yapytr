import json
from datetime import datetime
from locale import getlocale

from .utils import get_colored_logger


class Timeline:
    def __init__(self, tr):
        self.tr = tr

        self.log = get_colored_logger(__name__)

        self.received_detail = 0

        self.requested_detail = 0

        self.num_timeline_details = 0

        self.events_without_docs = []

        self.events_with_docs = []

        self.num_timelines = 0

        self.timeline_events = []

    async def get_next_timeline(self, response=None, max_age_timestamp=0):
        """

        Get timelines and save time in list timelines.

        Extract timeline events and save them in list timeline_events

        """

        if response is None:
            # empty response / first timeline

            self.log.info("Awaiting #1  timeline")

            # self.timelines = []

            await self.tr.timeline()
        else:
            timestamp = response["data"][-1]["data"]["timestamp"]

            self.num_timelines += 1

            # print(json.dumps(response))

            self.num_timeline_details += len(response["data"])

            for event in response["data"]:
                self.timeline_events.append(event)

            after = response["cursors"].get("after")

            if after is None:
                # last timeline is reached

                self.log.info("Received #%-2s (last) timeline", self.num_timelines)

                await self._get_timeline_details(5)

            elif max_age_timestamp != 0 and timestamp < max_age_timestamp:
                self.log.info("Received #%-2s timeline", self.num_timelines + 1)

                self.log.info("Reached last relevant timeline")

                await self._get_timeline_details(5, max_age_timestamp=max_age_timestamp)
            else:
                self.log.info(
                    "Received #%-2s timeline, awaiting #%-2s timeline",
                    self.num_timelines,
                    self.num_timelines + 1,
                )

                await self.tr.timeline(after)

    async def _get_timeline_details(self, num_torequest, max_age_timestamp=0):
        """

        request timeline details
        """

        while num_torequest > 0:
            if len(self.timeline_events) == 0:
                self.log.info("All timeline details requested")

                return False

            else:
                event = self.timeline_events.pop()

            action = event["data"].get("action")

            # icon = event['data'].get('icon')

            msg = ""

            if (
                max_age_timestamp != 0
                and event["data"]["timestamp"] > max_age_timestamp
            ):
                msg += "Skip: too old"

            # elif icon is None:

            #     pass

            # elif icon.endswith('/human.png'):

            #     msg += 'Skip: human'

            # elif icon.endswith('/CashIn.png'):

            #     msg += 'Skip: CashIn'

            # elif icon.endswith('/ExemptionOrderChanged.png'):

            #     msg += 'Skip: ExemptionOrderChanged'

            elif action is None:
                if event["data"].get("actionLabel") is None:
                    msg += "Skip: no action"

            elif action.get("type") != "timelineDetail":
                msg += f"Skip: action type unmatched ({action['type']})"

            elif action.get("payload") != event["data"]["id"]:
                msg += f"Skip: payload unmatched ({action['payload']})"

            if msg == "":
                self.events_with_docs.append(event)
            else:
                self.events_without_docs.append(event)

                self.log.debug(
                    "%s %s: %s %s",
                    msg,
                    event["data"]["title"],
                    event["data"].get("body"),
                    json.dumps(event),
                )

                self.num_timeline_details -= 1
                continue

            num_torequest -= 1

            self.requested_detail += 1

            await self.tr.timeline_detail(event["data"]["id"])

    async def timeline_detail(self, response, dl, max_age_timestamp=0):
        """

        process timeline response and request timelines
        """

        self.received_detail += 1

        # when all requested timeline events are received request 5 new

        if self.received_detail == self.requested_detail:
            remaining = len(self.timeline_events)

            if remaining < 5:
                await self._get_timeline_details(remaining)
            else:
                await self._get_timeline_details(5)

        # print(f'len timeline_events: {len(self.timeline_events)}')

        is_savings_plan = False

        if response["subtitleText"] == "Sparplan":
            is_savings_plan = True
        else:
            # some savingsPlan don't have the subtitleText == 'Sparplan' but there are actions just for savingsPans

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

        max_details_digits = len(str(self.num_timeline_details))

        self.log.info(
            f"{self.received_detail:>{max_details_digits}}/{self.num_timeline_details}: "
            + f"{response['titleText']} -- {response['subtitleText']}{savings_plan_fmt}"
        )

        for section in response["sections"]:
            if section["type"] == "documents":
                for doc in section["documents"]:
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
                            # In case of a stock transfer (Wertpapierübertrag) add additional information to the document title

                            if response["titleText"] == "Wertpapierübertrag":
                                body = next(
                                    item["data"]["body"]
                                    for item in self.events_with_docs
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

        if self.received_detail == self.num_timeline_details:
            self.log.info("Received all details")

            dl.output_path.mkdir(parents=True, exist_ok=True)

            with open(dl.output_path / "other_events.json", "w", encoding="utf-8") as f:
                json.dump(self.events_without_docs, f, ensure_ascii=False, indent=2)

            with open(
                dl.output_path / "events_with_documents.json", "w", encoding="utf-8"
            ) as f:
                json.dump(self.events_with_docs, f, ensure_ascii=False, indent=2)

            export_transactions(
                dl.output_path / "other_events.json",
                dl.output_path / "account_transactions.csv",
            )

            dl.dl_docs()


def export_transactions(input_path, output_path, lang="auto"):
    """
    Create a CSV file with the deposits and removals ready for importing into Portfolio Performance.

    Args:
        input_path: Path of a JSON file containing timeline events.
        output_path: Target path of the CSV file to be written.
        lang: Language of the created file. Defaults to "auto".
    """

    log = get_colored_logger(__name__)

    if lang == "auto":
        locale = getlocale()[0]

        if locale is None:
            lang = "en"
        else:
            lang = locale.split("_")[0]

    if lang not in ["cs", "de", "en", "es", "fr", "it", "nl", "pt", "ru"]:
        lang = "en"

    # i18n source from Portfolio Performance:
    # https://github.com/portfolio-performance/portfolio/blob/master/name.abuchen.portfolio/src/name/abuchen/portfolio/messages_de.properties
    # https://github.com/portfolio-performance/portfolio/blob/master/name.abuchen.portfolio/src/name/abuchen/portfolio/model/labels_de.properties

    i18n = {
        "date": {
            "cs": "Datum",
            "de": "Datum",
            "en": "Date",
            "es": "Fecha",
            "fr": "Date",
            "it": "Data",
            "nl": "Datum",
            "pt": "Data",
            "ru": "\u0414\u0430\u0442\u0430",
        },
        "type": {
            "cs": "Typ",
            "de": "Typ",
            "en": "Type",
            "es": "Tipo",
            "fr": "Type",
            "it": "Tipo",
            "nl": "Type",
            "pt": "Tipo",
            "ru": "\u0422\u0438\u043F",
        },
        "value": {
            "cs": "Hodnota",
            "de": "Wert",
            "en": "Value",
            "es": "Valor",
            "fr": "Valeur",
            "it": "Valore",
            "nl": "Waarde",
            "pt": "Valor",
            "ru": "\u0417\u043D\u0430\u0447\u0435\u043D\u0438\u0435",
        },
        "deposit": {
            "cs": "Vklad",
            "de": "Einlage",
            "en": "Deposit",
            "es": "Dep\u00F3sito",
            "fr": "D\u00E9p\u00F4t",
            "it": "Deposito",
            "nl": "Storting",
            "pt": "Dep\u00F3sito",
            "ru": "\u041F\u043E\u043F\u043E\u043B\u043D\u0435\u043D\u0438\u0435",
        },
        "removal": {
            "cs": "V\u00FDb\u011Br",
            "de": "Entnahme",
            "en": "Removal",
            "es": "Removal",
            "fr": "Retrait",
            "it": "Prelievo",
            "nl": "Opname",
            "pt": "Levantamento",
            "ru": "\u0421\u043F\u0438\u0441\u0430\u043D\u0438\u0435",
        },
    }

    # Read relevant deposit timeline entries

    with open(input_path, encoding="utf-8") as f:
        timeline = json.load(f)

    # Write deposit_transactions.csv file

    # date, transaction, shares, amount, total, fee, isin, name

    log.info("Write deposit entries")

    with open(output_path, "w", encoding="utf-8") as f:
        # f.write('Datum;Typ;Stück;amount;Wert;Gebühren;ISIN;name\n')

        csv_fmt = "{date};{type};{value}\n"

        header = csv_fmt.format(
            date=i18n["date"][lang], type=i18n["type"][lang], value=i18n["value"][lang]
        )

        f.write(header)

        for event in timeline:
            event = event["data"]

            date_time = datetime.fromtimestamp(int(event["timestamp"] / 1000))

            date = date_time.strftime("%Y-%m-%d")

            title = event["title"]

            try:
                body = event["body"]

            except KeyError:
                body = ""

            if "storniert" in body:
                continue

            # Cash in

            if title in ["Einzahlung", "Bonuszahlung"]:
                f.write(
                    csv_fmt.format(
                        date=date,
                        type=i18n["deposit"][lang],
                        value=event["cashChangeAmount"],
                    )
                )

            elif title == "Auszahlung":
                f.write(
                    csv_fmt.format(
                        date=date,
                        type=i18n["removal"][lang],
                        value=abs(event["cashChangeAmount"]),
                    )
                )

            # Dividend - Shares

            elif title == "Reinvestierung":
                # TODO: implement reinvestment export

                log.warning("Detected reinvestment, skipping... (not implemented yet)")

    log.info("Deposit creation finished!")
