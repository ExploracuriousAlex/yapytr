"""
An Alarms class.
"""
import asyncio
from datetime import datetime

from .utils import json_preview, get_colored_logger
from .tr_api import TradeRepublicError


class Alarms:
    """
    Class to receive and print price alarms from Trade Republic.
    """

    def __init__(self, tr_api):
        """
        Initializes the instance.

        Args:
            tr_api: The `TradeRepublicApi` object to be used to interact with Trade Republic.
        """
        self._log = get_colored_logger(__name__)
        self._tr_api = tr_api
        self._alarms = None

    async def _get_alarms_loop(self):
        """
        Receive price alarms.

        Subscribe to priceAlarms from Trade Republic websocket.
        Save it in the `Alarms` object upon receipt and unsubscribe.
        """

        await self._tr_api.price_alarm_overview()

        # define flags to control the loop
        flag_price_alarms_received = 1  # 2^0

        receiption_status = 0

        desired_receiption_status = 0
        desired_receiption_status |= flag_price_alarms_received

        while receiption_status != desired_receiption_status:
            subscription_id, subscription, response = await self._tr_api.recv()

            if subscription["type"] == "priceAlarms":
                receiption_status |= flag_price_alarms_received
                self._alarms = response
            else:
                self._log.debug(
                    "Unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

            await self._tr_api.unsubscribe(subscription_id)

    async def _set_alarm_loop(self, isin, price):
        """
        Set price alarm.

        Set the price alarm by subscribing to createPriceAlarm from Trade Republic websocket.
        Process the answer and print the result.

        Args:
            isin: ISIN (International Security Identification Number)
            for which an alarm is to be created.
            price: The target price.
        """

        await self._tr_api.create_price_alarm(isin, price)

        # define flags to control the loop
        flag_create_price_alarm_received = 1  # 2^0

        receiption_status = 0

        desired_receiption_status = 0
        desired_receiption_status |= flag_create_price_alarm_received

        create_price_alarm_answer = ""

        while receiption_status != desired_receiption_status:
            subscription_id, subscription, response = await self._tr_api.recv()

            if subscription["type"] == "createPriceAlarm":
                receiption_status |= flag_create_price_alarm_received
                create_price_alarm_answer = response
            else:
                self._log.debug(
                    "Unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

            await self._tr_api.unsubscribe(subscription_id)

        # self._log.debug(json_preview(create_price_alarm_answer))

        if create_price_alarm_answer["status"] == "succeeded":
            print(f"Successfully set price alarm for instrument '{isin}'.")
        else:
            self._log.warning("Could not set price alarm for instrument '%s'.", isin)
            self._log.warning("Server answer was:\n%s", create_price_alarm_answer)

    async def _cancel_alarm_loop(self, alarm_id):
        """
        Cancel price alarm.

        Cancel a price alarm by subscribing to cancelPriceAlarm from Trade Republic websocket.
        Process the answer and print the result.

        Args:
            alarm_id: The price alarm id. Get it with `get_alarms` + `print_alarms`.
        """

        await self._tr_api.cancel_price_alarm(alarm_id)

        # define flags to control the loop
        flag_cancel_price_alarm_received = 1  # 2^0

        receiption_status = 0

        desired_receiption_status = 0
        desired_receiption_status |= flag_cancel_price_alarm_received

        cancel_price_alarm_answer = ""

        while receiption_status != desired_receiption_status:
            subscription_id, subscription, response = await self._tr_api.recv()

            if subscription["type"] == "cancelPriceAlarm":
                receiption_status |= flag_cancel_price_alarm_received
                cancel_price_alarm_answer = response
            else:
                self._log.debug(
                    "Unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

            await self._tr_api.unsubscribe(subscription_id)

        # self._log.debug(json_preview(cancel_price_alarm_answer))

        if cancel_price_alarm_answer["status"] == "succeeded":
            print(f"Successfully canceled price alarm '{alarm_id}'.")
        else:
            self._log.warning("Could not cancel price alarm '%s'.", alarm_id)
            self._log.warning("Server answer was:\n%s", cancel_price_alarm_answer)

    def print_alarms(self):
        """
        Print price alarms.

        Print price alarms to the standard output stream.
        """
        print(
            "ISIN         status    created   target    diff%     "
            + "createdAt        alarm id                             triggeredAT"
        )
        print(
            "------------ --------- --------- --------- --------- "
            + "---------------- ------------------------------------ ---------------- "
        )
        for a in self._alarms:
            ts = int(a["createdAt"]) / 1000.0

            created = datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="minutes")

            if a["triggeredAt"] is None:
                triggered = "-"
            else:
                ts = int(a["triggeredAt"]) / 1000.0

                triggered = datetime.fromtimestamp(ts).isoformat(
                    sep=" ", timespec="minutes"
                )

            if a["createdPrice"] == 0:
                price_difference = 0.0
            else:
                price_difference = (
                    float(a["targetPrice"]) / float(a["createdPrice"])
                ) * 100 - 100

            print(
                f"{a['instrumentId']} {a['status']:<9} {float(a['createdPrice']):>9.2f} "
                + f"{float(a['targetPrice']):>9.2f} "
                + f"{price_difference:>8.1f}% {created} {a['id']} {triggered}"
            )

    def get_alarms(self):
        """
        Execute the data receiving loop to receive price alarms.

        The received data can be printed with `print_alarms` method.
        """
        asyncio.get_event_loop().run_until_complete(self._get_alarms_loop())

    def set_alarm(self, isin, price):
        """
        Execute the loop to set a price alarm and receive confirmation.

        Args:
            isin: ISIN (International Security Identification Number)
            for which an alarm is to be created.
            price: The target price.
        """
        try:
            asyncio.get_event_loop().run_until_complete(
                self._set_alarm_loop(isin, price)
            )
        except TradeRepublicError as e:
            self._log.error("Could not set price alarm for instrument '%s'.", isin)
            self._log.error("Server answer was:\n%s", e.error)

    def cancel_alarm(self, alarm_id):
        """
        Execute the loop to cancel a price alarm and receive confirmation.

        Args:
            alarm_id: The price alarm id. Get it with `get_alarms` + `print_alarms`.
        """
        try:
            asyncio.get_event_loop().run_until_complete(
                self._cancel_alarm_loop(alarm_id)
            )
        except TradeRepublicError as e:
            self._log.error("Could not cancel price alarm '%s'.", alarm_id)
            self._log.error("Server answer was:\n%s", e.error)
